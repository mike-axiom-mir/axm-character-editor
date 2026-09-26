from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from axm_character_editor import new_blueprint
from axm_character_editor.human_asset import write_glb
from axm_character_editor.observation import render_observation_sheet, write_observation_pack


class ObservationTests(unittest.TestCase):
    def test_sheet_is_bound_to_actual_exported_glb(self):
        with tempfile.TemporaryDirectory() as tmp:
            glb = Path(tmp) / "character.glb"
            write_glb(new_blueprint("observe", preset_id="female-a"), glb)
            svg, receipt = render_observation_sheet(glb.read_bytes(), width=900, height=700)
            self.assertIn("ACTUAL EXPORTED GLB OBSERVATION", svg)
            self.assertEqual(receipt["source_sha256"], __import__("hashlib").sha256(glb.read_bytes()).hexdigest())
            self.assertEqual(len(receipt["panels"]), 5)
            self.assertTrue(all(row["rendered_triangles"] > 1000 for row in receipt["panels"]))

    def test_write_pack_retains_svg_and_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            glb = root / "character.glb"
            write_glb(new_blueprint("observe", preset_id="male-a"), glb)
            receipt = write_observation_pack(glb, root / "observations")
            self.assertEqual(receipt["schema"], "axm.character.visual-observation/v0.1")
            self.assertTrue((root / "observations" / "observation-sheet.svg").is_file())
            self.assertTrue((root / "observations" / "visual-observation.json").is_file())


if __name__ == "__main__":
    unittest.main()
