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
 
- [ ] load the tasks per shot, in order to avoid avoid errors if a shot don't have the same tasks as the others

- [ ] the unassignments are working but there is no unassign change displayed on the publish confirmation dialog
- [ ] check if the asset assignments work 
- [ ] how to deal with multiple users changing things at the same time? create a lock mechanism
 
*cleanup* 
- [ ] update the 0.0.0-prod addon version so I can deploy the whiteboard on the prod version
- [ ] add the ip into the dns, ask it
