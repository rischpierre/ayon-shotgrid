from pathlib import Path
import sys
import traceback

import logging
from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse
from fastapi.exceptions import HTTPException
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, field_validator, model_validator
import os
from shotgun_api3 import Shotgun
import ayon_api


TEMPLATES_COMMON_DIR = Path(__file__).parent / "templates"

logging.basicConfig(
    level=os.environ.get("LOGLEVEL") or os.environ.get("PYTHON_LOG_LEVEL") or logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

class FormRequest(BaseModel):
    user_id: int
    user_login: str
    selected_ids: list[int] = Field(min_length=1)
    project_id: int | None = None
    entity_type: str

    @model_validator(mode="after")
    def validate_project_id(self):
        if self.entity_type == "Project" and self.selected_ids:
            self.project_id = self.selected_ids[0]

        return self


    @field_validator("selected_ids", mode="before")
    @classmethod
    def validate_selected_ids(cls, value):
        if isinstance(value, list) and len(value) >= 1 and isinstance(value[0], str):
            return [int(i) for i in value[0].split(",")]
        return value

def register_common_endpoints(
    app: FastAPI,
    templates: Jinja2Templates,
    logger: logging.Logger,
) -> None:

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        logger.exception("Unhandled error while processing request")
        context = {
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context=context,
            status_code=500,
        )

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}

    @app.get("/styles.css")
    def styles_css():
        path = Path(TEMPLATES_COMMON_DIR / "styles.css")
        if path.exists():
            return FileResponse(path)
        raise HTTPException(status_code=404, detail="Stylesheet not found")

class AmiBase:
    def __init__(self) -> None:
        self.sg_session = self.get_sg_session()

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
        script_key = ayon_api.get_secret("flow_ami_service_key")["value"]
    
        if not script_name or not script_key:
            raise Exception("Script name or key is not set")
    
        proxy_url = http_proxy.replace("http://", "") if http_proxy else None
        return Shotgun(sg_url, script_name=script_name, api_key=script_key, http_proxy=proxy_url)
        
