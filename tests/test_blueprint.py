from __future__ import annotations

import copy
import unittest

from axm_character_editor import (
    BlueprintError,
    build_receipt,
    new_blueprint,
    signature_bundle,
    validate_blueprint,
)


class BlueprintTests(unittest.TestCase):
    def test_four_starting_presets_validate(self):
        for preset in ("female-a", "female-b", "male-a", "male-b"):
            value = new_blueprint("player", preset_id=preset)
            self.assertEqual(value["family"], "human-v0")
            self.assertEqual(value["preset"], preset)
            self.assertEqual(value["editor_profile"], "rpg-v0")

    def test_geometry_and_appearance_signatures_are_separate(self):
        base = new_blueprint("player", preset_id="female-a")
        changed = copy.deepcopy(base)
        changed["controls"]["hair_color"] = "#ffffff"
        a = signature_bundle(base)
        b = signature_bundle(changed)
        self.assertEqual(a["geometry_sha256"], b["geometry_sha256"])
        self.assertNotEqual(a["appearance_sha256"], b["appearance_sha256"])

    def test_geometry_change_changes_geometry_signature(self):
        base = new_blueprint("player", preset_id="male-a")
        changed = copy.deepcopy(base)
        changed["controls"]["jaw_width"] = 1.15
        self.assertNotEqual(
            signature_bundle(base)["geometry_sha256"],
            signature_bundle(changed)["geometry_sha256"],
        )

    def test_unknown_control_fails_closed(self):
        value = new_blueprint("player")
        value["controls"]["secret_magic_slider"] = 99
        with self.assertRaises(BlueprintError):
            validate_blueprint(value)

    def test_out_of_bounds_control_fails_closed(self):
        value = new_blueprint("player")
        value["controls"]["height"] = 99
        with self.assertRaises(BlueprintError):
            validate_blueprint(value)

    def test_receipt_distinguishes_candidate_from_game_ready(self):
        receipt = build_receipt(new_blueprint("player"))
        self.assertTrue(receipt["game_asset_candidate_ready"])
        self.assertFalse(receipt["game_asset_ready"])
        self.assertEqual(
            receipt["asset_build_status"],
            "STRUCTURAL_RIGGED_GLB_CANDIDATE_BUILDER_AVAILABLE",
        )


if __name__ == "__main__":
    unittest.main()
