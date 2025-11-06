import logging
import json
import os
import sys
from typing import Any, Dict, Optional

import ayon_api
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader
from shotgun_api3 import Shotgun

logging.basicConfig(
    level=os.environ.get("LOGLEVEL") or os.environ.get("PYTHON_LOG_LEVEL") or logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger(__file__)

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
AMI_BASE_DIR = os.path.dirname(__file__)

ami_loaders = []
for entry in os.listdir(AMI_BASE_DIR):
    entry_path = os.path.join(AMI_BASE_DIR, entry)
    if os.path.isdir(entry_path) and entry.startswith("ami_"):
        ami_loaders.append(FileSystemLoader(entry_path))

loader = ChoiceLoader(ami_loaders + [FileSystemLoader(TEMPLATES_DIR)])
templates = Jinja2Templates(directory=TEMPLATES_DIR)
templates.env.loader = loader

app = FastAPI(title="ShotGrid AMI Server")


def get_sg_session():
    ayon_api_key = os.environ.get("AYON_API_KEY")
    ayon_server_url = os.environ.get("AYON_SERVER_URL")
    sg_url = os.environ.get("SG_URL")
    proxy_url = os.environ.get("HTTP_PROXY").replace("http://", "")

    if not ayon_api_key or not ayon_server_url:
        raise Exception("AYON_API_KEY and AYON_SERVER_URL are required")

    if not sg_url or not proxy_url:
        raise Exception("SG_URL and HTTP_PROXY env vars are required")

    ayon_api.init_service(token=ayon_api_key, server_url=ayon_server_url)
    script_name = ayon_api.get_secret("flow_ami_service_name")["value"]
    script_key = ayon_api.get_secret("flow_ami_service_key")["value"]

    if not script_name or not script_key:
        raise Exception("Script name or key is not set")

    return Shotgun(sg_url, script_name=script_name, api_key=script_key, http_proxy=proxy_url)


def render_page(
    title: str,
    success: bool,
    message: str,
    lines: list[str],
    echo: Dict[str, Any]
) -> Dict[str, Any]:
    badge_color = "#16a34a" if success else "#dc2626"
    border_color = "#22c55e" if success else "#f87171"
    badge_label = "Success" if success else "Error"
    footer_text = "ShotGrid AMI Prototype • All good." if success else "ShotGrid AMI Prototype • Please review and retry."
    safe_pre = json.dumps(echo, ensure_ascii=False, indent=2)
    items_html = "".join(f"<li>{line}</li>" for line in lines)

    return {
        "title": title,
        "badge_color": badge_color,
        "border_color": border_color,
        "badge_label": badge_label,
        "message": message,
        "items_html": items_html,
        "safe_pre": safe_pre,
        "footer_text": footer_text,
    }


def build_result_page(data: Dict[str, Any], success: bool) -> Dict[str, Any]:
    action_name = data.get("action") or "unknown_action"
    if isinstance(action_name, list):
        action_name = action_name[0] if action_name else "unknown_action"

    lines = [
        f"Action: {action_name}",
        f"User: {data.get('user_id', 'unknown')}",
        f"Entity ids: {data.get('selected_ids', '')}",
        f"Project: {data.get('project_name', '')}",
    ]
    title = "Action Submitted" if success else "Action Failed"
    message = "Action received and processed." if success else "There was a problem processing your request."
    
    result = render_page(title=title, success=success, message=message, lines=lines, echo=data)
    
    if success and action_name == "ami_weekly_status_report":
        result["download_url"] = "/download/report"
    
    return result


def execute_ami(data: Dict[str, Any]) -> tuple[int, Optional[tuple]]:
    logger.debug(data)
    action = data.get("action")
    
    if not isinstance(action, str) or not action.strip():
        raise Exception("Invalid action value")

    try:
        module_name = f"ami.{action}.{action}"
        module = sys.modules.get(module_name)
        if not module:
            raise Exception(f"Action module not found: {module_name}")

        ami_class = None
        for name, obj in module.__dict__.items():
            if isinstance(obj, type) and hasattr(obj, "main") and callable(getattr(obj, "main")):
                ami_class = obj
                break

        if not ami_class:
            raise Exception("No class with main() found in ami.%s", action)

        sg = get_sg_session()
        
        # Check for project-specific override
        if data["entity_type"] == "Project":
            project_id = int(data["selected_ids"].split(",")[0] or 0)
        else:
            project_id = data.get("project_id")

        project = sg.find_one("Project", [["id", "is", project_id]], ["name"])
        project_name = project["name"]
        per_project_module_name = f"ami.{action}.per_project.{project_name}.{action}"

        # Try to import the project-specific module
        try:
            import importlib
            per_project_module = importlib.import_module(per_project_module_name)

            # Find the project-specific class
            for name, obj in per_project_module.__dict__.items():
                if isinstance(obj, type) and hasattr(obj, "main") and callable(getattr(obj, "main")):
                    if obj != ami_class:  # Make sure it's not the base class
                        ami_class = obj
                        logger.info(f"Using project-specific AMI class: {name} for project {project_name}")
                        break
        except ImportError:
            logger.debug(f"No project-specific override found for {project_name}, using base class")

        instance = ami_class(sg, data)

        params_fn = getattr(instance, "parameters", None)
        parameters = None
        if callable(params_fn):
            parameters = params_fn()

        has_custom_request_page = hasattr(instance, "get_request_page_template")
        
        if (parameters or has_custom_request_page) and not data.get("__form_submitted"):
            return -1, (action, parameters or [], data, instance)

        if parameters and data.get("__form_submitted"):
            for p in parameters:
                field_key = str(p.name)
                if field_key in data:
                    p.set(data.get(field_key))

        return instance.main(), instance

    except Exception as e:
        logger.exception(e)
        return 1, None


def build_parameters_form(action: str, parameters: list, original: Dict[str, Any]) -> Dict[str, Any]:
    def esc(s: str) -> str:
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    inputs_html = []
    for p in parameters:
        label = esc(str(p.name))
        try:
            current_val = p.value()
        except Exception:
            current_val = getattr(p, "default", "")
        
        if isinstance(current_val, bool):
            checked = " checked" if current_val else ""
            inputs_html.append(
                f'<label style="display:block;margin:8px 0;"><span style="display:inline-block;width:180px;">{label}</span>'
                f'<input type="checkbox" name="{esc(str(p.name))}" value="true"{checked}></label>'
            )
        else:
            inputs_html.append(
                f'<label style="display:block;margin:8px 0;"><span style="display:inline-block;width:180px;">{label}</span>'
                f'<input type="text" name="{esc(str(p.name))}" value="{esc(str(current_val))}" '
                f'style="min-width:320px;padding:6px;border-radius:6px;border:1px solid #555;background:#0b1220;color:#e5e7eb;"></label>'
            )

    hidden_inputs = []
    for k in original.keys():
        if k in ("__form_submitted", "action"):
            continue
        v = original.get(k)
        if v is None:
            continue
        hidden_inputs.append(f'<input type="hidden" name="{esc(str(k))}" value="{esc(str(v))}">')
    
    hidden_inputs.append('<input type="hidden" name="__form_submitted" value="1">')
    hidden_inputs.append(f'<input type="hidden" name="action" value="{esc(str(action))}">')

    return {
        "title": "Parameters",
        "heading": "Adjust Parameters",
        "action_url": "/ami",
        "hidden_inputs": "".join(hidden_inputs),
        "inputs_html": "".join(inputs_html),
        "submit_label": "Send",
    }

@app.get("/favicon.ico")
async def favicon():
    return JSONResponse(content=None, status_code=204)

@app.get("/download/report")
async def download_report():
    report_path = os.path.join(os.path.dirname(__file__), "ami_weekly_status_report", "report.xlsx")
    if not os.path.exists(report_path):
        return JSONResponse(content={"error": "Report file not found"}, status_code=404)
    
    with open(report_path, "rb") as f:
        content = f.read()
    
    from fastapi.responses import Response
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=weekly_status_report.xlsx"}
    )

@app.post("/")
@app.post("/ami")
async def post_ami(request: Request):
    form_data = await request.form()
    data = {}
    
    for key, value in form_data.items():
        if hasattr(value, 'file'):
            upload_file = value
            if upload_file.filename:
                temp_dir = os.path.join(os.path.dirname(__file__), "ami_weekly_status_report")
                file_path = os.path.join(temp_dir, "uploaded_template.xlsx")
                
                with open(file_path, "wb") as f:
                    content = await upload_file.read()
                    f.write(content)
                
                data[key] = file_path
                logger.info(f"Uploaded file saved to: {file_path}")
        else:
            data[key] = value
    
    query_params = dict(request.query_params)
    if query_params:
        data.update(query_params)

    try:
        preview = json.dumps(data, ensure_ascii=False)[:2000]
        logger.debug("AMI payload: %s%s", preview, " …" if len(preview) == 2000 else "")
    except Exception:
        logger.debug("AMI payload received (unprintable)")

    try:
        result, params_data = execute_ami(data)
        
        if result == -1 and params_data:
            action, parameters, original, instance = params_data
            context = build_parameters_form(action, parameters, original)
            
            # Merge additional context from AMI instance if available
            if hasattr(instance, "get_request_page_context"):
                try:
                    ami_context = instance.get_request_page_context()
                    if ami_context:
                        context.update(ami_context)
                except Exception as e:
                    logger.error(f"Error getting request page context: {e}")
            
            custom_template = None
            if hasattr(instance, "get_request_page_template"):
                custom_template = instance.get_request_page_template()
            
            template_name = custom_template if custom_template else "request_page.html"
            return templates.TemplateResponse(template_name, {"request": request, **context})
        
        if result == 0:
            context = build_result_page(data, success=True)
            
            custom_template = None
            if params_data and hasattr(params_data, "get_result_page_template"):
                custom_template = params_data.get_result_page_template()
            
            template_name = custom_template if custom_template else "result_page.html"
            return templates.TemplateResponse(template_name, {"request": request, **context})
        else:
            context = render_page(
                title="500 Internal Server Error",
                success=False,
                message="Internal server error",
                lines=[],
                echo=data,
            )
            return templates.TemplateResponse("result_page.html", {"request": request, **context}, status_code=500)
    
    except Exception as e:
        logger.exception(e)
        context = render_page(
            title="500 Internal Server Error",
            success=False,
            message=str(e),
            lines=[],
            echo=data,
        )
        return templates.TemplateResponse("result_page.html", {"request": request, **context}, status_code=500)


def service_main() -> int:
    import uvicorn
    
    logger.info("Running AMI server")
    host = os.environ.get("AMI_SERVER_HOST", "0.0.0.0")
    port = int(os.environ.get("AMI_SERVER_PORT", "8080"))
    
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(service_main())
