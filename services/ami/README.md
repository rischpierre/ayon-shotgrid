# Todo
- [x] replace a single cell in an excel sheet with corder
- [x] generate an excel file with a range of shots that have been replaced
- [x] get the fields from the template for shots
- [x] make a shot and asset tab and fill them up
- [x] start filling up the overview
- [x] reoganize the ami code with core and the amis, 
- [x] make the ami to work on project entity
- [x] convert ami_server.py and the html templates in templates folder to use fastapi instead I want the code to be simple and easy to read
- [x] test to run the ami server again with the migration to the fastapi
- [x] how to download the resulting template from the browser
- [x] for each AMI I want to be able to customize the parameters page and the result page
- [x] add the possibility to upload a xlsx file on the custom page
- [x] get the default excel template from shotgrid on the project enity under the field sg_wsr_template and display on the request page that there is already a template on the project, and give its name
- [x] modify jan's template to use corder, and compare it until I have the same result as he had
- [x] I need to create an ami per project, it will be easier to manage
- [x] fix the HB excel generation
- [x] add autofilter to the first line
- [x] udpate the dockerfile to add the corder repo
- [ ] fix traceback when generating the file
- [ ] check if the custom template is correctly used when uploaded
- [ ] make a mp4 for the demo


# How it works
1. read the excel template
2. get all the fields needed for the shots and assets tabs
3. make a query of all the shots updated this week with the fields from the template
4. replace the excel template with corder
5. post-process: stats on the first page
6. post-process: replace statuses