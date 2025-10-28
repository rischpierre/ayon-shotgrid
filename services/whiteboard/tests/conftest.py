import asyncio
import threading
import socket
import contextlib
import time
from typing import Callable

import pytest
import uvicorn


def _find_free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _current_week_wed_date_str():
    import datetime as _dt
    today = _dt.date.today()
    # Monday of current week (ISO: Monday = 1)
    monday = today - _dt.timedelta(days=(today.isoweekday() - 1))
    wed = monday + _dt.timedelta(days=2)
    return wed.isoformat()


@pytest.fixture(scope="session")
def server_url():
    """
    Start uvicorn with the FastAPI app in-process (same Python process),
    after monkeypatching whiteboard.app's sg_* functions to return deterministic data.
    Returns the base URL for the server.
    """
    import whiteboard.app as appmod

    # ---- Monkeypatch sg_helpers used by the app to return predictable data ----
    # Projects
    appmod.sg_list_projects = lambda: [{"id": 1, "name": "Test Project"}]

    # Tasks per entity (pulled by the UI) — structure expected by app.js:
    # { "Shot": { <entity_id>: [{"name": str, "id": int}, ...] }, "Asset": { ... } }
    def _mock_tasks_per_entity(project_id):
        return {
            "Shot": {
                1001: [{"name": "Animation", "id": 23}, {"name": "Comp", "id": 24}],
                1002: [{"name": "Animation", "id": 23}, {"name": "Comp", "id": 24}],
                1003: [{"name": "Animation", "id": 23}, {"name": "Comp", "id": 24}],
            },
            "Asset": {}
        }
    appmod.sg_find_tasks_per_entity = _mock_tasks_per_entity

    # Artists (avatars bar)
    appmod.sg_find_project_artists = lambda project_id: [
        {"id": 11, "name": "Alice", "image": {"url": None}},
        {"id": 22, "name": "Bob", "image": {"url": None}},
    ]

    # Groups
    appmod.sg_list_groups = lambda: [
        {"id": 101, "code": "Vendors", "sg_thumbnail": {"url": "http://example/thumb/vendors.png"}}
    ]

    # Annotations – persist in-memory for the test session
    _annotations_store = {}
    def _get_annotations(project_id):
        return dict(_annotations_store)
    def _set_annotations(project_id, data):
        _annotations_store.clear()
        if isinstance(data, dict):
            _annotations_store.update(data)
    appmod.sg_get_project_annotations = _get_annotations
    appmod.sg_set_project_annotations = _set_annotations

    # One shot scheduled on Wednesday of current week
    wed_str = _current_week_wed_date_str()

    appmod.sg_find_project_shots = lambda project_id: [
        {
            "id": 1001,
            "code": "sh010",
            "sg_next_delivery": wed_str,
            "sg_status_list": "wip",
            "tasks": [{"name": "Animation", "id": 23}],
            "image": {"url": None},
            "sg_sequence": {"name": "SQ01"},
        },
        {
            "id": 1002,
            "code": "sh020",
            "sg_next_delivery": None,
            "sg_status_list": "wip",
            "tasks": [{"name": "Animation", "id": 23}],
            "image": {"url": None},
            "sg_sequence": {"name": "SQ01"},
        },
        {
            "id": 1003,
            "code": "sh030",
            "sg_next_delivery": None,
            "sg_status_list": "omt",
            "tasks": [{"name": "Animation", "id": 23}],
            "image": {"url": None},
            "sg_sequence": {"name": "SQ01"},
        },
    ]

    # No assets to keep DOM minimal for this test
    appmod.sg_find_project_assets = lambda project_id: []

    # Shots by IDs used by /api/changes; provide minimal mapping
    appmod.sg_find_shots_by_ids = lambda ids: [
        {"id": 1001, "code": "sh010", "sg_next_delivery": wed_str},
        {"id": 1002, "code": "sh020", "sg_next_delivery": None},
        {"id": 1003, "code": "sh030", "sg_next_delivery": None},
    ]

    # Publish — no-op during tests
    appmod.sg_publish_changes = lambda project_id, overrides, assigns: None

    # ---- Spin up Uvicorn server in a background thread ----
    port = _find_free_port()

    config = uvicorn.Config(appmod.app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, name="uvicorn-test-server", daemon=True)
    thread.start()

    # Wait for server to start
    timeout = time.time() + 5.0
    url = f"http://127.0.0.1:{port}"
    import urllib.request
    while time.time() < timeout:
        try:
            with urllib.request.urlopen(url + "/api/projects", timeout=0.2) as resp:  # type: ignore
                if resp.status == 200:
                    break
        except Exception:
            time.sleep(0.05)
    else:
        # If we failed to start, ensure cleanup and raise
        try:
            server.should_exit = True
        except Exception:
            pass
        raise RuntimeError("Failed to start test server")

    try:
        yield url
    finally:
        # Signal server to stop and join the thread
        server.should_exit = True
        thread.join(timeout=5)
