
# coding guidelines
- when a task is done update the .junie/guidelines.md 
- write simple and easily readable code
- add comments only if necessary

# changelog

## 2025-11-04 - Converted to FastAPI
- Converted ami_server.py from BaseHTTPRequestHandler to FastAPI
- Updated HTML templates (page.html, parameters.html) to use Jinja2 template syntax
- Added dependencies: fastapi, uvicorn, jinja2, python-multipart
- Simplified code structure with clean route handlers and helper functions
- Server now uses uvicorn instead of ThreadingHTTPServer