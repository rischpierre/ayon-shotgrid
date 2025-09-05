from utils import get_logger
import ayon_api

log = get_logger(__file__)


def rvx_update_asset(ay_entity, sg_ay_dict, sg, ay_entity_hub):
    log.debug(f"RVX: Updating AYON Asset: {ay_entity.name}")
    sg_asset = sg.find_one(
        "Asset",
        [["id", "is", sg_ay_dict["attribs"]["shotgridId"]]],
        ["code", "sg_asset_type", "parents", "sg_ayon_folder_type", "assets"],
    )

    ay_folder_type = sg_asset["sg_ayon_folder_type"]
    if ay_folder_type != ay_entity.folder_type:
        log.debug(f"Updating AYON Asset folder type: {sg_asset['sg_ayon_folder_type']}")
        ay_entity.set_folder_type(ay_folder_type)

    parents = sg_asset.get("parents", [])
    parent_id = parents[0]["id"] if parents else None

    # Variant and sub assets: they need to be reparented and renamed if they have a parent
    if ay_folder_type in ("VariantAsset", "SubAsset") and parent_id is not None:
        log.debug(f"Updating AYON Asset parent: {parent_id}")
        sg_parent = sg.find_one("Asset", [["id", "is", parent_id]], ["sg_ayon_id", "code"])
        ay_parent = ay_entity_hub.get_or_query_entity_by_id(sg_parent["sg_ayon_id"], ["folder"])
        ay_entity.set_parent(ay_parent)

        if ay_folder_type == "VariantAsset":
            new_name = ay_entity.name.split("_")[-1]
            ay_entity.set_label(new_name)
            ay_entity.set_name(new_name)

    # if an asset is switched from variant to sub asset we need to reparent
    elif ay_folder_type in ("SubAsset", "ShowAsset") and parent_id is None:
        sg_asset_type = sg_asset["sg_asset_type"]
        ay_asset_category = ayon_api.get_folder_by_name(ay_entity_hub.project_name, sg_asset_type.lower())
        if ay_entity.parent.name != sg_asset_type:
            if ay_asset_category:
                ay_asset_category = ay_entity_hub.get_or_query_entity_by_id(ay_asset_category["id"], ["folder"])
                log.debug(f"Updating AYON Asset parent: {sg_asset_type}")
                ay_entity.set_parent(ay_asset_category)
            else:
                log.debug(f"AYON Asset parent not found: {sg_asset_type}")
                assets_folder = ayon_api.get_folder_by_name(ay_entity_hub.project_name, "assets")
                if assets_folder:
                    asset_cat = ay_entity_hub.add_new_folder(
                        name=sg_asset_type.lower(),
                        label=sg_asset_type,
                        folder_type="AssetCategory",
                        parent_id=assets_folder["id"],
                    )
                    ay_entity.set_parent(asset_cat)
                else:
                    raise ValueError(f"assets folder not found in ayon")
        else:
            log.debug(f"AYON Asset parent already set: {sg_asset_type}")

    ay_entity_hub.commit_changes()


def rvx_validate_sg_asset(sg_ay_dict, sg):
    id_ = sg_ay_dict["attribs"]["shotgridId"]
    sg_asset = sg.find_one(
        "Asset", [["id", "is", id_]], ["code", "sg_asset_type", "parents", "sg_ayon_folder_type", "assets"]
    )
    if not sg_asset:
        raise ValueError(f"Unable to find asset: {id_} in ShotGrid.")

    if not sg_asset["sg_asset_type"]:
        raise ValueError(f"Unable to find asset type for: {sg_asset['code']} in ShotGrid.")

    ay_folder_type = sg_asset["sg_ayon_folder_type"]

    if ay_folder_type == "VariantAsset":
        if not sg_asset["parents"]:
            raise ValueError(f"Variant Asset: {sg_asset['code']} has no parent in ShotGrid.")
        if sg_asset["assets"]:
            raise ValueError(f"Variant Asset: {sg_asset['code']} should not have children in ShotGrid.")

        # check if it has the same asset type as its parent
        parent_id = sg_asset["parents"][0]["id"]
        sg_parent = sg.find_one("Asset", [["id", "is", parent_id]], ["sg_asset_type"])
        if sg_parent["sg_asset_type"] != sg_asset["sg_asset_type"]:
            raise ValueError(
                f"Variant Asset: {sg_asset['code']} has a different asset type: {sg_asset['sg_asset_type']} than its parent: {sg_parent['sg_asset_type']}"
            )

    else:  # SubAsset, ShowAsset
        if ay_folder_type == "ShowAsset":
            if sg_asset["parents"]:
                raise ValueError(f"ShowAsset: {sg_asset['code']} should not have parents in shotgrid")

        # if has children assets
        if sg_asset["assets"]:
            children = sg.find(
                "Asset", [["id", "in", [a["id"] for a in sg_asset["assets"]]]], ["code", "sg_asset_type"]
            )
            for c in children:
                if c["sg_asset_type"] != sg_asset["sg_asset_type"]:
                    raise ValueError(
                        f"SubAsset: {sg_asset['code']} has children: {c['code']} with a different asset type."
                    )
