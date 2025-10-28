from playwright.sync_api import Page, expect

# The server_url fixture is provided by tests/e2e/conftest.py


def _open_home(page: Page, server_url: str):
    page.goto(f"{server_url}/")
    expect(page.locator("select#projectSelect")).to_be_visible()


def test_drag_and_drop_shot_between_days(page: Page, server_url: str):
    _open_home(page, server_url)
    # Start: 1001 at w0/wed
    wed_card = page.locator('[data-week="w0"][data-day="wed"] .list .card[data-item-id="1001"]')
    expect(wed_card).to_be_visible()

    # Drop onto Thursday list
    thu_list = page.locator('[data-week="w0"][data-day="thu"] .list')
    expect(thu_list).to_be_visible()
    wed_card.drag_to(thu_list)

    import time; time.sleep(200)
    # Verify move
    expect(page.locator('[data-week="w0"][data-day="thu"] .list .card[data-item-id="1001"]')).to_be_visible()
    expect(page.locator('[data-week="w0"][data-day="wed"] .list .card[data-item-id="1001"]')).to_have_count(0)


def test_omitted_board_contains_shot(page: Page, server_url: str):
    _open_home(page, server_url)
    # Omitted section is appended at bottom when in shots mode
    omitted_card = page.locator('#holdOmitSection .card[data-item-id="1003"]')
    expect(omitted_card).to_be_visible()


def test_no_due_date_contains_shot(page: Page, server_url: str):
    _open_home(page, server_url)
    no_due_card = page.locator('#noDueSection .card[data-item-id="1002"]')
    expect(no_due_card).to_be_visible()


def test_assign_artist_to_shot(page: Page, server_url: str):
    _open_home(page, server_url)
    # Drag first artist to shot 1001 → task picker should open → choose Animation
    artist = page.locator('#artistBar .artist').first
    target_card = page.locator('[data-week="w0"][data-day="wed"] .list .card[data-item-id="1001"]')
    expect(target_card).to_be_visible()
    artist.drag_to(target_card)

    # Task picker appears; click Animation
    task_option = page.locator('.task-option', has_text='Animation').first
    expect(task_option).to_be_visible()
    task_option.click()

    # Expect an assignee avatar now on the card
    assignees = page.locator('[data-shot-assignees="1001"] .assignee')
    expect(assignees).to_have_count(1)


def test_add_annotation_with_color(page: Page, server_url: str):
    _open_home(page, server_url)
    header = page.locator('[data-week="w0"][data-day="wed"] h3').first

    # Add text via context menu (prompt)
    with page.expect_event('dialog') as dialog_info:
        header.click(button='right')
        page.click('#dayAddEdit')
    dialog = dialog_info.value
    dialog.accept('Standup')

    # Set color via submenu
    header.click(button='right')
    page.hover('#dayColor')
    # Pick #3498db (appears uppercased in menu)
    page.get_by_text('#3498DB', exact=True).click()

    # Verify annotation text visible with color
    ann_span = header.locator('xpath=.//span[last()]')
    expect(ann_span).to_have_text('Standup')
    # Check the computed color equals rgb(52, 152, 219)
    color = ann_span.evaluate('el => getComputedStyle(el).color')
    assert color.replace(' ', '') in ('rgb(52,152,219)', 'rgba(52,152,219,1)')


def test_publish_displays_changes(page: Page, server_url: str):
    _open_home(page, server_url)

    # Move shot 1001 to Thursday
    page.locator('[data-week="w0"][data-day="wed"] .card[data-item-id="1001"]').drag_to(
        page.locator('[data-week="w0"][data-day="thu"] .list')
    )

    # Assign Alice to shot 1001 (Animation)
    page.locator('#artistBar .artist').first.drag_to(
        page.locator('[data-week="w0"][data-day="thu"] .card[data-item-id="1001"]')
    )
    page.locator('.task-option', has_text='Animation').first.click()

    # Open publish modal and verify changes listed
    page.click('#publishBtn')
    modal = page.locator('#publishModal')
    expect(modal).to_be_visible()
    expect(modal.locator('.changes-list')).to_be_visible()
    expect(modal.locator('.changes-list')).to_contain_text('Reschedules')
    expect(modal.locator('.changes-list')).to_contain_text('sh010')
    expect(modal.locator('.changes-list')).to_contain_text('Assignments')
    expect(modal.locator('.changes-list')).to_contain_text('Animation')

    # Optionally, confirm publish and verify cleared state
    page.click('#confirmPublish')
    # Modal hides and UI reloads
    expect(modal).to_be_hidden()
    # Re-open publish → No changes pending
    page.click('#publishBtn')
    expect(page.locator('#changesContainer')).to_contain_text('No changes pending.')
    # Also confirm card returned to original day (wed)
    expect(page.locator('[data-week="w0"][data-day="wed"] .card[data-item-id="1001"]')).to_be_visible()
