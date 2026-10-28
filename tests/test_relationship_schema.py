"""Offline MCP contract checks; no request is sent to Visual Paradigm."""
import unittest
from mcp_server import BY_NAME, validate


class RelationshipSchemaTests(unittest.TestCase):
    def test_connector_style_is_narrow_and_validated(self):
        schema = BY_NAME["set_connector_style"]["inputSchema"]
        ids = {"diagram_id": "d", "element_id": "e"}
        for style in ["rectilinear", "oblique"]:
            validate({**ids, "style": style}, schema)
        for arguments in [ids, {**ids, "style": "curve"}, {**ids, "style": 1},
                          {**ids, "style": "rectilinear", "from_id": "other"}]:
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                validate(arguments, schema)

    def test_node_delete_and_guard_are_narrow(self):
        ids = {"diagram_id": "d", "element_id": "e"}
        validate(ids, BY_NAME["delete_disconnected_node"]["inputSchema"])
        with self.assertRaises(ValueError):
            validate({**ids, "cascade": True}, BY_NAME["delete_disconnected_node"]["inputSchema"])
        schema = BY_NAME["set_flow_guard"]["inputSchema"]
        validate({**ids, "guard": "ready"}, schema)
        for extra in [{}, {"guard": ""}, {"guard": "ready", "from_id": "other"}]:
            with self.assertRaises(ValueError): validate({**ids, **extra}, schema)
        schema = BY_NAME["set_object_type"]["inputSchema"]
        validate({**ids, "type_name": "Draft"}, schema)
        with self.assertRaises(ValueError): validate({**ids, "type_name": "", "classifier_id": "other"}, schema)

    def test_delete_accepts_only_explicit_diagram_and_element_ids(self):
        schema = BY_NAME["delete_relationship"]["inputSchema"]
        validate({"diagram_id": "diagram", "element_id": "connector"}, schema)
        for arguments in [{}, {"diagram_id": "diagram"},
                          {"diagram_id": "diagram", "element_id": ""},
                          {"diagram_id": "diagram", "element_id": "connector", "force": True},
                          {"diagram_id": "diagram", "element_id": "connector", "model_type": "Actor"}]:
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                validate(arguments, schema)

    def test_backup_has_no_path_or_overwrite_parameter(self):
        schema = BY_NAME["backup_project"]["inputSchema"]
        validate({}, schema)
        for arguments in [{"path": "somewhere.vpp"}, {"overwrite": True}]:
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                validate(arguments, schema)

    def test_tool_annotations(self):
        deletion = BY_NAME["delete_relationship"]["annotations"]
        self.assertFalse(deletion["readOnlyHint"])
        self.assertTrue(deletion["destructiveHint"])
        self.assertFalse(deletion["idempotentHint"])
        backup = BY_NAME["backup_project"]["annotations"]
        self.assertFalse(backup["readOnlyHint"])
        self.assertFalse(backup["destructiveHint"])

    def test_connector_getter_requires_ids_and_is_readonly(self):
        tool = BY_NAME["get_connector"]
        validate({"diagram_id": "diagram", "element_id": "connector"}, tool["inputSchema"])
        self.assertTrue(tool["annotations"]["readOnlyHint"])
        with self.assertRaises(ValueError):
            validate({"diagram_id": "diagram", "element_id": "connector", "reset": True}, tool["inputSchema"])

    def test_connector_points_are_validated_before_dispatch(self):
        schema = BY_NAME["set_connector_points"]["inputSchema"]
        arguments = {"diagram_id": "diagram", "element_id": "connector", "points": [[10, 20], [30, 40]]}
        validate(arguments, schema)
        for points in [[], [[10, 20]], [[10, 20], [30]], [[True, 20], [30, 40]], [[10, 20], [30, 40, 50]]]:
            with self.subTest(points=points), self.assertRaises(ValueError):
                validate({**arguments, "points": points}, schema)
        with self.assertRaises(ValueError):
            validate({**arguments, "from_id": "changed"}, schema)

    def test_connector_caption_accepts_only_bounds_and_ids(self):
        schema = BY_NAME["set_connector_caption"]["inputSchema"]
        arguments = {"diagram_id": "diagram", "element_id": "connector", "x": 10, "y": 20, "width": 94, "height": 14}
        validate(arguments, schema)
        for replacement in [{"width": 0}, {"height": -1}, {"x": True}, {"model_id": "changed"}, {"points": [[1, 2], [3, 4]]}]:
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                validate({**arguments, **replacement}, schema)


if __name__ == "__main__":
    unittest.main()
