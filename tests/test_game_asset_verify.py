from __future__ import annotations

import unittest

from axm_character_editor import new_blueprint
from axm_character_editor.game_asset_verify import Asset, verify_bytes
from axm_character_editor.human_asset import build_glb


class IndependentGameAssetVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.body, _ = build_glb(new_blueprint("verify-me", preset_id="female-a"))
        cls.result = verify_bytes(cls.body)

    def test_exported_bytes_pass_independent_skin_playback(self):
        self.assertEqual(self.result["status"], "SOFTWARE_DEFORMATION_PASS")
        self.assertTrue(self.result["checks"]["all_clips_deform"])
        self.assertTrue(self.result["checks"]["all_clip_endpoints_close"])
        self.assertGreater(self.result["vertices"], 15000)

    def test_rest_pose_is_grounded_and_metre_scaled(self):
        self.assertGreater(self.result["height_m"], 1.35)
        self.assertLess(self.result["height_m"], 2.20)
        self.assertGreaterEqual(self.result["ground_min_y_m"], -0.002)
        self.assertLessEqual(self.result["ground_min_y_m"], 0.03)

    def test_all_three_clips_move_actual_exported_vertices(self):
        rows = {row["clip"]: row for row in self.result["clips"]}
        self.assertEqual(set(rows), {"Idle", "Walk", "Wave"})
        for row in rows.values():
            self.assertGreater(row["max_vertex_motion_m"], 0.001)
            self.assertLess(row["endpoint_delta_m"], 1e-5)

    def test_verifier_decodes_export_without_builder_state(self):
        asset = Asset(self.body)
        self.assertEqual(len(asset.doc["skins"][0]["joints"]), 18)
        self.assertEqual(
            {animation["name"] for animation in asset.doc["animations"]},
            {"Idle", "Walk", "Wave"},
        )
        self.assertGreater(len(asset.mesh_records()), 10)


if __name__ == "__main__":
    unittest.main()
