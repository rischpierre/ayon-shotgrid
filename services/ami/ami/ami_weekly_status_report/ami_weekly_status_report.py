import os
from typing import Any, Dict
from typing import Literal

# todo move corder here
import corder

from ami import ami_base
# todo get this lib from somewhere else
from ami.ami_weekly_status_report.path_templates import StringTemplate


class AMIWeeklyStatusReport(ami_base.AmiBase):

    def __init__(self, sg_session: Any, data: Dict[str, Any]) -> None:
        super().__init__(sg_session, data)
        self.template = self.get_template()

    def parameters(self):
        return []

    def get_template(self):
        path = os.path.dirname(__file__) + "/template.xlsx"
        crd = corder.Corder(path)
        crd.parse_replacements()
        return crd

    def get_fields(self, entity_type: Literal["asset", "shot"]):
        range = self.template.range(entity_type)
        return [x.lstrip("{").rstrip("}") for x in range.tags]

    def get_shots(self, fields):
        return self.sg_session.find("Shot", filters=[["project.Project.id", "is", self.project_id]], fields=fields)

    def get_assets(self, fields):
        return self.sg_session.find("Asset", filters=[["project.Project.id", "is", self.project_id]], fields=fields)

    def fill_shots(self, shots):
        rows = []
        rng = self.template.range("shot")  # or your range type as defined in the template
        for shot in shots:

            row = {}
            for tag in rng.tags:
                rendered = StringTemplate(tag).format(shot)
                # If your StringTemplate returns an object with .missing_keys/.invalid_types, handle as needed
                value = "" if getattr(rendered, "missing_keys", []) or getattr(rendered, "invalid_types", []) else str(
                    rendered)

                row[tag] = value
            rows.append(row)

        rng.set_replacement_values(rows)
        self.template.fill()

    def fill_assets(self, assets):
        rows = []
        rng = self.template.range("asset")  # or your range type as defined in the template
        for asset in assets:

            row = {}
            for tag in rng.tags:
                rendered = StringTemplate(tag).format(asset)
                # If your StringTemplate returns an object with .missing_keys/.invalid_types, handle as needed
                value = "" if getattr(rendered, "missing_keys", []) or getattr(rendered, "invalid_types", []) else str(
                    rendered)

                row[tag] = value
            rows.append(row)

        rng.set_replacement_values(rows)
        self.template.fill()

    def get_dates_per_pipeline_step(self, shots):
        steps = self.sg_session.find("Step", [["code", "in", ["Compositing", "Animation", "Layout"]]], ["code"])
        step_map = {x['id']: x for x in steps}
        shot_map = {x['id']: x for x in shots}
        tasks = self.sg_session.find(
            "Task",
            filters=[["project.Project.id", "is", self.project_id],
                     ['entity', 'in', list(shot_map.values())],
                     ["step", "in", steps]
                     ],
            fields=["sg_blocking", "due_date", "entity", "step", "content"]
        )
        task_map = {x['entity']['id']: x for x in tasks}
        out_shots = []
        for shot in shots:
            task = task_map.get(shot["id"])
            if not task:
                continue
            step_code = step_map[task["step"]["id"]]["code"]
            if task["due_date"]:
                shot[step_code.lower() + "_" + "due_date"] = task["due_date"]
            if task["sg_blocking"]:
                shot[step_code.lower() + "_" + "sg_blocking"] = task["sg_blocking"]
            out_shots.append(shot)
        return out_shots

    def export_file(self):
        out_file = os.path.dirname(__file__) + "/report.xlsx"
        print(f"Export excel file {out_file}")
        self.template.write(out_file)

    def fill_overview(self):

        data = {
            "date": "toto",
            "week_ending": "todo",
        }

        for tag in self.template.tags:
            rendered = StringTemplate(tag).format(data)
            # If your StringTemplate returns an object with .missing_keys/.invalid_types, handle as needed
            value = "" if getattr(rendered, "missing_keys", []) or getattr(rendered, "invalid_types", []) else str(
                rendered)

            self.template.replacements[tag].set_value(str(value))

        self.template.fill()

    def main(self):
        shot_fields = self.get_fields("shot")
        asset_fields = self.get_fields("asset")
        shots = self.get_shots(shot_fields)
        shots = self.get_dates_per_pipeline_step(shots)

        assets = self.get_assets(asset_fields)

        self.fill_overview()

        self.fill_shots( shots)
        self.fill_assets( assets)

        self.export_file()
        return 0


if __name__ == "__main__":
    from ami.ami_server import get_sg_session
    # Zero_Flow project
    data = {"selected_ids": [353], "project_id": 353}
    AMIWeeklyStatusReport(get_sg_session(), data).main()
