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

    # Tasks per entity (pulled by the UI)
    appmod.sg_find_tasks_per_entity = lambda project_id: {
        "Shot": {"task_names": ["Animation", "Comp"]},
        "Asset": {"task_names": ["Modeling"]},
    }

    # Artists (avatars bar)
    appmod.sg_find_project_artists = lambda project_id: [
        {"id": 11, "name": "Alice", "image": {"url": None}},
        {"id": 22, "name": "Bob", "image": {"url": None}},
    ]

    # Groups
    appmod.sg_list_groups = lambda: [
        {"id": 101, "code": "Vendors", "sg_thumbnail": {"url": "http://example/thumb/vendors.png"}}
    ]

    # Annotations
    appmod.sg_get_project_annotations = lambda project_id: {}
    appmod.sg_set_project_annotations = lambda project_id, data: None

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
        {"id": 1001, "code": "sh010", "sg_next_delivery": wed_str}
    ]

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
