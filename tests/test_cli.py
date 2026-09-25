from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from axm_character_editor import new_blueprint
from axm_character_editor.human_asset import write_glb


ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def test_verify_deformation_command_is_wired(self):
        with tempfile.TemporaryDirectory() as tmp:
            glb = Path(tmp) / "character.glb"
            write_glb(new_blueprint("cli-test", preset_id="female-a"), glb)
            env = dict(os.environ)
            env["PYTHONPATH"] = str(ROOT / "src")
            run = subprocess.run(
                [sys.executable, "-m", "axm_character_editor.cli", "verify-deformation", str(glb)],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            result = json.loads(run.stdout)
            self.assertEqual(result["status"], "SOFTWARE_DEFORMATION_PASS")


if __name__ == "__main__":
    unittest.main()
