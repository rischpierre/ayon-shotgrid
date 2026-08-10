import logging
import os
import sys

from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, Request
from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader

from ami_common import AmiBase, FormRequest, register_common_endpoints, TEMPLATES_COMMON_DIR

logging.basicConfig(
    level=os.environ.get("LOGLEVEL") or os.environ.get("PYTHON_LOG_LEVEL") or logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)

SERVICE_BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = SERVICE_BASE_DIR / "templates"

loader = ChoiceLoader([
    FileSystemLoader(SERVICE_BASE_DIR),
    FileSystemLoader(TEMPLATES_DIR),
    FileSystemLoader(TEMPLATES_COMMON_DIR)
])
templates = Jinja2Templates(directory=TEMPLATES_DIR)
templates.env.loader = loader

app = FastAPI(title="AMI Outsource Playlist Service")
register_common_endpoints(app, templates, logger)

AMI_OUTSOURCE_PLAYLIST_PORT = int(os.environ.get("AMI_OUTSOURCE_PLAYLIST_PORT", 45142))


OUTSOURCE_SG_TYPE = "Outsource"
DEPARTMENT = "outsource"
HOWLER_SCRIPT = "/pipeline/AstralProjection/scripts/rvx-howler"


class SubmitRequest(FormRequest):
    vendor: str
    description: str



class AMIOutsourcePlaylist(AmiBase):
    """Submit an outsource collection job to the farm from a selected Playlist.

    The job runs `rvx-howler collect outsource`
    on the farm via rvx_beryl. Validates that only outsource playlists are used,
    pre-populates vendor/description from the playlist, and writes back any vendor
    change the user makes.
    """

    def __init__(self):
        super().__init__()

    def _get_context(self, payload: FormRequest):
        playlist_id = payload.selected_ids[0]
        playlist = self.sg_session.find_one(
            "Playlist",
            [["id", "is", playlist_id]],
            ["code", "sg_type", "sg_vendor", "description", "sg_ayon_id"]
        )

        if not playlist:
            raise Exception(f"Playlist {playlist_id} not found")

        if playlist.get("sg_type") != OUTSOURCE_SG_TYPE:
            sg_type = playlist.get("sg_type")
            raise Exception(
                f"Playlist '{playlist['code']}' is of type '{sg_type}', "
                f"expected '{OUTSOURCE_SG_TYPE}'"
            )

        original_vendor = playlist.get("sg_vendor") or ""
        if original_vendor:
            original_vendor = self.sg_session.find_one("Group", [['id', "is", original_vendor["id"]]], ["code"])

        original_vendor_name = original_vendor.get("code") if original_vendor else ""
        original_description = playlist.get("description") or ""

        return {
            "project_id": payload.project_id,
            "selected_ids": payload.selected_ids,
            "vendor_name": original_vendor_name,
            "description": original_description,
            "playlist": playlist,
            "playlist_id": playlist_id,
        }

    def generate_from(self, request: Request, payload: FormRequest):
        context = self._get_context(payload)
        return templates.TemplateResponse(request, "form.html", context)


    def submit(self, request:  Request, payload: SubmitRequest) -> int:
        context = self._get_context(payload)
        playlist = context["playlist"]
        playlist_id = context["playlist_id"]
        project_id = context["project_id"]
        original_description = context["description"]
        original_vendor_name = context["vendor_name"]

        # Resolve project name (== AYON project name)
        project = self.sg_session.find_one(
            "Project", [["id", "is", project_id]], ["name"]
        )
        project_name = project["name"]

        ayon_playlist_id = playlist.get("sg_ayon_id")
        if not ayon_playlist_id:
            raise Exception("Playlist has no sg_ayon_id – not synced to AYON yet")

        new_vendor_name = payload.vendor_name
        new_description = payload.description

        update_data = {}
        if new_vendor_name != original_vendor_name:
            # Validate vendor exists
            new_vendor = self._get_vendor_from_name(new_vendor_name)
            if not new_vendor:
                raise Exception(f"Vendor '{new_vendor_name}' is not a valid vendor")
            update_data["sg_vendor"] = new_vendor

        if new_description != original_description:
            update_data["description"] = new_description

        if update_data:
            self.sg_session.update("Playlist", playlist_id, update_data)


        command = (
            f"{HOWLER_SCRIPT} collect outsource "
            f"--project {project_name} --playlist-id {ayon_playlist_id} "
            f"--vendor '{new_vendor_name}' --description '{new_description}'"
        )

        job_name = f"Howler: collect {new_description} [{new_vendor_name}]"

        layer = rvx_beryl.farm.CommandLineLayer(
            job_name,
            self._get_user(),
            command,
            shell_execute=True,
            department=DEPARTMENT,
        )

        rvx_beryl.farm.Job(job_name, [layer]).submit()
        return 0

    def _get_user(self) -> str:
        user_id = self.data.get("user_id")
        if user_id:
            sg_user = self.sg_session.find_one(
                "HumanUser", [["id", "is", int(user_id)]], ["login"]
            )
            if sg_user:
                return sg_user["login"].split("@")[0]
        return "unknown"

    def _get_vendor_from_name(self, name: str):
        return self.sg_session.find_one("Group", [["code", "is", name]], ["code"])

@app.post("/outsource-playlist/form")
async def form(
        request: Request,
        payload: Annotated[FormRequest, Form()],
):
    logger.info(f"Received payload: {payload}")
    ami = AMIOutsourcePlaylist()
    return ami.generate_from(request, payload)


@app.post("/outsource-playlists")
async def submit(
        request: Request,
        payload: Annotated[SubmitRequest, Form()],
):
    logger.info(f"Received payload: {payload}")
    ami = AMIOutsourcePlaylist()
    return ami.submit(request, payload)


def run():
    import uvicorn
    logger.info(f"Starting AMI Create Outsource Playlist service on port {AMI_OUTSOURCE_PLAYLIST_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=AMI_OUTSOURCE_PLAYLIST_PORT)