from __future__ import annotations
from typing import Dict, List, Optional, Tuple, Set
import os
import datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from whiteboard.models import (
    Day, Week, Artist, Item, Board, AssignedTask, Task,
    DaySnapshot, WeekSnapshot, Project,
    MoveItemRequest, MoveByDayRequest, MoveByWeekDayRequest, AssignArtistRequest
)
from whiteboard.helpers import identicon_thumb, solid_color_thumb, _date_from_week_day
from whiteboard.sg_helpers import get_sg_session

# In-memory data
artists: Dict[str, Artist] = {}
# week -> day -> board_id -> list[item_id]
weeks_days: Dict[Week, Dict[Day, Dict[str, List[str]]]] = {}
boards: Dict[str, Board] = {}
items: Dict[str, Item] = {}                # shots and assets share same map; differentiate by board membership
assignments: Dict[str, List[AssignedTask]] = {}     # shot_id -> [AssignedTask, ...]
# Per-project overrides and assignments (project-aware mode)
moved_positions_by_project: Dict[str, Dict[str, Tuple[Week, Day]]] = {}
project_assignments: Dict[str, Dict[str, List[AssignedTask]]] = {}  # project_id -> shot_id -> [AssignedTask]
project_unassign_overrides: Dict[str, Dict[str, List[AssignedTask]]] = {}  # project_id -> shot_id -> [AssignedTask] marked for removal

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
    sg = get_sg_session()
    fields = ["name", "archived"]
    filters = [["sg_status", "is", "Active"]]  # fetch all, UI can filter archived client-side
    projs = sg.find("Project", filters, fields, order=[{"field_name": "name", "direction": "asc"}])
    return [Project(id=p.get("id"), name=p.get("name")) for p in projs]

@app.get("/api/tasks")
def get_tasks(project_id: Optional[str] = None):
    """
    Return task names for shots and assets derived from the first found shot/asset in the project.
    Fallback to defaults if ShotGrid is unavailable or no tasks found.
    """
    default = ["lighting", "tracking", "animation", "layout"]
    result = {"shots": default, "assets": default}
    if not project_id:
        return result
    try:
        sg = get_sg_session()
        pid = int(project_id)
        # Helper to get tasks for first entity of a given type
        def tasks_for(entity_type: str) -> List[str]:
            ent = sg.find_one(entity_type, [["project", "is", {"type": "Project", "id": pid}]], ["id"], order=[{"field_name": "id", "direction": "asc"}])
            if not ent:
                return []
            t_fields = ["content"]
            t_filters = [["project", "is", {"type": "Project", "id": pid}], ["entity", "is", {"type": entity_type, "id": ent["id"]}]]
            t_list = sg.find("Task", t_filters, t_fields, order=[{"field_name": "content", "direction": "asc"}])
            names = []
            seen = set()
            for t in t_list:
                name = (t.get("content") or "").strip()
                if name and name.lower() not in seen:
                    seen.add(name.lower())
                    names.append(name)
                if len(names) >= 8:
                    break
            return names
        s_tasks = tasks_for("Shot")
        a_tasks = tasks_for("Asset")
        if s_tasks:
            result["shots"] = s_tasks
        if a_tasks:
            result["assets"] = a_tasks
    except Exception as e:
        print(e)
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
        if b.kind != "shots":
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
def get_week(week: Week, project_id: Optional[str] = None, include_on_hold: bool = False, include_omitted: bool = False):
    # If a project is provided and ShotGrid is configured, try to build a project-aware snapshot
    if project_id:
        try:
            sg = get_sg_session()

            # Fetch artists linked to the project
            a_fields = ["name", "image"]
            a_filters = [["projects", "is", {"type": "Project", "id": int(project_id)}], ["sg_status_list", "is_not", "dis"]]
            sg_artists = sg.find("HumanUser", a_filters, a_fields, order=[{"field_name": "name", "direction": "asc"}])
            proj_artists: List[Artist] = []
            for a in sg_artists:
                img = a.get("image") or {}
                thumb_url = img.get("url") if isinstance(img, dict) else img
                if not thumb_url:
                    thumb_url = identicon_thumb(64, str(a.get("id") or a.get("name") or "user"))
                proj_artists.append(Artist(id=str(a.get("id")), name=a.get("name") or f"User {a.get('id')}", thumb_url=thumb_url))

            # Fetch shots with delivery dates
            s_fields = ["code", "sg_next_delivery", "image"]
            s_filters = [["project", "is", {"type": "Project", "id": int(project_id)}]]

            # Optionally exclude on-hold (hld) and omitted (omt) statuses
            exclude_codes: List[str] = []
            if not include_on_hold:
                exclude_codes.append("hld")
            if not include_omitted:
                exclude_codes.append("omt")
            if exclude_codes:
                s_filters.append(["sg_status_list", "not_in", exclude_codes])
            sg_shots = sg.find("Shot", s_filters, s_fields, order=[{"field_name": "code", "direction": "asc"}])

            # Build per-week/day mapping
            days_list: List[Day] = ["mon", "tue", "wed", "thu", "fri"]
            # Prepare minimal board structure: one shots board (index 1) per day, plus matching empty assets board
            boards_by_day: Dict[Day, List[Board]] = {d: [
                Board(id=f"{week}-{d}-shots-1", kind="shots", title="Shots"),
                Board(id=f"{week}-{d}-assets-1", kind="assets", title="Assets"),
            ] for d in days_list}
            board_items: Dict[str, List[Item]] = {f"{week}-{d}-shots-1": [] for d in days_list}
            for d in days_list:
                board_items[f"{week}-{d}-assets-1"] = []

            # Date mapping helpers
            today = datetime.date.today()
            # Find Monday of current ISO week
            monday = today - datetime.timedelta(days=(today.weekday()))  # Monday=0
            def to_week_and_day(dt: datetime.date) -> Optional[Tuple[Week, Day]]:
                if dt < monday:
                    return None
                delta_days = (dt - monday).days
                wk_idx = delta_days // 7
                if wk_idx not in (0, 1, 2, 3):
                    return None
                wd = dt.weekday()  # 0..6
                if wd > 4:
                    return None
                return (f"w{wk_idx}", ["mon","tue","wed","thu","fri"][wd])

            # Place shots occurring in requested week into that week's boards
            proj_over = moved_positions_by_project.get(str(project_id), {})
            for sh in sg_shots:
                # Default placement from delivery date
                raw_date = sh.get("sg_next_delivery")
                dt = None
                if raw_date:
                    try:
                        dt = datetime.date.fromisoformat(str(raw_date))
                    except Exception:
                        dt = None
                wk_day = to_week_and_day(dt) if dt else None
                # Apply override if present
                sid_str = str(sh.get("id"))
                if sid_str in proj_over:
                    wk_day = proj_over[sid_str]
                if not wk_day:
                    continue
                wk, day = wk_day
                if wk != week:
                    continue
                img = sh.get("image") or {}
                thumb_url = img.get("url") if isinstance(img, dict) else img
                if not thumb_url:
                    # Fallback to a deterministic solid color thumbnail
                    key = str(sh.get("id") or sh.get("code") or "shot")
                    thumb_url = solid_color_thumb(96, 64, key)
                item = Item(id=sid_str, name=sh.get("code") or f"Shot {sh.get('id')}", thumb_url=thumb_url)
                board_items[f"{week}-{day}-shots-1"].append(item)

            # Build assignments map for shot IDs present in this snapshot
            present_shot_ids: Set[str] = set()
            for d in days_list:
                for it in board_items.get(f"{week}-{d}-shots-1", []):
                    present_shot_ids.add(it.id)

            a_map: Dict[str, List[AssignedTask]] = {}

            # Prefill from ShotGrid existing Tasks/assignees so assignments show on initial load
            if present_shot_ids:
                try:
                    task_fields = ["content", "entity", "task_assignees"]
                    t_filters = [
                        ["project", "is", {"type": "Project", "id": int(project_id)}],
                        ["entity", "in", [{"type": "Shot", "id": int(sid)} for sid in present_shot_ids if sid.isdigit()]],
                    ]
                    sg_tasks = sg.find("Task", t_filters, task_fields, limit=2000)
                    for t in sg_tasks:
                        ent = t.get("entity") or {}
                        sid = str(ent.get("id")) if ent else None
                        if not sid or sid not in present_shot_ids:
                            continue
                        task_name = (t.get("content") or "").strip()
                        assignees = t.get("task_assignees") or []
                        if not task_name or not assignees:
                            continue
                        lst = a_map.setdefault(sid, [])
                        for hu in assignees:
                            aid = str(hu.get("id")) if isinstance(hu, dict) else None
                            if not aid:
                                continue
                            if not any(x.artist_id == aid and x.task == task_name for x in lst):
                                lst.append(AssignedTask(artist_id=aid, task=task_name))
                except Exception as e:
                    print(e)

            # Merge in pending (in-memory) project assignments, without duplicating
            proj_assign = project_assignments.get(str(project_id), {})
            for sid, lst in proj_assign.items():
                if sid not in present_shot_ids:
                    continue
                cur = a_map.setdefault(sid, [])
                for a in lst:
                    if not any(x.artist_id == a.artist_id and x.task == a.task for x in cur):
                        cur.append(a)

            # Apply unassignment overrides so UI hides removed assignees immediately
            overrides = project_unassign_overrides.get(str(project_id), {})
            if overrides:
                for sid, removed_list in overrides.items():
                    if sid in a_map:
                        existing = a_map[sid]
                        a_map[sid] = [x for x in existing if not any((x.artist_id == r.artist_id and x.task == r.task) for r in removed_list)]

            return WeekSnapshot(
                week=week,
                days=days_list,
                boards=boards_by_day,
                board_items=board_items,
                artists=proj_artists,
                assignments=a_map,
            )
        except Exception as e:
            print(e)

    # Default: in-memory snapshot
    if week not in weeks_days:
        raise HTTPException(status_code=404, detail="Week not found")
    days_list: List[Day] = ["mon", "tue", "wed", "thu", "fri"]
    boards_by_day: Dict[Day, List[Board]] = {}
    board_items_map: Dict[str, List[Item]] = {}
    a_map2: Dict[str, List[AssignedTask]] = {}
    for d in days_list:
        day_boards_ids = list(weeks_days[week][d].keys())
        day_boards = [boards[b] for b in day_boards_ids]
        boards_by_day[d] = day_boards
        for b in day_boards:
            ids = weeks_days[week][d][b.id]
            board_items_map[b.id] = [items[iid] for iid in ids]
            if b.kind == "shots":
                for iid in ids:
                    if iid in assignments:
                        a_map2[iid] = assignments[iid]
    return WeekSnapshot(
        week=week,
        days=days_list,
        boards=boards_by_day,
        board_items=board_items_map,
        artists=list(artists.values()),
        assignments=a_map2,
    )

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
                if boards[bid].kind != req.kind:
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

    # Determine target board (first board of that kind for the day) in current week (w0)
    if req.to_day not in weeks_days.get("w0", {}):
        raise HTTPException(status_code=404, detail="Target day not found")
    target_board_id = None
    for bid in weeks_days["w0"][req.to_day].keys():
        if boards[bid].kind == req.kind:
            target_board_id = bid
            break
    if not target_board_id:
        raise HTTPException(status_code=400, detail="No board of requested kind on target day")

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
    # Remove from any current board of the same kind across all weeks/days
    for _wk, days_map in weeks_days.items():
        for _d, bmap in days_map.items():
            for bid, idlist in bmap.items():
                if boards[bid].kind != req.kind:
                    continue
                if req.item_id in idlist:
                    idlist.remove(req.item_id)
                    break

    # Insert into the first board of that kind in the target week/day
    if req.to_week not in weeks_days:
        raise HTTPException(status_code=404, detail="Target week not found")
    if req.to_day not in weeks_days[req.to_week]:
        raise HTTPException(status_code=404, detail="Target day not found")

    target_board_id = None
    for bid in weeks_days[req.to_week][req.to_day].keys():
        if boards[bid].kind == req.kind:
            target_board_id = bid
            break
    if not target_board_id:
        raise HTTPException(status_code=400, detail="No board of requested kind on target day/week")

    lst = weeks_days[req.to_week][req.to_day][target_board_id]
    idx = req.to_index if req.to_index is not None and 0 <= req.to_index <= len(lst) else len(lst)
    lst.insert(idx, req.item_id)
    return {"ok": True, "to_board_id": target_board_id}

@app.post("/api/assign")
def assign_artist(req: AssignArtistRequest, project_id: Optional[str] = None):
    # Record assignment; prefer per-project store when project_id is provided
    if project_id:
        pid = str(project_id)
        pmap = project_assignments.setdefault(pid, {})
        cur = pmap.setdefault(req.shot_id, [])
        if not any(a.artist_id == req.artist_id and a.task == req.task for a in cur):
            cur.append(AssignedTask(artist_id=req.artist_id, task=req.task))
        return {"ok": True, "shot_id": req.shot_id, "assignments": cur}
    # Demo/global fallback
    current = assignments.setdefault(req.shot_id, [])
    if not any(a.artist_id == req.artist_id and a.task == req.task for a in current):
        current.append(AssignedTask(artist_id=req.artist_id, task=req.task))
    return {"ok": True, "shot_id": req.shot_id, "assignments": current}

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
        sg = get_sg_session()
        overrides = moved_positions_by_project.get(pid, {})
        if overrides:
            # fetch shots involved to get names and current delivery
            shot_ids = [int(sid) for sid in overrides.keys() if sid.isdigit()]
            if shot_ids:
                shots = sg.find("Shot", [["id", "in", shot_ids]], ["code", "sg_next_delivery"], limit=len(shot_ids))
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
    def _publish_sg():
        sg = get_sg_session()
        proj = {"type": "Project", "id": int(pid)}
        # Moves: update sg_next_delivery
        for sid, (wk, dy) in overrides.items():
            try:
                target_date = _date_from_week_day(wk, dy).isoformat()
                sg.update("Shot", int(sid), {"sg_next_delivery": target_date})
            except Exception as e:
                print(f"Failed updating shot {sid}: {e}")
        # Assignments: create tasks per (artist, task) for each shot
        for shot_id, task_list in assigns.items():
            for a in task_list:
                try:
                    payload = {
                        "project": proj,
                        "entity": {"type": "Shot", "id": int(shot_id)},
                        "content": a.task,
                        "task_assignees": [{"type": "HumanUser", "id": int(a.artist_id)}],
                    }
                    sg.create("Task", payload)
                except Exception as e:
                    print(f"Failed creating task for shot {shot_id}: {e}")

    try:
        _publish_sg()
    except Exception as e:
        print(e)
        # If ShotGrid not configured, still clear and return ok to keep demo usable

    # Clear pending changes for the project
    moved_positions_by_project[pid] = {}
    project_assignments[pid] = {}

    return {"ok": True}

def service_main() -> int:
    print("Running Whiteboard server")
    host = os.environ.get("WHITEBOARD_SERVER_HOST")
    port = os.environ.get("WHITEBOARD_SERVER_PORT")
    assert host, "WHITEBOARD_SERVER_HOST env var not set"
    assert port, "WHITEBOARD_SERVER_PORT env var not set"
    uvicorn.run(app, host=host, port=int(port))
    return 0

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)
