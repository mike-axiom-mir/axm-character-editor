from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from axm_character_editor import new_blueprint
from axm_character_editor.human_asset import (
    build_glb,
    build_package,
    parse_glb,
    verify_glb,
)


class HumanAssetTests(unittest.TestCase):
    def test_four_presets_build_structurally_valid_rigged_glbs(self):
        for preset in ("female-a", "female-b", "male-a", "male-b"):
            body, receipt = build_glb(new_blueprint("player", preset_id=preset))
            check = verify_glb(body)
            self.assertEqual(check["status"], "PASS")
            self.assertEqual(receipt["joints"], 18)
            self.assertEqual(receipt["clips"], ["Idle", "Walk", "Wave"])
            self.assertGreater(receipt["vertices"], 15000)
            self.assertGreater(receipt["triangles"], 25000)
            self.assertLess(check["max_weight_sum_error"], 1e-5)

    def test_idle_clip_leaves_authoring_t_pose(self):
        from axm_character_editor.human_asset import starter_clips
        idle = next(clip for clip in starter_clips() if clip["name"] == "Idle")
        tracks = {row["joint"]: row for row in idle["tracks"]}
        identity = [0.0, 0.0, 0.0, 1.0]
        self.assertIn("UpperArm.L", tracks)
        self.assertIn("UpperArm.R", tracks)
        self.assertNotEqual(tracks["UpperArm.L"]["values"][0], identity)
        self.assertNotEqual(tracks["UpperArm.R"]["values"][0], identity)

    def test_build_is_byte_deterministic(self):
        blueprint = new_blueprint("same", preset_id="female-a")
        a, ar = build_glb(blueprint)
        b, br = build_glb(blueprint)
        self.assertEqual(a, b)
        self.assertEqual(ar["sha256"], br["sha256"])

    def test_geometry_control_changes_asset_bytes(self):
        blueprint = new_blueprint("player", preset_id="male-a")
        changed = json.loads(json.dumps(blueprint))
        changed["preset"] = None
        changed["controls"]["jaw_width"] = 1.17
        changed["controls"]["height"] = 1.10
        a, _ = build_glb(blueprint)
        b, _ = build_glb(changed)
        self.assertNotEqual(a, b)

    def test_equipment_choices_change_real_parts(self):
        blueprint = new_blueprint("player", preset_id="female-a")
        changed = json.loads(json.dumps(blueprint))
        changed["preset"] = None
        changed["controls"]["hair"] = "none"
        changed["controls"]["top"] = "tunic"
        changed["controls"]["bottom"] = "skirt"
        a, ar = build_glb(blueprint)
        b, br = build_glb(changed)
        self.assertNotEqual(a, b)
        self.assertNotEqual(ar["sha256"], br["sha256"])

    def test_glb_contains_real_skin_and_animation_contract(self):
        body, _ = build_glb(new_blueprint("player", preset_id="female-b"))
        doc, binary = parse_glb(body)
        self.assertEqual(doc["asset"]["version"], "2.0")
        self.assertEqual(len(doc["skins"]), 1)
        self.assertEqual(len(doc["skins"][0]["joints"]), 18)
        self.assertEqual({x["name"] for x in doc["animations"]}, {"Idle", "Walk", "Wave"})
        self.assertGreater(len(binary), 1000)
        for node in doc["nodes"]:
            if "mesh" in node:
                self.assertEqual(node["skin"], 0)
        equipment = doc["extras"]["equipment"]
        expected = {row["id"] for row in equipment["sockets"]}
        observed = {
            node.get("extras", {}).get("id")
            for node in doc["nodes"]
            if node.get("extras", {}).get("schema") == "axm.character.socket/v0.1"
        }
        self.assertEqual(observed, expected)
        self.assertIn("back.center", observed)
        self.assertIn("grip.R", observed)

    def test_hair_shell_leaves_face_open(self):
        from axm_character_editor.human_asset import body_metrics, build_parts
        blueprint = new_blueprint("hair-open", preset_id="female-a")
        controls = blueprint["controls"]
        parts = {part["id"]: part for part in build_parts(controls)}
        cap = parts["hair-cap"]
        head_y = body_metrics(controls).head_y
        central_front_low = [
            p for p in cap["positions"]
            if p[2] > .04 and abs(p[0]) < .05 and p[1] < head_y + .04
        ]
        self.assertEqual(
            central_front_low,
            [],
            "hair shell must not cover the eyes/nose/mouth like the old full ellipsoid",
        )

    def test_glb_carries_face_quality_materials_and_vertex_color(self):
        body, receipt = build_glb(new_blueprint("face-quality", preset_id="female-a"))
        doc, _ = parse_glb(body)
        self.assertEqual(
            receipt["face_quality_floor"],
            "AURA_REVISION_2_FEATURES_ADAPTED",
        )
        materials = {row["name"] for row in doc["materials"]}
        self.assertTrue({
            "face_skin",
            "skin_detail",
            "eyelid",
            "mouth_seam",
            "nostril",
            "limbal",
            "catchlight",
            "brow",
        } <= materials)
        face_mesh = next(mesh for mesh in doc["meshes"] if mesh["name"] == "face-shell")
        attrs = face_mesh["primitives"][0]["attributes"]
        self.assertIn("COLOR_0", attrs)

    def test_package_retains_source_and_refuses_silent_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "character"
            receipt = build_package(new_blueprint("player", preset_id="male-b"), target)
            self.assertEqual(receipt["verification"]["status"], "PASS")
            self.assertEqual(
                receipt["software_deformation_verification"]["status"],
                "SOFTWARE_DEFORMATION_PASS",
            )
            self.assertEqual(receipt["visual_observation"]["schema"], "axm.character.visual-observation/v0.1")
            self.assertTrue((target / "observations" / "observation-sheet.svg").is_file())
            self.assertTrue((target / "observations" / "visual-observation.json").is_file())
            self.assertEqual(
                {p.name for p in target.iterdir()},
                {
                    "character.blueprint.json",
                    "character.glb",
                    "source-lock.json",
                    "equipment-contract.json",
                    "deformation-verification.json",
                    "observations",
                    "build-receipt.json",
                },
            )
            with self.assertRaises(FileExistsError):
                build_package(new_blueprint("player", preset_id="male-b"), target)


if __name__ == "__main__":
    unittest.main()
