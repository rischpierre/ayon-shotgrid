from pathlib import Path
from threading import Timer

import uvicorn
from shotgun_api3.lib.mockgun import mockgun

from ami_create_delivery_playlist.app import (
    AMICreateDeliveryPlaylist,
    app,
    AMI_CREATE_DELIVERY_PLAYLIST_PORT,
)
from tests.open_test_page import open_test_page

ami_common_dir = (
    Path(__file__).parent.parent.parent / "ami_common" / "ami_common" / "tests"
)
mockgun.Shotgun.set_schema_paths(
    ami_common_dir / "schema.bin",
    ami_common_dir / "schema_entity.bin",
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

if __name__ == "__main__":
    Timer(1.0, open_test_page).start()

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=AMI_CREATE_DELIVERY_PLAYLIST_PORT,
    )
