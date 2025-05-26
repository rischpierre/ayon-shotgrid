
import unittest
from unittest.mock import MagicMock, patch
from ayon_shotgrid_hub.rvx_update_from_shotgrid import rvx_validate_sg_asset, rvx_update_asset


class TestRVXValidateSGAsset(unittest.TestCase):
    def setUp(self):
        self.sg_mock = MagicMock()
        self.sg_ay_dict = {
            "attribs": {
                "shotgridId": 123
            }
        }

    def test_asset_not_found(self):
        self.sg_mock.find_one.return_value = None
        with self.assertRaises(ValueError) as context:
            rvx_validate_sg_asset(self.sg_ay_dict, self.sg_mock)

    def test_valid_sub_asset(self):
        self.sg_mock.find_one.return_value = {
            "sg_ayon_folder_type": "SubAsset",
            "code": "pedestrian",
            "parents": [],
            "assets": [{"id": 1}]
        }
        try:
            rvx_validate_sg_asset(self.sg_ay_dict, self.sg_mock)
        except:
            self.fail()

        # with no assets
        self.sg_mock.find_one.return_value = {
            "sg_ayon_folder_type": "SubAsset",
            "code": "pedestrian",
            "parents": [],
            "assets": [],
        }
        try:
            rvx_validate_sg_asset(self.sg_ay_dict, self.sg_mock)
        except:
            self.fail()

    def test_valid_variant_asset(self):
        self.sg_mock.find_one.side_effect = [
            {
                "sg_ayon_folder_type": "VariantAsset",
                "code": "pedestrian",
                "parents": [{"id": 1}],
                "assets": [],
                "sg_asset_type": "Character"
            },
            {
                "sg_asset_type": "Character"
            }
        ]
        try:
            rvx_validate_sg_asset(self.sg_ay_dict, self.sg_mock)
        except:
            self.fail()

    def test_variant_asset_no_parent(self):
        self.sg_mock.find_one.return_value = {
            "sg_ayon_folder_type": "VariantAsset",
            "code": "pedestrian",
            "parents": [],
            "assets": []
        }
        with self.assertRaises(ValueError) as context:
            rvx_validate_sg_asset(self.sg_ay_dict, self.sg_mock)

    def test_variant_asset_with_children(self):
        self.sg_mock.find_one.return_value = {
            "sg_ayon_folder_type": "VariantAsset",
            "code": "pedestrian",
            "parents": [{"id": 1}],
            "assets": [{"id": 2}]
        }
        with self.assertRaises(ValueError) as context:
            rvx_validate_sg_asset(self.sg_ay_dict, self.sg_mock)

    def test_variant_asset_parent_type_mismatch(self):
        # side effect is used to simulate multiple return values for consecutive calls
        self.sg_mock.find_one.side_effect = [
            {
                "sg_ayon_folder_type": "VariantAsset",
                "code": "pedestrian",
                "parents": [{"id": 1}],
                "assets": [],
                "sg_asset_type": "Character",
            },
            {
                "sg_asset_type": "Environment",
            }
        ]
        with self.assertRaises(ValueError) as context:
            rvx_validate_sg_asset(self.sg_ay_dict, self.sg_mock)

    def test_sub_asset_with_parents_should_raise(self):
        self.sg_mock.find_one.return_value = {
            "sg_ayon_folder_type": "SubAsset",
            "code": "pedestrian",
            "parents": [{"id": 1}],
            "assets": []
        }
        with self.assertRaises(ValueError) as context:
            rvx_validate_sg_asset(self.sg_ay_dict, self.sg_mock)
        self.assertIn("should not have parents in shotgrid", str(context.exception))

    def test_sub_asset_with_children_type_mismatch(self):
        self.sg_mock.find_one.return_value = {
            "sg_ayon_folder_type": "SubAsset",
            "code": "pedestrian",
            "parents": [],
            "assets": [{"id": 2}],
            "sg_asset_type": "Environment",
        }
        self.sg_mock.find.return_value = [
            {"code": "pedestrian_A", "sg_asset_type": "Character"}
        ]
        with self.assertRaises(ValueError) as context:
            rvx_validate_sg_asset(self.sg_ay_dict, self.sg_mock)



class TestRVXUpdateAsset(unittest.TestCase):
    def setUp(self):
        self.ay_entity = MagicMock()
        self.sg_ay_dict = {
            "attribs": {
                "shotgridId": 123
            }
        }
        self.sg = MagicMock()
        self.ay_entity_hub = MagicMock()

    @patch('ayon_shotgrid_hub.rvx_update_from_shotgrid.ayon_api')
    def test_update_folder_type(self, ayon_api):
        ayon_api.get_folder_by_name.return_value = {"name": "pedestrian", "id": 123}
        self.sg.find_one.return_value = {
            "sg_ayon_folder_type": "SubAsset",
            "sg_asset_type": "Character",
            "parents": [],
        }
        self.ay_entity.folder_type = "VariantAsset"

        rvx_update_asset(self.ay_entity, self.sg_ay_dict, self.sg, self.ay_entity_hub)

        self.ay_entity.set_folder_type.assert_called_once_with("SubAsset")
        self.ay_entity_hub.commit_changes.assert_called_once()

    def test_variant_asset_reparent_and_rename(self):
        self.sg.find_one.side_effect = [
            {
                "sg_ayon_folder_type": "VariantAsset",
                "sg_asset_type": "Character",
                "parents": [{"id": 1}],
            },
            {
                "sg_ayon_id": 123,
                "code": "pedestrian",
            },
        ]
        self.ay_entity.name = "pedestrian_A"
        self.ay_entity_hub.get_or_query_entity_by_id.return_value = "pedestrian"

        rvx_update_asset(self.ay_entity, self.sg_ay_dict, self.sg, self.ay_entity_hub)

        self.ay_entity.set_parent.assert_called_once_with("pedestrian")
        self.ay_entity.set_label.assert_called_once_with("A")
        self.ay_entity.set_name.assert_called_once_with("A")
        self.ay_entity_hub.commit_changes.assert_called_once()

    @patch('ayon_shotgrid_hub.rvx_update_from_shotgrid.ayon_api')
    def test_sub_asset_reparent(self, ayon_api):
        self.sg.find_one.return_value = {
            "sg_ayon_folder_type": "SubAsset",
            "sg_asset_type": "Environment",
            "parents": [],
        }
        ayon_api.get_folder_by_name.return_value={"id": "new_parent_id"}
        self.ay_entity.parent.label = "OldParent"
        self.ay_entity_hub.get_or_query_entity_by_id.return_value = MagicMock()

        rvx_update_asset(self.ay_entity, self.sg_ay_dict, self.sg, self.ay_entity_hub)

        self.ay_entity.set_parent.assert_called_once()
        self.ay_entity_hub.commit_changes.assert_called_once()

    @patch('ayon_shotgrid_hub.rvx_update_from_shotgrid.ayon_api')
    def test_no_changes(self, ayon_api):
        ayon_api.get_folder_by_name.return_value = {"name": "pedestrian", "id": 123}
        self.sg.find_one.return_value = {
            "sg_ayon_folder_type": "SubAsset",
            "sg_asset_type": "Character",
            "parents": [],
        }
        self.ay_entity.folder_type = "SubAsset"
        self.ay_entity.parent.name = "Character"

        rvx_update_asset(self.ay_entity, self.sg_ay_dict, self.sg, self.ay_entity_hub)

        self.ay_entity.set_folder_type.assert_not_called()
        self.ay_entity.set_parent.assert_not_called()
        self.ay_entity.set_label.assert_not_called()
        self.ay_entity.set_name.assert_not_called()
        self.ay_entity_hub.commit_changes.assert_called_once()


if __name__ == "__main__":
    unittest.main()