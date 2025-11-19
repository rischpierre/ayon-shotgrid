# Basics
AMI means action menu item. it is a system to be able to execute actions on entities in shotgrid (flow)
It is a web server that listens to the requests made from shotgrid


# coding guidelines
- when a task is done update the .junie/guidelines.md 
- write simple and easily readable code
- add comments only if necessary

# changelog

## 2025-11-19 - Batched Queries for Weekly Status Report Query Fields
- Optimized `fetch_query_fields` in `ami/ami_weekly_status_report/per_project/Huckleberry/ami_weekly_status_report.py` to avoid per-entity `find_one` calls.
- Now performs a single batched `find` per field by replacing "Current Shot/Asset" placeholders with an `in` filter over all relevant entities.
- Preserves schema-defined ordering and assigns the top-ranked result per source entity.
- Maintains project scoping in filters.
- Significantly reduces ShotGrid API calls and computation time on large datasets.

## 2025-11-06 - Added SSH Key Support for Docker Build
- Added BuildKit syntax directive (# syntax=docker/dockerfile:1) to enable advanced Docker features
- Modified git clone command to use --mount=type=ssh for SSH agent forwarding during build
- Added ssh-keyscan command to add GitLab host to known_hosts to prevent host verification prompts
- Updated README.md with comprehensive build instructions including:
  - Prerequisites for SSH key authentication
  - Step-by-step commands to start SSH agent and add keys
  - Docker build command with DOCKER_BUILDKIT=1 and --ssh default flag
  - Alternative method for using specific SSH keys
- This allows the Docker container to clone private repositories using local SSH keys during the build process

## 2025-11-06 - Use Unique Temporary Filenames to Avoid Conflicts
- Modified export_file() method in AMIWeeklyStatusReport to use tempfile.mktemp() with prefix "report_" and suffix ".xlsx"
- Modified get_template() method to use tempfile.mktemp() with prefix "sg_template_" for downloaded ShotGrid templates
- Added report_cache dictionary in ami_server.py to store temporary report paths with unique UUID keys
- Updated build_result_page() to generate unique download URLs using UUID keys and store report paths in cache
- Modified download_report() endpoint to accept a report_key parameter and retrieve paths from cache
- Updated post_ami() to pass ami_instance to build_result_page() for accessing generated report paths
- This prevents conflicts when multiple users or processes generate reports simultaneously

## 2025-11-06 - Changed Temporary Files to Use /tmp Directory
- Modified export_file() method in AMIWeeklyStatusReport to use /tmp/report.xlsx as default output path instead of module directory
- Modified get_template() method in AMIWeeklyStatusReport to download sg_template.xlsx to /tmp/sg_template.xlsx instead of module directory
- This ensures temporary files are stored in the proper temporary directory rather than cluttering the module directory

## 2025-11-06 - Added Corder Repository to Dockerfile
- Added git clone step in Dockerfile to clone corder repository from https://gitlab.eu.rvx.is/pipeline/corder.git
- Repository is cloned to /service/corder directory
- Clone step occurs after poetry install but before git package is removed
- Corder is used by ami_weekly_status_report for Excel template manipulation

## 2025-11-06 - Fixed Weekly Status Report to Use ShotGrid Template
- Modified get_template() method in AMIWeeklyStatusReport to download and use the template from sg_wsr_template field
- Added urllib.request import to download template file from ShotGrid URL
- Template priority order is now: 1) uploaded file, 2) ShotGrid sg_wsr_template, 3) default template.xlsx
- Downloaded ShotGrid template is cached as sg_template.xlsx in ami_weekly_status_report directory
- Previously, the sg_wsr_template field was only being fetched and displayed but not actually used for report generation

## 2025-11-05 - Display Project Template from ShotGrid on Request Page
- Added get_project_template_info() method to AMIWeeklyStatusReport to fetch sg_wsr_template field from Project entity
- Added get_request_page_context() method to AMIWeeklyStatusReport to provide template info to request page
- Modified ami_server.py post_ami() to check for get_request_page_context() method and merge AMI context with template context
- Updated request_page.html for weekly status report to display green info box when project template exists
- Info box shows "Project Template Found" with the template name from ShotGrid
- Template info is fetched via ShotGrid API using sg_session.find_one() with sg_wsr_template field

## 2025-11-05 - Fixed Content-Length Error in POST /ami Endpoint
- Removed `response_class=HTMLResponse` from POST endpoint decorators in ami_server.py
- The issue was caused by FastAPI's HTMLResponse class interfering with TemplateResponse's internal encoding and Content-Length calculation
- TemplateResponse already handles response encoding and headers properly, so forcing HTMLResponse caused a mismatch
- This fixes the "Too much data for declared Content-Length" error that occurred when returning HTML responses from the weekly status report AMI
- Error was appearing in uvicorn logs during h11 protocol handling when sending response body

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