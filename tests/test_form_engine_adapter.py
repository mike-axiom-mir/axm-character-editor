from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch

from axm_character_editor import new_blueprint
from axm_character_editor.human_asset import HumanAssetError, build_glb
from axm_character_editor.form_engine_adapter import create_buffer_builder
from axm_character_editor.game_asset_verify import verify_bytes

HAS_FORM_ENGINE = importlib.util.find_spec('axm_form_engine') is not None


class BackendSelectionTests(unittest.TestCase):
    def test_default_never_loads_optional_backend(self):
        with patch('axm_character_editor.form_engine_adapter.create_buffer_builder', side_effect=AssertionError('unexpected optional backend')):
            body, receipt = build_glb(new_blueprint('default-is-stable'))
        self.assertEqual(body[:4], b'glTF')
        self.assertNotIn('buffer_backend', receipt)

    def test_missing_dependency_is_explicit_and_does_not_fall_back(self):
        with patch.dict('sys.modules', {'axm_form_engine.gltf_buffer': None}):
            with self.assertRaisesRegex(ValueError, 'Install its local checkout'):
                create_buffer_builder()

    def test_unknown_backend_is_rejected(self):
        with self.assertRaisesRegex(HumanAssetError, 'unknown buffer backend'):
            build_glb(new_blueprint('bad-backend'), buffer_backend='guess')


@unittest.skipUnless(HAS_FORM_ENGINE, 'optional Form Engine is tested in the integration job')
class FormEngineIntegrationTests(unittest.TestCase):
    def test_four_presets_are_byte_identical(self):
        for preset in ('female-a','female-b','male-a','male-b'):
            with self.subTest(preset=preset):
                blueprint = new_blueprint('shared-packing-'+preset, preset_id=preset)
                builtin, old = build_glb(blueprint)
                shared, new = build_glb(blueprint, buffer_backend='form-engine')
                self.assertEqual(shared, builtin)
                source = new.pop('buffer_backend')
                self.assertEqual(source['contract'], 'axm.form.gltf-buffer/v0.1')
                self.assertEqual(new, old)
                self.assertEqual(verify_bytes(shared)['status'],'SOFTWARE_DEFORMATION_PASS')

    def test_package_retains_provenance_outside_unchanged_asset(self):
        blueprint = new_blueprint('package-bridge', preset_id='female-b')
        builtin, _ = build_glb(blueprint)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)/'asset'
            source_path = Path(tmp)/'character.json'
            source_path.write_text(json.dumps(blueprint))
            run = subprocess.run([sys.executable, '-m', 'axm_character_editor.cli',
                                  'build', str(source_path), str(target),
                                  '--buffer-backend', 'form-engine'],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            result = json.loads(run.stdout)
            self.assertEqual((target/'character.glb').read_bytes(), builtin)
            source = json.loads((target/'source-lock.json').read_text())
            self.assertEqual(source['buffer_backend'],result['buffer_backend'])
            self.assertEqual(result['software_deformation_verification']['status'],'SOFTWARE_DEFORMATION_PASS')
