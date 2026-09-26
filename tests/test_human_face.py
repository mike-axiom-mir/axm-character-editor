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
        self.assertEqual(
            summary["topology_status"],
            "STABLE_FACE_SHELL_INDEX_LAYOUT_WITHIN_HUMAN_V0",
        )
        self.assertEqual(
            summary["quality_floor"],
            "AURA_REVISION_2_GEOMETRY_FEATURES_ADAPTED",
        )
        self.assertIn("upper/lower eyelid rims and lashline", summary["features"])

    def test_face_shell_winding_is_outward(self):
        shell = build_face_surface(self.controls("female-a"))
        points = shell["positions"]
        positive = 0
        checked = 0
        for a, b, c in shell["triangles"][::257]:
            pa, pb, pc = points[a], points[b], points[c]
            u = [pb[i] - pa[i] for i in range(3)]
            v = [pc[i] - pa[i] for i in range(3)]
            normal = [
                u[1]*v[2] - u[2]*v[1],
                u[2]*v[0] - u[0]*v[2],
                u[0]*v[1] - u[1]*v[0],
            ]
            center = [
                (pa[i] + pb[i] + pc[i]) / 3
                for i in range(3)
            ]
            # human_face local coordinates are centered close to [0,0,0]
            if sum(normal[i] * center[i] for i in range(3)) > 0:
                positive += 1
            checked += 1
        self.assertGreater(checked, 20)
        self.assertGreater(positive / checked, .95)

    def test_quality_parts_are_present(self):
        parts = {part["part"]: part for part in build_face_parts(self.controls("female-a"))}
        required = {
            "face-shell",
            "upper-lip",
            "lower-lip",
            "mouth-seam",
            "nostril-l",
            "nostril-r",
            "eye-l-sclera",
            "eye-r-sclera",
            "eye-l-limbal",
            "eye-r-limbal",
            "eye-l-upper-lid",
            "eye-r-upper-lid",
            "brow-l",
            "brow-r",
            "ear-l",
            "ear-r",
        }
        self.assertTrue(required <= set(parts))
        self.assertIn("colors", parts["face-shell"])
        self.assertEqual(
            len(parts["face-shell"]["colors"]),
            len(parts["face-shell"]["positions"]),
        )

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
