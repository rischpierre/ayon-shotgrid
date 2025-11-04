# Todo
- [x] replace a single cell in an excel sheet with corder
- [x] generate an excel file with a range of shots that have been replaced
- [x] get the fields from the template for shots
- [x] make a shot and asset tab and fill them up
- [x] start filling up the overview
- [ ] reoganize the ami code with core and the amis, 
- [ ] prepare the questions for the meeting
    - [ ] filter the shots and assets with updated date ? (meeting) 
- [ ] do I need to put ami_server.py somewhere because it seems to be related to the create delivery only
- [ ] make the ami to work on project entity
- [ ] how to download the resulting template from the browser ? 


# How it works
1. read the excel template
2. get all the fields needed for the shots and assets tabs
3. make a query of all the shots updated this week with the fields from the template
4. replace the excel template with corder
5. post-process: stats on the first page
6. post-process: replace statuses