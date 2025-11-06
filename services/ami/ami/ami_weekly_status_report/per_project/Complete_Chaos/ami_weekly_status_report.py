import argparse
from datetime import date
from typing import Any, Dict

from ami.ami_weekly_status_report.ami_weekly_status_report import AMIWeeklyStatusReport


class AMIWeeklyStatusReportCompleteChaos(AMIWeeklyStatusReport):

    def __init__(self, sg_session: Any, data: Dict[str, Any]) -> None:
        super().__init__(sg_session, data)
        self.template = self.get_template()
        self.out_file = data.get("out_file")

    def main(self):
        shot_fields = self.get_fields("shot")
        asset_fields = self.get_fields("asset")
        shots = self.get_shots(shot_fields)
        assets = self.get_assets(asset_fields)

        shots, assets = self._fill_additionnal_fields(shots, assets)
        shots, assets = self._format_fields(shots, assets)

        self.fill_shots(shots)
        self.fill_assets(assets)

        self.export_file()
        return 0

    @staticmethod
    def _fill_additionnal_fields(shots, assets):
        # RVX_WeeklyReport_20251002_01
        today = date.today().strftime("%Y-%m-%d")
        for shot in shots:
            shot["_report_name"] = f"RVX_WeeklyReport_{today.replace('-', '')}_01"
            shot["_date"] = today

        for asset in assets:
            asset["_report_name"] = f"RVX_WeeklyReport_{today.replace('-', '')}_01"
            asset["_date"] = today

        return shots, assets

    def _format_fields(self, shots, assets):
        for shot in shots:
            shot["sg__"] = "{}%".format(shot["sg__"]) if shot["sg__"] else ""
            shot["sg_shared_shot"] = "Yes" if shot["sg_shared_shot"] else "No"

        return shots, assets


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

    AMIWeeklyStatusReportCompleteChaos(sg_session, data).main()
