from __future__ import annotations
import os

import ayon_api
import shotgun_api3

def get_sg_session():
    ayon_api_key = os.environ.get("AYON_API_KEY")
    ayon_server_url = os.environ.get("AYON_SERVER_URL")
    sg_url = os.environ.get("SG_URL")
    proxy = os.environ.get("HTTP_PROXY")
    proxy_url = proxy.replace("http://", "") if proxy else None

    if not ayon_api_key or not ayon_server_url:
        raise Exception("AYON_API_KEY and AYON_SERVER_URL are required")

    if not sg_url or not proxy_url:
        raise Exception("SG_URL and HTTP_PROXY env vars are required")

    ayon_api.init_service(token=ayon_api_key, server_url=ayon_server_url)
    script_name = ayon_api.get_secret("flow_whiteboard_service_name")["value"]
    script_key = ayon_api.get_secret("flow_whiteboard_service_key")["value"]

    if not script_name or not script_key:
        raise Exception("Script name or key is not set")

    return shotgun_api3.Shotgun(sg_url, script_name=script_name, api_key=script_key, http_proxy=proxy_url)
