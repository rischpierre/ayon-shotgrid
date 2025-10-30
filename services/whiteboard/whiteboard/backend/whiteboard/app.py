from __future__ import annotations

import datetime
import logging
import os
from typing import Set

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from whiteboard.helpers import (
    identicon_thumb,
    solid_color_thumb,
    date_from_week_day,
    to_week_and_day,
)
from whiteboard.models import *

from whiteboard.sg_helpers import (
    sg_list_projects,
    sg_find_tasks_per_entity,
    sg_find_project_artists,
    sg_list_groups,
    sg_find_project_shots,
    sg_find_project_assets,
    sg_find_entities_by_ids,
    sg_publish_changes,
    sg_get_project_annotations,
    sg_set_project_annotations,
)

logger = logging.getLogger(__name__)


app = FastAPI(title="Whiteboard")

# Enable CORS for Vite dev server and same-origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost",
        "http://127.0.0.1",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static mount for assets (favicon, css, js)
root = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(root, "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    # Serve built Vite assets under /assets (e.g., /assets/index-*.js)
    assets_dir = os.path.join(static_dir, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    setattr(app.state, "has_static", True)
else:
    logger.warning(
        "Static directory not found at %s; skipping static mounts. Run `npm run build` to generate assets, or use the Vite dev server.",
        static_dir,
    )
    setattr(app.state, "has_static", False)


@app.get("/")
def index():
    path = os.path.join(root, "static", "index.html")
    if getattr(app.state, "has_static", False) and os.path.isfile(path):
        return FileResponse(path, media_type="text/html")
    # Fallback helpful message in dev when static bundle is not present
    return {
        "message": "Frontend bundle not found. Run the Vite dev server or build the frontend.",
        "dev": bool(getattr(app.state, "dev", False)),
        "tips": [
            "For development: cd whiteboard/frontend && npm run dev (open http://localhost:5173)",
            "For production: cd whiteboard/frontend && npm run build (assets will appear under backend/whiteboard/static)",
        ],
    }


# Direct routes for root-level built assets expected by index.html
@app.get("/styles.css")
def styles_css():
    path = os.path.join(static_dir, "styles.css")
    if os.path.isfile(path):
        return FileResponse(path, media_type="text/css")
    raise HTTPException(
        status_code=404, detail="styles.css not found; run npm run build"
    )


@app.get("/favicon.png")
def favicon_png():
    path = os.path.join(static_dir, "favicon.png")
    if os.path.isfile(path):
        return FileResponse(path, media_type="image/png")
    raise HTTPException(
        status_code=404, detail="favicon.png not found; run npm run build"
    )


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
        for sg_asset in sg_artists:
            img = sg_asset.get("image") or {}
            thumb_url = img.get("url") if isinstance(img, dict) else img

            # deterministic avatar based on name
            if not thumb_url:
                key = (
                    sg_asset.get("name") or str(sg_asset.get("id") or "user")
                ).strip()
                thumb_url = identicon_thumb(64, key)

            proj_artists.append(
                Artist(
                    id=sg_asset["id"],
                    name=sg_asset["name"],
                    thumb_url=thumb_url,
                    is_group=False,
                )
            )

        sg_groups = sg_list_groups()
        for group in sg_groups:
            g_thumb = group.get("sg_thumbnail")
            if not g_thumb:
                continue
            url = g_thumb.get("url")
            if not url:
                continue
            proj_artists.append(
                Artist(id=group["id"], name=group["code"], thumb_url=url, is_group=True)
            )

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
                Board(
                    id=f"{week}-{d}-shots-1", entity_type=EntityType.Shot, title="Shots"
                ),
                Board(
                    id=f"{week}-{d}-assets-1",
                    entity_type=EntityType.Asset,
                    title="Assets",
                ),
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
        project_moves = moves_overrides.get(project_id, {})
        project_no_due = no_due_overrides.get(project_id, {})
        no_due: List[Item] = []
        on_hold_list: List[Item] = []
        omitted_list: List[Item] = []
        sequences: Set[str] = set()
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
                sequences.add(seq_name)

            shot_item = Item(
                id=shot["id"],
                name=shot["code"],
                thumb_url=thumb_url,
                parent=seq_name,
                entity_type=EntityType.Shot,
            )

            if status == "hld":
                on_hold_list.append(shot_item)
                continue
            if status == "omt":
                omitted_list.append(shot_item)
                continue

            # Explicit override: force into No Due Date
            if shot_item.id in (project_no_due.get(EntityType.Shot, set()) or set()):
                no_due.append(shot_item)
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
            if shot_item.id in project_moves.get(EntityType.Shot, {}):
                wk_day = project_moves[EntityType.Shot][shot_item.id]

            if not wk_day:
                no_due.append(shot_item)
                continue
            wk, day = wk_day
            if wk != week:
                # Only place into the requested week's board, but still continue loop to build full lists above
                continue
            board_items[f"{week}-{day}-shots-1"].append(shot_item)

        # Assets classification and placement for requested week
        asset_types: Set[str] = set()
        for sg_asset in sg_assets:
            status = sg_asset.get("sg_status_list")
            img = sg_asset.get("image") or {}
            thumb_url = img.get("url") if isinstance(img, dict) else img
            if not thumb_url:
                key = str(
                    sg_asset.get("id") or sg_asset.get("code") or "asset"
                )
                thumb_url = solid_color_thumb(96, 64, key)

            asset_type = sg_asset.get("sg_asset_type")
            if asset_type:
                asset_types.add(str(asset_type))
            asset_id = sg_asset["id"]
            asset_item = Item(
                id=asset_id,
                name=sg_asset.get("code"),
                thumb_url=thumb_url,
                parent=asset_type,
                entity_type=EntityType.Asset,
            )

            # Respect on hold/omitted similarly to shots
            if status == "hld":
                # No special hold/omit boards for assets in UI yet; place into no-due list to keep visible
                no_due.append(asset_item)
                continue
            if status == "omt":
                # Skip omitted assets by default
                continue

            # Explicit override for assets: force into No Due Date
            if asset_id in (project_no_due.get(EntityType.Asset, set()) or set()):
                no_due.append(asset_item)
                continue

            raw_date = sg_asset.get("sg_next_delivery")
            adt = None
            if raw_date:
                try:
                    adt = datetime.date.fromisoformat(str(raw_date))
                except Exception as e:
                    logger.exception(f"Failed to parse asset next delivery date: {e}")
                    adt = None

            # Use the same baseline Monday as shots to avoid any drift between modes
            wk_day = to_week_and_day(adt, current_monday=monday) if adt else None

            if asset_id in project_moves.get(EntityType.Asset, {}):
                wk_day = project_moves[EntityType.Asset][asset_id]

            if not wk_day:
                no_due.append(asset_item)
                continue
            awk, aday = wk_day
            if awk != week:
                continue
            board_items[f"{week}-{aday}-assets-1"].append(asset_item)

        shot_ids: Set[int] = set()
        asset_ids: Set[int] = set()
        for day in Days:
            for item in board_items.get(f"{week}-{day}-shots-1", []):
                shot_ids.add(item.id)

            for item in board_items.get(f"{week}-{day}-assets-1", []):
                asset_ids.add(item.id)

        assignee_map: Dict[EntityType, Dict[int, List[AssignedTask]]] = {EntityType.Shot: {}, EntityType.Asset: {}}
        tasks_map: Dict[int, List[str]] = {}

        sg_tasks = []
        current_ids = shot_ids.union(asset_ids)

        if shot_ids:
            for shot_id, tasks in tasks_per_entity.get(EntityType.Shot, {}).items():
                if shot_id in shot_ids:
                    sg_tasks.extend(tasks)
        else:
            for asset_id, tasks in tasks_per_entity.get(EntityType.Asset, {}).items():
                if asset_id in asset_ids:
                    sg_tasks.extend(tasks)

        for sg_task in sg_tasks:
            sg_entity = sg_task.get("entity") or {}
            entity_id = sg_entity["id"] if sg_entity else None
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

            assigned_tasks = assignee_map.setdefault(EntityType[sg_entity["type"]]).setdefault(entity_id, [])

            for assignee in assignees:
                if not isinstance(assignee, dict):
                    continue

                asset_id = assignee["id"]

                if not any(
                    x.artist_id == asset_id and x.task_name == task_name
                    for x in assigned_tasks
                ):
                    assigned_tasks.append(
                        AssignedTask(
                            artist_is_group=(
                                True if assignee["type"] == "Group" else False
                            ),
                            artist_id=asset_id,
                            task_name=task_name,
                            task_id=sg_task["id"],
                        )
                    )

        # Merge in pending (in-memory) project assignments, without duplicating
        proj_assign = assignments_overrides.get(project_id, {})
        for entity_type, v in proj_assign.items():
            for entity_id, assigned_tasks in v.items():
                if entity_id not in current_ids:
                    continue
                cur = assignee_map.setdefault(entity_type, {}).setdefault(entity_id, [])
                for assigned_task in assigned_tasks:
                    if not any(
                        x.artist_id == assigned_task.artist_id
                        and x.task_name == assigned_task.task_name
                        for x in cur
                    ):
                        cur.append(assigned_task)

        # Apply unassignment overrides so UI hides removed assignees immediately
        overrides = project_unassign_overrides.get(project_id, {})
        if overrides:
            for entity_type, v in overrides.items():
                for entity_id, removed_list in v.items():
                    if entity_id in v:
                        existing = assignee_map[entity_type][entity_id]
                        assignee_map[entity_type][entity_id] = [
                            x
                            for x in existing
                            if not any(
                                (x.artist_id == r.artist_id and x.task_name == r.task_name)
                                for r in removed_list
                            )
                        ]
        return WeekSnapshot(
            week=week,
            days=Days,
            boards=boards_by_day,
            board_items=board_items,
            artists=proj_artists,
            assignments=assignee_map,
            no_due_date=(
                sorted(no_due, key=lambda x: x.name.lower()) if no_due else None
            ),
            parents={EntityType.Shot: sorted(sequences), EntityType.Asset: sorted(asset_types)},
            on_hold=(
                sorted(on_hold_list, key=lambda x: x.name.lower())
                if on_hold_list
                else None
            ),
            omitted=(
                sorted(omitted_list, key=lambda x: x.name.lower())
                if omitted_list
                else None
            ),
            annotations=annotations_map or None,
        )
    except Exception as e:
        logger.exception(f"Failed to build project-aware week snapshot {e}")
        raise HTTPException(status_code=500, detail="Failed to build week snapshot")


@app.post("/api/move_item")
def move_item(request: MoveByWeekDayRequest, project_id: Optional[str] = None):

    project_id = int(project_id)
    mp = moves_overrides.setdefault(project_id, {}).setdefault(request.entity_type, {})
    mp[int(request.item_id)] = (request.to_week, request.to_day)
    return {"ok": True}


@app.post("/api/remove_due_date")
def remove_due_date(payload: Dict[str, Any], project_id: Optional[str] = None):
    project_ids = int(project_id)
    entity_id = int(payload.get("item_id"))

    entity_type = EntityType[payload.get("entity_type")]
    overrides = no_due_overrides.setdefault(project_ids, {})
    ids_overrides = overrides.setdefault(entity_type, set())
    ids_overrides.add(entity_id)
    return {"ok": True}


@app.post("/api/assign")
def assign_artist(request: AssignArtistRequest, project_id: str):

    project_id = int(project_id)
    assign_map = assignments_overrides.setdefault(project_id, {}).setdefault(
        request.entity_type, {}
    )
    assignments = assign_map.setdefault(request.entity_id, [])

    if not any(
        assignment.artist_id == request.artist_id and assignment.task_name == request.task_name
        for assignment in assignments
    ):
        assignments.append(
            AssignedTask(
                artist_id=request.artist_id,
                artist_is_group=request.artist_is_group,
                task_name=request.task_name,
                task_id=request.task_id,
            )
        )
    return {"ok": True, "shot_id": request.entity_id, "assignments": assignments}


@app.post("/api/unassign")
def unassign_artist(request: AssignArtistRequest, project_id: Optional[str] = None):
    # Remove an assignment if present; prefer per-project store when project_id is provided
    project_id = int(project_id)
    pmap = assignments_overrides.setdefault(project_id, {}).setdefault(
        request.entity_type, {}
    )
    cur = pmap.get(request.entity_id, [])

    # Filter out matching entries
    filtered = [
        a
        for a in cur
        if not (a.artist_id == request.artist_id and a.task_name == request.task_name)
    ]
    pmap[request.entity_id] = filtered

    # Record an override so prefilled ShotGrid assignees are hidden in the UI
    ov_map = project_unassign_overrides.setdefault(project_id, {})
    ov_list = ov_map.setdefault(request.entity_id, [])
    if not any(
        a.artist_id == request.artist_id and a.task_name == request.task_name
        for a in ov_list
    ):
        ov_list.append(
            AssignedTask(
                artist_id=request.artist_id,
                task_name=request.task_name,
                task_id=request.task_id,
                artist_is_group=request.artist_is_group,
            )
        )
    return {"ok": True, "entity_id": request.entity_id, "assignments": filtered}


@app.get("/api/changes")
def list_changes(project_id: str):

    project_id = int(project_id)
    assigns = assignments_overrides.get(project_id, {})
    moves = moves_overrides.get(project_id, {})

    if not moves and not assigns:
        return {"moves": moves, "assignments": assigns}

    shot_ids = list(moves.get(EntityType.Shot, {}).keys())
    asset_ids = list(moves.get(EntityType.Asset, {}).keys())

    if not shot_ids and not asset_ids:
        return {"moves": moves, "assignments": assigns}

    shots = sg_find_entities_by_ids(EntityType.Shot, shot_ids)
    assets = sg_find_entities_by_ids(EntityType.Asset, asset_ids)
    shot_moves = moves.get(EntityType.Shot, {})
    asset_moves = moves.get(EntityType.Asset, {})

    entities_by_id = {
        EntityType.Shot: {s["id"]: s for s in shots},
        EntityType.Asset: {a["id"]: a for a in assets},
    }
    result_moves = []
    for entity_type, v in moves.items():
        for entity_id, (week, day) in v.items():
            entity = entities_by_id.get(entity_type, {}).get(entity_id)
            code = None
            from_date = None
            if isinstance(entity, dict):
                code = entity.get("code")
                from_date = entity.get("sg_next_delivery")

            try:
                to_date = date_from_week_day(week, day).isoformat()
            except Exception:
                # Fallback: leave to_date None if helper fails
                to_date = None

            result_moves.append(
                {
                    "shot_id": entity_id,
                    "shot_name": code
                    or f"{getattr(entity_type, 'name', str(entity_type))} {entity_id}",
                    "from_date": from_date,
                    "to_week": week.value,
                    "to_day": day.value,
                    "to_date": to_date,
                }
            )

    return {"moves": result_moves, "assignments": assigns}


@app.post("/api/publish")
def publish_changes(project_id: Optional[str] = None):

    project_id = int(project_id)

    # Prepare data
    moves = moves_overrides.get(project_id, {})
    assigns = assignments_overrides.get(project_id, {})

    # Try publishing to ShotGrid; if not configured, treat as success and clear
    try:
        sg_publish_changes(project_id, moves, assigns)
    except Exception as e:
        logger.exception(
            f"Failed to publish to ShotGrid; continuing to clear local state: {e}"
        )

    # Clear pending changes for the project
    moves_overrides[project_id] = {}
    assignments_overrides[project_id] = {}

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
    raw_week = payload.get("week")
    raw_day = payload.get("day")
    text = payload.get("text", "")
    color = payload.get("color", "#c7cbe0")

    key = f"{raw_week}/{raw_day}"
    try:
        data = sg_get_project_annotations(int(project_id))
        if not isinstance(data, dict):
            data = {}

        # remove annotation if text is empty
        if not text.strip():
            if key in data:
                try:
                    del data[key]
                except Exception:
                    data[key] = None  # fallback no-op
        else:
            data[key] = {"text": text, "color": color}

        sg_set_project_annotations(int(project_id), data)
        # Normalize output like GET (ensure {text, color})
        out: Dict[str, Dict[str, str]] = {}
        for k, v in data.items():

            text = v.get("text", "")
            color = v.get("color", "#c7cbe0")

            out[k] = {"text": text, "color": color}

        return {"ok": True, "annotations": out}
    except Exception:
        logger.exception("Failed to save annotation to ShotGrid")
        raise HTTPException(status_code=500, detail="Failed to save annotation")


def service_main() -> int:

    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    host = os.environ.get("WHITEBOARD_SERVER_HOST", "127.0.0.1")
    port = int(os.environ.get("WHITEBOARD_SERVER_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)
    return 0


if __name__ == "__main__":
    service_main()
