name = "shotgrid"
title = "Shotgrid"
version = "0.6.10-rvx.1"
client_dir = "ayon_shotgrid"

services = {
    "ShotgridLeecher": {
        "image": f"docker.eu.rvx.is/rvx/ayon-shotgrid-leecher:{version}"},
    "ShotgridProcessor": {
        "image": f"docker.eu.rvx.is/rvx/ayon-shotgrid-processor:{version}"},
    "ShotgridTransmitter": {
        "image": f"docker.eu.rvx.is/rvx/ayon-shotgrid-transmitter:{version}"},
}
ayon_required_addons = {
    "core": ">=0.3.0",
}
ayon_compatible_addons = {}
