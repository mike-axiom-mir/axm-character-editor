from __future__ import annotations

import unittest

from axm_character_editor import new_blueprint
from axm_character_editor.equipment import (
    EQUIPMENT_SCHEMA,
    SOCKET_SCHEMA,
    compile_human_v0_equipment,
    validate_equipment_contract,
)
from axm_character_editor.human_asset import body_metrics, skeleton


class EquipmentTests(unittest.TestCase):
    def contract(self, preset: str = "female-a"):
        blueprint = new_blueprint("equipment-test", preset_id=preset)
        controls = blueprint["controls"]
        joints = skeleton(controls)
        return compile_human_v0_equipment(
            controls,
            body_metrics(controls),
            joint_names={row["id"] for row in joints},
        )

    def test_default_contract_has_expected_growth_surface(self):
        contract = self.contract()
        self.assertEqual(contract["schema"], EQUIPMENT_SCHEMA)
        slots = {row["id"] for row in contract["slots"]}
        sockets = {row["id"] for row in contract["sockets"]}
        self.assertTrue({"body", "top", "bottom", "feet", "headwear", "outerwear"} <= slots)
        self.assertTrue({
            "back.center",
            "back.upper",
            "cape.L",
            "cape.R",
            "grip.L",
            "grip.R",
            "weapon.back",
            "weapon.hip.L",
            "weapon.hip.R",
            "item.L",
            "item.R",
        } <= sockets)

    def test_all_sockets_bind_to_existing_rig_joints(self):
        contract = self.contract("male-b")
        joints = {row["id"] for row in skeleton(new_blueprint("x", preset_id="male-b")["controls"])}
        self.assertTrue(all(row["parent_joint"] in joints for row in contract["sockets"]))

    def test_socket_contract_is_valid_and_unique(self):
        contract = validate_equipment_contract(self.contract())
        socket_ids = [row["id"] for row in contract["sockets"]]
        self.assertEqual(len(socket_ids), len(set(socket_ids)))
        self.assertTrue(all(row["schema"] == SOCKET_SCHEMA for row in contract["sockets"]))

    def test_socket_positions_follow_character_scale(self):
        a = new_blueprint("a", preset_id="female-a")
        b = new_blueprint("b", preset_id="female-a")
        b["preset"] = None
        b["controls"]["height"] = 1.15
        ca = compile_human_v0_equipment(
            a["controls"], body_metrics(a["controls"]),
            joint_names={row["id"] for row in skeleton(a["controls"])},
        )
        cb = compile_human_v0_equipment(
            b["controls"], body_metrics(b["controls"]),
            joint_names={row["id"] for row in skeleton(b["controls"])},
        )
        sa = {row["id"]: row for row in ca["sockets"]}
        sb = {row["id"]: row for row in cb["sockets"]}
        self.assertNotEqual(sa["back.center"]["translation"], sb["back.center"]["translation"])
        self.assertNotEqual(sa["grip.R"]["translation"], sb["grip.R"]["translation"])


if __name__ == "__main__":
    unittest.main()
