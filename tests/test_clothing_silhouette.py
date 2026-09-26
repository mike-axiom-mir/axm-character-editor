from __future__ import annotations

import unittest

from axm_character_editor import new_blueprint
from axm_character_editor.human_asset import body_metrics, build_parts


class ClothingSilhouetteTests(unittest.TestCase):
    def test_body_core_adds_hem_and_waist_profile_without_new_rig_contract(self):
        controls = new_blueprint("clothing-silhouette", preset_id="female-a")["controls"]
        metrics = body_metrics(controls)
        parts = {part["id"]: part for part in build_parts(controls)}
        core = parts["body-core"]

        rings = {}
        for x, y, z in core["positions"]:
            rings.setdefault(round(y, 6), []).append((x, z))

        self.assertEqual(core["material_role"], "top")
        self.assertGreaterEqual(len(rings), 10)

        lower_torso_y = round(metrics.hip_y + metrics.pelvis_h * .12, 6)
        waist_y = round(metrics.hip_y + metrics.pelvis_h + metrics.torso_h * .11, 6)
        self.assertIn(lower_torso_y, rings)
        self.assertIn(waist_y, rings)

        lower_width = max(abs(x) for x, _ in rings[lower_torso_y])
        waist_width = max(abs(x) for x, _ in rings[waist_y])
        self.assertLess(waist_width, lower_width)


if __name__ == "__main__":
    unittest.main()
