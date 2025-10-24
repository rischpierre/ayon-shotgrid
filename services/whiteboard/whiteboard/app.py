from __future__ import annotations
from typing import Dict, List, Optional, Tuple, Set
import os
import datetime
import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from whiteboard.models import *

from whiteboard.helpers import identicon_thumb, solid_color_thumb, _date_from_week_day, to_week_and_day
from whiteboard.sg_helpers import (
    sg_list_projects,
    sg_get_sample_tasks_for_entity,
    sg_find_project_artists,
    sg_list_groups,
    sg_find_project_shots,
    sg_find_project_assets,
    sg_find_tasks_for_shots,
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
    projs = sg_list_projects()
    return [Project(id=p.get("id"), name=p.get("name")) for p in projs]

@app.get("/api/tasks")
def get_tasks(project_id: Optional[str] = None):
    """
    Return task names for shots and assets derived from the first found shot/asset in the project.
    Fallback to defaults if ShotGrid is unavailable or no tasks found.
    """
    default = ["lighting", "tracking", "animation", "layout"]
    result = {EntityType.Shot: default, EntityType.Asset: default}
    if not project_id:
        return result
    try:
        pid = int(project_id)
        s_tasks = sg_get_sample_tasks_for_entity(pid, "Shot")
        a_tasks = sg_get_sample_tasks_for_entity(pid, "Asset")
        if s_tasks:
            result[EntityType.Shot] = s_tasks
        if a_tasks:
            result[EntityType.Asset] = a_tasks
    except Exception:
        logger.exception("Failed to fetch tasks from ShotGrid")
    return result

@app.get("/api/day/{day}", response_model=DaySnapshot)
def get_day(day: Day):
    # Back-compat endpoint: returns current week (w0) view for a single day
    if day not in weeks_days.get("w0", {}):
        raise HTTPException(status_code=404, detail="Day not found")

    b_ids = list(weeks_days["w0"][day].keys())
    day_boards = [boards[b] for b in b_ids]
    board_items_map: Dict[str, List[Item]] = {}
    for b in day_boards:
        board_items_map[b.id] = [items[iid] for iid in weeks_days["w0"][day][b.id]]

    # Only include shots in assignments map
    a_map: Dict[str, List[AssignedTask]] = {}
    for b in day_boards:
        if b.entity_type != EntityType.Shot:
            continue
        for iid in weeks_days["w0"][day][b.id]:
            if iid in assignments:
                a_map[iid] = assignments[iid]

    return DaySnapshot(
        day=day,
        boards=day_boards,
        board_items=board_items_map,
        artists=list(artists.values()),
        assignments=a_map
    )

@app.get("/api/week/{week}", response_model=WeekSnapshot)
def get_week(week: Week, project_id: str):
    project_id = int(project_id)
    try:
        # Fetch artists linked to the project
        sg_artists = sg_find_project_artists(project_id)
        proj_artists: List[Artist] = []
        for artist in sg_artists:
            img = artist.get("image") or {}
            thumb_url = img.get("url") if isinstance(img, dict) else img

            # deterministic avatar based on name
            if not thumb_url:
                key = (artist.get("name") or str(artist.get("id") or "user")).strip()
                thumb_url = identicon_thumb(64, key)

            proj_artists.append(Artist(id=artist["id"], name=artist["name"], thumb_url=thumb_url, is_group=False))

        sg_groups = sg_list_groups()
        for group in sg_groups:
            g_thumb = group.get("sg_thumbnail", {}).get("url")
            if not g_thumb:
                continue
            proj_artists.append(Artist(id=group["id"], name=group["code"], thumb_url=g_thumb, is_group=True))

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
        boards_by_day: Dict[Day, List[Board]] = {d: [
            Board(id=f"{week}-{d}-shots-1", entity_type=EntityType.Shot, title="Shots"),
            Board(id=f"{week}-{d}-assets-1", entity_type=EntityType.Asset, title="Assets"),
        ] for d in Days}
        board_items: Dict[str, List[Item]] = {f"{week}-{d}-shots-1": [] for d in Days}
        for d in Days:
            board_items[f"{week}-{d}-assets-1"] = []

        # Date mapping helpers
        today = datetime.date.today()
        # Find Monday of current ISO week
        monday = today - datetime.timedelta(days=(today.weekday()))  # Monday=0


        # Place shots occurring in requested week into that week's boards
        proj_over = moved_positions_by_project.get(project_id, {})
        no_due: List[Item] = []
        on_hold_list: List[Item] = []
        omitted_list: List[Item] = []
        seq_names: Set[str] = set()
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
                seq_names.add(seq_name)

            shot_item = Item(id=shot["id"], name=shot["code"], thumb_url=thumb_url, sequence=seq_name, entity_type=EntityType.Shot)

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
                except Exception:
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
        for artist in sg_assets:
            status = (artist.get("sg_status_list") or "").strip().lower()
            img = artist.get("image") or {}
            thumb_url = img.get("url") if isinstance(img, dict) else img
            if not thumb_url:
                key = str(artist.get("id") or artist.get("code") or "asset")
                thumb_url = solid_color_thumb(96, 64, key)
            a_type = artist.get("sg_asset_type") or None
            if a_type:
                asset_types.add(str(a_type))
            aid_str = str(artist.get("id"))
            shot_item = Item(id=aid_str, name=artist.get("code") or f"Asset {artist.get('id')}", thumb_url=thumb_url, sequence=str(a_type) if a_type else None)

            # Respect on hold/omitted similarly to shots
            if status == "hld":
                # No special hold/omit boards for assets in UI yet; place into no-due list to keep visible
                assets_no_due.append(shot_item)
                continue
            if status == "omt":
                # Skip omitted assets by default
                continue

            raw_date = artist.get("sg_next_delivery")
            adt = None
            if raw_date:
                try:
                    adt = datetime.date.fromisoformat(str(raw_date))
                except Exception:
                    adt = None
            wk_day = to_week_and_day(adt) if adt else None
            # Apply override if present (support assets moves too)
            if aid_str in proj_over:
                wk_day = proj_over[aid_str]
            if not wk_day:
                assets_no_due.append(shot_item)
                continue
            awk, aday = wk_day
            if awk != week:
                continue
            board_items[f"{week}-{aday}-assets-1"].append(shot_item)

        # Build assignments map for shot IDs present in this snapshot
        present_shot_ids: Set[str] = set()
        for d in Days:
            for it in board_items.get(f"{week}-{d}-shots-1", []):
                present_shot_ids.add(it.id)
        # Include assets present in this snapshot as well, so assignments can attach to assets
        for d in Days:
            for it in board_items.get(f"{week}-{d}-assets-1", []):
                present_shot_ids.add(it.id)

        a_map: Dict[str, List[AssignedTask]] = {}
        tasks_map: Dict[str, List[str]] = {}

        # Prefill from ShotGrid existing Tasks/assignees so assignments show on initial load
        if present_shot_ids:
            try:
                sg_tasks = sg_find_tasks_for_shots(project_id, [int(sid) for sid in present_shot_ids if sid.isdigit()])
                for t in sg_tasks:
                    ent = t.get("entity") or {}
                    sid = str(ent.get("id")) if ent else None
                    if not sid or sid not in present_shot_ids:
                        continue
                    task_name = (t.get("content") or "").strip()
                    # Build per-shot tasks list
                    if task_name:
                        cur_list = tasks_map.setdefault(sid, [])
                        if task_name not in cur_list:
                            cur_list.append(task_name)
                    assignees = t.get("task_assignees") or []
                    if not task_name or not assignees:
                        continue
                    lst = a_map.setdefault(sid, [])
                    for hu in assignees:
                        if not isinstance(hu, dict):
                            continue
                        hu_id = hu.get("id")
                        hu_type = (hu.get("type") or "HumanUser").strip()
                        if hu_id is None:
                            continue
                        aid = f"g:{hu_id}" if hu_type == "Group" else str(hu_id)
                        if not any(x.artist_id == aid and x.task == task_name for x in lst):
                            lst.append(AssignedTask(artist_id=aid, task=task_name, task_id=str(t.get("id")) if t.get("id") is not None else None))
            except Exception:
                logger.exception("Failed to prefill assignments from ShotGrid")

        # Merge in pending (in-memory) project assignments, without duplicating
        proj_assign = project_assignments.get(str(project_id), {})
        for sid, lst in proj_assign.items():
            if sid not in present_shot_ids:
                continue
            cur = a_map.setdefault(sid, [])
            for artist in lst:
                if not any(x.artist_id == artist.artist_id and x.task == artist.task for x in cur):
                    cur.append(artist)

        # Apply unassignment overrides so UI hides removed assignees immediately
        overrides = project_unassign_overrides.get(str(project_id), {})
        if overrides:
            for sid, removed_list in overrides.items():
                if sid in a_map:
                    existing = a_map[sid]
                    a_map[sid] = [x for x in existing if not any((x.artist_id == r.artist_id and x.task == r.task) for r in removed_list)]

        return WeekSnapshot(
            week=week,
            days=Days,
            boards=boards_by_day,
            board_items=board_items,
            artists=proj_artists,
            assignments=a_map,
            no_due_date=sorted(no_due, key=lambda x: x.name.lower()) if no_due else None,
            sequences=sorted(seq_names) if seq_names else None,
            on_hold=sorted(on_hold_list, key=lambda x: x.name.lower()) if on_hold_list else None,
            omitted=sorted(omitted_list, key=lambda x: x.name.lower()) if omitted_list else None,
            annotations=annotations_map or None,
            assets_no_due_date=sorted(assets_no_due, key=lambda x: x.name.lower()) if assets_no_due else None,
            asset_types=sorted(asset_types) if asset_types else None,
            tasks_per_shot=tasks_map or None,
        )
    except Exception:
        logger.exception("Failed to build project-aware week snapshot")


@app.post("/api/move")
def move_item(req: MoveItemRequest):
    # Move item between boards or reorder within board (optional)
    if req.to_board_id not in boards:
        raise HTTPException(status_code=404, detail="Target board not found")
    # Validate item existence
    if req.item_id not in items:
        raise HTTPException(status_code=404, detail="Item not found")

    # Remove from source board if provided (search across all weeks/days)
    if req.from_board_id:
        for _wk, days_map in weeks_days.items():
            for _d, bmap in days_map.items():
                if req.from_board_id in bmap:
                    if req.item_id in bmap[req.from_board_id]:
                        bmap[req.from_board_id].remove(req.item_id)
                    break

    # Insert into target board (resolve target week/day)
    resolved: Optional[Tuple[Week, Day]] = None
    for wk, days_map in weeks_days.items():
        for d, bmap in days_map.items():
            if req.to_board_id in bmap:
                resolved = (wk, d)
                lst = bmap[req.to_board_id]
                idx = req.to_index if req.to_index is not None and 0 <= req.to_index <= len(lst) else len(lst)
                lst.insert(idx, req.item_id)
                break
        if resolved:
            break
    if not resolved:
        raise HTTPException(status_code=400, detail="Target board not found in weeks/days")

    return {"ok": True}

@app.post("/api/move_day")
def move_item_by_day(req: MoveByDayRequest):
    # Back-compat: move within current week (w0) across days
    current_board_id: Optional[str] = None
    current_loc: Optional[Tuple[Week, Day]] = None
    for wk, days_map in weeks_days.items():
        for d, bmap in days_map.items():
            for bid, idlist in bmap.items():
                if boards[bid].entity_type != req.entity_type:
                    continue
                if req.item_id in idlist:
                    current_board_id = bid
                    current_loc = (wk, d)
                    break
            if current_board_id:
                break
        if current_board_id:
            break

    # Remove from current board if found
    if current_board_id and current_loc:
        weeks_days[current_loc[0]][current_loc[1]][current_board_id].remove(req.item_id)

    # Determine target board (first board of that entity_type for the day) in current week (w0)
    if req.to_day not in weeks_days.get("w0", {}):
        raise HTTPException(status_code=404, detail="Target day not found")
    target_board_id = None
    for bid in weeks_days["w0"][req.to_day].keys():
        if boards[bid].entity_type == req.entity_type:
            target_board_id = bid
            break
    if not target_board_id:
        raise HTTPException(status_code=400, detail="No board of requested entity_type on target day")

    lst = weeks_days["w0"][req.to_day][target_board_id]
    idx = req.to_index if req.to_index is not None and 0 <= req.to_index <= len(lst) else len(lst)
    lst.insert(idx, req.item_id)
    return {"ok": True, "to_board_id": target_board_id}

@app.post("/api/move_week_day")
def move_item_by_week_day(req: MoveByWeekDayRequest, project_id: Optional[str] = None):
    # If project-aware, just record override and return ok (UI reload will reflect)
    if project_id:
        pid = str(project_id)
        mp = moved_positions_by_project.setdefault(pid, {})
        mp[req.item_id] = (req.to_week, req.to_day)
        return {"ok": True}

    # Demo mode: manipulate in-memory weeks_days structure
    # Remove from any current board of the same entity_type across all weeks/days
    for _wk, days_map in weeks_days.items():
        for _d, bmap in days_map.items():
            for bid, idlist in bmap.items():
                if boards[bid].entity_type != req.entity_type:
                    continue
                if req.item_id in idlist:
                    idlist.remove(req.item_id)
                    break

    # Insert into the first board of that entity_type in the target week/day
    if req.to_week not in weeks_days:
        raise HTTPException(status_code=404, detail="Target week not found")
    if req.to_day not in weeks_days[req.to_week]:
        raise HTTPException(status_code=404, detail="Target day not found")

    target_board_id = None
    for bid in weeks_days[req.to_week][req.to_day].keys():
        if boards[bid].entity_type == req.entity_type:
            target_board_id = bid
            break
    if not target_board_id:
        raise HTTPException(status_code=400, detail="No board of requested entity_type on target day/week")

    lst = weeks_days[req.to_week][req.to_day][target_board_id]
    idx = req.to_index if req.to_index is not None and 0 <= req.to_index <= len(lst) else len(lst)
    lst.insert(idx, req.item_id)
    return {"ok": True, "to_board_id": target_board_id}

@app.post("/api/assign")
def assign_artist(req: AssignArtistRequest, project_id: str):
    artist_id, entity_id, entity_type, task = (req["artist_id"], req["entity_id"], req["entity_type"], req["task"])

    project_id = str(project_id)
    assign_map = project_assignments.setdefault(project_id, {})
    cur = assign_map.setdefault(req.shot_id, [])

    if not any(a.artist_id == req.artist_id and a.task == req.task for a in cur):
        cur.append(AssignedTask(artist_id=req.artist_id, task=req.task))
    return {"ok": True, "shot_id": req.shot_id, "assignments": cur}

@app.post("/api/unassign")
def unassign_artist(req: AssignArtistRequest, project_id: Optional[str] = None):
    # Remove an assignment if present; prefer per-project store when project_id is provided
    if project_id:
        pid = str(project_id)
        pmap = project_assignments.setdefault(pid, {})
        cur = pmap.get(req.shot_id, [])
        # Filter out matching entries
        filtered = [a for a in cur if not (a.artist_id == req.artist_id and a.task == req.task)]
        pmap[req.shot_id] = filtered
        # Record an override so prefilled ShotGrid assignees are hidden in the UI
        ov_map = project_unassign_overrides.setdefault(pid, {})
        ov_list = ov_map.setdefault(req.shot_id, [])
        if not any(a.artist_id == req.artist_id and a.task == req.task for a in ov_list):
            ov_list.append(AssignedTask(artist_id=req.artist_id, task=req.task))
        return {"ok": True, "shot_id": req.shot_id, "assignments": filtered}
    # Demo/global fallback
    cur = assignments.get(req.shot_id, [])
    filtered = [a for a in cur if not (a.artist_id == req.artist_id and a.task == req.task)]
    assignments[req.shot_id] = filtered
    return {"ok": True, "shot_id": req.shot_id, "assignments": filtered}

@app.get("/api/changes")
def list_changes(project_id: Optional[str] = None):
    if not project_id:
        return {"moves": [], "assignments": {}}
    pid = str(project_id)
    # Build move list by comparing overrides to current ShotGrid dates
    moves = []
    try:
        overrides = moved_positions_by_project.get(pid, {})
        if overrides:
            # fetch shots involved to get names and current delivery
            shot_ids = [int(sid) for sid in overrides.keys() if sid.isdigit()]
            if shot_ids:
                shots = sg_find_shots_by_ids(shot_ids)
                by_id = {str(s["id"]): s for s in shots}
                for sid, (wk, dy) in overrides.items():
                    sh = by_id.get(sid, {"code": sid, "sg_next_delivery": None, "id": int(sid) if sid.isdigit() else sid})
                    from_date = sh.get("sg_next_delivery")
                    to_date = _date_from_week_day(wk, dy).isoformat()
                    moves.append({
                        "shot_id": sid,
                        "shot_name": sh.get("code") or f"Shot {sid}",
                        "from_date": from_date,
                        "to_week": wk,
                        "to_day": dy,
                        "to_date": to_date,
                    })
    except Exception:
        # If ShotGrid not configured, still show moves based on overrides only
        overrides = moved_positions_by_project.get(pid, {})
        for sid, (wk, dy) in overrides.items():
            to_date = _date_from_week_day(wk, dy).isoformat()
            moves.append({
                "shot_id": sid,
                "shot_name": f"Shot {sid}",
                "from_date": None,
                "to_week": wk,
                "to_day": dy,
                "to_date": to_date,
            })

    assigns = project_assignments.get(pid, {})
    return {"moves": moves, "assignments": assigns}

@app.post("/api/publish")
def publish_changes(project_id: Optional[str] = None):
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id required")
    pid = str(project_id)

    # Prepare data
    overrides = moved_positions_by_project.get(pid, {})
    assigns = project_assignments.get(pid, {})

    # Try publishing to ShotGrid; if not configured, treat as success and clear
    try:
        sg_publish_changes(int(pid), overrides, assigns)
    except Exception:
        logger.exception("Failed to publish to ShotGrid; continuing to clear local state")
        # If ShotGrid not configured, still clear and return ok to keep demo usable

    # Clear pending changes for the project
    moved_positions_by_project[pid] = {}
    project_assignments[pid] = {}

    return {"ok": True}


@app.get("/api/annotations")
def get_annotations(project_id: Optional[str] = None):
    if not project_id:
        return {}
    try:
        data = sg_get_project_annotations(int(project_id))
        if not isinstance(data, dict):
            return {}
        # Ensure values are objects with text and color
        out: Dict[str, Dict[str, str]] = {}
        for k, v in data.items():
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
    if week not in ("w0","w1","w2","w3"):
        raise HTTPException(status_code=400, detail="invalid week")
    if day not in ("mon","tue","wed","thu","fri"):
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
    logging.basicConfig(level=getattr(logging, log_level, logging.INFO), format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    logger.info("Running Whiteboard server")
    host = os.environ.get("WHITEBOARD_SERVER_HOST")
    port = os.environ.get("WHITEBOARD_SERVER_PORT")
    assert host, "WHITEBOARD_SERVER_HOST env var not set"
    assert port, "WHITEBOARD_SERVER_PORT env var not set"
    uvicorn.run(app, host=host, port=int(port))
    return 0

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)
