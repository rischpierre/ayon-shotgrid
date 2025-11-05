# Basics
AMI means action menu item. it is a system to be able to execute actions on entities in shotgrid (flow)
It is a web server that listens to the requests made from shotgrid


# coding guidelines
- when a task is done update the .junie/guidelines.md 
- write simple and easily readable code
- add comments only if necessary

# changelog

## 2025-11-05 - Fixed Content-Length Error in Download Report Endpoint
- Modified /download/report endpoint in ami_server.py to use Response instead of FileResponse
- Changed to read entire file content into memory before creating response
- This fixes "Too much data for declared Content-Length" error caused by FileResponse streaming files that may not be fully flushed
- File content is now read with `open(report_path, "rb")` before response creation
- Added explicit Content-Disposition header for proper file download handling

## 2025-11-05 - Fixed Template Loader Order for AMI-Specific Templates
- Modified ChoiceLoader in ami_server.py to search ami_* directories before templates/ directory
- Changed from `[FileSystemLoader(TEMPLATES_DIR)] + ami_loaders` to `ami_loaders + [FileSystemLoader(TEMPLATES_DIR)]`
- This ensures AMI-specific templates (like ami_weekly_status_report/request_page.html) take precedence over default templates
- Fixes the issue where the file upload button was not showing because the default template was being used instead of the custom one

## 2025-11-05 - Added Back Favicon Route
- Added /favicon.ico GET route in ami_server.py that returns 204 No Content
- This restores the favicon handling that was present in the old HTTP server implementation before FastAPI conversion

## 2025-11-05 - Fixed Request Page Not Showing for Weekly Status Report
- Modified execute_ami in ami_server.py to check for get_request_page_template() method
- Request page now displays even when parameters() returns an empty list
- AMIs with custom request page templates will always show the request page on first load
- This fixes the issue where weekly status report AMI would skip directly to execution

## 2025-11-05 - Added Excel Template Upload for Weekly Status Report
- Created custom request_page.html for ami_weekly_status_report with file upload input
- Added get_request_page_template() method to AMIWeeklyStatusReport to use custom template
- Updated ami_server.py to handle file uploads:
  - Added UploadFile, File, and Form imports from FastAPI
  - Modified post_ami to detect and save uploaded files
  - Files are saved to ami_weekly_status_report directory as uploaded_template.xlsx
- Modified get_template() in AMIWeeklyStatusReport to use uploaded template if available
- Template file path is passed through data dict from server to AMI instance
- Falls back to default template.xlsx if no file is uploaded

## 2025-11-05 - Custom Templates for Each AMI
- Added get_parameters_template() and get_result_template() methods to AmiBase
- Modified ami_server.py to check for custom templates from AMI instances before using defaults
- Updated execute_ami to return AMI instance along with results for template access
- Configured Jinja2 ChoiceLoader to search templates in ami_* directories
- Created example custom templates:
  - ami_weekly_status_report/result.html with enhanced styling and download button
  - ami_create_delivery_playlist/parameters.html with info box and custom styling
- Each AMI can now provide custom HTML templates for parameters and result pages by overriding the template methods

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