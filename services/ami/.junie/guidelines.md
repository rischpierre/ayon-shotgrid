# Basics
AMI means action menu item. it is a system to be able to execute actions on entities in shotgrid (flow)
It is a web server that listens to the requests made from shotgrid


# coding guidelines
- when a task is done update the .junie/guidelines.md 
- write simple and easily readable code
- add comments only if necessary

# changelog

## 2025-11-05 - Added Download Button for Weekly Status Report
- Added /download/report endpoint in ami_server.py to serve generated xlsx files
- Modified build_result_page to pass download_url context for ami_weekly_status_report action
- Added download button styling and conditional rendering in page.html template
- Button appears only on success page for weekly status report action

## 2025-11-04 - Converted to FastAPI
- Converted ami_server.py from BaseHTTPRequestHandler to FastAPI
- Updated HTML templates (page.html, parameters.html) to use Jinja2 template syntax
- Added dependencies: fastapi, uvicorn, jinja2, python-multipart
- Simplified code structure with clean route handlers and helper functions
- Server now uses uvicorn instead of ThreadingHTTPServer