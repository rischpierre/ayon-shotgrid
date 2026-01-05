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
    w4 = "w4"  # four weeks from now
    w5 = "w5"  # five weeks from now


Weeks: List[Week] = [Week.w0, Week.w1, Week.w2, Week.w3, Week.w4, Week.w5]


class EntityType(Enum):
    Shot = "Shot"
    Asset = "Asset"

EntityTypes = [EntityType.Shot, EntityType.Asset]

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
    color: Optional[str] = None

class WeekSnapshot(BaseModel):
    week: Week
    days: List[Day]
    boards: Dict[Day, List[Board]]
    board_items: Dict[str, List[Item]]  # board_id -> items for all days in week
    artists: List[Artist]
    assignments: Dict[EntityType, Dict[int, List[AssignedTask]]] = None
    no_due_date: Optional[List[Item]] = None
    parents: Dict[EntityType, List[str]] = None
    on_hold: Optional[List[Item]] = None
    omitted: Optional[List[Item]] = None
    annotations: Optional[Dict[str, Any]] = None


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
    entity_id: int
    entity_type: EntityType
    task_name: str
    task_id: int


Artists: Dict[str, Artist] = {}

# todo what is this weeks_days it does not make sense
Weeks_days: Dict[Week, Dict[Day, Dict[str, List[str]]]] = {} # week -> day -> board_id -> list[item_id]
Boards: Dict[str, Board] = {}
Assignments: Dict[int, List[AssignedTask]] = {}  # entity_id -> [AssignedTask, ...]

# Per-project overrides and assignments (project-aware mode)
Moves_overrides: Dict[int, Dict[EntityType, Dict[int, Tuple[Week, Day]]]] = {}  # project_id -> entity_type -> entity_id -> (week, day)
Assignments_overrides: Dict[int, Dict[EntityType, Dict[int, List[AssignedTask]]]] = {}  # project_id -> entity_type -> entity_id -> [AssignedTask]
Unassign_overrides: Dict[int, Dict[EntityType, Dict[int, List[AssignedTask]]]] = {}
Tasks_per_entity: Dict[EntityType, dict[int, list[Dict[str, Any]]]] = {}
# Items changed to have no due date project_id -> entityType -> [entity_id]
Unschedules_overrides: Dict[int, Dict[EntityType, set[int]]] = {}
