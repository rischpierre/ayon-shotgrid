from pprint import pformat

import logging
import os
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader

import rvx_beryl

from ami_common import (
    AmiBase,
    FormRequest,
    register_common_endpoints,
    TEMPLATES_COMMON_DIR,
)

AYON_BUNDLE_OPTIONS = {
    "Prod": "",
    "Staging": "--use-staging",
    "Dev": "--use-dev",
}


logger = logging.getLogger(__name__)

SERVICE_BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = SERVICE_BASE_DIR / "templates"
DEPARTMENT = "delivery"

loader = ChoiceLoader(
    [
        FileSystemLoader(SERVICE_BASE_DIR),
        FileSystemLoader(TEMPLATES_DIR),
        FileSystemLoader(TEMPLATES_COMMON_DIR),
    ]
)
templates = Jinja2Templates(directory=TEMPLATES_DIR)
templates.env.loader = loader

app = FastAPI(title="AMI Create Delivery Playlist Service")
register_common_endpoints(app, templates, logger)

AMI_CLIENT_DELIVERY_PORT = int(os.environ.get("AMI_CLIENT_DELIVERY_PORT", 45140))


class AMIClientDelivery(AmiBase):

    def __init__(self) -> None:
        super().__init__()

    def generate_form(self, request: Request, payload: FormRequest):
        projec_id = payload.project_id
        sg_project = self.sg_session.find_one(
            "Project", [["id", "is", projec_id]], ["code"]
        )
        playlist = self.sg_session.find_one(
            "Playlist", [["id", "is", payload.selected_ids[0]]], ["versions"]
        )
        versions_ids = [x["id"] for x in playlist.get("versions", [])]

        per_version_fields = {
                "version_name": {
                    "label": "Version Name",
                    "type": "text",
                    "sg_field_name": "code",
                    "locked": True,
                },
                "client_name": {
                    "label": "Client Name",
                    "type": "text",
                    "sg_field_name": "client_code",
                    "locked": True,
                    "default": "",
                },
            }
        per_version_fields.update(_get_delivery_fields(self.sg_session, sg_project))

        search_fields = [x.get("sg_field_name") for x in per_version_fields.values() if x.get("sg_field_name")]
        versions = self.sg_session.find(
            "Version", [["id", "in", versions_ids]], search_fields
        )

        context = payload.model_dump()
        per_delivery_fields = {
            "client_notes": {
                "label": "Client Notes",
                "type": "text",
            },
            "ayon_bundle": {
                "label": "Ayon Bundle",
                "type": "list",
                "options": list(AYON_BUNDLE_OPTIONS.keys()),
                "default": "Prod",
            }
        }

        context.update(
            {
                "versions": versions,
                "per_version_fields": per_version_fields,
                "per_delivery_fields": per_delivery_fields,
            }
        )
        return templates.TemplateResponse(
            request=request, name="form.html", context=context
        )

    def save_fields(self, request: Request, payload: dict):
        versions = payload["versions"]
        versions_id = list(versions.keys())
        sg_versions = self.sg_session.find("Version", [["id", "in", versions_id]])
        batch_update = []
        for version in sg_versions:
            version_fields = versions[version["id"]]
            batch_update.append(
                {
                    "request_type": "update",
                    "entity_type": "Version",
                    "entity_id": version["id"],
                    "data": version_fields,
                }
            )
        logger.info(f"Batch update: {pformat(batch_update)}")
        updated_fields = self.sg_session.batch(batch_update)
        context = {
            "message": f"Data: {pformat(updated_fields)}",
            "header": "Successfully Updated Versions",
        }
        return templates.TemplateResponse(
            request=request, name="result.html", context=context
        )

    def submit(self, request: Request, payload: dict):
        common_fields = payload["common_fields"]
        project_id = int(common_fields["project_id"])
        ayon_bundle = common_fields["ayon_bundle"]
        project = self.sg_session.find_one(
            "Project", [["id", "is", project_id]], ["name"]
        )
        playlist_id = common_fields["selected_ids"]

        command = f"/pipeline/AstralProjection/apps/ayon/run.sh"
        command += " " + AYON_BUNDLE_OPTIONS[ayon_bundle] + " "
        command += f"addon rvx delivery --playlist-id {playlist_id} --project-name {project['name']} --client-notes '{common_fields['client_notes']}'"

        job_name = f"CLient Delivery: {project['name']} [{playlist_id}]"

        user = self.get_user(common_fields["user_id"])
        logger.info(f"User: {user}")
        logger.info(f"Command: {command}")
        logger.info(f"Job name: {job_name}")
        layer = rvx_beryl.farm.CommandLineLayer(
            job_name,
            user,
            command,
            shell_execute=True,
            department=DEPARTMENT,
        )

        rvx_beryl.farm.Job(job_name, [layer]).submit()

        context = {}
        context["message"] = f"Successfully Submitted Job on the farm: {job_name}"

        return templates.TemplateResponse(
            request=request, name="result.html", context=context
        )


@app.get("/client-delivery/validate.js")
async def validate_js():
    return FileResponse(TEMPLATES_DIR / "validate.js")


@app.post("/client-delivery/form")
async def form(
    request: Request,
    payload: Annotated[FormRequest, Form()],
):
    logger.info(f"Received payload: {payload}")
    ami = AMIClientDelivery()
    return ami.generate_form(request, payload)


def _get_delivery_fields(sg_session, sg_project):

    prefix = f"sg_delivery_{sg_project['code']}_"
    result_schema = {}
    schema = sg_session.schema_field_read(
        entity_type="Version", project_entity=sg_project
    )
    for name, field_data in schema.items():
        if name.startswith(prefix):
            properties = field_data.get("properties", {})
            result_schema[name] = {
                "sg_field_name": name,
                "label": name.replace(prefix, "").replace("_", " ").title(),
                "options": properties.get("valid_values", {}).get("value", []),
                "type": field_data["data_type"]["value"],
                "default": properties.get("default_value", {}).get("value"),
            }
    return result_schema


def _parse_form_data(form_data):
    versions = {}
    common_fields = {}
    for field_name, value in form_data.items():
        value = {"true": True, "false": False}.get(value, value)

        # 'version__7161__deliver_exr', 'true')
        if field_name.startswith("version__"):
            split = field_name.split("__")
            version_id = int(split[1])
            field = split[2]
            versions.setdefault(version_id, {})[field] = value
        else:
            common_fields[field_name] = value

    return versions, common_fields


@app.post("/client-delivery/fields/save")
async def save_fields(request: Request):
    form_data = await request.form()
    versions, common_fields = _parse_form_data(form_data)
    logger.info(f"Received versions: {pformat(versions)}")
    logger.info(f"Received versions: {pformat(common_fields)}")
    payload = {
        "versions": versions,
        "common_fields": common_fields,
    }

    ami = AMIClientDelivery()
    return ami.save_fields(request, payload)


@app.post("/client-delivery/submit")
async def submit(request: Request):
    form_data = await request.form()
    versions, common_fields = _parse_form_data(form_data)
    logger.info(f"Received versions: {pformat(versions)}")
    logger.info(f"Received versions: {pformat(common_fields)}")
    payload = {
        "versions": versions,
        "common_fields": common_fields,
    }

    ami = AMIClientDelivery()
    ami.save_fields(request, payload)
    return ami.submit(request, payload)


def run():
    import uvicorn

    logger.info(
        f"Starting AMI Create Delivery Playlist service on port {AMI_CLIENT_DELIVERY_PORT}"
    )
    uvicorn.run(app, host="0.0.0.0", port=AMI_CLIENT_DELIVERY_PORT)
