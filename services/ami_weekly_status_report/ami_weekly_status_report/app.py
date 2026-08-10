import os, sys
from pathlib import Path
import logging
import urllib.request
from typing import Any, Dict, Annotated
from typing import Literal

import corder

from ami.ami_weekly_status_report.path_templates import StringTemplate

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

AMI_WSR_PORT = int(os.environ.get("AMI_WSR_PORT", 45143))

app = FastAPI(title="AMI Weekly Status Report")


class SubmitRequest(FormRequest):
    vendor: str
    description: str


class AMIWeeklyStatusReport(AmiBase):

    def __init__(self) -> None:
        super().__init__()
        self.template = self._get_template()
        self.out_file = data.get("out_file")
        self.client_to_internal_status_map = {}


    def _translate_client_statuses(self, entities, status_field="sg_status_list"):
        if not self.client_to_internal_status_map:
            return entities

        internal_to_client_status_map = {code: status for status, codes in
                                         self.client_to_internal_status_map.items() for code in codes}
        for entity in entities:
            if status_field in entity:
                entity[status_field] = internal_to_client_status_map.get(entity[status_field],
                                                                         entity[status_field])

        return entities

    def _get_project_template_info(self):
        """Fetch the project's default WSR template from ShotGrid."""
        try:
            project = self.sg_session.find_one(
                "Project",
                [["id", "is", self.project_id]],
                ["sg_wsr_template"]
            )
            if project and project.get("sg_wsr_template"):
                template_data = project["sg_wsr_template"]
                return {
                    "exists": True,
                    "name": template_data.get("name", "Unknown"),
                    "url": template_data.get("url", "")
                }
        except Exception as e:
            print(f"Error fetching project template: {e}")
        return {"exists": False, "name": None, "url": None}

    def get_request_page_context(self):
        """Provide additional context for the request page."""
        return {
            "project_template": self._get_project_template_info()
        }

    def _get_template(self):
        # Priority 1: Check for uploaded template file
        template_file = self.data.get("template_file")
        if template_file and os.path.exists(template_file):
            path = template_file
        else:
            # Priority 2: Download template from ShotGrid if available
            template_info = self._get_project_template_info()
            if template_info.get("exists") and template_info.get("url"):
                try:
                    template_url = template_info["url"]
                    sg_template_path = "/tmp/sg_template.xlsx"
                    urllib.request.urlretrieve(template_url, sg_template_path)
                    path = sg_template_path
                    print(f"Downloaded template from ShotGrid: {template_info['name']}")
                except Exception as e:
                    print(f"Failed to download template from ShotGrid: {e}")
                    path = os.path.dirname(__file__) + "/template_examples/template.xlsx"
            else:
                # Priority 3: Fall back to default template
                path = os.path.dirname(__file__) + "/template_examples/template.xlsx"

        crd = corder.Corder(path)
        crd.parse_replacements()
        return crd

    def _get_fields(self, entity_type: Literal["asset", "shot"]):
        range = self.template.range(entity_type)
        return [x.lstrip("{").rstrip("}") for x in range.tags]

    def _get_shots(self, fields, additional_filters=None):
        filters = [["project.Project.id", "is", self.project_id], ["sg_shot_type", "is_not", "Test"]]
        if additional_filters:
            filters.append(additional_filters)
        return self.sg_session.find("Shot", filters=filters, fields=fields)

    def _get_assets(self, fields):
        filters = [
            ["project.Project.id", "is", self.project_id],
            ["tags", "in", {"type": "Tag", "id": 342, "name": "Report"}],
        ]
        return self.sg_session.find("Asset", filters=filters, fields=fields)

    def _fill_entities(self, entity_type: Literal["shot", "asset"], entities: list[Dict[str, Any]]):
        rows = []
        rng = self.template.range(entity_type)
        for entity in entities:

            row = {}
            for tag in rng.tags:
                rendered = StringTemplate(tag).format(entity)
                # If your StringTemplate returns an object with .missing_keys/.invalid_types, handle as needed
                value = "" if getattr(rendered, "missing_keys", []) or getattr(rendered, "invalid_types", []) else str(
                    rendered)

                row[tag] = value
            rows.append(row)

        rng.set_replacement_values(rows)

    def _export_file(self):
        self.template.fill()
        if self.out_file:
            out_file = self.out_file
        else:
            out_file = "/tmp/ami_weekly_status_report_report.xlsx"
        print(f"Export excel file {out_file}")
        self.template.write(out_file)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/styles.css")
def styles_css():
    path = Path(TEMPLATES_DIR / "styles.css")
    if path.exists():
        return FileResponse(path)
    raise HTTPException(status_code=404, detail="Stylesheet not found")


@app.post("/weekly-status-report/form")
async def form(
        request: Request,
        payload: Annotated[FormRequest, Form()],
):
    logger.info(f"Received payload: {payload}")
    ami = AMIWeeklyStatusReport()
    return ami.generate_from(request, payload)


@app.post("/weekly-status-report")
async def submit(
        request: Request,
        payload: Annotated[SubmitRequest, Form()],
):
    logger.info(f"Received payload: {payload}")
    ami = AMIWeeklyStatusReport()
    return ami.submit(request, payload)


def run():
    import uvicorn
    logger.info(f"Starting AMI Create Weekly Status Report service on port {AMI_WSR_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=AMI_WSR_PORT)
