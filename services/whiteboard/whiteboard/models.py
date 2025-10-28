from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional, Tuple, Any

from pydantic import BaseModel


class Day(Enum):
    mon = "mon"
    tue = "tue"
    wed = "wed"
    thu = "thu"
    fri = "fri"


Days = [Day.mon, Day.tue, Day.wed, Day.thu, Day.fri]


class Week(Enum):
    w0 = "w0"  # current week
    w1 = "w1"  # next week
    w2 = "w2"  # two weeks from now
    w3 = "w3"  # three weeks from now


Weeks = [Week.w0, Week.w1, Week.w2, Week.w3]


class EntityType(Enum):
    Shot = "Shot"
    Asset = "Asset"


class Artist(BaseModel):
    id: int
    name: str
    thumb_url: str
    is_group: bool


class Item(BaseModel):
    id: int  # entity id
    name: str
    thumb_url: str
    parent: str  # sequence or asset type
    entity_type: EntityType


class Board(BaseModel):
    id: str  # e.g., "shots-1", "assets-3"
    entity_type: EntityType
    title: str


class AssignedTask(BaseModel):
    artist_id: int
    artist_is_group: bool
    task_name: str
    task_id: int

class WeekSnapshot(BaseModel):
    week: Week
    days: List[Day]
    boards: Dict[Day, List[Board]]
    board_items: Dict[str, List[Item]]  # board_id -> items for all days in week
    artists: List[Artist]
    assignments: Dict[int, List[AssignedTask]]
    no_due_date: Optional[List[Item]] = None
    parents: Optional[List[str]] = None
    on_hold: Optional[List[Item]] = None
    omitted: Optional[List[Item]] = None
    annotations: Optional[Dict[str, Any]] = None
    assets_no_due_date: Optional[List[Item]] = None
    tasks_per_shot: Optional[Dict[int, List[str]]] = None


class Project(BaseModel):
    id: int
    name: str


class MoveByWeekDayRequest(BaseModel):
    item_id: int
    entity_type: EntityType
    to_week: Week
    to_day: Day
    to_index: Optional[int] = None


class AssignArtistRequest(BaseModel):
    artist_id: int
    artist_is_group: bool
    shot_id: int
    task_name: str
    task_id: int


artists: Dict[str, Artist] = {}

# todo what is this weeks_days it does not make sense
weeks_days: Dict[Week, Dict[Day, Dict[str, List[str]]]] = {} # week -> day -> board_id -> list[item_id]
boards: Dict[str, Board] = {}
assignments: Dict[int, List[AssignedTask]] = {}  # entity_id -> [AssignedTask, ...]

# Per-project overrides and assignments (project-aware mode)
moves_overrides: Dict[int, Dict[EntityType, Dict[int, Tuple[Week, Day]]]] = {}  # project_id -> entity_type -> entity_id -> (week, day)
assignments_overrides: Dict[int, Dict[EntityType, Dict[int, List[AssignedTask]]]] = {}  # project_id -> entity_type -> entity_id -> [AssignedTask]
project_unassign_overrides: Dict[int, Dict[int, List[AssignedTask]]] = (
    {}
)  # project_id -> shot_id -> [AssignedTask] marked for removal
tasks_per_entity: Dict[EntityType, dict[int, Any]] = {}
