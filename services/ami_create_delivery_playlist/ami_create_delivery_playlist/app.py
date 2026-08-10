import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from pprint import pformat
from typing import Annotated

from fastapi import FastAPI, Form, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse
from fastapi.exceptions import HTTPException
from jinja2 import ChoiceLoader, FileSystemLoader

from ami_common import AmiBase, FormRequest

logging.basicConfig(
    level=os.environ.get("LOGLEVEL") or os.environ.get("PYTHON_LOG_LEVEL") or logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)

SERVICE_BASE_DIR = Path(__file__).parent
AMI_COMMON_DIR = SERVICE_BASE_DIR.parent / "ami_common"

TEMPLATES_DIR = SERVICE_BASE_DIR / "templates"
TEMPLATES_COMMON_DIR = AMI_COMMON_DIR / "templates"

loader = ChoiceLoader([
    FileSystemLoader(SERVICE_BASE_DIR),
    FileSystemLoader(TEMPLATES_DIR),
    FileSystemLoader(TEMPLATES_COMMON_DIR)
])
templates = Jinja2Templates(directory=TEMPLATES_DIR)
templates.env.loader = loader

app = FastAPI(title="AMI Create Delivery Playlist Service")

AMI_CREATE_DELIVERY_PLAYLIST_PORT = int(os.environ.get("AMI_CREATE_DELIVERY_PLAYLIST_PORT", 45141))



class SubmitRequest(FormRequest):
    name: str


class AMICreateDeliveryPlaylist(AmiBase):

    def __init__(self) -> None:
        super().__init__()

    def _generate_playlist_name(self, project_id: int):
        today_str = datetime.now().strftime("%Y-%m-%d")
        base_name = f"delivery_{today_str}"
        version = self._get_next_available_version(base_name, project_id)
        name = f"{base_name}_{version:02d}"
        return name

    def _get_next_available_version(self, base_name: str, project_id: int) -> int:
        """Find the next numeric suffix for a playlist code containing base_name."""
        playlists = self.sg_session.find(
            "Playlist",
            [["project.Project.id", "is", project_id], ["code", "contains", f"{base_name}"]],
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

    def generate_from(self, request: Request, payload: FormRequest):

        context = payload.model_dump()
        context["playlist_name"] = self._generate_playlist_name(payload.project_id)
        return templates.TemplateResponse(request=request, name="form.html", context=payload.model_dump())

    def submit(self, request: Request, payload: SubmitRequest):

        if not payload.selected_ids:
            raise Exception("Found no selected versions")

        versions = self.sg_session.find(
            "Version",
            [["id", "in", payload.selected_ids]],
            ["code", "sg_path_to_movie"]
        )

        data = {
            "project": {"id": payload.project_id, "type": "Project"},
            "code": payload.name,
            "versions": versions,
            "sg_type": "Delivery",
        }
        result = self.sg_session.create("Playlist", data)
        if result:
            context = payload.model_dump()
            context["message"] = f"Playlist id: {result['id']}"
            return templates.TemplateResponse(request=request, name="result.html", context=context)

        raise RuntimeError(f"Failed to create playlist with data: {pformat(data)}")


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception):
    logger.exception("Unhandled error while processing request")
    context = {
        "message": str(exc),
        "traceback": traceback.format_exc(),
    }
    return templates.TemplateResponse(request=request, name="error.html", context=context, status_code=500)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/styles.css")
def styles_css():
    path = Path(TEMPLATES_COMMON_DIR / "styles.css")
    if path.exists():
        return FileResponse(path)
    raise HTTPException(status_code=404, detail="Stylesheet not found")


@app.get("/validate-playlist-name.js")
def validate_playlist_name_js():
    path = Path(TEMPLATES_DIR / "validate-playlist-name.js")
    if path.exists():
        return FileResponse(path)
    raise HTTPException(status_code=404, detail="Script not found")


@app.post("/delivery-playlists/form")
async def form(
        request: Request,
        payload: Annotated[FormRequest, Form()],
):
    logger.info(f"Received payload: {payload}")
    ami = AMICreateDeliveryPlaylist()
    return ami.generate_from(request, payload)


@app.post("/delivery-playlists")
async def submit(
        request: Request,
        payload: Annotated[SubmitRequest, Form()],
):
    logger.info(f"Received payload: {payload}")
    ami = AMICreateDeliveryPlaylist()
    return ami.submit(request, payload)


def run():
    import uvicorn
    logger.info(f"Starting AMI Create Delivery Playlist service on port {AMI_CREATE_DELIVERY_PLAYLIST_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=AMI_CREATE_DELIVERY_PLAYLIST_PORT)
