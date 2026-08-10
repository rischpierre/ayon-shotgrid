import os
import webbrowser
from pathlib import Path
from threading import Timer

import uvicorn
from shotgun_api3.lib.mockgun import mockgun

from ami_create_delivery_playlist.app import (
    AMICreateDeliveryPlaylist,
    app,
    AMI_CREATE_DELIVERY_PLAYLIST_PORT,
)


_current_dir = os.path.dirname(__file__)
mockgun.Shotgun.set_schema_paths(
    os.path.join(_current_dir, "basic_sg_schema"),
    os.path.join(_current_dir, "basic_sg_entity_schema"),
)

def create_mock_sg():
    sg = mockgun.Shotgun("http://mock-shotgrid.local")

    project = sg.create(
        "Project",
        {
            "name": "Mock Project",
            "code": "mock_project",
        },
    )

    sg.create(
        "Version",
        {
            "project": project,
            "code": "mock_version_001",
            "sg_path_to_movie": "/tmp/mock_version_001.mov",
        },
    )

    sg.create(
        "Version",
        {
            "project": project,
            "code": "mock_version_002",
            "sg_path_to_movie": "/tmp/mock_version_002.mov",
        },
    )

    sg.create(
        "Playlist",
        {
            "project": project,
            "code": "delivery_2026-08-10_01",
            # todo this does not work
            # "sg_type": "Delivery",
        },
    )

    return sg


mock_sg = create_mock_sg()


def get_mock_sg_session(self):
    return mock_sg


AMICreateDeliveryPlaylist.get_sg_session = get_mock_sg_session


def open_test_page():
    test_page = Path(__file__).parent /  "test_request.html"
    webbrowser.open(test_page.as_uri())


if __name__ == "__main__":
    Timer(1.0, open_test_page).start()

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=AMI_CREATE_DELIVERY_PLAYLIST_PORT,
    )