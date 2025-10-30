from __future__ import annotations


import datetime as _dt
from typing import Any, Dict, List, Sequence, Tuple

from ..models import EntityType, Week, Day  # type: ignore

# In-memory storage for annotations in mock mode
_annotations_store: Dict[int, Dict[str, Any]] = {}


def _today() -> _dt.date:
    return _dt.date.today()


def sg_list_projects() -> List[Dict[str, Any]]:
    return [
        {"type": "Project", "id": 1, "name": "Demo Project", "archived": False},
        {"type": "Project", "id": 2, "name": "Sandbox", "archived": False},
    ]


def sg_find_project_artists(project_id: int) -> List[Dict[str, Any]]:
    return [
        {
            "type": "HumanUser",
            "id": 11,
            "name": "Alice Artist",
            "image": {"url": "https://placekitten.com/64/64"},
        },
        {
            "type": "HumanUser",
            "id": 12,
            "name": "Bob Builder",
            "image": {"url": "https://placekitten.com/65/65"},
        },
    ]


def sg_list_groups() -> List[Dict[str, Any]]:
    return [
        {
            "type": "Group",
            "id": 101,
            "code": "Comp",
            "sg_thumbnail": {"url": "https://placehold.co/64x64"},
        },
        {
            "type": "Group",
            "id": 102,
            "code": "Anim",
            "sg_thumbnail": {"url": "https://placehold.co/64x64?text=A"},
        },
    ]


def sg_find_project_shots(project_id: int) -> List[Dict[str, Any]]:
    base = _today()

    no_due_date_shots = []
    for i in range(10):
        name = f"shot_00{i}"
        id_ = 230 + i
        no_due_date_shots.append(
            {
                "type": "Shot",
                "id": id_,
                "code": name,
                "sg_next_delivery": None,
                "image": {"url": f"https://placehold.co/320x180?text={name}"},
                "sg_sequence": {"type": "Sequence", "id": id_, "name": "seq0xx"},
                "sg_status_list": "ip",
            }
        )

    shots = [
        {
            "type": "Shot",
            "id": 201,
            "code": "sh010",
            "sg_next_delivery": (base + _dt.timedelta(days=1)).isoformat(),
            "image": {"url": "https://placehold.co/320x180?text=sh010"},
            "sg_sequence": {"type": "Sequence", "id": 301, "name": "seq001"},
            "sg_status_list": "ip",
        },
        {
            "type": "Shot",
            "id": 202,
            "code": "sh020",
            "sg_next_delivery": (base + _dt.timedelta(days=3)).isoformat(),
            "image": {"url": "https://placehold.co/320x180?text=sh020"},
            "sg_sequence": {"type": "Sequence", "id": 301, "name": "seq001"},
            "sg_status_list": "wtg",
        },
        {
            "type": "Shot",
            "id": 203,
            "code": "sh030",
            "sg_next_delivery": None,
            "image": {"url": "https://placehold.co/320x180?text=sh030"},
            "sg_sequence": {"type": "Sequence", "id": 302, "name": "seq002"},
            "sg_status_list": "omt",
        },
    ]
    shots.extend(no_due_date_shots)
    return shots


def sg_find_project_assets(project_id: int) -> List[Dict[str, Any]]:
    base = _today()
    assets: List[Dict[str, Any]] = [
        {
            "type": "Asset",
            "id": 401,
            "code": "chr_alice",
            "sg_next_delivery": (base + _dt.timedelta(days=5)).isoformat(),
            "image": {"url": "https://placehold.co/320x180?text=alice"},
            "sg_asset_type": "Character",
            "sg_status_list": "ip",
        },
        {
            "type": "Asset",
            "id": 402,
            "code": "prp_hammer",
            "sg_next_delivery": None,
            "image": {"url": "https://placehold.co/320x180?text=hammer"},
            "sg_asset_type": "Prop",
            "sg_status_list": "hld",
        },
    ]

    more_defs = [
        (403, "chr_bob", "Character", 2),
        (404, "chr_eve", "Character", 8),
        (405, "prp_wrench", "Prop", None),
        (406, "prp_lantern", "Prop", 1),
        (407, "veh_truck", "Vehicle", 6),
        (408, "veh_bike", "Vehicle", None),
        (409, "env_forest", "Environment", 10),
        (410, "env_cave", "Environment", None),
        (411, "set_kitchen", "Set", 4),
        (412, "set_office", "Set", None),
        (413, "wep_sword", "Weapon", 3),
        (414, "wep_blaster", "Weapon", None),
        (415, "cr_creatureA", "Creature", 7),
        (416, "cr_creatureB", "Creature", None),
        (417, "fx_smoke", "FX", 9),
        (418, "fx_fire", "FX", None),
        (419, "chr_charlie", "Character", None),
        (420, "prp_shield", "Prop", 11),
    ]

    for _id, code, a_type, days in more_defs:
        due = (base + _dt.timedelta(days=days)).isoformat() if isinstance(days, int) else None
        assets.append(
            {
                "type": "Asset",
                "id": _id,
                "code": code,
                "sg_next_delivery": due,
                "image": {"url": f"https://placehold.co/320x180?text={code}"},
                "sg_asset_type": a_type,
                "sg_status_list": "ip" if due else "wtg",
            }
        )

    return assets


def sg_find_tasks_per_entity(project_id: int) -> dict[EntityType, dict[int, Any]]:
    # very simple mapping of entity -> list of tasks
    # Frontend expects tasks per Shot primarily
    tasks_for_shots = {
        201: [
            {"id": 9001, "content": "Animation", "entity": {"type": "Shot", "id": 201}},
            {"id": 9002, "content": "Lighting", "entity": {"type": "Shot", "id": 201}},
        ],
        202: [
            {"id": 9003, "content": "Comp", "entity": {"type": "Shot", "id": 202}},
        ],
    }
    for i in range(10):
        id_ = 230 + i
        tasks_for_shots[id_] = [
            {"id": 9000 + id_, "content": "Comp", "entity": {"type": "Shot", "id": id_}},
            {"id": 9001 + id_, "content": "Layout", "entity": {"type": "Shot", "id": id_}},
        ]

    tasks_for_assets: dict[int, Any] = {
        401: [
            {"id": 9101, "content": "Modeling", "entity": {"type": "Asset", "id": 401}},
        ]
    }
    # add basic tasks for the rest of the mocked assets so UI can assign
    for asset in sg_find_project_assets(project_id):
        aid = int(asset["id"])
        if aid not in tasks_for_assets:
            base_id = 9100 + aid
            tasks_for_assets[aid] = [
                {"id": base_id, "content": "Modeling", "entity": {"type": "Asset", "id": aid}},
            ]
    return {EntityType.Shot: tasks_for_shots, EntityType.Asset: tasks_for_assets}


def sg_find_entities_by_ids(
    entity_type: EntityType, ids: Sequence[int]
) -> List[Dict[str, Any]]:
    # Merge shots and assets to respond by ID
    all_entities = {
        e["id"]: e for e in (sg_find_project_shots(0) + sg_find_project_assets(0))
    }
    out: List[Dict[str, Any]] = []
    for _id in ids:
        ent = all_entities.get(_id)
        if ent and ent.get("type") == entity_type.name:
            out.append(ent)
    return out


def sg_publish_changes(
    project_id: int,
    moves: Dict[EntityType, Dict[int, Tuple[Week, Day]]],
    assigns: Dict[EntityType, Dict[int, List[Any]]],
) -> None:
    # In mock mode just accept and do nothing
    return None


def sg_get_project_annotations(project_id: int) -> Dict[str, Any]:
    return _annotations_store.get(int(project_id), {})


def sg_set_project_annotations(project_id: int, data: Dict[str, Any]) -> None:
    _annotations_store[int(project_id)] = dict(data or {})
