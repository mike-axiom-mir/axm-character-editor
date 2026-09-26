from __future__ import annotations

import unittest

from axm_character_editor import new_blueprint
from axm_character_editor.human_asset import build_parts


class ThumbArticulationTests(unittest.TestCase):
    def test_thumb_tapers_angles_and_keeps_existing_hand_joint(self):
        controls = new_blueprint("thumb-articulation", preset_id="female-a")["controls"]
        parts = {part["id"]: part for part in build_parts(controls)}

        for suffix in ("L", "R"):
            thumb = parts[f"thumb-{suffix.lower()}"]
            thenar = parts[f"thenar-pad-{suffix.lower()}"]
            self.assertEqual(thumb["material_role"], "skin")
            self.assertEqual(len(thumb["positions"]), 4 * 18)

            rings = [
                thumb["positions"][index:index + 18]
                for index in range(0, len(thumb["positions"]), 18)
            ]
            centers_x = [
                sum(abs(x) for x, _, _ in ring) / len(ring)
                for ring in rings
            ]
            centers_z = [
                sum(z for _, _, z in ring) / len(ring)
                for ring in rings
            ]
            diameters_y = [
                max(y for _, y, _ in ring) - min(y for _, y, _ in ring)
                for ring in rings
            ]

            self.assertTrue(all(a < b for a, b in zip(centers_x, centers_x[1:])))
            self.assertGreater(centers_z[-1], centers_z[0])
            self.assertLess(diameters_y[-1], diameters_y[0] * .65)
            self.assertTrue(all(row == {f"Hand.{suffix}": 1.0} for row in thumb["weights"]))

            thenar_x = [abs(x) for x, _, _ in thenar["positions"]]
            self.assertLess(min(thenar_x), centers_x[0])
            self.assertGreater(max(thenar_x), centers_x[0])


if __name__ == "__main__":
    unittest.main()
