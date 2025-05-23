import os
import unittest
from dotenv import load_dotenv

import ayon_api
from shotgun_api3 import Shotgun
from ayon_api.entity_hub import EntityHub


from ayon_shotgrid_hub.update_from_shotgrid import create_ay_entity_from_sg_event, update_ayon_entity_from_sg_event

load_dotenv(os.path.expanduser("~/.env"))


class TestUpdateFromShotGrid(unittest.TestCase):

    PROJECT = "Tests"
    SHOTGUN_URL = "https://apavatn.shotgrid.autodesk.com"
    SG_SCRIPT_NAME = os.getenv("SG_SCRIPT_NAME")
    SG_SCRIPT_KEY = os.getenv("SG_API_KEY")
    PROXY_URL = os.getenv("HTTP_PROXY").replace("http://", "")
    sg = Shotgun(SHOTGUN_URL, script_name=SG_SCRIPT_NAME, api_key=SG_SCRIPT_KEY, http_proxy=PROXY_URL)
    sg_project = sg.find_one("Project", [["code", "is", PROJECT]], ["code"])

    test_sub_asset_name_a = "pedestrian"
    test_sub_asset_name_b = "human"
    test_variant_asset_name = "pedestrian_A"
    test_show_asset_name = "cliff"

    sg_test_show_asset = sg.find_one(
        "Asset", [["project.Project.code", "is", PROJECT], ["code", "is", test_show_asset_name]], ["code"]
    )

    ayon_api.init_service()
    entity_hub = EntityHub(PROJECT, allow_data_changes=True)

    addon_settings = ayon_api.get_addons_settings(project_name=PROJECT)["shotgrid"]
    settings = ayon_api.get_service_addon_settings()
    project_code_field = settings["shotgrid_project_code_field"]
    service_settings = settings["service_settings"]
    compatibility_settings = settings["compatibility_settings"]
    sg_enabled_entities = compatibility_settings["shotgrid_enabled_entities"]
    default_task_type = compatibility_settings["default_task_type"]
    folder_parenting = compatibility_settings["folder_parenting"]

    custom_attribs_map = {
        attr["ayon"]: attr["sg"] for attr in compatibility_settings["custom_attribs_map"] if attr["sg"]
    }

    # @classmethod
    # def setUpClass(cls):
    #     cls.sg_test_sub_asset_a = cls._get_or_create_test_sub_asset(cls.test_sub_asset_name_a)
    #     cls.sg_test_sub_asset_b = cls._get_or_create_test_sub_asset(cls.test_sub_asset_name_b)
    #     cls.sg_test_variant_asset = cls._get_or_create_test_variant_asset()
        
    def setUp(self):
        self.sg_test_sub_asset_a = self._get_or_create_test_sub_asset(self.test_sub_asset_name_a)
        self.sg_test_sub_asset_b = self._get_or_create_test_sub_asset(self.test_sub_asset_name_b)
        self.sg_test_variant_asset = self._get_or_create_test_variant_asset()

    def _get_or_create_test_sub_asset(self, name):
        sg_asset = self.sg.find_one(
            "Asset",
            [["project.Project.code", "is", self.PROJECT], ["code", "is", name]],
            ["code", "sg_ayon_folder_type", "parents", "sg_asset_type"],
        )
        if not sg_asset:
            sg_asset = self.sg.create(
                "Asset",
                {
                    "project": self.sg_project,
                    "code": name,
                    "sg_ayon_folder_type": "SubAsset",
                    "sg_asset_type": "Character",
                    "parents": [],
                },
            )
        else:

            self.sg.update("Asset", sg_asset["id"], {"parents": []})
            self.sg.update("Asset", sg_asset["id"], {"sg_ayon_folder_type": "SubAsset"})
            self.sg.update("Asset", sg_asset["id"], {"sg_asset_type": "Character"})
            sg_asset["sg_ayon_folder_type"] = "SubAsset"
            sg_asset["sg_asset_type"] = "Character"
            sg_asset["parents"] = []

        return sg_asset

    def _get_or_create_test_variant_asset(self):
        sg_test_variant_asset = self.sg.find_one(
            "Asset",
            [["project.Project.code", "is", self.PROJECT], ["code", "is", self.test_variant_asset_name]],
            ["code", "parents", "sg_ayon_folder_type"],
        )
        if not sg_test_variant_asset:
            sg_test_variant_asset = self.sg.create(
                "Asset",
                {
                    "project": self.sg_project,
                    "code": self.test_variant_asset_name,
                    "sg_ayon_folder_type": "VariantAsset",
                    "parents": [self.sg_test_sub_asset_a],
                    "sg_asset_type": "Character",
                },
            )
        else:
            self.sg.update("Asset", sg_test_variant_asset["id"], {"parents": [self.sg_test_sub_asset_a]})
            self.sg.update("Asset", sg_test_variant_asset["id"], {"sg_ayon_folder_type": "VariantAsset"})
            self.sg.update("Asset", sg_test_variant_asset["id"], {"sg_asset_type": "Character"})
            sg_test_variant_asset["sg_ayon_folder_type"] = "VariantAsset"
            sg_test_variant_asset["sg_asset_type"] = "Character"
            sg_test_variant_asset["parents"] = [self.sg_test_sub_asset_a]

        return sg_test_variant_asset

    def _delete_all_ay_assets(self):
        children = self.entity_hub.project_entity.get_children()
        assets = None
        for i in children:
            if i["name"] == "assets":
                assets = i
                break

        if assets:
            self.entity_hub.delete_entity(assets)
            self.entity_hub.commit_changes()

    def _create_ay_test_sub_asset_a(self):
        sg_event = {
            "event_type": "Shotgun_Entity_Created",
            "entity_type": "Asset",
            "entity_id": self.sg_test_sub_asset_a["id"],
            "project_id": self.sg_project["id"],
        }

        return create_ay_entity_from_sg_event(
            sg_event=sg_event,
            sg_project=self.sg_project,
            sg_session=self.sg,
            ayon_entity_hub=self.entity_hub,
            sg_enabled_entities=self.sg_enabled_entities,
            project_code_field=self.project_code_field,
            custom_attribs_map=self.custom_attribs_map,
            addon_settings=self.addon_settings,
        )

    def _create_ay_test_sub_asset_b(self):
        sg_event = {
            "event_type": "Shotgun_Entity_Created",
            "entity_type": "Asset",
            "entity_id": self.sg_test_sub_asset_b["id"],
            "project_id": self.sg_project["id"],
        }

        return create_ay_entity_from_sg_event(
            sg_event=sg_event,
            sg_project=self.sg_project,
            sg_session=self.sg,
            ayon_entity_hub=self.entity_hub,
            sg_enabled_entities=self.sg_enabled_entities,
            project_code_field=self.project_code_field,
            custom_attribs_map=self.custom_attribs_map,
            addon_settings=self.addon_settings,
        )

    def _create_ay_test_variant_asset(self):
        sg_event = {
            "event_type": "Shotgun_Entity_Created",
            "entity_type": "Asset",
            "entity_id": self.sg_test_variant_asset["id"],
            "project_id": self.sg_project["id"],
        }
        return create_ay_entity_from_sg_event(
            sg_event=sg_event,
            sg_project=self.sg_project,
            sg_session=self.sg,
            ayon_entity_hub=self.entity_hub,
            sg_enabled_entities=self.sg_enabled_entities,
            project_code_field=self.project_code_field,
            custom_attribs_map=self.custom_attribs_map,
            addon_settings=self.addon_settings,
        )

    def test_create_sub_asset(self):
        self._delete_all_ay_assets()
        entity = self._create_ay_test_sub_asset_a()

        self.assertEqual("SubAsset", entity.folder_type)
        self.assertEqual(self.test_sub_asset_name_a, entity.name)
        self.assertEqual("character", entity.parent.name)

    def test_create_variant_asset(self):
        self._delete_all_ay_assets()

        # recreate first the subAsset in order for the variant asset to be parented under it
        self._create_ay_test_sub_asset_a()
        entity = self._create_ay_test_variant_asset()

        expected_short_name = self.test_variant_asset_name.split("_")[-1]  # pedestrian_A -> A

        self.assertEqual("VariantAsset", entity.folder_type)
        self.assertEqual(expected_short_name, entity.name)
        self.assertEqual(expected_short_name, entity.label)
        self.assertEqual(self.test_sub_asset_name_a, entity.parent.name)
        self.assertEqual("character", entity.parent.parent.name)

    def test_update_from_variant_to_sub_asset(self):
        self._delete_all_ay_assets()
        self._create_ay_test_sub_asset_a()
        ay_test_variant = self._create_ay_test_variant_asset()

        # change variant asset to sub asset
        self.sg.update("Asset", self.sg_test_variant_asset["id"], {"sg_ayon_folder_type": "SubAsset"})
        self.sg.update("Asset", self.sg_test_variant_asset["id"], {"parents": []})
        self.sg_test_variant_asset["sg_ayon_folder_type"] = "SubAsset"
        self.sg_test_variant_asset["parents"] = []

        sg_event = {
            "event_type": "attribute_change",
            "entity_type": "Asset",
            "entity_id": self.sg_test_variant_asset["id"],
            "project_id": self.sg_project["id"],
        }
        update_ayon_entity_from_sg_event(
            sg_event=sg_event,
            sg_project=self.sg_project,
            sg_session=self.sg,
            ayon_entity_hub=self.entity_hub,
            sg_enabled_entities=self.sg_enabled_entities,
            project_code_field=self.project_code_field,
            custom_attribs_map=self.custom_attribs_map,
            addon_settings=self.addon_settings,
        )
        self.assertEqual("SubAsset", ay_test_variant.folder_type)
        self.assertEqual("character", ay_test_variant.parent.name)
        self.assertEqual(self.test_variant_asset_name, ay_test_variant.name)
        self.assertEqual(self.test_variant_asset_name, ay_test_variant.label)

    def test_update_from_sub_to_variant_asset(self):
        self._delete_all_ay_assets()
        ay_test_sub_asset_a = self._create_ay_test_sub_asset_a()
        ay_test_sub_asset_b = self._create_ay_test_sub_asset_b()
        ay_test_variant = self._create_ay_test_variant_asset()

        # change sub asset b to variant asset and parent it under sub asset a
        self.sg.update("Asset", self.sg_test_sub_asset_b["id"], {"sg_ayon_folder_type": "VariantAsset"})
        self.sg.update("Asset", self.sg_test_sub_asset_b["id"], {"parents": [self.sg_test_sub_asset_a]})
        self.sg_test_sub_asset_b["sg_ayon_folder_type"] = "VariantAsset"
        self.sg_test_sub_asset_b["parents"] = [self.sg_test_sub_asset_a]

        sg_event = {
            "event_type": "attribute_change",
            "entity_type": "Asset",
            "entity_id": self.sg_test_sub_asset_b["id"],
            "project_id": self.sg_project["id"],
        }
        update_ayon_entity_from_sg_event(
            sg_event=sg_event,
            sg_project=self.sg_project,
            sg_session=self.sg,
            ayon_entity_hub=self.entity_hub,
            sg_enabled_entities=self.sg_enabled_entities,
            project_code_field=self.project_code_field,
            custom_attribs_map=self.custom_attribs_map,
            addon_settings=self.addon_settings,
        )
        # original variant asset should not be updated
        self.assertEqual("VariantAsset", ay_test_variant.folder_type)
        self.assertEqual(self.test_sub_asset_name_a, ay_test_variant.parent.name)

        # original sub asset a should not be updated
        self.assertEqual("SubAsset", ay_test_sub_asset_a.folder_type)
        self.assertEqual("character", ay_test_sub_asset_a.parent.name)

        # b should be updated to variant asset and under a
        self.assertEqual("VariantAsset", ay_test_sub_asset_b.folder_type)
        self.assertEqual(self.test_sub_asset_name_b.split("_")[-1], ay_test_sub_asset_b.name)
        self.assertEqual(self.test_sub_asset_name_a, ay_test_sub_asset_b.parent.name)

    def test_update_asset_type(self):
        self._delete_all_ay_assets()
        ay_test_sub_asset_b = self._create_ay_test_sub_asset_b()

        self.sg.update("Asset", self.sg_test_sub_asset_b["id"], {"sg_asset_type": "Environment"})
        self.sg_test_sub_asset_b["sg_asset_type"] = "Environment"

        sg_event = {
            "event_type": "attribute_change",
            "entity_type": "Asset",
            "entity_id": self.sg_test_sub_asset_b["id"],
            "project_id": self.sg_project["id"],
        }
        update_ayon_entity_from_sg_event(
            sg_event=sg_event,
            sg_project=self.sg_project,
            sg_session=self.sg,
            ayon_entity_hub=self.entity_hub,
            sg_enabled_entities=self.sg_enabled_entities,
            project_code_field=self.project_code_field,
            custom_attribs_map=self.custom_attribs_map,
            addon_settings=self.addon_settings,
        )

        self.assertEqual("SubAsset", ay_test_sub_asset_b.folder_type)
        self.assertEqual("environment", ay_test_sub_asset_b.parent.name)
