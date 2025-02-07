name = "shotgrid"
title = "Shotgrid"
version = "0.5.2+dev"
client_dir = "ayon_shotgrid"

services = {
    "ShotgridLeecher": {
        "image": f"rvx/ayon-shotgrid-leecher:{version}"},
    "ShotgridProcessor": {
        "image": f"rvx/ayon-shotgrid-processor:{version}"},
    "ShotgridTransmitter": {
        "image": f"rvx/ayon-shotgrid-transmitter:{version}"},
}
ayon_required_addons = {
    "core": ">=0.3.0",
}
ayon_compatible_addons = {}
