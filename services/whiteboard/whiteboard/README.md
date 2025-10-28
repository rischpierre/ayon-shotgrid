# TODO
- [ ] add button to remove due date (use a menu to remove the due date from the item)
- [ ] get tasks per entity instead of getting a sample for all the shots and assets in the project

- [ ] update the 0.0.0-prod addon version so I can deploy the whiteboard on the prod version
 
- [ ] make the manual tests


# Playwright tests
1) Install Playwright for Python (dev dependencies):
```
poetry add -D playwright pytest-playwright
poetry run playwright install
```
2) Run the E2E test:
```
poetry run pytest -q tests/test_drag_drop_shot.py
```

# Tests to do
for assets:
- [_] move an entity on another day and publish
- [ ] set an entity to no date (right click menu) and publish
 
- [ ] create an annotation with a color
- [ ] change the color
- [ ] remove the annotation

- [ ] assign an artist and publish
- [ ] unassign an artist and publish 
- [ ] assign a group and publish
- [ ] unassign a group and publish
 
for shots:
- [ ] move an entity on another day
- [ ] set an entity to no date (right click menu)
 
- [ ] create an annotation with a color
- [ ] change the color
- [ ] remove the annotation

- [ ] assign an artist
- [ ] unassign an artist
- [ ] assign a group
- [ ] unassign a group