import logging
from datetime import date

from ami_weekly_status_report.app import AMIWeeklyStatusReport, SubmitRequest
from fastapi import Request

logger = logging.getLogger(__name__)


class AMIWeeklyStatusReportComplete_Chaos(AMIWeeklyStatusReport):

    def __init__(self) -> None:
        super().__init__()

        self.client_to_internal_status_map = {
            "TURNED OVER": ["wtg", "start"],
            "IN PROGRESS": ["ip", "lay", "1pass", "swip"],
            "HOLD": ["hld"],
            "OMIT": ["omt"],
            "CBB": ["cb"],
            "FINAL": ["4k", "intc", "tcok", "stfnl", "pdi", "dinote"],
            "FINAL TECH CHECKED": ["fin"],
        }

    def submit(self, request: Request, payload: SubmitRequest):
        shot_fields = self.get_fields("shot")
        asset_fields = self.get_fields("asset")
        shots = self.get_shots(shot_fields)
        assets = self.get_assets(asset_fields)

        shots, assets = self._fill_additional_fields(shots, assets)
        shots, assets = self._format_fields(shots, assets)

        assets = self.translate_client_statuses(assets)
        shots = self.translate_client_statuses(shots)

        self.fill_entities("shot", shots)
        self.fill_entities("asset", assets)

        self.export_file()
        logger.info(f"Exported file")
        return super().submit(request, payload)

    @staticmethod
    def _fill_additional_fields(shots, assets):
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
            shot["sg__"] = "{}%".format(shot["sg__"]) if "sg__" in shot else ""
            shot["sg_progress"] = (
                "{}%".format(shot["sg_progress"]) if "sg_progress" in shot else ""
            )
            shot["sg_shared_shot"] = "Yes" if "sg_shared_shot" in shot else "No"

        return shots, assets
