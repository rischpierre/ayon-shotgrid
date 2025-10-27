# TODO

- [x] the API key is not set
- [x] are the shot thumbnails working? -> update the thumbnails on Zero_flow to check it out
- [x] add a right click menu when I click on artist to unassign
- [x] add a favicon for the browser
- [x] use instead the local icon: /cache/dev/ayon-shotgrid/services/whiteboard/whiteboard/favicon.png
- [x] the right click appear to unassign but once clicked the the artist is not removed
- [x] cleanup the index.html split into .js, .css files
- [x] the python module whiteboard_server.py should be split in multiple modules: helpers, models, server, sg_helpers(
  for shotgun api)
- [x] add 3rd and 4th Week
- [x] add a toggle for on hold and omitted shots
- [x] add a board with the shots that don't have a date, so we can drag and drop them
- [x] add shotgun groups (use only the ones with the thumbnail field available, the field is called thumbnail)
- [x] make sure the artists icons are based on the names of the artists so they are the same everytime we reload the
  server
- [x] ensure that the color of the tasks are based on their name so they are the same everytime we reload the server
- [x] use logging instead of print on the whole project
- [x] add the number of the day on each day cell like Mon 12 or tues 15
- [x] remove the hold and omit checkboxes and create boards for both of them instead, both of the board should appear
  after the 4th week board
- [x] add the possibility to add a custom annotation on each day cell. we store this information on a text project field
  called: sg_whiteboard_annotations we need to serialize and deserialize it with json
- [x] add the it into the dns, ask it
- [x] annotations
- [x] is it possible to have a singleton sg_session or something else to avoid creating new objects everytime
- [x] change the vendors thumbnails to be black letter on a white background
- [x] add entity_type on the url so we can load a page with the assets tab open first
- [x] add no due date week board for assets also, and it should have a combobox to filter them by type (like it is done
  for shots)
- [x] load the tasks per shot, in order to avoid avoid errors if a shot don't have the same tasks as the others
- [x] check if the asset assignments work

- [ ] add button to remove due date (use a menu to remove the due date from the item)
- [ ] get tasks per entity instead of getting a sample for all the shots and assets in the project

- [ ] update the 0.0.0-prod addon version so I can deploy the whiteboard on the prod version
