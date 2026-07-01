import argparse
import datetime
import logging
from datetime import timedelta
from typing import Any, Dict

from ami.ami_weekly_status_report.ami_weekly_status_report import AMIWeeklyStatusReport
from ami.ami_weekly_status_report.path_templates import StringTemplate

logger = logging.getLogger(__name__)


# to run
"""
cd ayon-shotgrid/services/ami
env PYTHONPATH="{$PYTHONPATH}:." uv run ami/ami_weekly_status_report/per_project/Sweetfoot2/ami_weekly_status_report.py --project-name Sweetfoot2 --out-file result_swe2.xlxs --template ami/ami_weekly_status_report/per_project/Sweetfoot2/Sweetfoot2_wsr_template.xlsx
"""
class AMIWeeklyStatusReportSweetfoot2(AMIWeeklyStatusReport):

    def __init__(self, sg_session: Any, data: Dict[str, Any]) -> None:
        super().__init__(sg_session, data)
        self.template = self.get_template()
        self.out_file = data.get("out_file")

        self.date_format = "%m/%d/%Y"

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
        shot_query_fields = self.get_query_fields("Shot", shot_fields)

        asset_fields = self.get_fields("asset")
        asset_query_fields = self.get_query_fields("Asset", asset_fields)

        shot_fields.extend(["sg_status_list", "sg_sequence"])
        asset_fields.extend(["sg_status_list", "shots"])

        filters = ["sg_client_shot_name", "is_not", None]
        shots = self.get_shots(shot_fields, additional_filters=filters)
        assets = self.get_assets(asset_fields)

        assets, shots = self._get_episode(assets, shots)

        shots = self.get_dates_per_tasks(shots, shot_fields)
        shots = self.convert_field_entities_to_text(shots)
        shots = self.fetch_query_fields("Shot", shots, shot_query_fields)

        assets = self.get_dates_per_tasks(assets, asset_fields)
        assets = self.convert_field_entities_to_text(assets)
        assets = self.fetch_query_fields("Asset", assets, asset_query_fields)

        assets = self.translate_client_statuses(assets)
        shots = self.translate_client_statuses(shots)

        report_name = f"RVX_Weekly_Report_{datetime.date.today().strftime(self.date_format.replace('/', '_'))}"
        today = datetime.date.today().strftime(self.date_format)
        for a in assets:
            a["_date"] = today
            a["_report_name"] = report_name
        for s in shots:
            s["_date"] = today
            s["_report_name"] = report_name

        assets = self._format_dates(assets)
        shots = self._format_dates(shots)

        self.fill_entities("shot", shots)
        self.fill_entities("asset", assets)

        self.fill_overview(shots, assets)

        self.export_file()
        return 0

    def _get_episode(self, assets, shots):
        for asset in assets:
            linked_shots = asset.get("shots")
            if not linked_shots or len(linked_shots) == 0:
                logger.warning(f"Asset {asset.get('id')} has no linked shots")
                continue
            linked_shot = linked_shots[0]
            linked_shot = self.sg_session.find_one("Shot", [["id", "is", linked_shot["id"]]], ["sg_sequence"])
            if not linked_shot:
                logger.warning(f"Could not find Shot with id {linked_shots[0].get('id')}")
                continue
            sequence = linked_shot.get("sg_sequence")
            if not sequence:
                logger.warning(f"Shot {linked_shot.get('id')} has no sg_sequence")
                continue

            sequence = self.sg_session.find_one("Sequence", [["id", 'is', sequence['id']]], ["episode"])
            if not sequence:
                logger.warning(f"Could not find Sequence with id {linked_shot.get('sg_sequence', {}).get('id')}")
                continue
            episode = sequence.get('episode')
            if not episode:
                logger.warning(f"Sequence {sequence.get('id')} has no episode")
                continue
            episode = self.sg_session.find_one("Episode", [['id', "is", episode['id']]], ["code"])

            asset["____episode"] = episode.get("code", "")

        for shot in shots:
            sequence = shot.get("sg_sequence")

            if not sequence:
                logger.warning(f"Shot {shot.get('id')} has no sg_sequence")
                continue

            sequence = self.sg_session.find_one("Sequence", [["id", 'is', sequence['id']]], ["episode"])
            if not sequence:
                logger.warning(f"Could not find Sequence with id{sequence['id']}")
                continue
            episode = sequence.get('episode')
            if not episode:
                logger.warning(f"Sequence {sequence.get('id')} has no episode")
                continue
            episode = self.sg_session.find_one("Episode", [['id', "is", episode['id']]], ["code"])

            shot["____episode"] = episode.get("code", "")

        return assets, shots
             

    def _format_dates(self, entities):
        for entity in entities:
            for field_name, field_value in entity.items():
                try:
                    date_ = datetime.datetime.strptime(field_value, "%Y-%m-%d")
                    date_formatted = date_.strftime(self.date_format)
                    entity[field_name] = date_.strftime(self.date_format)
                except:
                    pass
        return entities

    def get_query_fields(self, entity_type, fields_on_template):
        shot_schema = self.sg_session.schema_field_read(entity_type)
        fields_with_query = []
        for name, value in shot_schema.items():
            if name in fields_on_template and value.get("properties", {}).get("query"):
                fields_with_query.append(name)
        return fields_with_query

    def fetch_query_fields(self, entity_type, entities, query_fields):
        # Build schema for all fields once
        schema_per_field = {}
        for field in query_fields:
            schema_per_field[field] = self.sg_session.schema_field_read(entity_type, field)[field]

        # Prepare a list of all source entities for IN queries
        truncated_entities = [{"type": e["type"], "id": e["id"]} for e in entities if e.get("type") and e.get("id")]

        for field, schema in schema_per_field.items():
            query = schema.get('properties', {}).get("query", {}).get("value", {})
            filters = query.get("filters", {}).get("conditions", [])
            order = schema.get("properties", {}).get("summary_value", {}).get("value", {})
            direction = order.get("direction", "desc")
            order_by = order.get("column", "id")

            target_entity_type = query.get("entity_type")
            filter_list = []

            for flt in filters:
                values_final = []
                values = flt.get("values", [])
                contains_current = False
                for v in values:
                    if isinstance(v, dict) and v.get("name") in ("Current Shot", "Current Asset"):
                        contains_current = True
                    else:
                        values_final.append(v)

                # If the filter refers to the current entity, replace with an IN over all entities
                if contains_current:
                    # If there are additional static values, include them too
                    values_final = values_final + truncated_entities
                
                # Normalize relation if we are passing a list
                relation = flt.get("relation")
                if isinstance(values_final, list) and len(values_final) > 1:
                    if relation == "is":
                        relation = "in"
                    elif relation == "is_not":
                        relation = "not_in"

                # If only one value, pass the scalar
                if len(values_final) == 1:
                    value_for_filter = values_final[0]
                else:
                    value_for_filter = values_final

                # Only append if there is at least one value; otherwise keep as-is (some filters may not need values)
                if values_final:
                    filter_list.append([flt.get("path"), relation, value_for_filter])
                else:
                    # Fallback to original filter if no values were computed (unlikely)
                    filter_list.append([flt.get("path"), flt.get("relation"), flt.get("values")])

            # Always scope to project
            filter_list.append(["project.Project.id", "is", self.project_id])

            # Fetch all matching target entities once
            records = self.sg_session.find(
                target_entity_type,
                filter_list,
                ["entity", "code", "client_code"],
                order=[{"field_name": order_by, "direction": direction}],
            )

            # Group by source entity id, pick the first (best by order)
            best_by_entity_id = {}
            for rec in records:
                ent = rec.get("entity")
                if not ent:
                    continue
                eid = ent.get("id")
                if eid is None:
                    continue
                if eid not in best_by_entity_id:
                    best_by_entity_id[eid] = rec.get("client_code") or rec.get("code")

            # Assign back to original entities
            for e in entities:
                e[field] = best_by_entity_id.get(e.get("id"))

        return entities


    def convert_field_entities_to_text(self, entities):
        ids_by_type = {}
        for entity in entities:
            for value in entity.values():
                if isinstance(value, dict) and "id" in value and "type" in value:
                    ids_by_type.setdefault(value["type"], set()).add(value["id"])

        lookup = {}
        for entity_type, ids in ids_by_type.items():
            records = self.sg_session.find(entity_type, [["id", "in", list(ids)]], ["code"])
            lookup[entity_type] = {r["id"]: r.get("code") for r in records}

        for entity in entities:
            for field_name, value in entity.items():
                if isinstance(value, dict) and "id" in value and "type" in value:
                    type_lookup = lookup.get(value["type"])
                    if type_lookup and value["id"] in type_lookup:
                        entity[field_name] = type_lookup[value["id"]]
        return entities

    def get_dates_per_tasks(self, entities, entity_fields):

        delimiter = "___"
        task_names = list(set([x.split(delimiter)[0] for x in entity_fields if delimiter in x]))
        task_fields = list(set([x.split(delimiter)[-1] for x in entity_fields if delimiter in x]))
        fields = task_fields.copy()
        fields.extend(["entity", "content"])
        sg_tasks = self.sg_session.find("Task", [["project.Project.id", "is", self.project_id],["content", "in", task_names]], fields)

        for entity in entities:
            for task in sg_tasks:
                if not task.get("entity"):
                    continue

                if task["entity"]["id"] != entity["id"]:
                    continue
                for field in task_fields:
                    value = task.get(field)
                    if not value:
                        continue
                    entity[f"{task['content']}{delimiter}{field}"] = value

        return entities

    def fill_overview(self, shots, assets):
        today = datetime.datetime.today()
        today_str = today.strftime(self.date_format)

        current_monday = today - timedelta(days=today.weekday())
        friday_of_the_next_week = (current_monday + timedelta(days=7+4)).strftime(self.date_format)

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
            "_date": today_str,
            "_week_ending": friday_of_the_next_week,

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

        # fill the values based on the statuses
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
    parser.add_argument("--project-name", help="Name of the project in ShotGrid")
    parser.add_argument("--out-file", help="Output file path for the generated report")
    parser.add_argument("--template", help="Path to the Excel template file")
    args = parser.parse_args()

    sg_session = get_sg_session()

    project = sg_session.find_one("Project", [["name", "is", args.project_name]], ["id"])
    if not project:
        logger.error(f"Project '{args.project_name}' not found in ShotGrid")
        exit(1)

    project_id = project["id"]
    data = {
        "selected_ids": str(project_id),
        "project_id": project_id,
        "template_file": args.template,
        "out_file": args.out_file
    }

    AMIWeeklyStatusReportSweetfoot2(sg_session, data).main()
