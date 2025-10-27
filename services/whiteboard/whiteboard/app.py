from __future__ import annotations

import datetime
import logging
import os
from typing import Set

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from whiteboard.helpers import identicon_thumb, solid_color_thumb, _date_from_week_day, to_week_and_day
from whiteboard.models import *
from whiteboard.sg_helpers import (
    sg_list_projects,
    sg_find_tasks_per_entity,
    sg_find_project_artists,
    sg_list_groups,
    sg_find_project_shots,
    sg_find_project_assets,
    sg_find_shots_by_ids,
    sg_publish_changes,
    sg_get_project_annotations,
    sg_set_project_annotations,
)

logger = logging.getLogger(__name__)


app = FastAPI(title="Whiteboard")

# Static mount for assets (favicon, css, js)
root = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(root, "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def index():
    path = os.path.join(root, "static", "index.html")
    return FileResponse(path, media_type="text/html")


@app.get("/api/projects", response_model=List[Project])
def list_projects():
    return [Project(id=p.get("id"), name=p.get("name")) for p in sg_list_projects()]


@app.get("/api/tasks")
def get_tasks(project_id: str):
    global tasks_per_entity
    tasks_per_entity = sg_find_tasks_per_entity(int(project_id))
    return tasks_per_entity

@app.get("/api/week/{week}", response_model=WeekSnapshot)
def get_week(week: Week, project_id: str):
    # todo this function is too big, split this up
    project_id = int(project_id)
    try:
        # Fetch artists linked to the project
        sg_artists = sg_find_project_artists(project_id)
        proj_artists: List[Artist] = []
        for asset in sg_artists:
            img = asset.get("image") or {}
            thumb_url = img.get("url") if isinstance(img, dict) else img

            # deterministic avatar based on name
            if not thumb_url:
                key = (asset.get("name") or str(asset.get("id") or "user")).strip()
                thumb_url = identicon_thumb(64, key)

            proj_artists.append(Artist(id=asset["id"], name=asset["name"], thumb_url=thumb_url, is_group=False))

        sg_groups = sg_list_groups()
        for group in sg_groups:
            g_thumb = group.get("sg_thumbnail")
            if not g_thumb:
                continue
            url = g_thumb.get("url")
            if not url:
                continue
            proj_artists.append(Artist(id=group["id"], name=group["code"], thumb_url=url, is_group=True))

        # Fetch project annotations
        annotations_map: Dict[str, object] = {}
        try:
            raw = sg_get_project_annotations(project_id)
            if isinstance(raw, dict):
                # normalize values to {text, color}
                for k, v in raw.items():
                    if isinstance(v, dict):
                        text = str(v.get("text", ""))
                        color = str(v.get("color", "#c7cbe0"))
                    elif isinstance(v, str):
                        text = v
                        color = "#c7cbe0"
                    else:
                        text = str(v)
                        color = "#c7cbe0"
                    annotations_map[str(k)] = {"text": text, "color": color}
        except Exception:
            logger.exception("Failed to fetch project annotations")

        # Fetch shots with delivery dates and status
        sg_shots = sg_find_project_shots(project_id)
        sg_assets = sg_find_project_assets(project_id)

        # Prepare minimal board structure: one shots board (index 1) per day, plus matching empty assets board
        boards_by_day: Dict[Day, List[Board]] = {
            d: [
                Board(id=f"{week}-{d}-shots-1", entity_type=EntityType.Shot, title="Shots"),
                Board(id=f"{week}-{d}-assets-1", entity_type=EntityType.Asset, title="Assets"),
            ]
            for d in Days
        }
        board_items: Dict[str, List[Item]] = {f"{week}-{d}-shots-1": [] for d in Days}
        for day in Days:
            board_items[f"{week}-{day}-assets-1"] = []

        # Date mapping helpers
        today = datetime.date.today()
        # Find Monday of current ISO week
        monday = today - datetime.timedelta(days=(today.weekday()))  # Monday=0

        # Place shots occurring in requested week into that week's boards
        proj_over = moved_positions_by_project.get(project_id, {})
        no_due: List[Item] = []
        on_hold_list: List[Item] = []
        omitted_list: List[Item] = []
        parent_names: Set[str] = set()
        for shot in sg_shots:
            status = shot.get("sg_status_list")
            img = shot.get("image") or {}
            thumb_url = img.get("url") if isinstance(img, dict) else img
            if not thumb_url:
                # Fallback to a deterministic solid color thumbnail
                key = str(shot.get("id") or shot.get("code") or "shot")
                thumb_url = solid_color_thumb(96, 64, key)
            seq_name = shot.get("sg_sequence", {}).get("name")

            if seq_name:
                parent_names.add(seq_name)

            shot_item = Item(
                id=shot["id"], name=shot["code"], thumb_url=thumb_url, parent=seq_name, entity_type=EntityType.Shot
            )

            if status == "hld":
                on_hold_list.append(shot_item)
                continue
            if status == "omt":
                omitted_list.append(shot_item)
                continue

            # Default placement from delivery date
            raw_date = shot.get("sg_next_delivery")
            dt = None
            if raw_date:
                try:
                    dt = datetime.date.fromisoformat(str(raw_date))
                except Exception as e:
                    logger.exception(f"Failed to parse shot next delivery date: {e}")
                    dt = None

            wk_day = to_week_and_day(dt, current_monday=monday) if dt else None
            if shot_item.id in proj_over:
                wk_day = proj_over[shot_item.id]

            if not wk_day:
                no_due.append(shot_item)
                continue
            wk, day = wk_day
            if wk != week:
                # Only place into the requested week's board, but still continue loop to build full lists above
                continue
            board_items[f"{week}-{day}-shots-1"].append(shot_item)

        # Assets classification and placement for requested week
        assets_no_due: List[Item] = []
        asset_types: Set[str] = set()
        for asset in sg_assets:
            status = asset.get("sg_status_list")
            img = asset.get("image") or {}
            thumb_url = img.get("url") if isinstance(img, dict) else img
            if not thumb_url:
                key = str(asset.get("id") or asset.get("code") or "asset")
                thumb_url = solid_color_thumb(96, 64, key)

            asset_type = asset.get("sg_asset_type")
            if asset_type:
                asset_types.add(str(asset_type))
            asset_id = asset["id"]
            shot_item = Item(
                id=asset_id,
                name=asset.get("code"),
                thumb_url=thumb_url,
                parent=asset_type,
                entity_type=EntityType.Asset,
            )

            # Respect on hold/omitted similarly to shots
            if status == "hld":
                # No special hold/omit boards for assets in UI yet; place into no-due list to keep visible
                assets_no_due.append(shot_item)
                continue
            if status == "omt":
                # Skip omitted assets by default
                continue

            raw_date = asset.get("sg_next_delivery")
            adt = None
            if raw_date:
                try:
                    adt = datetime.date.fromisoformat(str(raw_date))
                except Exception as e:
                    logger.exception(f"Failed to parse asset next delivery date: {e}")
                    adt = None

            monday = today - datetime.timedelta(days=(datetime.date.today().weekday()))  #
            wk_day = to_week_and_day(adt, monday) if adt else None

            if asset_id in proj_over:
                wk_day = proj_over[asset_id]

            if not wk_day:
                assets_no_due.append(shot_item)
                continue
            awk, aday = wk_day
            if awk != week:
                continue
            board_items[f"{week}-{aday}-assets-1"].append(shot_item)

        shot_ids: Set[int] = set()
        asset_ids: Set[int] = set()
        for day in Days:
            for item in board_items.get(f"{week}-{day}-shots-1", []):
                shot_ids.add(item.id)

            for item in board_items.get(f"{week}-{day}-assets-1", []):
                asset_ids.add(item.id)

        assignee_map: Dict[int, List[AssignedTask]] = {}
        tasks_map: Dict[int, List[str]] = {}

        current_ids = shot_ids or asset_ids
        if current_ids:
            try:
                if shot_ids:
                    sg_tasks = [
                        task for shot_id, task in tasks_per_entity[EntityType.Shot].items() if shot_id in shot_ids
                    ]
                else:
                    sg_tasks = [
                        task for asset_id, task in tasks_per_entity[EntityType.Asset].items() if asset_id in asset_ids
                    ]

                for sg_task in sg_tasks:
                    entity = sg_task.get("entity") or {}
                    entity_id = entity["id"] if entity else None
                    if not entity_id or entity_id not in current_ids:
                        continue

                    task_name = sg_task.get("content")

                    # Build per-shot tasks list
                    if task_name:
                        cur_list = tasks_map.setdefault(entity_id, [])
                        if task_name not in cur_list:
                            cur_list.append(task_name)

                    assignees = sg_task.get("task_assignees")
                    if not task_name or not assignees:
                        continue

                    lst = assignee_map.setdefault(entity_id, [])

                    for assignee in assignees:
                        if not isinstance(assignee, dict):
                            continue

                        asset_id = assignee["id"]

                        if not any(x.artist_id == asset_id and x.task_name == task_name for x in lst):
                            lst.append(
                                AssignedTask(
                                    artist_is_group=True if assignee["type"] == "Group" else False,
                                    artist_id=asset_id,
                                    task_name=task_name,
                                    task_id=sg_task["id"],
                                )
                            )
            except Exception as e:
                logger.exception(f"Failed to prefill assignments from ShotGrid: {e}")

        # Merge in pending (in-memory) project assignments, without duplicating
        proj_assign = project_assignments.get(project_id, {})
        for entity_id, lst in proj_assign.items():
            if entity_id not in current_ids:
                continue
            cur = assignee_map.setdefault(entity_id, [])
            for asset in lst:
                if not any(x.artist_id == asset.artist_id and x.task_name == asset.task_name for x in cur):
                    cur.append(asset)

        # Apply unassignment overrides so UI hides removed assignees immediately
        overrides = project_unassign_overrides.get(project_id, {})
        if overrides:
            for entity_id, removed_list in overrides.items():
                if entity_id in assignee_map:
                    existing = assignee_map[entity_id]
                    assignee_map[entity_id] = [
                        x
                        for x in existing
                        if not any((x.artist_id == r.artist_id and x.task_name == r.task_name) for r in removed_list)
                    ]
        return WeekSnapshot(
            week=week,
            days=Days,
            boards=boards_by_day,
            board_items=board_items,
            artists=proj_artists,
            assignments=assignee_map,
            no_due_date=sorted(no_due, key=lambda x: x.name.lower()) if no_due else None,
            parents=sorted(parent_names) or sorted(asset_types),
            on_hold=sorted(on_hold_list, key=lambda x: x.name.lower()) if on_hold_list else None,
            omitted=sorted(omitted_list, key=lambda x: x.name.lower()) if omitted_list else None,
            annotations=annotations_map or None,
            assets_no_due_date=sorted(assets_no_due, key=lambda x: x.name.lower()) if assets_no_due else None,
            tasks_per_shot=tasks_map or None,
        )
    except Exception as e:
        logger.exception(f"Failed to build project-aware week snapshot {e}")
        raise HTTPException(status_code=500, detail="Failed to build week snapshot")


@app.post("/api/move_item")
def move_item(req: MoveByWeekDayRequest, project_id: Optional[str] = None):

    project_id = int(project_id)
    mp = moved_positions_by_project.setdefault(project_id, {})
    mp[int(req.item_id)] = (req.to_week, req.to_day)
    return {"ok": True}


@app.post("/api/assign")
def assign_artist(req: AssignArtistRequest, project_id: str):

    project_id = int(project_id)
    assign_map = project_assignments.setdefault(project_id, {})
    assignments = assign_map.setdefault(req.shot_id, [])

    if not any(a.artist_id == req.artist_id and a.task_name == req.task_name for a in assignments):
        assignments.append(
            AssignedTask(
                artist_id=req.artist_id,
                artist_is_group=req.artist_is_group,
                task_name=req.task_name,
                task_id=req.task_id,
            )
        )
    return {"ok": True, "shot_id": req.shot_id, "assignments": assignments}


@app.post("/api/unassign")
def unassign_artist(req: AssignArtistRequest, project_id: Optional[str] = None):
    # Remove an assignment if present; prefer per-project store when project_id is provided
    project_id = int(project_id)
    pmap = project_assignments.setdefault(project_id, {})
    cur = pmap.get(req.shot_id, [])

    # Filter out matching entries
    filtered = [a for a in cur if not (a.artist_id == req.artist_id and a.task_name == req.task_name)]
    pmap[req.shot_id] = filtered

    # Record an override so prefilled ShotGrid assignees are hidden in the UI
    ov_map = project_unassign_overrides.setdefault(project_id, {})
    ov_list = ov_map.setdefault(req.shot_id, [])
    if not any(a.artist_id == req.artist_id and a.task_name == req.task_name for a in ov_list):
        ov_list.append(
            AssignedTask(
                artist_id=req.artist_id,
                task_name=req.task_name,
                task_id=req.task_id,
                artist_is_group=req.artist_is_group,
            )
        )
    return {"ok": True, "shot_id": req.shot_id, "assignments": filtered}


@app.get("/api/changes")
def list_changes(project_id: Optional[str] = None):

    project_id = int(project_id)
    # Build move list by comparing overrides to current ShotGrid dates
    moves = []
    assigns = project_assignments.get(project_id, {})

    overrides = moved_positions_by_project.get(project_id, {})
    if not overrides:
        return {"moves": moves, "assignments": assigns}
    # fetch shots involved to get names and current delivery
    shot_ids = list(overrides.keys())
    if not shot_ids:
        return {"moves": moves, "assignments": assigns}

    # todo need to handle assets as well
    shots = sg_find_shots_by_ids(shot_ids)
    by_id = {s["id"]: s for s in shots}
    for shot_id, (week, day) in overrides.items():
        sh = by_id.get(shot_id, {"code": shot_id, "sg_next_delivery": None, "id": shot_id})
        from_date = sh.get("sg_next_delivery")
        to_date = _date_from_week_day(week, day).isoformat()
        moves.append(
            {
                "shot_id": shot_id,
                "shot_name": sh.get("code") or f"Shot {shot_id}",
                "from_date": from_date,
                "to_week": week,
                "to_day": day,
                "to_date": to_date,
            }
        )

    return {"moves": moves, "assignments": assigns}


@app.post("/api/publish")
def publish_changes(project_id: Optional[str] = None):

    project_id = int(project_id)

    # Prepare data
    overrides = moved_positions_by_project.get(project_id, {})
    assigns = project_assignments.get(project_id, {})

    # Try publishing to ShotGrid; if not configured, treat as success and clear
    try:
        sg_publish_changes(project_id, overrides, assigns)
    except Exception as e:
        logger.exception(f"Failed to publish to ShotGrid; continuing to clear local state: {e}")
        # If ShotGrid not configured, still clear and return ok to keep demo usable

    # Clear pending changes for the project
    moved_positions_by_project[project_id] = {}
    project_assignments[project_id] = {}

    return {"ok": True}


@app.get("/api/annotations")
def get_annotations(project_id: Optional[str] = None):
    try:
        annotations_ = sg_get_project_annotations(int(project_id))
        if not isinstance(annotations_, dict):
            return {}

        # Ensure values are objects with text and color
        out: Dict[str, Dict[str, str]] = {}
        for k, v in annotations_.items():
            if isinstance(v, dict):
                text = str(v.get("text", ""))
                color = str(v.get("color", "#c7cbe0"))
            elif isinstance(v, str):
                text = v
                color = "#c7cbe0"
            else:
                text = str(v)
                color = "#c7cbe0"
            out[str(k)] = {"text": text, "color": color}
        return out
    except Exception:
        logger.exception("Failed to load annotations from ShotGrid")
        return {}


@app.post("/api/annotations")
def set_annotation(payload: Dict[str, str], project_id: Optional[str] = None):
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id required")
    week = payload.get("week")
    day = payload.get("day")
    text = payload.get("text", "")
    color = payload.get("color", "#c7cbe0")
    if week not in (Week.w0, Week.w1, Week.w2, Week.w3):
        raise HTTPException(status_code=400, detail="invalid week")
    if day not in ("mon", "tue", "wed", "thu", "fri"):
        raise HTTPException(status_code=400, detail="invalid day")
    key = f"{week}/{day}"
    try:
        data = sg_get_project_annotations(int(project_id))
        if not isinstance(data, dict):
            data = {}
        # If text is empty/whitespace, remove the annotation entry entirely
        if not str(text).strip():
            if key in data:
                try:
                    del data[key]
                except Exception:
                    data[key] = None  # fallback no-op
        else:
            data[key] = {"text": str(text), "color": str(color) or "#c7cbe0"}
        sg_set_project_annotations(int(project_id), data)
        # Normalize output like GET (ensure {text, color})
        out: Dict[str, Dict[str, str]] = {}
        for k, v in (data or {}).items():
            if isinstance(v, dict):
                text = str(v.get("text", ""))
                color = str(v.get("color", "#c7cbe0"))
            elif isinstance(v, str):
                text = v
                color = "#c7cbe0"
            else:
                text = str(v)
                color = "#c7cbe0"
            out[str(k)] = {"text": text, "color": color}
        return {"ok": True, "annotations": out}
    except Exception:
        logger.exception("Failed to save annotation to ShotGrid")
        raise HTTPException(status_code=500, detail="Failed to save annotation")


def service_main() -> int:
    # Configure logging
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO), format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    logger.info("Running Whiteboard server")
    host = os.environ.get("WHITEBOARD_SERVER_HOST")
    port = os.environ.get("WHITEBOARD_SERVER_PORT")
    assert host, "WHITEBOARD_SERVER_HOST env var not set"
    assert port, "WHITEBOARD_SERVER_PORT env var not set"
    uvicorn.run(app, host=host, port=int(port))
    return 0


if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)
