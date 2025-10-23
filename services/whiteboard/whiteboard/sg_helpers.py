from __future__ import annotations
import os
import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

import ayon_api
import shotgun_api3

logger = logging.getLogger(__name__)


def get_sg_session():
    ayon_api_key = os.environ.get("AYON_API_KEY")
    ayon_server_url = os.environ.get("AYON_SERVER_URL")
    sg_url = os.environ.get("SG_URL")
    proxy = os.environ.get("HTTP_PROXY")
    proxy_url = proxy.replace("http://", "") if proxy else None

    if not ayon_api_key or not ayon_server_url:
        raise Exception("AYON_API_KEY and AYON_SERVER_URL are required")

    if not sg_url or not proxy_url:
        raise Exception("SG_URL and HTTP_PROXY env vars are required")

    ayon_api.init_service(token=ayon_api_key, server_url=ayon_server_url)
    script_name = ayon_api.get_secret("flow_whiteboard_service_name")["value"]
    script_key = ayon_api.get_secret("flow_whiteboard_service_key")["value"]

    if not script_name or not script_key:
        raise Exception("Script name or key is not set")

    return shotgun_api3.Shotgun(sg_url, script_name=script_name, api_key=script_key, http_proxy=proxy_url)


# Below are thin helpers that encapsulate all direct ShotGrid API calls.
# app.py should import and use only these helpers so the backend is not tightly coupled
# to ShotGrid specifics and can be swapped later.


def sg_list_projects() -> List[Dict[str, Any]]:
    sg = get_sg_session()
    fields = ["name", "archived"]
    filters = [["sg_status", "is", "Active"]]
    return sg.find("Project", filters, fields, order=[{"field_name": "name", "direction": "asc"}])


def sg_get_sample_tasks_for_entity(project_id: int, entity_type: str, limit: int = 8) -> List[str]:
    """Return up to `limit` distinct task names for the first entity of given type in the project."""
    sg = get_sg_session()
    ent = sg.find_one(entity_type, [["project", "is", {"type": "Project", "id": project_id}]], ["id"], order=[{"field_name": "id", "direction": "asc"}])
    if not ent:
        return []
    t_fields = ["content"]
    t_filters = [["project", "is", {"type": "Project", "id": project_id}], ["entity", "is", {"type": entity_type, "id": ent["id"]}]]
    t_list = sg.find("Task", t_filters, t_fields, order=[{"field_name": "content", "direction": "asc"}])
    names: List[str] = []
    seen = set()
    for t in t_list:
        name = (t.get("content") or "").strip()
        if name and name.lower() not in seen:
            seen.add(name.lower())
            names.append(name)
        if len(names) >= limit:
            break
    return names


def sg_find_project_artists(project_id: int) -> List[Dict[str, Any]]:
    sg = get_sg_session()
    a_fields = ["name", "image"]
    a_filters = [["projects", "is", {"type": "Project", "id": project_id}], ["sg_status_list", "is_not", "dis"]]
    return sg.find("HumanUser", a_filters, a_fields, order=[{"field_name": "name", "direction": "asc"}])


def sg_list_groups_with_thumbnails() -> List[Dict[str, Any]]:
    sg = get_sg_session()
    g_fields = ["code", "sg_thumbnail"]
    return sg.find("Group", [], g_fields, order=[{"field_name": "code", "direction": "asc"}])


def sg_find_project_shots(project_id: int, include_on_hold: bool, include_omitted: bool) -> List[Dict[str, Any]]:
    sg = get_sg_session()
    s_fields = ["code", "sg_next_delivery", "image", "sg_sequence"]
    s_filters: List[Any] = [["project", "is", {"type": "Project", "id": project_id}]]
    exclude_codes: List[str] = []
    if not include_on_hold:
        exclude_codes.append("hld")
    if not include_omitted:
        exclude_codes.append("omt")
    if exclude_codes:
        s_filters.append(["sg_status_list", "not_in", exclude_codes])
    return sg.find("Shot", s_filters, s_fields, order=[{"field_name": "code", "direction": "asc"}])


def sg_find_tasks_for_shots(project_id: int, shot_ids: Sequence[int]) -> List[Dict[str, Any]]:
    sg = get_sg_session()
    task_fields = ["content", "entity", "task_assignees"]
    t_filters = [["project", "is", {"type": "Project", "id": project_id}], ["entity", "in", [{"type": "Shot", "id": int(sid)} for sid in shot_ids]]]
    return sg.find("Task", t_filters, task_fields, limit=2000)


def sg_find_shots_by_ids(shot_ids: Sequence[int]) -> List[Dict[str, Any]]:
    sg = get_sg_session()
    return sg.find("Shot", [["id", "in", list(map(int, shot_ids))]], ["code", "sg_next_delivery"], limit=len(shot_ids))


def sg_publish_changes(project_id: int, overrides: Dict[str, Tuple[str, str]], assigns: Dict[str, List[Any]]) -> None:
    """Perform updates and task creations in ShotGrid.

    overrides: shot_id -> (week, day)
    assigns: shot_id -> List[AssignedTask-like {artist_id, task}] (duck-typed)
    """
    sg = get_sg_session()
    proj = {"type": "Project", "id": int(project_id)}
    from whiteboard.helpers import _date_from_week_day  # local import to avoid circular

    # Moves: update sg_next_delivery
    for sid, (wk, dy) in overrides.items():
        try:
            target_date = _date_from_week_day(wk, dy).isoformat()
            sg.update("Shot", int(sid), {"sg_next_delivery": target_date})
        except Exception:
            logger.exception(f"Failed updating shot {sid}")

    # Assignments: create tasks per (artist, task) for each shot
    for shot_id, task_list in assigns.items():
        for a in task_list or []:
            try:
                is_group = isinstance(a.artist_id, str) and a.artist_id.startswith("g:")
                assignee_id = int(a.artist_id[2:]) if is_group else int(a.artist_id)
                assignee = {"type": "Group", "id": assignee_id} if is_group else {"type": "HumanUser", "id": assignee_id}
                payload = {
                    "project": proj,
                    "entity": {"type": "Shot", "id": int(shot_id)},
                    "content": a.task,
                    "task_assignees": [assignee],
                }
                sg.create("Task", payload)
            except Exception:
                logger.exception(f"Failed creating task for shot {shot_id}")
