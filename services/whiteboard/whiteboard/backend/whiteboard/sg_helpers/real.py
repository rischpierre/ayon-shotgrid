from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any, Dict, List, Sequence, Tuple

import ayon_api
import shotgun_api3

from whiteboard.models import EntityType, Week, Day, AssignedTask

logger = logging.getLogger(__name__)

_SG_LOCAL = threading.local()


def get_sg_session():
    sg = getattr(_SG_LOCAL, "session", None)
    if sg is not None:
        return sg

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

    sg = shotgun_api3.Shotgun(
        sg_url,
        script_name=script_name,
        api_key=script_key,
        http_proxy=proxy_url,
    )
    setattr(_SG_LOCAL, "session", sg)
    return sg


# Below are thin helpers that encapsulate all direct ShotGrid API calls.
# app.py should import and use only these helpers so the backend is not tightly coupled
# to ShotGrid specifics and can be swapped later.


def sg_list_projects() -> List[Dict[str, Any]]:
    sg = get_sg_session()
    fields = ["name", "archived"]
    filters = [["sg_status", "is", "Active"]]
    return sg.find("Project", filters, fields, order=[{"field_name": "name", "direction": "asc"}])


def sg_find_project_artists(project_id: int) -> List[Dict[str, Any]]:
    sg = get_sg_session()
    a_fields = ["name", "image"]
    a_filters = [["projects", "is", {"type": "Project", "id": project_id}], ["sg_status_list", "is_not", "dis"]]
    return sg.find("HumanUser", a_filters, a_fields, order=[{"field_name": "name", "direction": "asc"}])


def sg_list_groups() -> List[Dict[str, Any]]:
    sg = get_sg_session()
    return sg.find("Group", [], ["code", "sg_thumbnail"], order=[{"field_name": "code", "direction": "asc"}])


def sg_find_project_shots(project_id: int) -> List[Dict[str, Any]]:
    # Note: include_on_hold/include_omitted flags are ignored; we return all and let the app classify.
    sg = get_sg_session()
    s_fields = ["code", "sg_next_delivery", "image", "sg_sequence", "sg_status_list"]
    s_filters: List[Any] = [["project", "is", {"type": "Project", "id": project_id}]]
    return sg.find("Shot", s_filters, s_fields, order=[{"field_name": "code", "direction": "asc"}])


def sg_find_project_assets(project_id: int) -> List[Dict[str, Any]]:
    """Return all assets for a project with fields needed for whiteboard.
    Uses sg_asset_type for filtering and sg_next_delivery for scheduling when available.
    """
    sg = get_sg_session()
    a_fields = ["code", "sg_next_delivery", "image", "sg_asset_type", "sg_status_list"]
    a_filters: List[Any] = [["project", "is", {"type": "Project", "id": project_id}]]
    return sg.find("Asset", a_filters, a_fields, order=[{"field_name": "code", "direction": "asc"}])


def sg_find_tasks_per_entity(project_id: int) -> dict[EntityType, dict[int, list[Dict[str, Any]]]]:

    sg = get_sg_session()
    # Fetch all steps and their colors once
    step_list = sg.find("Step", [], ["id", "code", "color"])  # color used for task display
    step_color_by_id = {s.get("id"): s.get("color") for s in (step_list or [])}

    # Include step field on Task so we can map color
    task_fields = ["id", "content", "entity", "task_assignees", "step"]
    tasks = sg.find("Task", [["project.Project.id", "is", project_id]], task_fields)
    # Attach step_color to each task for downstream use
    for t in tasks:
        st = t.get("step") or {}
        sid = st.get("id") if isinstance(st, dict) else None
        if sid in step_color_by_id:
            t["step_color"] = step_color_by_id.get(sid)

    result = {EntityType.Shot: {}, EntityType.Asset: {}}
    for task in tasks:
        if not task.get("entity"):
            continue

        entity_type = task["entity"]["type"]
        entity_id = task["entity"]["id"]
        result[EntityType[entity_type]].setdefault(entity_id, []).append(task)
    return result


def sg_find_entities_by_ids(entity_type: EntityType, ids: Sequence[int]) -> List[Dict[str, Any]]:
    sg = get_sg_session()
    if not ids:
        return []
    return sg.find(entity_type.name, [["id", "in", ids]], ["code", "sg_next_delivery"])


def sg_publish_changes(project_id: int,
                       moves: Dict[EntityType, Dict[int, Tuple[Week, Day]]],
                       assigns: Dict[EntityType, Dict[int, List[Any]]],
                       unschedules: Dict[EntityType, set[int]],
                       unassigns: Dict[EntityType, Dict[int, List[AssignedTask]]],
                       ) -> None:

    sg = get_sg_session()
    project = {"type": "Project", "id": int(project_id)}
    from whiteboard.helpers import date_from_week_day  # local import to avoid circular

    batch_data = []

    # moves
    for entity_type, value in moves.items():
        for entity_id, (wk, dy) in value.items():
            target_date = date_from_week_day(wk, dy).isoformat()
            logger.info(f"Adding move to the batch: {entity_id} -> {target_date}")
            batch_data.append(
                    {
                        "request_type": "update",
                        "entity_type": entity_type.name,
                        "entity_id": entity_id,
                        "data": {"sg_next_delivery": target_date},
                    }
            )

    # unschedules
    for entity_type, value in unschedules.items():
        for entity_id in value:
            logger.info(f"Adding un-schedule to the batch: {entity_id}")
            batch_data.append(
                {
                    "request_type": "update",
                    "entity_type": entity_type.name,
                    "entity_id": entity_id,
                    "data": {"sg_next_delivery": None},
                }
            )

    # unassignments
    for entity_type, value in unassigns.items():
        for entity_id, task_list in value.items():
            for task in task_list:
                is_group = task.artist_is_group
                to_unassign_id = task.artist_id
                artist_to_unassign = {"type": "Group", "id": to_unassign_id} if is_group else {"type": "HumanUser", "id": to_unassign_id}

                sg_task = sg.find_one("Task", [["project", "is", project], ["id", "is", task.task_id]], ["id", "task_assignees"])
                if not sg_task:
                    continue

                already_assigned_list = sg_task.get("task_assignees")
                for already_assigned in already_assigned_list:
                    if already_assigned["id"] == to_unassign_id and already_assigned["type"] == artist_to_unassign["type"]:
                        already_assigned_list.remove(already_assigned)

                logger.info(f"Adding un-assignment to the batch: {task.task_id} -> {artist_to_unassign}")
                batch_data.append(
                    {
                        "request_type": "update",
                        "entity_type": "Task",
                        "entity_id": task.task_id,
                        "data": {"task_assignees": already_assigned_list}
                    }
                )

    # Assignments: update existing Task assignees per (artist, task) for each task
    for entity_type, value in assigns.items():
        for item_id, task_list in value.items():
            for task in task_list:

                is_group = task.artist_is_group
                assignee_id = task.artist_id
                assignee = {"type": "Group", "id": assignee_id} if is_group else {"type": "HumanUser", "id": assignee_id}
                sg_task = sg.find_one("Task", [["project", "is", project], ["id", "is", task.task_id]], ["id", "task_assignees"])
                if not sg_task:
                    continue

                already_assigned = sg_task.get("task_assignees", [])
                already_assigned.append(assignee)

                logger.info(f"Adding assignment to the batch: {task.task_id} -> {assignee}")
                batch_data.append(
                    {
                        "request_type": "update",
                        "entity_type": "Task",
                        "entity_id": task.task_id,
                        "data": {"task_assignees": already_assigned}
                    }
                )

    logger.info(f"Batch data: {batch_data}")
    if batch_data:
        sg.batch(batch_data)


def sg_get_project_annotations(project_id: int) -> Dict[str, Any]:
    """Fetch project's sg_whiteboard_annotations and return parsed JSON dict.
    Returns an empty dict if not set or invalid.
    """
    sg = get_sg_session()
    proj = sg.find_one("Project", [["id", "is", int(project_id)]], ["sg_whiteboard_annotations"]) or {}
    raw = proj.get("sg_whiteboard_annotations") if isinstance(proj, dict) else None
    if not raw:
        return {}
    try:
        if isinstance(raw, (dict, list)):
            return raw  # in case the field is a dict via API
        return json.loads(str(raw))
    except Exception as e:
        logger.exception("Failed to parse sg_whiteboard_annotations; returning empty dict {e}")
        return {}


def sg_set_project_annotations(project_id: int, data: Dict[str, Any]) -> None:
    """Serialize data to JSON and store in Project.sg_whiteboard_annotations"""
    sg = get_sg_session()
    try:
        payload = {"sg_whiteboard_annotations": json.dumps(data)}
        sg.update("Project", int(project_id), payload)
    except Exception as e:
        logger.exception("Failed to update sg_whiteboard_annotations {e}")
