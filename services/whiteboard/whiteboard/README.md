# TODO
- [x] make the manual tests
- [x] get tasks per entity instead of getting a sample for all the shots and assets in the project
- [x] move the assignees to the right of the day cards
- [x] the thumbnails for the assingnees should have an outline color corresponding to the color of the task
- [x] add annotations back, there is no menu showing up on the day cards currently
- [x] add button to remove due date (use a menu to remove the due date from the item)
- [x] make a brighter color on the current day
- [x] the days on the day cards should be in the format of Thu, 25
- [x] add a filter for the shots by their sequence name and for the assets use their asset_type, the filter should be a combo box on the top of the board
- [x] the combobox filter should be on the left side of the no due date board
- [x] the combobox filter should filter only the shots in the no due date board
- [x] is there a black formatter for js ?
- [x] make sure there is no more string literal for Shot or Asset on the frontend, we need to use EntityType.Shot or EntityType.Asset for that
- [x] I tried to build the frontend with npm run build, it created files in backend/static but when I run the backend with python -m whiteboard --dev and when I go to the browser it is blank. I have errors on the terminal too:
- [x] test to build the front with npm build to see if it works and how the built code looks like
- [x] I want to have a context menu popping up when I right-click on the item card, with an `Unschedule` action, instead of the confirmation dialog we had previously (no window.confirm)
- [x] I want to have a context menu popping up when I click or right-click on an assigned artist avatar, with an `Unassign` action (no window.prompt)
- [x] The shots on the No Due Date board are fixed width and flow left-to-right with wrapping; the same layout is applied to the Omitted and On Hold boards
- [x] find a better way to mock the imports of the sg_helpers, currently I just forced the import of sg_helpers_mocked
- [x] on the day boad and for the annotations, we need to have a right click context menu instead of the confirmation dialog we had previously (no window.confirm)
- [x] create more assets on the mocked sg 
- [x] bugfix on the asset tab, when I unschedule an asset it does not go to the no due date board 
- [x] the no due date title should be aligned to the left of the no due date board
- [x] the assets boards don't look the same as the shot boards
- [x] currently on the no due date board, the shots are layout in column first, I want them in row first
- [x] there is no asset type filter on the asset tab
- [x] all the entity cards (shots and assets) should have a fixed width and height regardless of where they are on the boards
- [x] the asset type filter on the assets tabs should be in the no due date board only, it should only affect the assets inside this board
- [x] remove app_deprecated.js when the react migration is done
- [x] make shots and assets cards a bit bigger on their height like 3px (done: --card-h 64px -> 67px)
- [x] make the boards a bit bigger on their height like 20px (done: min-height 220px -> 240px; list max-height 420px -> 440px)
- [x] if there are more than 5 shots on a day, the shots should be in a scrollable container
- [x] update the Dockerfile with npm install and npm build
- [x] publish: make batch updates instead
- [x] remove the loading text appearing when I do a drag and drop
- [x] fix publish it does not work
- [x] I need to publish also the unassignments and the set to no due date too
- [x] make artists icons 20% bigger when they are assigned on cards
- [x] make card entities 30% wider everywhere (shots and assets)
- [x] currently the changes display the assignments like this: `Assignments: 1 entities with changes`, instead, display all the changes
- [x] on the shots and assets cards, the artists thumbnails are overlapping the labels of the entities, make the artists thumbnails aligned on the bottom and the label on the top so there is no overlap
- [x] on the get_week there is a call to find shots and assets, this function takes time, cache it up for 5 seconds
- [x] split api/week, it is too big
- [x] bugfix: on hold and omit assets are not displayed in their respective boards like the shots, update the classify function in app.py
- [x] unassings and unschedules are not displayed in the changes
- [x] bugfix: assets artists assigns are not shoing up on the cards 
- [x] update the url when project is set and entity type tab is set like: ?project=353&entity_type=Shot
- [x] Use the step colors of the task for the tasks colors
  - make a query of all the pipeline steps in shotgrid: sg.find("Step", ... fields=["color"])
  - when doing the task query, get the step and get the color from the step list
  - normalize SG step color values to valid CSS (e.g., '#rrggbb') so outlines render reliably
- [x] When I leave the web page open, in the morning the day and the board is not updated with the current day and date, what to do about this ?

# features for the future 
- [ ] add the feature to schedule a shot from the on hold or omit: it should schedule it and ask for the new status to set  
 
# How to run
1. build the front-end:
   `npm install   # only first time`
   `npm run build `
2. run the backend  
   `export WHITEBOARD_SG_DEV_MODE=1`  -> in order to use sg mocked data
   `python -m whiteboard`

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
