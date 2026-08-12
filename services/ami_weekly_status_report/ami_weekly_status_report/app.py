import importlib
import os, sys
import shutil
from functools import cache
from pathlib import Path
import logging
import urllib.request
from typing import Any, Dict, Annotated
from typing import Literal

import corder

from fastapi import FastAPI, Form, Request, UploadFile
from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader
from fastapi.responses import JSONResponse
from ami_common import (
    AmiBase,
    FormRequest,
    register_common_endpoints,
    TEMPLATES_COMMON_DIR,
)

from ami_weekly_status_report.path_templates import StringTemplate

OUT_FILE_REPORT = Path("/tmp/ami_weekly_status_report_report.xlsx")

logging.basicConfig(
    level=os.environ.get("LOGLEVEL")
    or os.environ.get("PYTHON_LOG_LEVEL")
    or logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)

SERVICE_BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = SERVICE_BASE_DIR / "templates"
SHEET_TEMPLATE_DIR = SERVICE_BASE_DIR / "sheet_templates"

loader = ChoiceLoader(
    [
        FileSystemLoader(SERVICE_BASE_DIR),
        FileSystemLoader(TEMPLATES_DIR),
        FileSystemLoader(TEMPLATES_COMMON_DIR),
    ]
)
templates = Jinja2Templates(directory=TEMPLATES_DIR)
templates.env.loader = loader

AMI_WSR_PORT = int(os.environ.get("AMI_WSR_PORT", 45143))
app = FastAPI(title="AMI Weekly Status Report")
register_common_endpoints(app, templates, logger)


class SubmitRequest(FormRequest):
    template_file: UploadFile | None = None


class AMIWeeklyStatusReport(AmiBase):

    def __init__(self) -> None:
        super().__init__()
        self.crd_template = None
        self.out_file = None
        self.project_id = None
        self.client_to_internal_status_map = {}

    def translate_client_statuses(self, entities, status_field="sg_status_list"):
        if not self.client_to_internal_status_map:
            return entities

        internal_to_client_status_map = {
            code: status
            for status, codes in self.client_to_internal_status_map.items()
            for code in codes
        }
        for entity in entities:
            if status_field in entity:
                entity[status_field] = internal_to_client_status_map.get(
                    entity[status_field], entity[status_field]
                )

        return entities

    def _get_project_template_info(self, payload: FormRequest):
        """Fetch the project's default WSR template from ShotGrid."""
        project = self.sg_session.find_one(
            "Project", [["id", "is", payload.project_id]], ["sg_wsr_template"]
        )
        if project and project.get("sg_wsr_template"):
            template_data = project["sg_wsr_template"]
            return {
                "exists": True,
                "name": template_data.get("name", "Unknown"),
                "url": template_data.get("url", ""),
            }

    def _get_template(self, payload: FormRequest) -> Path:
        template_info = self._get_project_template_info(payload)
        if template_info and template_info.get("exists") and template_info.get("url"):
            try:
                template_url = template_info["url"]
                path = Path("/tmp") / Path(template_info["name"])
                urllib.request.urlretrieve(template_url, path)
                logger.info(
                    f"Downloaded template from ShotGrid: {template_info['name']}"
                )
            except Exception as e:
                logger.error(f"Failed to download template from ShotGrid: {e}")
                path = SHEET_TEMPLATE_DIR / "default" / "template.xlsx"
        else:
            path = SHEET_TEMPLATE_DIR / "default" / "template.xlsx"

        return path

    def _load_template(self, payload: SubmitRequest):
        if payload.template_file and payload.template_file.filename:
            logger.info("Loading template from upload")
            path = "/tmp/sg_template.xlsx"
            with open(path, "w") as fp:
                shutil.copyfileobj(payload.template_file.file, fp)
        else:
            path = self._get_template(payload)

        logger.info(f"Loaded template: {path}")
        crd = corder.Corder(str(path))
        crd.parse_replacements()
        return crd

    def get_fields(self, entity_type: Literal["asset", "shot"]):
        range = self.crd_template.range(entity_type)
        return [x.lstrip("{").rstrip("}") for x in range.tags]

    def get_shots(self, fields, additional_filters=None):
        filters = [
            ["project.Project.id", "is", self.project_id],
            ["sg_shot_type", "is_not", "Test"],
        ]
        if additional_filters:
            filters.append(additional_filters)
        return self.sg_session.find("Shot", filters=filters, fields=fields)

    def get_assets(self, fields):
        filters = [
            ["project.Project.id", "is", self.project_id],
            ["tags", "in", {"type": "Tag", "id": 342, "name": "Report"}],
        ]
        return self.sg_session.find("Asset", filters=filters, fields=fields)

    def fill_entities(
        self, entity_type: Literal["shot", "asset"], entities: list[Dict[str, Any]]
    ):
        rows = []
        rng = self.crd_template.range(entity_type)
        for entity in entities:

            row = {}
            for tag in rng.tags:
                rendered = StringTemplate(tag).format(entity)
                # If your StringTemplate returns an object with .missing_keys/.invalid_types, handle as needed
                value = (
                    ""
                    if getattr(rendered, "missing_keys", [])
                    or getattr(rendered, "invalid_types", [])
                    else str(rendered)
                )

                row[tag] = value
            rows.append(row)

        rng.set_replacement_values(rows)

    def export_file(self):
        self.crd_template.fill()
        if self.out_file:
            out_file = self.out_file
        else:
            out_file = OUT_FILE_REPORT
        logger.info(f"Export excel file {out_file}")
        self.crd_template.write(out_file)

    def generate_form(self, request: Request, payload: FormRequest):
        template = self._get_template(payload)
        logger.info(f"Using template {template}")

        context = payload.model_dump()
        context["project_template"] = template

        return templates.TemplateResponse(
            request=request, name="form.html", context=context
        )

    def submit(self, request: Request, payload: SubmitRequest):
        context = payload.model_dump()

        context["message"] = f"Successfully generated Weekly Status Report"

        return templates.TemplateResponse(
            request=request, name="result_wsr.html", context=context
        )


@cache
def _projects(sg_session):
    return sg_session.find("Project", [["sg_status", "is", "Active"]], ["id", "name"])


def _get_project_ami(payload):
    ami_common = AMIWeeklyStatusReport()
    sg_session = ami_common.sg_session

    project_id = payload.project_id
    project_name = next(
        p["name"] for p in _projects(sg_session) if p["id"] == project_id
    )
    logger.info(f"Project name: {project_name}")
    found_module = SHEET_TEMPLATE_DIR.rglob(project_name + "/app.py")
    logger.info(f"Found module: {found_module}")
    if found_module:
        module = importlib.import_module(
            f"ami_weekly_status_report.sheet_templates.{project_name}.app"
        )
        cls = getattr(module, f"AMIWeeklyStatusReport{project_name}")

        ami = cls()
        ami.project_id = project_id
        return ami
    else:
        ami_common.project_id = project_id
        return ami_common


@app.get("/weekly-status-report/download/report")
async def download_report():
    if not OUT_FILE_REPORT.exists():
        return JSONResponse(content={"error": "Report file not found"}, status_code=404)

    with open(OUT_FILE_REPORT, "rb") as f:
        content = f.read()

    from fastapi.responses import Response

    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=weekly_status_report.xlsx"
        },
    )


@app.post("/weekly-status-report/form")
async def form(
    request: Request,
    payload: Annotated[FormRequest, Form()],
):
    logger.info(f"/weekly-status-report/form received payload: {payload}")
    ami = _get_project_ami(payload)
    return ami.generate_form(request, payload)


@app.post("/weekly-status-report")
async def submit(
    request: Request,
    payload: Annotated[SubmitRequest, Form()],
):
    logger.info(f"/weekly-status-report received payload: {payload}")

    ami = _get_project_ami(payload)
    return ami.submit(request, payload)


def run():
    import uvicorn

    logger.info(
        f"Starting AMI Create Weekly Status Report service on port {AMI_WSR_PORT}"
    )
    uvicorn.run(app, host="0.0.0.0", port=AMI_WSR_PORT)
