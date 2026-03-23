import os
import urllib.request
from typing import Any, Dict
from typing import Literal

import corder

from ami import ami_base
from ami.ami_weekly_status_report.path_templates import StringTemplate


class AMIWeeklyStatusReport(ami_base.AmiBase):

    def __init__(self, sg_session: Any, data: Dict[str, Any]) -> None:
        super().__init__(sg_session, data)
        self.template = self.get_template()
        self.out_file = data.get("out_file")
        self.client_to_internal_status_map = {}

    def parameters(self):
        return []

    def get_request_page_template(self):
        return "ami_weekly_status_report/html_pages/request_page.html"

    def get_result_page_template(self):
        return "ami_weekly_status_report/html_pages/result_page.html"

    def translate_client_statuses(self, entities, status_field="sg_status_list"):
        if not self.client_to_internal_status_map:
            return entities

        internal_to_client_status_map = {code: status for status, codes in
                                         self.client_to_internal_status_map.items() for code in codes}
        for entity in entities:
            if status_field in entity:
                entity[status_field] = internal_to_client_status_map.get(entity[status_field],
                                                                         entity[status_field])

        return entities

    def get_project_template_info(self):
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
            "project_template": self.get_project_template_info()
        }

    def get_template(self):
        # Priority 1: Check for uploaded template file
        template_file = self.data.get("template_file")
        if template_file and os.path.exists(template_file):
            path = template_file
        else:
            # Priority 2: Download template from ShotGrid if available
            template_info = self.get_project_template_info()
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

    def get_fields(self, entity_type: Literal["asset", "shot"]):
        range = self.template.range(entity_type)
        return [x.lstrip("{").rstrip("}") for x in range.tags]

    def get_shots(self, fields, additional_filters=None):
        filters = [["project.Project.id", "is", self.project_id], ["sg_shot_type", "is_not", "Test"]]
        if additional_filters:
            filters.append(additional_filters)
        return self.sg_session.find("Shot", filters=filters, fields=fields)

    def get_assets(self, fields):
        filters = [
            ["project.Project.id", "is", self.project_id],
            ["tags", "in", {"type": "Tag", "id": 342, "name": "Report"}],
        ]
        return self.sg_session.find("Asset", filters=filters, fields=fields)

    def fill_entities(self, entity_type: Literal["shot", "asset"], entities: list[Dict[str, Any]]):
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

    def export_file(self):
        self.template.fill()
        if self.out_file:
            out_file = self.out_file
        else:
            out_file = "/tmp/ami_weekly_status_report_report.xlsx"
        print(f"Export excel file {out_file}")
        self.template.write(out_file)
