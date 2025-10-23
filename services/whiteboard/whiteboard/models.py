from __future__ import annotations
from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel

Day = Literal["mon", "tue", "wed", "thu", "fri"]
Week = Literal["w0", "w1", "w2", "w3"]

class Artist(BaseModel):
    id: str
    name: str
    thumb_url: str

class Item(BaseModel):
    id: str
    name: str
    thumb_url: str
    sequence: Optional[str] = None

class Board(BaseModel):
    id: str         # e.g., "shots-1", "assets-3"
    kind: Literal["shots", "assets"]
    title: str

class TaskLiteral(str):
    pass

Task = str

class Assignment(BaseModel):
    artist_id: str
    item_id: str     # must reference a shot item

class AssignedTask(BaseModel):
    artist_id: str
    task: Task

class DaySnapshot(BaseModel):
    day: Day
    boards: List[Board]
    board_items: Dict[str, List[Item]]  # board_id -> items
    artists: List[Artist]
    assignments: Dict[str, List[AssignedTask]]   # shot_id -> [AssignedTask]

class WeekSnapshot(BaseModel):
    week: Week
    days: List[Day]
    boards: Dict[Day, List[Board]]
    board_items: Dict[str, List[Item]]  # board_id -> items for all days in week
    artists: List[Artist]
    assignments: Dict[str, List[AssignedTask]]
    no_due_date: Optional[List[Item]] = None
    sequences: Optional[List[str]] = None

class Project(BaseModel):
    id: Any
    name: str

class MoveItemRequest(BaseModel):
    item_id: str
    from_board_id: Optional[str]
    to_board_id: str
    to_index: Optional[int] = None

class MoveByDayRequest(BaseModel):
    item_id: str
    kind: Literal["shots", "assets"]
    to_day: Day
    to_index: Optional[int] = None

class MoveByWeekDayRequest(BaseModel):
    item_id: str
    kind: Literal["shots", "assets"]
    to_week: Week
    to_day: Day
    to_index: Optional[int] = None

class AssignArtistRequest(BaseModel):
    artist_id: str
    shot_id: str
    task: Task
