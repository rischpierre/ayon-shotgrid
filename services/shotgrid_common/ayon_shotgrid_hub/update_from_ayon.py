"""Module that handles creation, update or removal of SG entities based on AYON events.
"""
from typing import Dict, List, Any
import tempfile
import os
import copy

import shotgun_api3

import ayon_api

from utils import (
    get_sg_statuses,
    get_sg_tags,
    get_sg_custom_attributes_data,
    create_new_sg_entity
)
from constants import (
    CUST_FIELD_CODE_ID,  # Shotgrid Field for the AYON ID.
    SHOTGRID_ID_ATTRIB,  # AYON Entity Attribute.
    SHOTGRID_TYPE_ATTRIB,  # AYON Entity Attribute.
)

from utils import get_logger


log = get_logger(__file__)

def _rvx_update_sg_playlist(
    ayon_event: Dict[str, Any],
    sg_session: shotgun_api3.Shotgun,
    sg_project: Dict[str, Any],
    ayon_entity_hub: ayon_api.entity_hub.EntityHub,
) -> None:
    """
    Syncs an AYON entity list of type 'version' with a ShotGrid Playlist.

    Args:
        ayon_event (Dict[str, Any]): The AYON event containing summary and entity list info.
        sg_session (shotgun_api3.Shotgun): The ShotGrid API session.
        sg_project (Dict[str, Any]): The ShotGrid project dictionary.
        ayon_entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub instance.
    """
    ay_entitity_list_id = ayon_event["summary"]["id"]
    project_name = ayon_entity_hub.project_entity.project_name

    query = ayon_api.raw_get(f"projects/{project_name}/lists/{ay_entitity_list_id}")
    if query.status != 200:
        log.error(f"Entity list {ay_entitity_list_id} does not exists in AYON")
        return

    entity_list = query.data

    shotgrid_id = entity_list["attrib"].get("shotgridId")
    sg_playlist = None
    if shotgrid_id:
        log.debug(f"Entity list {ay_entitity_list_id} already has a ShotGrid ID: {shotgrid_id}")
        sg_playlist = sg_session.find_one(
            "Playlist",
            [["project", "is", sg_project], ["id", "is", int(shotgrid_id)]],
            ["versions", "project", "code", "tag_list", "locked"],
        )
        if not sg_playlist:
            log.error(f"ShotGrid Playlist with ID {shotgrid_id} not found in ShotGrid, creating it")
            return

    # not found in sg, create it
    if not shotgrid_id or not sg_playlist:
        log.debug(
            f"Entity list {ay_entitity_list_id} does not have a ShotGrid ID "
            f"or the shotgrid playlist is not in shotgrid anymore, creating it in ShotGrid"
        )
        data = {
            "code": entity_list["label"],
            "project": sg_project,
            "sg_ayon_id": ay_entitity_list_id,
            "tag_list": entity_list["tags"],
            "locked": entity_list["active"],
        }
        sg_playlist = sg_session.create("Playlist", data, return_fields=["versions", "code"])
        log.debug(f"Created Playlist in ShotGrid: {sg_playlist['id']}")

        data = {"attrib": {"shotgridId": str(sg_playlist["id"]), "shotgridType": "Playlist"}}
        result = ayon_api.raw_patch(f"projects/{project_name}/lists/{ay_entitity_list_id}", json=data)
        if result.status != 204:
            log.error(f"Failed to update entity list with ShotGrid ID: {result.status} - {result.data}")
            return

        log.debug(f"Updated AYON entity list {ay_entitity_list_id} with ShotGrid ID: {sg_playlist['id']}")

    # update versions in the ShotGrid Playlist
    version_count_ay = len(entity_list["items"])
    version_count_sg = len(sg_playlist["versions"])
    if version_count_ay != version_count_sg:
        log.debug(
            f"Entity list {entity_list['label']} has a different number of versions than the ShotGrid Playlist, Updating it"
        )
        version_ids_ay = [x["entityId"] for x in entity_list["items"]]
        ay_versions = ayon_api.get_versions(project_name, version_ids_ay)
        matching_versions_sg_ids = [int(v["attrib"].get("shotgridId")) for v in list(ay_versions) if v["attrib"].get("shotgridId")]
        if not matching_versions_sg_ids:
            sg_versions = []
        else:
            sg_versions = sg_session.find("Version", [["project", "is", sg_project], ["id", "in", matching_versions_sg_ids]])

        log.debug(f"Updating Playlist {sg_playlist['id']} with {len(sg_versions)} versions")
        sg_session.update(
            "Playlist",
            sg_playlist["id"],
            {"versions": sg_versions, "project": sg_project},
        )
    else:
        log.debug(f"Sg Playlist versions count matches AYON entity list, no update needed")

    # sync attributes
    if ayon_event["topic"] == "entity_list.changed":

        active_in_ay = entity_list["active"]
        active_in_sg = not sg_playlist["locked"]
        label_to_update = entity_list["label"] != sg_playlist["code"]
        tags_to_update = entity_list["tags"] != sg_playlist["tag_list"]

        # we need to unloack and lock the playlist in SG because it blocks the udpate if already locked
        # or if the locked: True attribute is passed to the udpate
        if not active_in_sg:
            log.debug(f"Entity list {ay_entitity_list_id} is active in AYON but not in ShotGrid, "
                      f"unlocking it in ShotGrid before setting more attributes")
            sg_session.update("Playlist", sg_playlist["id"], {"locked": False})

        data = {}
        if label_to_update:
            data["code"] = entity_list["label"]

        if tags_to_update:
            data["tag_list"] = entity_list["tags"]

        if not data:
            log.debug(f"Entity list {ay_entitity_list_id} attribute(s) unchanged, no update needed")
            return

        log.debug(f"Entity list {ay_entitity_list_id} attribute(s) changed, "
                  f"updating ShotGrid Playlist with data : {data}")
        sg_session.update("Playlist", sg_playlist["id"], data)

        if not active_in_ay:
            log.debug(f"locking playlist in sg")
            sg_session.update("Playlist", sg_playlist["id"], {"locked": True})



def create_sg_entity_from_ayon_event(
    ayon_event: Dict,
    sg_session: shotgun_api3.Shotgun,
    ayon_entity_hub: ayon_api.entity_hub.EntityHub,
    sg_project: Dict,
    sg_enabled_entities: List[str],
    sg_project_code_field: [str],
    custom_attribs_map: Dict[str, str],
    addon_settings: Dict[str, Any],
):
    """Create a Shotgrid entity from an AYON event.

    Args:
        sg_event (dict): AYON event.
        sg_session (shotgun_api3.Shotgun): The Shotgrid API session.
        ayon_entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
        sg_project (dict): The Shotgrid project.
        sg_enabled_entities (list): List of Shotgrid entities to be enabled.
        sg_project_code_field (str): 'code' most likely
        custom_attribs_map (dict): Dictionary that maps a list of attribute names from
            AYON to Shotgrid.

    Returns:
        ay_entity (ayon_api.entity_hub.EntityHub.Entity): The newly
            created entity.
    """
    # entity lista can be other than versions, we want to sync only list that contains versions for the sg playlists
    if ayon_event["summary"].get("entity_list_type") and ayon_event["summary"]["entity_type"] == "version":
        _rvx_update_sg_playlist(ayon_event, sg_session, sg_project, ayon_entity_hub)
        return

    ay_id = ayon_event["summary"]["entityId"]
    ay_entity = ayon_entity_hub.get_or_query_entity_by_id(
        ay_id, ["folder", "task", "version"])

    if not ay_entity:
        raise ValueError(
            "Event has a non existent entity? "
            f"{ayon_event['summary']['entityId']}"
        )

    sg_id = ay_entity.attribs.get("shotgridId")
    sg_type = ay_entity.attribs.get("shotgridType")

    if not sg_type:
        if ay_entity.entity_type == "task":
            sg_type = "Task"
        elif ay_entity.entity_type == "version":
            sg_type = "Version"
        else:
            sg_type = ay_entity.folder_type

    sg_entity = None

    if sg_id and sg_type:
        sg_entity = sg_session.find_one(sg_type, [["id", "is", int(sg_id)]])

    if sg_entity:
        log.warning(f"Entity {sg_entity} already exists in Shotgrid!")
        return ay_entity

    try:
        sg_parent_entity = _get_sg_parent_entity(
            sg_session, ay_entity, ayon_event)

        sg_entity = create_new_sg_entity(
            ay_entity,
            sg_session,
            sg_project,
            sg_parent_entity,
            sg_enabled_entities,
            sg_project_code_field,
            custom_attribs_map,
            addon_settings,
            ayon_event["project"]
        )
        if not sg_entity:
            log.warning(f"Couldn't create SG entity for '{ay_id}")

        if (
            ay_entity.entity_type == "folder"
            and ay_entity.folder_type == "AssetCategory"
        ):
            # AssetCategory is special, we don't want to create it in Shotgrid
            # but we need to assign Shotgrid ID and Type to it
            sg_entity = {
                "id": ay_entity.name.lower(),
                "type": "AssetCategory"
            }

        if not sg_entity:
            if hasattr(ay_entity, "folder_type"):
                log.warning(
                    f"Unable to create `{ay_entity.folder_type}` <{ay_id}> "
                    "in Shotgrid!"
                )
            else:
                log.warning(
                    f"Unable to create `{ay_entity.entity_type}` <{ay_id}> "
                    "in Shotgrid!"
                )
            return None

        sg_id = sg_entity["attribs"]["shotgridId"]
        sg_type = sg_entity["attribs"]["shotgridType"]
        log.info(f"Created Shotgrid entity: {sg_id} of {sg_type}")

        ay_entity.attribs.set(
            SHOTGRID_ID_ATTRIB,
            sg_id
        )
        ay_entity.attribs.set(
            SHOTGRID_TYPE_ATTRIB,
            sg_type
        )
        ayon_entity_hub.commit_changes()
        return ay_entity

    except Exception:
        log.error(
            f"Unable to create {sg_type} <{ay_id}> in Shotgrid!",
            exc_info=True
        )
        return None


def _get_parent_sg_id_type(ay_entity):
    """ Recursively find a parent with a valid Shotgrid ID.
    """
    # Sync new Asset parented under an AssetCategory.
    # Sync children of a generic Folder.
    sg_parent_id = ay_entity.parent.attribs.get(SHOTGRID_ID_ATTRIB)
    sg_parent_type = ay_entity.parent.attribs.get(SHOTGRID_TYPE_ATTRIB)

    if sg_parent_id and sg_parent_type:
        return sg_parent_id, sg_parent_type

    elif not ay_entity.parent:
        return None, None

    return _get_parent_sg_id_type(ay_entity.parent)


def _get_sg_parent_entity(sg_session, ay_entity, ayon_event):
    """Returns SG parent for currently created ay_entity

    Returns:
        Dict[str, str]  {"id": XXXX, "type": "Asset|.."}
    """
    if ay_entity.entity_type == "version":
        folder_id = ay_entity.parent.parent.id
        ayon_asset = ayon_api.get_folder_by_id(
            ayon_event["project"], folder_id)

        if not ayon_asset:
            raise ValueError(
                f"Could not find Version parent folder from ID: '{folder_id}'."
            )

        sg_parent_id = ayon_asset["attrib"].get(SHOTGRID_ID_ATTRIB)
        sg_parent_type = ayon_asset["attrib"].get(SHOTGRID_TYPE_ATTRIB)
    else:
        sg_parent_id, sg_parent_type = _get_parent_sg_id_type(ay_entity)

    if not sg_parent_id or not sg_parent_type:
        raise ValueError(f"Could not find valid parent for {ay_entity}.")

    sg_parent_entity = sg_session.find_one(
        sg_parent_type,
        filters=[[
            "id",
            "is",
            int(sg_parent_id)
        ]]
    )
    return sg_parent_entity


def update_sg_entity_from_ayon_event(
    ayon_event: Dict,
    sg_session: shotgun_api3.Shotgun,
    ayon_entity_hub: ayon_api.entity_hub.EntityHub,
    sg_project: Dict,
    sg_enabled_entities: List[str],
    sg_project_code_field: [str],
    custom_attribs_map: Dict[str, str],
    addon_settings: Dict[str, Any],
):
    """Try to update a Shotgrid entity from an AYON event.

    Args:
        sg_event (dict): The `meta` key from a Shotgrid Event.
        sg_session (shotgun_api3.Shotgun): The Shotgrid API session.
        ayon_entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
        custom_attribs_map (dict): A mapping of custom attributes to update.

    Returns:
        sg_entity (dict): The modified Shotgrid entity.

    """
    if ayon_event["summary"].get("entity_list_type") and ayon_event["summary"]["entity_type"] == "version":
        sg_project = sg_session.find_one("Project", [["name", "is", ayon_entity_hub.project_entity.project_name]])
        _rvx_update_sg_playlist(ayon_event, sg_session, sg_project, ayon_entity_hub)
        return

    ay_id = ayon_event["summary"]["entityId"]
    ay_entity = ayon_entity_hub.get_or_query_entity_by_id(
        ay_id, ["folder", "task", "version"])

    if not ay_entity:
        raise ValueError(
            "Event has a non existent entity? "
            f"{ayon_event['summary']['entityId']}"
        )

    sg_id = ay_entity.attribs.get("shotgridId")
    sg_entity_type = ay_entity.attribs.get("shotgridType")

    # react to an AYON entity being updated
    # that does not exist yet in Shotgrid.
    if sg_id is None:

        # Create SG entity and update existing ay_entity.
        ay_entity = create_sg_entity_from_ayon_event(
            ayon_event,
            sg_session,
            ayon_entity_hub,
            sg_project,
            sg_enabled_entities,
            sg_project_code_field,
            custom_attribs_map,
            addon_settings,
        )

        sg_id = ay_entity.attribs.get("shotgridId")
        sg_entity_type = ay_entity.attribs.get("shotgridType")

        if sg_id is None:
            log.warning(f"Could not create SG entity from {ay_entity}.")
            return

    try:
        sg_field_name = "code"
        if ay_entity["entity_type"] == "task":
            sg_field_name = "content"

        # Change the name of the variant asset: in SG: pedestrian_A, in AY: A
        name = ay_entity["name"]
        if sg_entity_type == "Asset":
            sg_asset = sg_session.find_one(
                "Asset",
                filters=[["id", "is", int(sg_id)]],
                fields=["sg_ayon_folder_type", "code"]
            )
            if sg_asset and sg_asset["sg_ayon_folder_type"] == "VariantAsset":
                name = name.split("_")[-1]  # pedestrian_A -> A
                log.debug(f"Updating AYON Asset name: {sg_asset['code']}, new name: {name}")

        data_to_update = {
            sg_field_name: name,
            CUST_FIELD_CODE_ID: ay_entity["id"]
        }

        try:
            data_to_update[sg_field_name] = ay_entity["name"]
        except NotImplementedError:
            pass  # Version does not have a name.

        # Add any possible new values to update
        new_attribs = ayon_event["payload"].get("newValue")

        if isinstance(new_attribs, dict):
            # If payload newValue is a dict it means it's an attribute update
            # but this only apply to case were attribs key is in the
            # newValue dict
            if "attribs" in new_attribs:
                new_attribs = new_attribs["attribs"]

        # Label changed
        elif ayon_event["topic"].endswith("label_changed"):
            new_value = ayon_event["payload"].get("newValue")
            data_to_update[sg_field_name] = new_value
            new_attribs = None

        # Otherwise it's a tag/status update
        elif ayon_event["topic"].endswith("status_changed"):
            sg_statuses = get_sg_statuses(sg_session, sg_entity_type)
            ay_statuses = {
                status.name: status.short_name
                for status in  ayon_entity_hub.project_entity.statuses
            }
            short_name = ay_statuses.get(new_attribs)
            if short_name in sg_statuses:
                new_attribs = {"status": short_name}
            else:
                log.error(
                    f"Unable to update '{sg_entity_type}' with status "
                    f"'{new_attribs}' in Shotgrid as it's not compatible! "
                    f"It should be one of: {sg_statuses}"
                )
                return

        elif ayon_event["topic"].endswith("tags_changed"):
            tags_event_list = new_attribs
            new_attribs = {"tags": []}
            sg_tags = get_sg_tags(sg_session)
            for tag_name in tags_event_list:
                if tag_name.lower() in sg_tags:
                    tag_id = sg_tags[tag_name]
                else:
                    log.info(
                        f"Tag '{tag_name}' not found in ShotGrid, "
                        "creating a new one."
                    )
                    new_tag = sg_session.create("Tag", {'name': tag_name})
                    tag_id = new_tag["id"]

                new_attribs["tags"].append(
                    {"name": tag_name, "id": tag_id, "type": "Tag"}
                )
        elif ayon_event["topic"].endswith("assignees_changed"):
            sg_assignees = []
            for user_name in new_attribs:
                ayon_user = ayon_api.get_user(user_name)
                if not ayon_user or not ayon_user["data"].get("sg_user_id"):
                    log.warning(f"User {user_name} is not synched to SG yet.")
                    continue
                sg_assignees.append(
                    {"type": "HumanUser",
                     "id": ayon_user["data"]["sg_user_id"]}
                )
            new_attribs = {"assignees": sg_assignees}
        else:
            log.warning(
                "Unknown event type, skipping update of custom attribs.")
            new_attribs = None

        if new_attribs:
            data_to_update.update(get_sg_custom_attributes_data(
                sg_session,
                new_attribs,
                sg_entity_type,
                custom_attribs_map
            ))


        sg_entity = sg_session.update(
            sg_entity_type,
            int(sg_id),
            data_to_update
        )
        log.info(f"Updated ShotGrid entity: {sg_entity}")
        return sg_entity

    except Exception:
        log.error(
            f"Unable to update {sg_entity_type} <{sg_id}> in ShotGrid!",
            exc_info=True
        )


def remove_sg_entity_from_ayon_event(
    ayon_event: Dict,
    sg_session: shotgun_api3.Shotgun
):
    """Try to remove a Shotgrid entity from an AYON event.

    Args:
        ayon_event (dict): The `meta` key from a Shotgrid Event.
        sg_session (shotgun_api3.Shotgun): The Shotgrid API session.
    """
    ay_id = ayon_event["payload"]["entityData"]["id"]
    log.debug(f"Removing Shotgrid entity: {ayon_event['payload']}")

    sg_id = ayon_event["payload"]["entityData"]["attrib"].get("shotgridId")

    if not sg_id:
        ay_entity_path = ayon_event["payload"]["entityData"]["path"]
        log.warning(
            f"Entity '{ay_entity_path}' does not have a "
            "ShotGrid ID to remove."
        )
        return

    sg_type = ayon_event["payload"]["entityData"]["attrib"]["shotgridType"]

    if not sg_type:
        sg_type = ayon_event["payload"]["folderType"]

    if sg_id and sg_type:
        sg_entity = sg_session.find_one(
            sg_type,
            filters=[["id", "is", int(sg_id)]]
        )
    else:
        sg_entity = sg_session.find_one(
            sg_type,
            filters=[[CUST_FIELD_CODE_ID, "is", ay_id]]
        )

    if not sg_entity:
        log.warning(
            f"Unable to find AYON entity with id '{ay_id}' in Shotgrid.")
        return

    sg_id = sg_entity["id"]

    try:
        sg_session.delete(sg_type, int(sg_id))
        log.info(f"Retired Shotgrid entity: {sg_type} <{sg_id}>")
    except Exception:
        log.error(
            f"Unable to delete {sg_type} <{sg_id}> in Shotgrid!",
            exc_info=True
        )

