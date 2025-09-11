import logging
import os
import time
from uuid import uuid4

import ayon_api
import pytest
from shotgun_api3 import Shotgun

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger("tmp_ayon_prod")

SHOTGUN_URL = os.getenv("SG_URL")
SCRIPT_NAME = os.getenv("SG_SCRIPT_NAME")
SCRIPT_KEY = os.getenv("SG_API_KEY")
HTTP_PROXY = os.getenv("HTTP_PROXY").split("://")[-1]
AYON_SERVER_URL = os.getenv("AYON_SERVER_URL")
TOKEN = os.getenv("AYON_API_KEY")

assert SHOTGUN_URL, "SG_URL environment variable is not set"
assert SCRIPT_NAME, "SG_SCRIPT_NAME environment variable is not set"
assert SCRIPT_KEY, "SG_API_KEY environment variable is not set"
assert HTTP_PROXY, "HTTP_PROXY environment variable is not set"
assert AYON_SERVER_URL, "AYON_SERVER_URL environment variable is not set"
assert TOKEN, "AYON_API_KEY environment variable is not set"

sg_session = Shotgun(SHOTGUN_URL, script_name=SCRIPT_NAME, api_key=SCRIPT_KEY, http_proxy=HTTP_PROXY)
project_name = "Zero_Flow"


# IMPORTANT: the services must be running before running this test suite

@pytest.fixture
def playlist_name():
    return f"playlist-{uuid4().hex[:8]}"


def clean_playlists(sg_playlist, ay_playlist, project_name: str):
    try:
        sg_session.delete("Playlist", sg_playlist["id"])
    except Exception as e:
        print(f"SG playlist cleanup failed: {e}")
    try:
        ayon_api.delete_entity_list(project_name, ay_playlist["id"])
    except Exception as e:
        print(f"AYON list cleanup failed: {e}")


def test_sg_script_emits_events():
    # make sure the script api item emits events, if not, the ayon entities will not be created
    scripts = sg_session.find('ApiUser', filters=[], fields=["generate_event_log_entries", "firstname"])

    for script in scripts:
        if script["firstname"] == SCRIPT_NAME:
            assert script["generate_event_log_entries"] == True


def test_create_playlist_from_sg(playlist_name: str):
    ayon_api.init_service(token=TOKEN,
                          server_url=AYON_SERVER_URL)

    sg_playlist = None
    ay_playlist = None
    versions_ids = []
    try:
        sg_project = sg_session.find_one("Project", [["name", "is", project_name]], ["name"])
        versions = sg_session.find("Version", [["project.Project.name", "is", project_name]], ["code"])
        data = {
            "code": playlist_name,
            "project": sg_project,
            "tag_list": ["toto"],
            "sg_type": "Dailies",
            "versions": versions[:2],
        }
        sg_playlist = sg_session.create("Playlist", data, return_fields=["versions", "code"])

        t = time.time()
        while ay_playlist is None:
            if time.time() - t > 60:
                break

            result = ayon_api.get_entity_lists(project_name)
            for i in result:
                if i["label"] == playlist_name:

                    t2 = time.time()
                    ay_playlist = i
                    while True:
                        result = ayon_api.raw_get(f"projects/{project_name}/lists/{ay_playlist['id']}/entities")
                        if result.status_code != 200:
                            continue
                        versions_ids = result.data["entityIds"]

                        time.sleep(1)

                        if time.time() - t2 > 10:
                            break

            time.sleep(3)

    except Exception as e:
        print(e)
    finally:
        clean_playlists(sg_playlist, ay_playlist, project_name)

    assert ay_playlist is not None, "Playlist not found"
    assert ay_playlist["label"] == playlist_name, "code does not match"
    assert ay_playlist["tags"] == ["toto"], "tags do not match"
    assert ay_playlist["data"]["sg_type"] == "Dailies", "sg_type does not match"
    assert ay_playlist["active"], "playlist is not active"
    assert ay_playlist["entityType"] == "version", "entity_type does not match"
    assert len(versions_ids) == 2, "not the correct number of versions"


def test_create_playlist_from_ay(playlist_name: str):
    ayon_api.init_service(token=TOKEN,
                          server_url=AYON_SERVER_URL)

    sg_playlist = None
    ay_playlist = None
    try:
        data = {
            "label": playlist_name,
            "entity_type": "version",
            "tags": ["toto"],
            "active": True,
            "data": {"sg_type": "Dailies"},
        }
        result = ayon_api.raw_post(f"projects/{project_name}/lists", json=data)
        if result.status_code != 201:
            raise Exception(f"Unable to create playlist {result.text}")
        ay_playlist = result.data

        # adding versions to the playlist
        for version in list(ayon_api.get_versions(project_name))[:2]:
            result = ayon_api.raw_post(f"projects/{project_name}/lists/{ay_playlist['id']}/items",
                                       json={"entity_id": version["id"]})
            if result.status_code != 201:
                raise Exception(f"Unable to add version to playlist {result.text}")

        t = time.time()
        while sg_playlist is None:
            if time.time() - t > 60:
                break

            sg_playlist = sg_session.find_one(
                "Playlist",
                [["project.Project.name", "is", project_name], ["code", "is", playlist_name]],
                ["code", "tags", "sg_type", "locked", "versions"])

            time.sleep(3)
    except Exception as e:
        print(e)
    finally:
        clean_playlists(sg_playlist, ay_playlist, project_name)

    assert sg_playlist is not None, "Playlist not found"
    assert sg_playlist["code"] == playlist_name, "code does not match"
    assert sg_playlist["tags"][0]["name"] == "toto", "tags do not match"
    assert sg_playlist["sg_type"] == "Dailies", f"sg_type does not match {sg_playlist['sg_type']}"
    assert len(sg_playlist["versions"]) == 2, "not the same number of versions"
    assert not sg_playlist["locked"], "locked does not match"
