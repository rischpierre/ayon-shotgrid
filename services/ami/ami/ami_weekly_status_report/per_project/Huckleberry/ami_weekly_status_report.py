import argparse
import datetime
from typing import Any, Dict

from ami.ami_weekly_status_report.ami_weekly_status_report import AMIWeeklyStatusReport
from ami.ami_weekly_status_report.path_templates import StringTemplate


class AMIWeeklyStatusReportHuckleberry(AMIWeeklyStatusReport):

    def __init__(self, sg_session: Any, data: Dict[str, Any]) -> None:
        super().__init__(sg_session, data)
        self.template = self.get_template()
        self.out_file = data.get("out_file")

        self.client_to_internal_status_map = {
            "wtg": ["wtg"],
            "ip": ["ip"],
            "omt": ["omt"],
            "hld": ["hld"],
            "capt": ["sndca"],
            "cb": ["qccbb"],
            "tfnl": ["stfnl"],
            "tfccbb": ["tfccbb"],
            "tprev": ["pdi"],
            "fin": ["fpqc"],
            "cmpt": ["cmpt"],
        }

    def main(self):
        shot_fields = self.get_fields("shot")
        asset_fields = self.get_fields("asset")
        shot_fields.append("sg_status_list")
        asset_fields.append("sg_status_list")

        filters = ["sg_client_shot_name", "is_not", None]

        shots = self.get_shots(shot_fields, additional_filters=filters)
        shots = self.get_dates_per_pipeline_step(shots)

        assets = self.get_assets(asset_fields)

        assets = self.translate_client_statuses(assets)
        shots = self.translate_client_statuses(shots)

        report_name = f"RVX_Weekly_Report_{datetime.date.today().strftime('%y%m%d')}"
        today = datetime.date.today().strftime("%Y-%m-%d")
        for a in assets:
            a["_date"] = today
            a["_report_name"] = report_name
        for s in shots:
            s["_date"] = today
            s["_report_name"] = report_name

        self.fill_entities("shot", shots)
        self.fill_entities("asset", assets)

        self.fill_overview(shots, assets)

        self.export_file()
        return 0

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
                out_shots.append(shot)
                continue
            step_code = step_map[task["step"]["id"]]["code"]
            if task["due_date"]:
                shot[step_code.lower() + "_" + "due_date"] = task["due_date"]
            if task["sg_blocking"]:
                shot[step_code.lower() + "_" + "sg_blocking"] = task["sg_blocking"]
            out_shots.append(shot)

        return out_shots

    def fill_overview(self, shots, assets):
        today = datetime.date.today().strftime("%Y-%m-%d")
        friday_of_this_week = (datetime.date.today() + datetime.timedelta(days=4)).strftime("%Y-%m-%d")

        status_map = {
            "turned_over": None,
            "in_progress": "ip",
            "awaiting_material": None,
            "omits": "omt",
            "on_hold": "hld",
            "pending_review": "rev",
            "final_pending_qc": None,
            "finals": "fin",
            "cbbs": "cb",
        }

        data = {
            "_date": today,
            "_week_ending": friday_of_this_week,

            # OVERALL ASSET STATUS
            "_total_assets": len(assets),
            "_total_assets_turned_over": 0,
            "_assets_in_progress": 0,
            "_assets_awaiting_material": 0,
            "_assets_omits": 0,
            "_assets_on_hold": 0,
            "_assets_pending_review": 0,
            "_assets_final_pending_qc": 0,
            "_assets_finals": 0,
            "_assets_cbbs": 0,

            "_total_assets_turned_over_percent": 0,
            "_assets_in_progress_percent": 0,
            "_assets_awaiting_material_percent": 0,
            "_assets_omits_percent": 0,
            "_assets_on_hold_percent": 0,
            "_assets_pending_review_percent": 0,
            "_assets_final_pending_qc_percent": 0,
            "_assets_finals_percent": 0,
            "_assets_cbbs_percent": 0,

            # OVERALL SHOTS STATUS
            "_total_shots": len(shots),
            "_total_shots_turned_over": 0,
            "_shots_in_progress": 0,
            "_shots_awaiting_material": 0,
            "_shots_omits": 0,
            "_shots_on_hold": 0,
            "_shots_pending_review": 0,
            "_shots_proposed_final": 0,
            "_shots_final_pending_qc": 0,
            "_shots_finals": 0,
            "_shots_cbbs": 0,

            "_total_shots_turned_over_percent": 0,
            "_shots_in_progress_percent": 0,
            "_shots_awaiting_material_percent": 0,
            "_shots_omits_percent": 0,
            "_shots_on_hold_percent": 0,
            "_shots_pending_review_percent": 0,
            "_shots_proposed_final_percent": 0,
            "_shots_final_pending_qc_percent": 0,
            "_shots_finals_percent": 0,
            "_shots_cbbs_percent": 0,

            # WEEKLY SHOT STATUS UPDATES
            "_official_counts_received_this_week": 0,
            "_shots_omitted_this_week": 0,
            "_shots_added_this_week": 0,
            "_shots_submitted_for_comp_finals_this_week": 0,
            "_finals_received_this_week": 0,
            "_finals_with_tech_fix_received_this_week": 0,
            "_cbbs_received_this_week": 0,
        }

        for k, v in data.items():
            for x, sg_status in status_map.items():
                if k.endswith(x):
                    if k.startswith("_assets_"):
                        data[k] = len([y for y in assets if y["sg_status_list"] == sg_status])
                    elif k.startswith("_shots_"):
                        data[k] = len([y for y in shots if y["sg_status_list"] == sg_status])

        for k, v in data.items():
            original_value = data.get(k.replace("_percent", ""), 0)
            if k.endswith("_percent") and k.startswith("_shots"):
                value = round(original_value / len(shots) * 100, 2) if len(shots) > 0 else 0
                data[k] = f"{value}%"
            elif k.endswith("_percent") and k.startswith("_assets"):
                value = round(original_value / len(assets) * 100, 2) if len(assets) > 0 else 0
                data[k] = f"{value}%"

        for tag in self.template.tags:
            rendered = StringTemplate(tag).format(data)
            # If your StringTemplate returns an object with .missing_keys/.invalid_types, handle as needed
            value = "" if getattr(rendered, "missing_keys", []) or getattr(rendered, "invalid_types", []) else str(
                rendered)

            self.template.replacements[tag].set_value(str(value))


if __name__ == "__main__":
    from ami.ami_server import get_sg_session

    parser = argparse.ArgumentParser(description="Generate Weekly Status Report")
    parser.add_argument("--project_name", help="Name of the project in ShotGrid")
    parser.add_argument("--out_file", help="Output file path for the generated report")
    parser.add_argument("--template", help="Path to the Excel template file")
    args = parser.parse_args()

    sg_session = get_sg_session()

    project = sg_session.find_one("Project", [["name", "is", args.project_name]], ["id"])
    if not project:
        print(f"Error: Project '{args.project_name}' not found in ShotGrid")
        exit(1)

    project_id = project["id"]
    data = {
        "selected_ids": str(project_id),
        "project_id": project_id,
        "template_file": args.template,
        "out_file": args.out_file
    }

    AMIWeeklyStatusReportHuckleberry(sg_session, data).main()
