from __future__ import annotations

import unittest

from axm_character_editor import new_blueprint
from axm_character_editor.human_asset import body_metrics, build_parts


class ElbowTransitionTests(unittest.TestCase):
    def test_bridge_spans_elbow_and_blends_existing_joints(self):
        controls = new_blueprint("elbow-transition", preset_id="female-a")["controls"]
        metrics = body_metrics(controls)
        parts = {part["id"]: part for part in build_parts(controls)}
        elbow_x = metrics.shoulder_half + metrics.upper_arm
        expected_role = "top" if controls["top"] == "jacket" else "skin"

        for suffix in ("L", "R"):
            bridge = parts[f"elbow-bridge-{suffix.lower()}"]
            xs = [abs(position[0]) for position in bridge["positions"]]
            self.assertLess(min(xs), elbow_x)
            self.assertGreater(max(xs), elbow_x)
            self.assertEqual(bridge["material_role"], expected_role)
            self.assertTrue(any(
                f"UpperArm.{suffix}" in row and f"Forearm.{suffix}" in row
                for row in bridge["weights"]
            ))


if __name__ == "__main__":
    unittest.main()
