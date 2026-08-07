import json
import logging
import os
import sys
from typing import Any, Dict
from pprint import pformat

from fastapi import FastAPI, Request, APIRouter
from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader

from datetime import datetime
from typing import Any, Dict, List

from ami_common import AmiBase, StringParameter

logging.basicConfig(
    level=os.environ.get("LOGLEVEL") or os.environ.get("PYTHON_LOG_LEVEL") or logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
SERVICE_BASE_DIR = os.path.dirname(__file__)

required_templates = ["request_page.html", "result_page.html"]

loader = ChoiceLoader([
    FileSystemLoader(SERVICE_BASE_DIR),
    FileSystemLoader(TEMPLATES_DIR)
])
templates = Jinja2Templates(directory=TEMPLATES_DIR)
templates.env.loader = loader

app = FastAPI(title="AMI Create Delivery Playlist Service")

AMI_CREATE_DELIVERY_PLAYLIST_PORT = int(os.environ.get("AMI_CREATE_DELIVERY_PLAYLIST_PORT", 45141))


class AMICreateDeliveryPlaylist(AmiBase):
    """Create a delivery playlist for selected versions.

    The default playlist name is generated as 'delivery_YYYY-MM-DD_##' where
    the numeric suffix increments to the next available version for the day.
    """

    def __init__(self) -> None:
        super().__init__()
        
        self.router =  APIRouter()
        self.router.add_api_route("/", self.handle_request, methods=["POST"])

    def generate_parameters(self):
        today_str = datetime.now().strftime("%Y-%m-%d")
        base_name = f"delivery_{today_str}"
        version = self._get_next_available_version(base_name)
        name = f"{base_name}_{version:02d}"

        self.playlist_param = StringParameter("Playlist Name", default=name)

    def _get_next_available_version(self, base_name: str) -> int:
        """Find the next numeric suffix for a playlist code containing base_name."""
        playlists = self.sg_session.find(
            "Playlist",
            [["project.Project.id", "is", self.project_id], ["code", "contains", f"{base_name}"]],
            ["code"]
        )
        max_ = 0
        for p in playlists:
            digits = p["code"].split("_")[-1]
            try:
                value = int(digits)
                if value > max_:
                    max_ = value
            except ValueError:
                continue
        return max_ + 1

    def parameters(self) -> List[StringParameter]:
        """Expose the configurable parameters for this action."""
        return [self.playlist_param]

    def get_request_page_template(self):
        """Return custom parameters template."""
        return "request_page.html"

    def main(self) -> int:
        """Create a playlist containing the selected versions."""
        if not self.selected_ids:
            raise Exception("Found no selected versions")

        versions = self.sg_session.find(
            "Version",
            [["id", "in", self.selected_ids]],
            ["code", "sg_path_to_movie"]
        )

        data = {
            "project": {"id": self.project_id, "type": "Project"},
            "code": self.playlist_param.value(),
            "versions": versions,
            "sg_type": "Delivery",
        }
        result = self.sg_session.create("Playlist", data)
        if result:
            return 0
        else:
            return -1

    async def handle_request(self, request: Request):
        try:
            data = await request.form()
            self.parse_request_data(data)
            self.generate_parameters()
            
            logger.info(f"Received request: {pformat(data)}")
    
    
            if not data.get("__form_submitted"):
                parameters = self.parameters()
                context = build_parameters_form(parameters, data)
                return templates.TemplateResponse(request=request, name ="request_page.html", context={"request": request, **context})
    
            result = self.main()
    
            if result == 0:
                context = build_result_page(data, success=True)
                return templates.TemplateResponse(request=request, name ="result_page.html", context={"request": request, **context})
            else:
                context = build_result_page(data, success=False)
                return templates.TemplateResponse(request=request, name ="result_page.html", context={"request": request, **context})
    
        except Exception as e:
            logger.exception(e)
            context = render_page(
                title="500 Internal Server Error",
                success=False,
                message=str(e),
                lines=[],
                echo={"error": str(e), "type": type(e).__name__},
            )
            return templates.TemplateResponse(request=request, name ="result_page.html", context={"request": request, **context}, status_code=500)




def render_page(title: str, success: bool, message: str, lines: list[str], echo: Dict[str, Any]) -> Dict[str, Any]:
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
    lines = [
        f"Action: ami_create_delivery_playlist",
        f"User: {data.get('user_id', 'unknown')}",
        f"Entity ids: {data.get('selected_ids', '')}",
        f"Project: {data.get('project_name', '')}",
    ]
    title = "Playlist Created" if success else "Creation Failed"
    message = "Delivery playlist created successfully." if success else "There was a problem creating the playlist."

    return render_page(title=title, success=success, message=message, lines=lines, echo=data)


def build_parameters_form(parameters: list, original: Dict[str, Any]) -> Dict[str, Any]:
    def esc(s: str) -> str:
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    inputs_html = []
    for p in parameters:
        label = esc(str(p.name))
        try:
            current_val = p.value()
        except Exception:
            current_val = getattr(p, "default", "")

        inputs_html.append(
            f'<label><span>{label}</span>'
            f'<input type="text" name="{esc(str(p.name))}" value="{esc(str(current_val))}" /></label>'
        )

    hidden_inputs = []
    for k, v in original.items():
        if k in ("__form_submitted", "action", "__action_type"):
            continue
        if v is None:
            continue
        v_str = str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
        k_str = str(k).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
        hidden_inputs.append(f'<input type="hidden" name="{k_str}" value="{v_str}">')

    hidden_inputs.append('<input type="hidden" name="__form_submitted" value="1">')

    return {
        "title": "Create Delivery Playlist",
        "heading": "Create Delivery Playlist",
        "action_url": "/",
        "submit_label": "Create Playlist",
        "inputs_html": "".join(inputs_html),
        "hidden_inputs": "".join(hidden_inputs),
    }


@app.get("/health")
async def health_check():
    return {"status": "ok"}


def run():
    import uvicorn
    instance =  AMICreateDeliveryPlaylist()
    app.include_router(instance.router)
    uvicorn.run(app, host="0.0.0.0", port=AMI_CREATE_DELIVERY_PLAYLIST_PORT)
