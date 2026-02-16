import datetime
import pytest
from whiteboard.app import _classify_assets_into_week
from whiteboard.models import Week


@pytest.fixture
def base_monday():
    return datetime.date(2026, 2, 16)  # A Monday


@pytest.fixture
def empty_overrides():
    return {}, {}


def test_mixed_assets_all_statuses(base_monday):
    project_moves = {}
    project_no_due = {}


    sg_assets = [
        {
            "id": 24,
            "code": "asset_24",
            "image": None,
            "sg_asset_type": "Character",
            "sg_status_list": None,
            "sg_next_delivery": datetime.date(2026, 2, 19),
        },
    ]

    board_items, no_due, on_hold, omitted, asset_types = _classify_assets_into_week(
        week=Week.w0,
        monday=base_monday,
        sg_assets=sg_assets,
        project_moves=project_moves,
        project_no_due=project_no_due,
    )
    print("board items: ", board_items)
    print("no due: ", no_due)
    print("on hold: ", on_hold)
    assert "Week.w0-Day.thu-assets" in board_items
