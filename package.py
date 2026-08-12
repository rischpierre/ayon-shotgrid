name = "shotgrid"
title = "Shotgrid"
version = "0.6.14-rvx.17"
client_dir = "ayon_shotgrid"

services = {
    "ShotgridLeecher": {
        "image": f"docker.eu.rvx.is/rvx/ayon-shotgrid-leecher:{version}"},
    "ShotgridProcessor": {
        "image": f"docker.eu.rvx.is/rvx/ayon-shotgrid-processor:{version}"},
    "ShotgridTransmitter": {
        "image": f"docker.eu.rvx.is/rvx/ayon-shotgrid-transmitter:{version}"},
    "ShotgridAmiCreateDeliveryPlaylist": {
            "image": f"docker.eu.rvx.is/rvx/ayon-shotgrid-ami-create-delivery-playlist:{version}"},
    "ShotgridAmiOutsourcePlaylist": {
        "image": f"docker.eu.rvx.is/rvx/ayon-shotgrid-ami-outsource-playlist:{version}"},
    "ShotgridAmiWeeklyStatusReport": {
        "image": f"docker.eu.rvx.is/rvx/ayon-shotgrid-ami-weekly-status-report:{version}"},
    "ShotgridWhiteboard": {
        "image": f"docker.eu.rvx.is/rvx/ayon-shotgrid-whiteboard:{version}"},
}
ayon_required_addons = {
    "core": ">=0.3.0",
}
ayon_compatible_addons = {}
ayon_server_version = ">=1.12.5"
