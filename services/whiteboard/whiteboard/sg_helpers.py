from __future__ import annotations
import os
import logging
import threading
from typing import Any, Dict, List, Optional, Sequence, Tuple

import ayon_api
import shotgun_api3

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
    # Note: include_on_hold/include_omitted flags are ignored; we return all and let the app classify.
    sg = get_sg_session()
    s_fields = ["code", "sg_next_delivery", "image", "sg_sequence", "sg_status_list"]
    s_filters: List[Any] = [["project", "is", {"type": "Project", "id": project_id}]]
    return sg.find("Shot", s_filters, s_fields, order=[{"field_name": "code", "direction": "asc"}])


def sg_find_project_assets(project_id: int, include_on_hold: bool, include_omitted: bool) -> List[Dict[str, Any]]:
    """Return all assets for a project with fields needed for whiteboard.
    Uses sg_asset_type for filtering and sg_next_delivery for scheduling when available.
    """
    sg = get_sg_session()
    a_fields = ["code", "sg_next_delivery", "image", "sg_asset_type", "sg_status_list"]
    a_filters: List[Any] = [["project", "is", {"type": "Project", "id": project_id}]]
    return sg.find("Asset", a_filters, a_fields, order=[{"field_name": "code", "direction": "asc"}])


def sg_find_tasks_for_shots(project_id: int, shot_ids: Sequence[int]) -> List[Dict[str, Any]]:
    sg = get_sg_session()
    task_fields = ["id", "content", "entity", "task_assignees"]
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

    # Moves: update sg_next_delivery for Shots or Assets based on actual entity type
    for sid, (wk, dy) in overrides.items():
        try:
            # Skip non-numeric IDs defensively
            if not str(sid).isdigit():
                logger.warning(f"Skipping move for non-numeric id '{sid}'")
                continue
            target_date = _date_from_week_day(wk, dy).isoformat()
            eid = int(sid)
            # Resolve entity type cheaply: check Shot first, then Asset
            ent_type: Optional[str] = None
            try:
                found_shot = sg.find_one("Shot", [["id", "is", eid]], ["id"])  # type: ignore
                if found_shot:
                    ent_type = "Shot"
                else:
                    found_asset = sg.find_one("Asset", [["id", "is", eid]], ["id"])  # type: ignore
                    if found_asset:
                        ent_type = "Asset"
            except Exception:
                # If type resolution fails, fall back to trying Shot then Asset via update
                ent_type = None
            if ent_type:
                sg.update(ent_type, eid, {"sg_next_delivery": target_date})
                logger.info(f"Updated {ent_type} {eid} sg_next_delivery -> {target_date}")
            else:
                # Fallback: try Shot then Asset updates, logging failures
                try:
                    sg.update("Shot", eid, {"sg_next_delivery": target_date})
                    logger.info(f"Updated Shot {eid} sg_next_delivery -> {target_date}")
                except Exception:
                    try:
                        sg.update("Asset", eid, {"sg_next_delivery": target_date})
                        logger.info(f"Updated Asset {eid} sg_next_delivery -> {target_date}")
                    except Exception:
                        logger.exception(f"Failed updating sg_next_delivery for id {sid} (Shot/Asset)")
        except Exception:
            logger.exception(f"Failed processing move for id {sid}")

    # Assignments: update existing Task assignees per (artist, task) for each item (shot or asset)
    for item_id, task_list in assigns.items():
        for a in task_list or []:
            # Determine assignee entity
            is_group = isinstance(a.artist_id, str) and a.artist_id.startswith("g:")
            assignee_id = int(a.artist_id[2:]) if is_group else int(a.artist_id)
            assignee = {"type": "Group", "id": assignee_id} if is_group else {"type": "HumanUser", "id": assignee_id}

            def _update_task_for(entity_type: str) -> bool:
                try:
                    # Find existing Task by entity and content
                    filters = [
                        ["project", "is", proj],
                        ["entity", "is", {"type": entity_type, "id": int(item_id)}],
                        ["content", "is", a.task],
                    ]
                    found = sg.find_one("Task", filters, ["id", "task_assignees"])
                    if not found:
                        return False
                    tid = int(found["id"])  # type: ignore
                    existing = found.get("task_assignees") or []
                    # Check presence
                    exists = any((isinstance(x, dict) and int(x.get("id", -1)) == assignee_id and (x.get("type") or ("Group" if is_group else "HumanUser")) == ("Group" if is_group else "HumanUser")) for x in existing)
                    if not exists:
                        updated = list(existing) + [assignee]
                        sg.update("Task", tid, {"task_assignees": updated})
                    return True
                except Exception:
                    logger.exception(f"Failed updating assignees for {entity_type} {item_id} task '{a.task}'")
                    return False

            # Try updating Shot task first, then Asset
            if _update_task_for("Shot"):
                continue
            if _update_task_for("Asset"):
                continue
            logger.warning(f"No existing Task found for item {item_id} with name '{a.task}'. Skipping creation per policy.")


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
        import json
        if isinstance(raw, (dict, list)):
            return raw  # in case the field is a dict via API
        return json.loads(str(raw))
    except Exception:
        logger.exception("Failed to parse sg_whiteboard_annotations; returning empty dict")
        return {}


def sg_set_project_annotations(project_id: int, data: Dict[str, Any]) -> None:
    """Serialize data to JSON and store in Project.sg_whiteboard_annotations"""
    sg = get_sg_session()
    try:
        import json
        payload = {"sg_whiteboard_annotations": json.dumps(data)}
        sg.update("Project", int(project_id), payload)
    except Exception:
        logger.exception("Failed to update sg_whiteboard_annotations")
