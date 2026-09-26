from __future__ import annotations

import unittest

from axm_character_editor import new_blueprint
from axm_character_editor.human_asset import body_metrics, build_parts


class WristTransitionTests(unittest.TestCase):
    def test_bridge_spans_wrist_and_blends_existing_joints(self):
        controls = new_blueprint("wrist-transition", preset_id="female-a")["controls"]
        metrics = body_metrics(controls)
        parts = {part["id"]: part for part in build_parts(controls)}
        wrist_x = metrics.shoulder_half + metrics.upper_arm + metrics.forearm

        for suffix in ("L", "R"):
            bridge = parts[f"wrist-bridge-{suffix.lower()}"]
            self.assertEqual(bridge["material_role"], "skin")
            xs = [abs(position[0]) for position in bridge["positions"]]
            self.assertLess(min(xs), wrist_x)
            self.assertGreater(max(xs), wrist_x + metrics.hand_len * .10)
            self.assertTrue(any(
                f"Forearm.{suffix}" in row and f"Hand.{suffix}" in row
                for row in bridge["weights"]
            ))


if __name__ == "__main__":
    unittest.main()
