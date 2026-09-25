from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path

from axm_character_editor import new_blueprint
from axm_character_editor.human_face import build_face_parts, build_face_surface, face_summary, write_obj


class HumanFaceTests(unittest.TestCase):
    def controls(self, preset: str):
        return new_blueprint("face-test", preset_id=preset)["controls"]

    def test_starting_presets_share_face_shell_topology(self):
        rows = [
            build_face_surface(self.controls(preset))
            for preset in ("female-a", "female-b", "male-a", "male-b")
        ]
        signatures = {
            (
                row["topology"]["vertex_count"],
                row["topology"]["triangle_count"],
                tuple(row["triangles"][:32]),
            )
            for row in rows
        }
        self.assertEqual(len(signatures), 1)

    def test_control_change_changes_geometry_without_changing_topology(self):
        base = self.controls("female-a")
        changed = dict(base)
        changed["jaw_width"] = 1.16
        changed["nose_projection"] = 1.12
        a = build_face_surface(base)
        b = build_face_surface(changed)
        self.assertEqual(a["triangles"], b["triangles"])
        self.assertNotEqual(a["positions"], b["positions"])

    def test_all_generated_positions_are_finite(self):
        for preset in ("female-a", "female-b", "male-a", "male-b"):
            for part in build_face_parts(self.controls(preset)):
                self.assertTrue(part["positions"])
                self.assertTrue(
                    all(math.isfinite(value) for point in part["positions"] for value in point)
                )

    def test_summary_has_real_geometry(self):
        summary = face_summary(self.controls("female-a"))
        self.assertGreater(summary["vertices"], 10000)
        self.assertGreater(summary["triangles"], 20000)
        self.assertEqual(summary["topology_status"], "STABLE_INDEX_LAYOUT_WITHIN_HUMAN_V0")

    def test_obj_proof_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "face.obj"
            write_obj(self.controls("male-a"), path)
            body = path.read_text(encoding="utf-8")
            self.assertIn("o face-shell", body)
            self.assertIn("\nv ", body)
            self.assertIn("\nf ", body)


if __name__ == "__main__":
    unittest.main()
