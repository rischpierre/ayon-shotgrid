from playwright.sync_api import Page, expect

# The server_url fixture is provided by tests/e2e/conftest.py

# to run: poetry run pytest -q tests/e2e/test_drag_drop_shot.py --headed --slowmo 1600

def test_drag_and_drop_shot_between_days(page: Page, server_url: str):
    # Open the Whiteboard page
    page.goto(f"{server_url}/")

    # in order to see the page
    import time; time.sleep(2000)

    # Wait for the project select to populate and the initial week to render
    project_select = page.locator("select#projectSelect")
    expect(project_select).to_be_visible()

    # Wait for our known shot card (id=1001, name=sh010) to appear in Wednesday (w0/wed)
    wed_card = page.locator('[data-week="w0"][data-day="wed"] .list .card[data-item-id="1001"]')
    expect(wed_card).to_be_visible()

    # Identify Thursday list as the drop target
    thu_list = page.locator('[data-week="w0"][data-day="thu"] .list')
    expect(thu_list).to_be_visible()

    # Perform drag-and-drop of the card to Thursday list
    wed_card.drag_to(thu_list)

    # After drop, the app reloads the mode; wait for the card to appear under Thursday
    moved_card = page.locator('[data-week="w0"][data-day="thu"] .list .card[data-item-id="1001"]')
    expect(moved_card).to_be_visible()

    # Optional: ensure it no longer appears in Wednesday
    expect(page.locator('[data-week="w0"][data-day="wed"] .list .card[data-item-id="1001"]')).to_have_count(0)
