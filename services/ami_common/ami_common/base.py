from typing import Any, Dict, List, Optional
import os 
from shotgun_api3 import Shotgun
import ayon_api

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
        
