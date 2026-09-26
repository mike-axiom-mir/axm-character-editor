from __future__ import annotations

import unittest

from axm_character_editor import new_blueprint
from axm_character_editor.human_asset import body_metrics, build_parts


class AnkleTransitionTests(unittest.TestCase):
    def test_bridge_spans_ankle_and_blends_existing_joints(self):
        controls = new_blueprint("ankle-transition", preset_id="female-a")["controls"]
        metrics = body_metrics(controls)
        parts = {part["id"]: part for part in build_parts(controls)}
        expected_role = "bottom" if controls["bottom"] == "trousers" else "skin"

        for suffix in ("L", "R"):
            bridge = parts[f"ankle-bridge-{suffix.lower()}"]
            ys = [position[1] for position in bridge["positions"]]
            self.assertLess(min(ys), metrics.foot_h)
            self.assertGreater(max(ys), metrics.foot_h)
            self.assertEqual(bridge["material_role"], expected_role)
            self.assertTrue(any(
                f"Shin.{suffix}" in row and f"Foot.{suffix}" in row
                for row in bridge["weights"]
            ))


if __name__ == "__main__":
    unittest.main()
