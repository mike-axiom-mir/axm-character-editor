from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class EditorBuildTests(unittest.TestCase):
    def test_single_file_editor_builds_with_embedded_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "character-editor.html"
            subprocess.run(
                [sys.executable, str(ROOT / "tools" / "build_editor.py"), "--out", str(out)],
                cwd=ROOT,
                check=True,
            )
            body = out.read_text(encoding="utf-8")
            self.assertIn("AXM / CHARACTER EDITOR", body)
            self.assertIn('"id":"human-v0"', body)
            self.assertNotIn("__AXM_EDITOR_DATA__", body)
            self.assertIn("SCHEMATIC PREVIEW / NOT FINAL MESH", body)


if __name__ == "__main__":
    unittest.main()
