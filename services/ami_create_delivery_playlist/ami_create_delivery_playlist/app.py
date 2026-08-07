import logging
import os
import sys
from pydantic import BaseModel, Field
from fastapi import FastAPI, Form, Request
from typing import Annotated
from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader

from datetime import datetime
from typing import List


logging.basicConfig(
    level=os.environ.get("LOGLEVEL") or os.environ.get("PYTHON_LOG_LEVEL") or logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
SERVICE_BASE_DIR = os.path.dirname(__file__)

loader = ChoiceLoader([
    FileSystemLoader(SERVICE_BASE_DIR),
    FileSystemLoader(TEMPLATES_DIR)
])
templates = Jinja2Templates(directory=TEMPLATES_DIR)
templates.env.loader = loader

app = FastAPI(title="AMI Create Delivery Playlist Service")

AMI_CREATE_DELIVERY_PLAYLIST_PORT = int(os.environ.get("AMI_CREATE_DELIVERY_PLAYLIST_PORT", 45141))

class PlaylistFormRequest(BaseModel):
    project_id: int
    selected_ids: list[int] = Field(min_length =1)

class PlaylistSubmitRequest(BaseModel):
    project_id: int
    selected_ids: list[int] = Field(min_length =1)
    name: str

class AMICreateDeliveryPlaylist():

    def __init__(self) -> None:
        if False:
            self.sg = self.get_sg_session()
            
    def get_sg_session(self):
        ayon_api_key = os.environ.get("AYON_API_KEY")
        ayon_server_url = os.environ.get("AYON_SERVER_URL")
        sg_url = os.environ.get("SG_URL")
        http_proxy = os.environ.get("HTTP_PROXY", "")
    
        if not ayon_api_key or not ayon_server_url:
            raise Exception("AYON_API_KEY and AYON_SERVER_URL are required")
    
        if not sg_url:
            raise Exception("SG_URL env var is required")
    
        ayon_api.init_service(token=ayon_api_key, server_url=ayon_server_url)
        script_name = ayon_api.get_secret("flow_ami_service_name")["value"]
        script_key = ayon_api.get_secreet("flow_ami_service_key")["value"]
    
        if not script_name or not script_key:
            raise Exception("Script name or key is not set")
    
        proxy_url = http_proxy.replace("http://", "") if http_proxy else None
        return Shotgun(sg_url, script_name=script_name, api_key=script_key, http_proxy=proxy_url)
        
    def _generate_playlist_name(self):
        today_str = datetime.now().strftime("%Y-%m-%d")
        base_name = f"delivery_{today_str}"
        version = self._get_next_available_version(base_name)
        name = f"{base_name}_{version:02d}"
        return name


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

    def get_form(self, request: Request, payload: PlaylistFormRequest):
        context = {
            "project_id": payload.project_id,
            "selected_ids": payload.selected_ids,
        }
        return templates.TemplateResponse(request=request, name ="form.html", context={"request": request, **context})
        
    def submit(self, request: PlaylistSubmitRequest) -> int:
        selected_ids = request.selected_ids
        
        if not selected_ids:
            raise Exception("Found no selected versions")

        versions = self.sg_session.find(
            "Version",
            [["id", "in", self.selected_ids]],
            ["code", "sg_path_to_movie"]
        )

        data = {
            "project": {"id": request.project_id, "type": "Project"},
            "code": request.name,
            "versions": versions,
            "sg_type": "Delivery",
        }
        result = self.sg_session.create("Playlist", data)
        if result:
            return 0
        else:
            return -1

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/get_playlist_name_select_form")
async def form(
    request: Request,
    project_id: Annotated[int, Form()],
    selected_ids: Annotated[str, Form()],
):
    ids = [int(x) for x in selected_ids.split(",") if x]
    payload = PlaylistFormRequest(project_id=project_id, selected_ids=ids)
    ami = AMICreateDeliveryPlaylist()
    return ami.get_form(request, payload)

@app.post("/submit_playlist_creation")
async def form(request: PlaylistSubmitRequest):
    ami =  AMICreateDeliveryPlaylist()
    ami.submit(request)
    return templates.TemplateResponse(request=request, name ="form.html", context={"request": request, **context})

def run():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=AMI_CREATE_DELIVERY_PLAYLIST_PORT)