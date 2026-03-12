"""Module that handles creation, update or removal of AYON entities
based on ShotGrid Events.

The updates come through `meta` dictionaries such as:
"meta": {
    "id": 1274,
    "type": "entity_retirement",
    "entity_id": 1274,
    "class_name": "Shot",
    "entity_type": "Shot",
    "display_name": "bunny_099_012",
    "retirement_date": "2023-03-31 15:26:16 UTC"
}

And most of the times it fetches the ShotGrid entity as an AYON dict like:
{
    "label": label,
    "name": name,
    SHOTGRID_ID_ATTRIB: ShotGrid id,
    CUST_FIELD_CODE_ID: ayon id stored in ShotGrid,
    CUST_FIELD_CODE_SYNC: sync status stored in ShotGrid,
    "type": the entity type,
}

"""
import json
import collections

import shotgun_api3
import ayon_api

from ayon_api import slugify_string

from typing import Dict, List, Optional, Any

from ayon_shotgrid_hub.rvx_update_from_shotgrid import rvx_update_asset, rvx_validate_sg_asset, rvx_validate_sg_shot, \
    rvx_validate_sg_sequence

from utils import (
    create_new_ayon_entity,
    get_sg_entity_as_ay_dict,
    get_sg_entity_parent_field,
    get_reparenting_from_settings,
    update_ay_entity_custom_attributes,
    handle_comment,
    handle_reply,
)
from constants import (
    CUST_FIELD_CODE_ID,  # ShotGrid Field for the AYON ID.
    SHOTGRID_ID_ATTRIB,  # AYON Entity Attribute.
    SHOTGRID_TYPE_ATTRIB,  # AYON Entity Attribute.
    SHOTGRID_REMOVED_VALUE,  # Value for removed entities.
    SG_RESTRICTED_ATTR_FIELDS,
)

from utils import get_logger


log = get_logger(__file__)

def _get_entity_list_by_name(project_name, label):
    # GraphQL query is used because the REST API does not support getting entity lists
    query_str = f'''
        query {{
          project(name: "{project_name}") {{
            entityLists {{
              edges {{
                node {{
                  id
                  label
                }}
              }}
            }}
          }}
        }}
    '''
    query = ayon_api.query_graphql(query_str)
    if query.errors:
        log.error(f"Failed to get entity list")
        return
    entity_lists = query.data.data["data"]["project"]["entityLists"]["edges"]
    for entity_list in entity_lists:
        if entity_list["node"]["label"] == label:
            log.debug(f"Entity list found: {entity_list['node']['id']} - {entity_list['node']['label']}")
            return entity_list["node"]

def _get_entity_list_item_from_entity_id(project_name, entity_list_id, entity_id):
    query_str = f'''
        query {{
          project(name: "{project_name}") {{
            entityList(id: "{entity_list_id}") {{
              items {{
                edges {{
                  id
                  entityId
                }}
              }}
            }}
          }}
        }}
    '''
    query = ayon_api.query_graphql(query_str)
    if query.errors:
        print(f"Failed to get entity list")
        return
    nodes = query.data.data["data"]["project"]["entityList"]["items"]["edges"]
    for node in nodes:
        if node["entityId"] == entity_id:
            return node["id"]

def create_ay_entity_from_sg_event(
    sg_event: Dict,
    sg_project: Dict,
    sg_session: shotgun_api3.Shotgun,
    ayon_entity_hub: ayon_api.entity_hub.EntityHub,
    sg_enabled_entities: List[str],
    project_code_field: str,
    custom_attribs_map: Optional[Dict[str, str]] = None,
    addon_settings: Optional[Dict[str, str]] = None
):
    """Create an AYON entity from a ShotGrid Event.

    Args:
        sg_event (dict): The `meta` key from a ShotGrid Event.
        sg_project (dict): The ShotGrid project.
        sg_session (shotgun_api3.Shotgun): The ShotGrid API session.
        ayon_entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
        sg_enabled_entities (list[str]): List of entity strings enabled.
        project_code_field (str): The Shotgrid project code field.
        custom_attribs_map (Optional[dict]): A dictionary that maps ShotGrid
            attributes to Ayon attributes.
        addon_settings (Optional[dict]): A dictionary of Settings

    Returns:
        ay_entity (ayon_api.entity_hub.EntityHub.Entity): The newly
            created entity.
    """
    default_task_type = addon_settings["compatibility_settings"]["default_task_type"]
    sg_parent_field = get_sg_entity_parent_field(
        sg_session,
        sg_project,
        sg_event["entity_type"],
        sg_enabled_entities,
    )

    extra_fields = [sg_parent_field]

    sg_ay_dict = get_sg_entity_as_ay_dict(
        sg_session,
        sg_event["entity_type"],
        sg_event["entity_id"],
        project_code_field,
        default_task_type,
        custom_attribs_map=custom_attribs_map,
        extra_fields=extra_fields,
    )
    if sg_event["entity_type"] == "Asset":
        rvx_validate_sg_asset(sg_ay_dict, sg_session)
    elif sg_event["entity_type"] == "Shot":
        rvx_validate_sg_shot(sg_ay_dict, sg_session)
    elif sg_event["entity_type"] == "Sequence":
        rvx_validate_sg_sequence(sg_ay_dict, sg_session)

    log.debug(f"ShotGrid Entity as AYON dict: {sg_ay_dict}")
    if not sg_ay_dict:
        log.warning(
            f"Entity {sg_event['entity_type']} <{sg_event['entity_id']}> "
            "no longer exists in ShotGrid, aborting..."
        )
        return

    if sg_ay_dict["type"].lower() == "comment":
        # SG note as AYON comment creation is
        # handled by update_ayon_entity_from_sg_event
        if sg_ay_dict["attribs"]["shotgridType"] == "Note":
            return
        if sg_ay_dict["attribs"]["shotgridType"] == "Reply":
            handle_reply(
                sg_ay_dict,
                sg_session,
                ayon_entity_hub,
            )
            return

    ayon_id_stored_in_sg = sg_ay_dict["data"].get(CUST_FIELD_CODE_ID)
    if ayon_id_stored_in_sg:
        # Revived entity, check if it's still in the Server
        ay_entity = ayon_entity_hub.get_or_query_entity_by_id(
            ayon_id_stored_in_sg,
            [sg_ay_dict["type"]]
        )

        if ay_entity:
            log.debug("ShotGrid Entity exists in AYON.")
            # Ensure AYON Entity has the correct ShotGrid ID
            ay_entity = _update_sg_id(
                ay_entity,
                custom_attribs_map,
                sg_ay_dict,
                ayon_entity_hub.project_entity
            )

            return ay_entity

    ay_parent_entity = None
    items_to_create = collections.deque()
    while ay_parent_entity is None:
        items_to_create.append(sg_ay_dict)
        ay_parent_entity = _get_ayon_parent_entity(
            ayon_entity_hub,
            project_code_field,
            sg_ay_dict,
            sg_parent_field,
            sg_project,
            sg_session,
            addon_settings
        )

        sg_parent = sg_ay_dict["data"].get(sg_parent_field)
        if not ay_parent_entity and not sg_parent:
            ay_parent_entity = ayon_entity_hub.project_entity

        if not ay_parent_entity:
            if sg_ay_dict["data"][sg_parent_field]["type"] == "Asset":
                extra_field = "sg_asset_type"

            else:
                extra_field = get_sg_entity_parent_field(
                    sg_session,
                    sg_project,
                    sg_ay_dict["data"][sg_parent_field]["type"],
                    sg_enabled_entities,
                )

            sg_ay_dict = get_sg_entity_as_ay_dict(
                sg_session,
                sg_ay_dict["data"][sg_parent_field]["type"],
                sg_ay_dict["data"][sg_parent_field]["id"],
                project_code_field,
                default_task_type,
                custom_attribs_map=custom_attribs_map,
                extra_fields=[extra_field],
            )
            sg_parent_field = extra_field

    while items_to_create:
        sg_ay_dict = items_to_create.pop()

        shotgrid_type = sg_ay_dict["attribs"][SHOTGRID_TYPE_ATTRIB]
        sg_parent_field = get_sg_entity_parent_field(
            sg_session,
            sg_project,
            shotgrid_type,
            sg_enabled_entities,
        )
        ay_parent_entity = _get_ayon_parent_entity(
            ayon_entity_hub,
            project_code_field,
            sg_ay_dict,
            sg_parent_field,
            sg_project,
            sg_session,
            addon_settings
        )

        ay_entity = create_new_ayon_entity(
            sg_session,
            ayon_entity_hub,
            ay_parent_entity,
            sg_ay_dict
        )

        if shotgrid_type == "Asset":
            rvx_update_asset(ay_entity, sg_ay_dict, sg_session, ayon_entity_hub)

    return ay_entity


def sync_ay_entity_list_from_sg_event(
    sg_event_meta: Dict,
    sg_project: Dict,
    sg_session: shotgun_api3.Shotgun,
):
    """
    Synchronize an AYON entity list with a ShotGrid Playlist event.

    Args:
        sg_event_meta (dict): Metadata from the ShotGrid event.
        sg_project (dict): The ShotGrid project dictionary.
        sg_session (shotgun_api3.Shotgun): The ShotGrid API session.
        ayon_entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub instance.

    Returns:
        None
    """
    project_name = sg_project["name"]
    sg_playlist = sg_session.find_one("Playlist",
                                      [["project", "is", sg_project], ["id", "is", sg_event_meta["entity_id"]]],
                                      ["sg_ayon_id", "type", "code", "versions", "tag_list", "locked", "sg_type"])
    if not sg_playlist:
        log.error(f"Playlist with id {sg_event_meta['entity_id']} not found in Shotgun.")
        return

    entity_list = None
    ay_entitity_list_id = sg_playlist.get("sg_ayon_id")
    if ay_entitity_list_id:
        query = ayon_api.raw_get(f"projects/{project_name}/lists/{ay_entitity_list_id}")
        if query.status == 200:
            entity_list = query.data
        else:
            log.debug(f"Entity list {ay_entitity_list_id} does not exists in AYON")

    # create entity list or reconnect it after retiring the entity list from ShotGrid
    if not ay_entitity_list_id or not entity_list:
        # in AYON entity list have unique names
        log.debug(f"Creating entity list for ShotGrid Playlist {sg_playlist['id']} in AYON")
        entity_list = _get_entity_list_by_name(project_name, sg_playlist["code"])
        if entity_list:
            # in this case the sg playlist has been retired and re-created, so let's reconnect it the ayon one
            data = {"attrib": {"shotgridId": sg_playlist["id"], "shotgridType": sg_playlist["type"]}}
            result = ayon_api.raw_patch(f"projects/{project_name}/lists/{entity_list['id']}", json=data)
            if not result.ok:
                log.error(f"Failed to update entity list {entity_list['label']} with data: {data}")
                return

            sg_session.update("Playlist", sg_playlist["id"], {"sg_ayon_id": entity_list["id"]})
            log.info(f"Entity list {entity_list['label']} already exists in AYON, reconnecting playlist to it.")
        else:
            data = {
                "label": sg_playlist["code"],
                "entity_type": "version",
                "attrib": {
                    "shotgridId": sg_playlist["id"],
                    "shotgridType": sg_playlist["type"]
                },
                "tags": sg_playlist["tag_list"],
                "active": not sg_playlist["locked"],
                "data": {
                    "sg_type": sg_playlist["sg_type"],
                },
            }

            result = ayon_api.raw_post(f"projects/{project_name}/lists", json=data)
            if not result.ok:
                log.error(f"Failed to create entity list: {result.status} - {result.data}")
                return

            data = {"sg_ayon_id": result.data["id"], "project": sg_project}
            sg_playlist_ = sg_session.update("Playlist", sg_playlist["id"], data)
            if not sg_playlist_:
                log.error(f"Failed to update ShotGrid Playlist with AYON entity list ID")
                return

            entity_list = result.data

    # update containing versions
    if sg_event_meta["type"] == "attribute_change" and sg_event_meta["attribute_name"] == "versions":
        log.debug(f"updating versions in entity list {entity_list['id']} from ShotGrid Playlist {sg_playlist['code']}")

        for added_version in sg_event_meta["added"]:
            log.debug(f"Adding version {added_version['id']} to entity list {entity_list['id']}")
            sg_version = sg_session.find_one("Version", [["project", "is", sg_project], ["id", "is", added_version["id"]]], ["sg_ayon_id"])
            if not sg_version:
                log.error(f"Unable to find version from id {added_version['id']}")
                return

            if not sg_version.get("sg_ayon_id"):
                log.error(f"Version {added_version['id']} does not have a corresponding AYON ID, skipping")
                return

            data = {"entityId": str(sg_version["sg_ayon_id"])}

            # add version to entity list
            result = ayon_api.raw_post(f"projects/{project_name}/lists/{entity_list['id']}/items", json=data)
            if result.status != 201:
                log.debug(f"Failed to update entity list with version: {added_version['id']}")
            else:
                log.debug(f"Added version {added_version['id']} to entity list {entity_list['id']}")

        for removed_version in sg_event_meta["removed"]:
            log.debug(f"Removing version {removed_version['id']} from entity list {entity_list['id']}")
            sg_version = sg_session.find_one("Version", [["project", "is", sg_project], ["id", "is", removed_version["id"]]], ["sg_ayon_id"])

            if not sg_version:
                log.error(f"Version {removed_version['id']} does not exists in ShotGrid, skipping")
                continue

            if not sg_version.get("sg_ayon_id"):
                log.error(f"Version {removed_version['id']} does not have a corresponding AYON ID, skipping")
                continue

            # remove version from entity list
            list_item_id = _get_entity_list_item_from_entity_id(project_name, entity_list["id"], sg_version['sg_ayon_id'])
            result = ayon_api.raw_delete(f"projects/{project_name}/lists/{entity_list['id']}/items/{list_item_id}")
            if result.status != 204:
                log.debug(f"Failed to remove version {removed_version['id']} from entity list {entity_list['id']}")
            else:
                log.debug(f"Removed version {removed_version['id']} from entity list {entity_list['id']}")

    # update entity list label
    attributes_to_sync_map = {
        # FLOW : AYON
        "code": "label",
        "tag_list": "tags",
        "locked": "active",
        "sg_type": "sg_type",
    }
    sg_attribute_to_update = sg_event_meta.get("attribute_name")
    if sg_attribute_to_update is None:
        log.error("Unable to find attribute_name from metadata")
        return

    if sg_event_meta["type"] == "attribute_change" and sg_attribute_to_update in attributes_to_sync_map.keys():

        new_value = sg_event_meta.get("new_value")
        if new_value is None:
            log.warning(f"Attribute {sg_attribute_to_update} has no new value, skipping.")
            return

        # locked is the opposite of active in AYON
        new_value = not new_value if sg_attribute_to_update == "locked" else new_value

        if sg_attribute_to_update == "code":
            log.debug(f"Updating entity list label from ShotGrid Playlist {sg_playlist['code']}")

            # I need to check if the entity list name is not already used
            existing_entity_list = _get_entity_list_by_name(project_name, new_value)
            if existing_entity_list:
                log.error(
                    f"Entity list {entity_list['label']} already exists in AYON, "
                    f"skipping label update because labels should be unique."
                )
                return

        if sg_attribute_to_update == "sg_type":
            data = {"data": entity_list["data"]}
            data["data"]["sg_type"] = new_value
        else:
            data = {attributes_to_sync_map[sg_attribute_to_update]: new_value}

        result = ayon_api.raw_patch(f"projects/{project_name}/lists/{entity_list['id']}", json=data)

        if result.status != 204:
            log.error(f"Failed to update entity list with new label")
        else:
            log.debug(f"Updated entity list attribute: {attributes_to_sync_map[sg_attribute_to_update]} "
                      f"with new value: {new_value}")

        log.debug("Entity list updated with versions from ShotGrid Playlist.")


def _get_ayon_parent_entity(
    ayon_entity_hub,
    project_code_field,
    sg_ay_dict,
    sg_parent_field,
    sg_project,
    sg_session,
    addon_settings
):
    """Tries to find parent entity in AYON

    Args:
        ayon_entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
        project_code_field (str): The Shotgrid project code field.
        sg_ay_dict (dict): The ShotGrid entity ready for AYON consumption.:
        sg_parent_field (str): 'project'|'sequence'
        sg_project (dict): The ShotGrid project.
        sg_session (shotgun_api3.Shotgun): The ShotGrid API session.
        addon_settings (Optional[dict]): A dictionary of Settings. Used to
            query location of custom folders (`shots`, `sequences`)

    Returns:
        ay_entity (ayon_api.entity_hub.EntityHub.Entity):
            FolderEntity|ProjectEntity
    """
    default_task_type = addon_settings[
        "compatibility_settings"]["default_task_type"]

    shotgrid_type = sg_ay_dict["attribs"][SHOTGRID_TYPE_ATTRIB]
    sg_parent = sg_ay_dict["data"].get(sg_parent_field)
    ay_parent_entity = None

    if shotgrid_type in ("Shot", "Sequence", "Episode", "Asset"):
        ay_parent_entity = get_reparenting_from_settings(
            ayon_entity_hub,
            sg_ay_dict,
            addon_settings
        )

        # Reparenting Asset under an AssetCategory ?
        # if sg_asset_type is defined in the data, that's because
        # the Asset needs to be parented to the AssetCategory.
        sg_asset_type = sg_ay_dict["data"].get("sg_asset_type")
        if (
            shotgrid_type == "Asset"
            and sg_asset_type
        ):
            name = slugify_string(sg_asset_type)
            ay_parent_entity = ay_parent_entity or ayon_entity_hub.project_entity
            # Gather or create AssetCategory parent.
            for child in ay_parent_entity.children:
                if (
                    child.folder_type == "AssetCategory"
                    and child.name.lower() == name.lower()
                ):
                    ay_parent_entity = child
                    break
            else:
                ay_parent_entity = create_new_ayon_entity(
                    sg_session,
                    ayon_entity_hub,
                    ay_parent_entity,
                    {
                        "folder_type": "AssetCategory",
                        "type": "AssetCategory",
                        "name": name.lower(),
                        "label": sg_asset_type,
                        "data": {CUST_FIELD_CODE_ID: name},
                        "attribs": {
                            SHOTGRID_ID_ATTRIB: name.lower(),
                            SHOTGRID_TYPE_ATTRIB: "AssetCategory"
                        }
                    },
                )

    if ay_parent_entity is None:
        # INFO: Parent entity might not be added in SG so this needs to
        # be handled with optional way.
        if not isinstance(sg_parent, dict):  # None (project) or str (AssetCategory)
            # Parent is the project
            log.debug(f"ShotGrid Parent is the Project: {sg_project}")
            ay_parent_entity = ayon_entity_hub.project_entity

        else:
            # Find parent entity ID
            sg_parent_entity_dict = get_sg_entity_as_ay_dict(
                sg_session,
                sg_parent["type"],
                sg_parent["id"],
                project_code_field,
                default_task_type,
            )

            log.debug(f"ShotGrid Parent entity: {sg_parent_entity_dict}")
            ay_parent_entity = ayon_entity_hub.get_or_query_entity_by_id(
                sg_parent_entity_dict["data"].get(CUST_FIELD_CODE_ID),
                [
                    (
                        "task"
                        if sg_parent_entity_dict["type"] == "task"
                        else "folder"
                    )
                ],
            )
    return ay_parent_entity


def _update_sg_id(ay_entity, custom_attribs_map, sg_ay_dict, project_entity):
    ayon_entity_sg_id = str(
        ay_entity.attribs.get_attribute(SHOTGRID_ID_ATTRIB).value)
    # Ensure AYON Entity has the correct Shotgrid ID
    ay_shotgrid_id = str(
        sg_ay_dict["attribs"].get(SHOTGRID_ID_ATTRIB, ""))
    if ayon_entity_sg_id != ay_shotgrid_id:
        ay_entity.attribs.set(
            SHOTGRID_ID_ATTRIB,
            ay_shotgrid_id
        )
        ay_entity.attribs.set(
            SHOTGRID_TYPE_ATTRIB,
            sg_ay_dict["type"]
        )
    update_ay_entity_custom_attributes(
        ay_entity, sg_ay_dict, custom_attribs_map, ay_project=project_entity
    )

    return ay_entity


def update_ayon_entity_from_sg_event(
    sg_event: Dict,
    sg_project: Dict,
    sg_session: shotgun_api3.Shotgun,
    ayon_entity_hub: ayon_api.entity_hub.EntityHub,
    sg_enabled_entities: List[str],
    project_code_field: str,
    addon_settings: Dict[str, Any],
    custom_attribs_map: Optional[Dict[str, str]] = None,
):
    """Try to update an entity in AYON.

    Args:
        sg_event (dict): The `meta` key from a ShotGrid Event.
        sg_project (dict): The ShotGrid project.
        sg_session (shotgun_api3.Shotgun): The ShotGrid API session.
        ayon_entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
        sg_enabled_entities (list[str]): List of entity strings enabled.
        project_code_field (str): The ShotGrid project code field.
        addon_settings (dict): A dictionary of Settings.
        custom_attribs_map (dict): A dictionary that maps ShotGrid
            attributes to AYON attributes.

    Returns:
        ay_entity (ayon_api.entity_hub.EntityHub.Entity): The modified entity.

    """
    default_task_type = addon_settings[
        "compatibility_settings"]["default_task_type"]

    sg_ay_dict = get_sg_entity_as_ay_dict(
        sg_session,
        sg_event["entity_type"],
        sg_event["entity_id"],
        project_code_field,
        default_task_type,
        custom_attribs_map=custom_attribs_map
    )

    if sg_event["entity_type"] == "Asset":
        rvx_validate_sg_asset(sg_ay_dict, sg_session)
    elif sg_event["entity_type"] == "Shot":
        rvx_validate_sg_shot(sg_ay_dict, sg_session)
    elif sg_event["entity_type"] == "Sequence":
        rvx_validate_sg_sequence(sg_ay_dict, sg_session)

    if not sg_ay_dict:
        log.warning(
            f"Entity {sg_event['entity_type']} <{sg_event['entity_id']}> "
            "no longer exists in ShotGrid, aborting..."
        )
        return

    if sg_ay_dict["type"].lower() == "comment":
        if sg_ay_dict["attribs"]["shotgridType"] == "Note":
            handle_comment(
                sg_ay_dict,
                sg_session,
                ayon_entity_hub,
            )
        else:
            handle_reply(
                sg_ay_dict,
                sg_session,
                ayon_entity_hub,
            )
        return

    # if the entity does not have an AYON ID, try to create it
    # and no need to update
    if not sg_ay_dict["data"].get(CUST_FIELD_CODE_ID):
        log.debug(f"Creating AYON Entity: {sg_ay_dict}")
        try:
            create_ay_entity_from_sg_event(
                sg_event,
                sg_project,
                sg_session,
                ayon_entity_hub,
                sg_enabled_entities,
                project_code_field,
                custom_attribs_map,
                addon_settings
            )
        except Exception:
            log.debug("AYON Entity could not be created", exc_info=True)
        return

    ay_entity = ayon_entity_hub.get_or_query_entity_by_id(
        sg_ay_dict["data"].get(CUST_FIELD_CODE_ID),
        [sg_ay_dict["type"]]
    )

    if not ay_entity:
        raise ValueError("Unable to update a non existing entity.")

    # make sure the entity is not immutable
    if (
        ay_entity.immutable_for_hierarchy
        and sg_event["attribute_name"] in SG_RESTRICTED_ATTR_FIELDS
    ):
        raise ValueError("Entity is immutable, aborting...")

    # Ensure AYON Entity has the correct ShotGrid ID
    ayon_entity_sg_id = str(
        ay_entity.attribs.get(SHOTGRID_ID_ATTRIB, "")
    )
    sg_entity_sg_id = str(
        sg_ay_dict["attribs"].get(SHOTGRID_ID_ATTRIB, "")
    )


    # We need to check for existence in `ayon_entity_sg_id` as it could be
    # that it's a new entity and it doesn't have a ShotGrid ID yet.
    if ayon_entity_sg_id and ayon_entity_sg_id != sg_entity_sg_id:
        log.error("Mismatching ShotGrid IDs, aborting...")
        raise ValueError("Mismatching ShotGrid IDs, aborting...")

    # Update entity label.
    if ay_entity.entity_type != "version":
        log.debug(f"Updating AYON Entity: {ay_entity.name}")
    else:
        log.debug(f"Updating AYON Entity: {ay_entity}")

    # TODO: Only update the updated fields in the event
    update_ay_entity_custom_attributes(
        ay_entity,
        sg_ay_dict,
        custom_attribs_map,
        ay_project=ayon_entity_hub.project_entity
    )

    ayon_entity_hub.commit_changes()

    if sg_ay_dict["data"].get(CUST_FIELD_CODE_ID) != ay_entity.id:
        sg_session.update(
            sg_ay_dict["attribs"][SHOTGRID_TYPE_ATTRIB],
            sg_ay_dict["attribs"][SHOTGRID_ID_ATTRIB],
            {
                CUST_FIELD_CODE_ID: ay_entity.id
            }
        )

    ay_entity.attribs.set(
        SHOTGRID_ID_ATTRIB,
        sg_ay_dict["attribs"].get(SHOTGRID_ID_ATTRIB, "")
    )
    ay_entity.attribs.set(
        SHOTGRID_TYPE_ATTRIB,
        sg_ay_dict["attribs"].get(SHOTGRID_TYPE_ATTRIB, "")
    )

    if sg_ay_dict["attribs"]["shotgridType"] == "Asset":
        rvx_update_asset(ay_entity, sg_ay_dict, sg_session, ayon_entity_hub)

    return ay_entity


def remove_ayon_entity_from_sg_event(
    sg_event: Dict,
    sg_session: shotgun_api3.Shotgun,
    ayon_entity_hub: ayon_api.entity_hub.EntityHub,
    project_code_field: str,
    addon_settings: Dict[str, Any],
):
    """Try to remove an entity in AYON.

    Args:
        sg_event (dict): The `meta` key from a ShotGrid Event.
        sg_session (shotgun_api3.Shotgun): The ShotGrid API session.
        ayon_entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
        project_code_field (str): The ShotGrid field that contains the AYON ID.
        addon_settings (dict): A dictionary of Settings.
    """
    default_task_type = addon_settings[
        "compatibility_settings"]["default_task_type"]

    sg_ay_dict = get_sg_entity_as_ay_dict(
        sg_session,
        sg_event["entity_type"],
        sg_event["entity_id"],
        project_code_field,
        default_task_type,
        retired_only=True
    )

    if not sg_ay_dict:
        sg_ay_dict = get_sg_entity_as_ay_dict(
            sg_session,
            sg_event["entity_type"],
            sg_event["entity_id"],
            project_code_field,
            default_task_type,
            retired_only=False,
        )
        if sg_ay_dict:
            log.info(
                f"No need to remove entity {sg_event['entity_type']} "
                f"<{sg_event['entity_id']}>, it's not retired anymore."
            )
            return
        else:
            log.warning(
                f"Entity {sg_event['entity_type']} <{sg_event['entity_id']}> "
                "no longer exists in ShotGrid."
            )

    if not sg_ay_dict["data"].get(CUST_FIELD_CODE_ID):
        log.warning(
            "Entity does not have an AYON ID, aborting..."
        )
        return

    ay_entity = ayon_entity_hub.get_or_query_entity_by_id(
        sg_ay_dict["data"].get(CUST_FIELD_CODE_ID),
        ["task" if sg_ay_dict.get("type").lower() == "task" else "folder"]
    )

    if not ay_entity:
        raise ValueError("Unable to update a non existing entity.")

    if sg_ay_dict["data"].get(CUST_FIELD_CODE_ID) != ay_entity.id:
        raise ValueError("Mismatching ShotGrid IDs, aborting...")

    if not ay_entity.immutable_for_hierarchy:
        log.info(f"Deleting AYON entity: {ay_entity}")
        ayon_entity_hub.delete_entity(ay_entity)
    else:
        log.info("Entity is immutable.")
        ay_entity.attribs.set(SHOTGRID_ID_ATTRIB, SHOTGRID_REMOVED_VALUE)

    ayon_entity_hub.commit_changes()
