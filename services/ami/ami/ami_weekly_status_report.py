import os

# todo get this lib from somewhere else
from path_templates import StringTemplate
import corder
import ayon_api
import shotgun_api3

def get_sg_session():
    ayon_api_key = os.environ.get("AYON_API_KEY")
    ayon_server_url = os.environ.get("AYON_SERVER_URL")
    sg_url = os.environ.get("SG_URL")
    proxy_url = os.environ.get("HTTP_PROXY").replace("http://", "")

    if not ayon_api_key or not ayon_server_url:
        raise Exception("AYON_API_KEY and AYON_SERVER_URL are required")

    if not sg_url or not proxy_url:
        raise Exception("SG_URL and HTTP_PROXY env vars are required")

    ayon_api.init_service(token=ayon_api_key, server_url=ayon_server_url)
    script_name = ayon_api.get_secret("flow_ami_service_name")["value"]
    script_key = ayon_api.get_secret("flow_ami_service_key")["value"]

    if not script_name or not script_key:
        raise Exception("Script name or key is not set")

    return shotgun_api3.Shotgun(sg_url, script_name=script_name, api_key=script_key, http_proxy=proxy_url)


def get_template():
    template = "ami/template.xlsx"

    crd = corder.Corder(template)
    crd.parse_replacements()

    return crd

def get_shot_fields(template: corder.Corder):
    range = template.range("shot")
    return [x.lstrip("{").rstrip("}") for x in range.tags]

def get_shots(sg, project_name, fields):
    return sg.find("Shot", filters=[["project.Project.name", "is", project_name]], fields=fields)

def fill_shots(template, shots):
    rows = []
    rng = template.range("shot")  # or your range type as defined in the template
    for shot in shots:

        row = {}
        for tag in rng.tags:
            rendered = StringTemplate(tag).format(shot)
            # If your StringTemplate returns an object with .missing_keys/.invalid_types, handle as needed
            value = "" if getattr(rendered, "missing_keys", []) or getattr(rendered, "invalid_types", []) else str(rendered)

            row[tag] = value
        rows.append(row)

    rng.set_replacement_values(rows)
    template.fill()


def export_file(template):
    out_file = "ami/template_out.xlsx"
    print(f"Export excel file {out_file}")
    template.write(out_file)


def main():
    project_name = "Zero_Flow"
    sg = get_sg_session()
    template = get_template()
    shot_fields = get_shot_fields(template)
    shots = get_shots(sg, project_name, shot_fields)
    fill_shots(template, shots)

    export_file(template)


if __name__ == "__main__":
    main()