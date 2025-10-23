# TODO
- [x] the API key is not set
- [x] are the shot thumbnails working? -> update the thumbnails on Zero_flow to check it out
- [x] add a right click menu when I click on artist to unassign 
- [x] add a favicon for the browser
- [x] use instead the local icon: /cache/dev/ayon-shotgrid/services/whiteboard/whiteboard/favicon.png
- [x] the right click appear to unassign but once clicked the the artist is not removed
- [x] cleanup the index.html split into .js, .css files
- [x] the python module whiteboard_server.py should be split in multiple modules: helpers, models, server, sg_helpers(for shotgun api)
- [x] add 3rd and 4th Week
- [x] add a toggle for on hold and omitted shots
- [x] add a board with the shots that don't have a date, so we can drag and drop them
- [x] add shotgun groups (use  only the ones with the thumbnail field available, the field is called thumbnail)
- [x] make sure the artists icons are based on the names of the artists so they are the same everytime we reload the server 
- [x] ensure that the color of the tasks are based on their name so they are the same everytime we reload the server
- [x] use logging instead of print on the whole project

- [x] add the number of the day on each day cell like Mon 12 or tues 15 
- [x] remove the hold and omit checkboxes and create boards for both of them instead, both of the board should appear after the 4th week board
- [x] add the possibility to add a custom annotation on each day cell. we store this information on a text project field called: sg_whiteboard_annotations we need to serialize and deserialize it with json
 
- [ ] add a set of swatches with a few colors to set the annotations
- [ ] instead of double click for the annotation, I want to have a right click on the day cell with a menu to set the annotation

- [ ] change the vendors thumbnails to be black letter on a white background
 
- [ ] load the tasks per shot, in order to avoid avoid errors if a shot don't have the same tasks as the others
- [ ] is it possible to have a singleton sg_session or something else to avoid creating new objects everytime
- [ ] the unassignments are working but there is no unassign change displayed on the publish confirmation dialog
- [ ] check if the asset assignments work 
- [ ] add the it into the dns, ask it
 
- [ ] update the 0.0.0-prod addon version so I can deploy the whiteboard on the prod version
