from __future__ import annotations

import datetime
import logging
import os
import time
from typing import Set, List, Dict

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

cache_timeout = 5.0  # seconds
entity_cache_query = {
    EntityType.Shot: {},  # project_id -> (time, data)
    EntityType.Asset: {},
}


def _get_cached_or_fetch(kind: EntityType, project_id: int, fetcher):
    now = time.monotonic()
    bucket = entity_cache_query.get(kind)
    if bucket is None:
        raise ValueError(f"Unknown cache kind: {kind}")
    entry = bucket.get(project_id)
    if entry is not None:
        time_, data = entry
        if now - time_ < cache_timeout:
            return data
    data = fetcher(project_id)
    bucket[project_id] = (now, data)
    return data


def _load_project_artists_and_groups(project_id: int) -> List[Artist]:
    proj_artists: List[Artist] = []
    for sg_asset in sg_find_project_artists(project_id):
        img = sg_asset.get("image") or {}
        thumb_url = img.get("url") if isinstance(img, dict) else img
        if not thumb_url:
            key = (sg_asset.get("name") or str(sg_asset.get("id") or "user")).strip()
            thumb_url = identicon_thumb(64, key)
        proj_artists.append(
            Artist(
                id=sg_asset["id"],
                name=sg_asset["name"],
                thumb_url=thumb_url,
                is_group=False,
            )
        )
    for group in sg_list_groups():
        g_thumb = group.get("sg_thumbnail")
        url = g_thumb.get("url") if g_thumb else None
        if url:
            proj_artists.append(
                Artist(id=group["id"], name=group["code"], thumb_url=url, is_group=True)
            )
    return proj_artists


def _load_annotations_map(project_id: int) -> Dict[datetime.date, Dict[str, str]]:
    annotations_map: Dict[datetime.date, Dict[str, str]] = {}
    try:
        raw = sg_get_project_annotations(project_id)
        raw = {
        "2025-11-11": {"text": "Bat as Lookdev /Eye as Model Final ", "color": "#c7cbe0"},
        "2025-11-12": {
            "text": "Butterfly as Model Final / Client will send Barossa Riverland RedFork SCANS + Hankley Somewhere SCANS",
            "color": "#c7cbe0",
        },
            "2025-11-24": {
                "text": "toto",
                "color": "#c7cbe0",
            },

        }
        for date_, annotation in raw.items():
            text = annotation.get("text", "")
            color = annotation.get("color", "#c7cbe0")
            annotations_map[datetime.date.fromisoformat(date_)] = {"text": text, "color": color}
    except Exception as e:
        logger.exception(f"Failed to fetch project annotations {e}")
    return annotations_map


def _load_project_entities(project_id: int) -> Tuple[List[dict], List[dict]]:
    # Use the small TTL cache already present
    shots = _get_cached_or_fetch(EntityType.Shot, project_id, sg_find_project_shots)
    assets = _get_cached_or_fetch(EntityType.Asset, project_id, sg_find_project_assets)
    return shots, assets


def _init_week_boards(
    week: Week,
) -> Tuple[Dict[Day, List[Board]], Dict[str, List[Item]]]:
    boards_by_day: Dict[Day, List[Board]] = {
        d: [
            Board(id=f"{week}-{d}-shots", entity_type=EntityType.Shot, title="Shots"),
            Board(
                id=f"{week}-{d}-assets", entity_type=EntityType.Asset, title="Assets"
            ),
        ]
        for d in Days
    }
    board_items: Dict[str, List[Item]] = {}
    for d in Days:
        board_items[f"{week}-{d}-shots"] = []
        board_items[f"{week}-{d}-assets"] = []
    return boards_by_day, board_items


def _classify_shots_into_week(
    week: Week,
    monday: datetime.date,
    sg_shots: List[dict],
    project_moves: Dict[EntityType, Dict[int, Tuple[Week, Day]]],
    project_no_due: Dict[EntityType, Set[int]],
) -> Tuple[Dict[str, List[Item]], List[Item], List[Item], List[Item], Set[str]]:
    board_items: Dict[str, List[Item]] = {}
    no_due: List[Item] = []
    on_hold: List[Item] = []
    omitted: List[Item] = []
    sequences: Set[str] = set()

    for shot in sg_shots:
        status = shot.get("sg_status_list")
        img = shot.get("image") or {}
        thumb_url = img.get("url") if isinstance(img, dict) else img
        if not thumb_url:
            key = str(shot.get("id") or shot.get("code") or "shot")
            thumb_url = solid_color_thumb(96, 64, key)
        seq_name = shot.get("sg_sequence", {}).get("name")
        if seq_name:
            sequences.add(seq_name)

        item = Item(
            id=shot["id"],
            name=shot["code"],
            thumb_url=thumb_url,
            parent=seq_name,
            entity_type=EntityType.Shot,
        )

        if status == "hld":
            on_hold.append(item)
            continue
        if status == "omt":
            omitted.append(item)
            continue

        if item.id in (project_no_due.get(EntityType.Shot, set()) or set()):
            no_due.append(item)
            continue

        raw_date = shot.get("sg_next_delivery")
        dt = None
        if raw_date:
            try:
                dt = datetime.date.fromisoformat(str(raw_date))
            except Exception as e:
                logger.exception(f"Failed to parse shot next delivery date: {e}")

        wk_day = to_week_and_day(dt, current_monday=monday) if dt else None
        if item.id in project_moves.get(EntityType.Shot, {}):
            wk_day = project_moves[EntityType.Shot][item.id]

        if not wk_day:
            no_due.append(item)
            continue
        wk, day = wk_day
        if wk != week:
            continue
        key = f"{week}-{day}-shots"
        board_items.setdefault(key, []).append(item)

    return board_items, no_due, on_hold, omitted, sequences


def _classify_assets_into_week(
    week: Week,
    monday: datetime.date,
    sg_assets: List[dict],
    project_moves: Dict[EntityType, Dict[int, Tuple[Week, Day]]],
    project_no_due: Dict[EntityType, Set[int]],
) -> Tuple[Dict[str, List[Item]], List[Item], List[Item], List[Item], Set[str]]:
    board_items: Dict[str, List[Item]] = {}
    no_due: List[Item] = []
    on_hold: List[Item] = []
    omitted: List[Item] = []
    asset_types: Set[str] = set()

    for sg_asset in sg_assets:
        status = sg_asset.get("sg_status_list")
        img = sg_asset.get("image") or {}
        thumb_url = img.get("url") if isinstance(img, dict) else img
        if not thumb_url:
            key = str(sg_asset.get("id") or sg_asset.get("code") or "asset")
            thumb_url = solid_color_thumb(96, 64, key)

        asset_type = sg_asset.get("sg_asset_type")
        if asset_type:
            asset_types.add(str(asset_type))
        asset_id = sg_asset["id"]

        item = Item(
            id=asset_id,
            name=sg_asset.get("code"),
            thumb_url=thumb_url,
            parent=asset_type,
            entity_type=EntityType.Asset,
        )

        if status == "hld":
            on_hold.append(item)
            continue
        if status == "omt":
            omitted.append(item)
            continue

        if asset_id in (project_no_due.get(EntityType.Asset, set()) or set()):
            no_due.append(item)
            continue

        adt = None
        raw_date = sg_asset.get("sg_next_delivery")
        if raw_date:
            try:
                adt = datetime.date.fromisoformat(str(raw_date))
            except Exception as e:
                logger.exception(f"Failed to parse asset next delivery date: {e}")

        wk_day = to_week_and_day(adt, current_monday=monday) if adt else None
        if asset_id in project_moves.get(EntityType.Asset, {}):
            wk_day = project_moves[EntityType.Asset][asset_id]

        if not wk_day:
            no_due.append(item)
            continue
        awk, aday = wk_day
        if awk != week:
            continue
        key = f"{week}-{aday}-assets"
        board_items.setdefault(key, []).append(item)

    return board_items, no_due, on_hold, omitted, asset_types


def _merge_board_items(dst: Dict[str, List[Item]], src: Dict[str, List[Item]]) -> None:
    for k, v in src.items():
        dst.setdefault(k, []).extend(v)


def _collect_entity_ids(
    board_items: Dict[str, List[Item]],
) -> Tuple[Set[int], Set[int]]:
    shot_ids: Set[int] = set()
    asset_ids: Set[int] = set()
    for key, items in board_items.items():
        if "-shots" in key:
            for it in items:
                shot_ids.add(it.id)
        else:
            for it in items:
                asset_ids.add(it.id)
    return shot_ids, asset_ids


def _build_tasks_and_assignees_for_current(
    board_items: Dict[str, List[Item]],
    tasks_per_entity: Dict[EntityType, Dict[int, List[dict]]],
) -> Tuple[Dict[int, List[str]], Dict[EntityType, Dict[int, List[AssignedTask]]]]:
    shot_ids, asset_ids = _collect_entity_ids(board_items)
    current_ids = shot_ids | asset_ids

    assignee_map: Dict[EntityType, Dict[int, List[AssignedTask]]] = {
        EntityType.Shot: {},
        EntityType.Asset: {},
    }
    tasks_map: Dict[int, List[str]] = {}

    sg_tasks: List[dict] = []
    # Collect tasks for both shots and assets present in the current snapshot
    for shot_id, tasks in tasks_per_entity.get(EntityType.Shot, {}).items():
        if shot_id in shot_ids:
            sg_tasks.extend(tasks)
    for asset_id, tasks in tasks_per_entity.get(EntityType.Asset, {}).items():
        if asset_id in asset_ids:
            sg_tasks.extend(tasks)

    for sg_task in sg_tasks:
        sg_entity = sg_task.get("entity") or {}
        entity_id = sg_entity.get("id")
        if not entity_id or entity_id not in current_ids:
            continue

        task_name = sg_task.get("content")
        if task_name:
            cur_list = tasks_map.setdefault(entity_id, [])
            if task_name not in cur_list:
                cur_list.append(task_name)

        assignees = sg_task.get("task_assignees")
        if not task_name or not assignees:
            continue

        entity_type = EntityType[sg_entity["type"]]
        assigned_tasks = assignee_map.setdefault(entity_type, {}).setdefault(
            entity_id, []
        )

        for assignee in assignees:
            if not isinstance(assignee, dict):
                continue
            artist_id = assignee["id"]
            if not any(
                x.artist_id == artist_id and x.task_name == task_name
                for x in assigned_tasks
            ):
                assigned_tasks.append(
                    AssignedTask(
                        artist_is_group=(assignee["type"] == "Group"),
                        artist_id=artist_id,
                        task_name=task_name,
                        task_id=sg_task["id"],
                        color=sg_task.get("step_color", "#dbdbdb"),
                    )
                )

    return tasks_map, assignee_map


def _apply_assignment_overrides(
    project_id: int, assignee_map, current_ids: Set[int]
) -> None:
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


def _apply_unassign_overrides(project_id: int, assignee_map) -> None:
    overrides = unassign_overrides.get(project_id, {})
    for entity_type, v in overrides.items():
        for entity_id, removed_list in v.items():
            existing = assignee_map.get(entity_type, {}).get(entity_id)
            if not existing:
                continue
            assignee_map[entity_type][entity_id] = [
                x
                for x in existing
                if not any(
                    (x.artist_id == r.artist_id and x.task_name == r.task_name)
                    for r in removed_list
                )
            ]


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
    project_id = int(project_id)
    try:
        # Data fetching and normalization
        proj_artists = _load_project_artists_and_groups(project_id)
        annotations_map = _load_annotations_map(project_id)
        sg_shots, sg_assets = _load_project_entities(project_id)

        # Boards skeleton and date baseline
        boards_by_day, board_items = _init_week_boards(week)
        monday = datetime.date.today() - datetime.timedelta(
            days=datetime.date.today().weekday()
        )

        # In-memory overrides
        project_moves = moves_overrides.get(project_id, {})
        project_no_due = unschedules_overrides.get(project_id, {})

        # Classification
        shot_board_items, no_due_shots, on_hold_shots, omitted_shots, sequences = (
            _classify_shots_into_week(
                week, monday, sg_shots, project_moves, project_no_due
            )
        )
        asset_board_items, no_due_assets, on_hold_assets, omitted_assets, asset_types = _classify_assets_into_week(
            week, monday, sg_assets, project_moves, project_no_due
        )

        _merge_board_items(board_items, shot_board_items)
        _merge_board_items(board_items, asset_board_items)

        # Merge no-due lists; UI currently shows a single pool
        no_due = [*no_due_shots, *no_due_assets]
        # Merge on-hold and omitted from shots and assets
        on_hold_all = [*on_hold_shots, *on_hold_assets]
        omitted_all = [*omitted_shots, *omitted_assets]

        # Tasks and assignees for visible entities
        shot_ids, asset_ids = _collect_entity_ids(board_items)
        _tasks_map, assignee_map = _build_tasks_and_assignees_for_current(
            board_items, tasks_per_entity
        )

        # Overrides for immediate UI feedback
        current_ids = shot_ids | asset_ids
        _apply_assignment_overrides(project_id, assignee_map, current_ids)
        _apply_unassign_overrides(project_id, assignee_map)

        week_offset = Weeks.index(week)  # week is a Week enum
        monday_of_the_current_week = monday + datetime.timedelta(days=7 * week_offset)
        friday_of_the_current_week = monday_of_the_current_week + datetime.timedelta(days=4)

        # Annotations: map absolute-date keys (YYYY-MM-DD) into this week's keys (wX/day)
        annotations_for_week: Dict[str, Dict[str, str]] = {}
        for date_, annotation in annotations_map.items():
            if monday_of_the_current_week <= date_ <= friday_of_the_current_week:
                day_idx = date_.weekday()  # 0..6
                if day_idx > 4:
                    continue

                day = Days[day_idx]
                annotations_for_week[f"{week.value}/{day.value}"] = annotation
                continue

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
            parents={
                EntityType.Shot: sorted(sequences),
                EntityType.Asset: sorted(asset_types),
            },
            on_hold=(
                sorted(on_hold_all, key=lambda x: x.name.lower())
                if on_hold_all
                else None
            ),
            omitted=(
                sorted(omitted_all, key=lambda x: x.name.lower())
                if omitted_all
                else None
            ),
            annotations=annotations_for_week or None,
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
    overrides = unschedules_overrides.setdefault(project_ids, {})
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
        assignment.artist_id == request.artist_id
        and assignment.task_name == request.task_name
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
    ov_map = unassign_overrides.setdefault(project_id, {})
    ov_list = ov_map.setdefault(request.entity_type, {}).setdefault(
        request.entity_id, []
    )
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
    unassigns = unassign_overrides.get(project_id, {})
    unschedules = unschedules_overrides.get(project_id, {})

    # If absolutely nothing is pending, return empty normalized structures
    if not moves and not assigns and not unassigns and not unschedules:
        return {"moves": [], "assignments": assigns, "unschedules": [], "unassigns": []}

    # Collect IDs we may need to resolve names for
    shot_ids = set(moves.get(EntityType.Shot, {}).keys())
    asset_ids = set(moves.get(EntityType.Asset, {}).keys())

    # Include unscheduled entity ids
    for etype, ids in (unschedules or {}).items():
        if etype == EntityType.Shot:
            shot_ids.update(ids or [])
        elif etype == EntityType.Asset:
            asset_ids.update(ids or [])

    # Include unassigned entity ids
    for etype, by_entity in (unassigns or {}).items():
        if etype == EntityType.Shot:
            shot_ids.update((by_entity or {}).keys())
        elif etype == EntityType.Asset:
            asset_ids.update((by_entity or {}).keys())

    # Resolve entity records for display
    shots = sg_find_entities_by_ids(EntityType.Shot, list(shot_ids)) if shot_ids else []
    assets = sg_find_entities_by_ids(EntityType.Asset, list(asset_ids)) if asset_ids else []

    entities_by_id = {
        EntityType.Shot: {s.get("id"): s for s in shots},
        EntityType.Asset: {a.get("id"): a for a in assets},
    }

    # Normalize moves list with friendly names and dates
    result_moves: List[Dict[str, object]] = []
    for entity_type, v in (moves or {}).items():
        for entity_id, (week, day) in (v or {}).items():
            entity = entities_by_id.get(entity_type, {}).get(entity_id)
            code = entity.get("code") if isinstance(entity, dict) else None
            from_date = entity.get("sg_next_delivery") if isinstance(entity, dict) else None
            try:
                to_date = date_from_week_day(week, day).isoformat()
            except Exception:
                to_date = None
            result_moves.append({
                "entity_type": entity_type.value,
                "entity_id": entity_id,
                "name": code or f"{getattr(entity_type, 'name', str(entity_type))} {entity_id}",
                "from_date": from_date,
                "to_week": week.value,
                "to_day": day.value,
                "to_date": to_date,
            })

    # Normalize unschedules list
    result_unschedules: List[Dict[str, object]] = []
    for entity_type, ids in (unschedules or {}).items():
        for entity_id in (ids or set()):
            entity = entities_by_id.get(entity_type, {}).get(entity_id)
            code = entity.get("code") if isinstance(entity, dict) else None
            result_unschedules.append({
                "entity_type": entity_type.value,
                "entity_id": entity_id,
                "name": code or f"{getattr(entity_type, 'name', str(entity_type))} {entity_id}",
            })

    # Normalize unassigns list
    result_unassigns: List[Dict[str, object]] = []
    for entity_type, by_entity in (unassigns or {}).items():
        for entity_id, removed_list in (by_entity or {}).items():
            entity = entities_by_id.get(entity_type, {}).get(entity_id)
            code = entity.get("code") if isinstance(entity, dict) else None
            for r in (removed_list or []):
                # r is AssignedTask
                result_unassigns.append({
                    "entity_type": entity_type.value,
                    "entity_id": entity_id,
                    "name": code or f"{getattr(entity_type, 'name', str(entity_type))} {entity_id}",
                    "task_name": getattr(r, 'task_name', None),
                    "task_id": getattr(r, 'task_id', None),
                    "artist_id": getattr(r, 'artist_id', None),
                    "artist_is_group": getattr(r, 'artist_is_group', False),
                })

    return {
        "moves": result_moves,
        "assignments": assigns,
        "unschedules": result_unschedules,
        "unassigns": result_unassigns,
    }


@app.post("/api/publish")
def publish_changes(project_id: Optional[str] = None):
    project_id = int(project_id)

    # Prepare data
    moves = moves_overrides.get(project_id, {})
    assigns = assignments_overrides.get(project_id, {})
    unassigns = unassign_overrides.get(project_id, {})
    unschedules = unschedules_overrides.get(project_id, {})

    # Try publishing to ShotGrid; if not configured, treat as success and clear
    try:
        sg_publish_changes(project_id, moves, assigns, unschedules, unassigns)
    except Exception as e:
        logger.exception(
            f"Failed to publish to ShotGrid; continuing to clear local state: {e}"
        )

    # Clear pending changes for the project
    moves_overrides[project_id] = {}
    assignments_overrides[project_id] = {}
    unassign_overrides[project_id] = {}
    unschedules_overrides[project_id] = {}

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

    # Compute absolute date key (YYYY-MM-DD) from provided week/day
    iso_key: Optional[str] = None
    legacy_key = f"{raw_week}/{raw_day}" if raw_week and raw_day else None
    try:
        if raw_week and raw_day:
            dt = date_from_week_day(Week(raw_week), Day(raw_day))
            iso_key = dt.isoformat()
    except Exception:
        # Fall back to legacy key only if conversion failed
        iso_key = None

    try:
        data = sg_get_project_annotations(int(project_id))
        if not isinstance(data, dict):
            data = {}

        if not text.strip():
            # Remove by absolute key primarily; also delete legacy if present
            if iso_key and iso_key in data:
                try:
                    del data[iso_key]
                except Exception:
                    data[iso_key] = None
            if legacy_key and legacy_key in data:
                try:
                    del data[legacy_key]
                except Exception:
                    data[legacy_key] = None
        else:
            # Write under absolute date key
            if iso_key:
                data[iso_key] = {"text": text, "color": color}
                # Clean up any legacy key for the same position
                if legacy_key and legacy_key in data:
                    try:
                        del data[legacy_key]
                    except Exception:
                        data[legacy_key] = None
            elif legacy_key:
                # Fallback storage if we couldn't compute absolute date (shouldn't happen)
                data[legacy_key] = {"text": text, "color": color}

        sg_set_project_annotations(int(project_id), data)

        # Normalize output like GET (ensure {text, color})
        out: Dict[str, Dict[str, str]] = {}
        for k, v in data.items():
            if isinstance(v, dict):
                t = v.get("text", "")
                c = v.get("color", "#c7cbe0")
            elif isinstance(v, str):
                t = v
                c = "#c7cbe0"
            else:
                t = str(v)
                c = "#c7cbe0"
            out[str(k)] = {"text": t, "color": c}

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
