"""Cross-language checks: browser decoder and validator against Python's actual GLB."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from axm_character_editor import new_blueprint
from axm_character_editor.blueprint import load_family, load_profile, presets
from axm_character_editor.human_asset import build_glb
from axm_character_editor.game_asset_verify import Asset, _mul
ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('node'), 'Node is needed for browser contract checks')
class BrowserContractTests(unittest.TestCase):
    def test_browser_skin_matrices_match_independent_decoder(self):
        body, _ = build_glb(new_blueprint('browser-contract', preset_id='male-b'))
        asset = Asset(body)
        samples = []
        joints, inverses = asset.skin()
        for clip, time in [('Idle', .6), ('Walk', .25), ('Wave', .82)]:
            world = asset.pose(clip, time)
            # Python matrices are row major, glTF / WebGL matrices are column major.
            matrices = [_mul(world[j], inv) for j, inv in zip(joints, inverses)]
            expected = [m[row*4+column] for m in matrices for column in range(4) for row in range(4)]
            samples.append({'clip': clip, 'time': time, 'expected': expected})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path/'character.glb').write_bytes(body)
            (path/'samples.json').write_text(json.dumps(samples))
            result = subprocess.run(['node', '-e', '''
const fs=require('node:fs'), assert=require('node:assert/strict');
require(process.argv[1]);const b=fs.readFileSync(process.argv[2]);
const asset=AXMAssetViewer.decode(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength));
for(const sample of JSON.parse(fs.readFileSync(process.argv[3]))){
 const actual=asset.matrices(sample.clip,sample.time);
 assert.equal(actual.length,sample.expected.length);
 actual.forEach((v,i)=>assert.ok(Math.abs(v-sample.expected[i])<2e-6,`${sample.clip} matrix ${i}: ${v} != ${sample.expected[i]}`));
}''', str(ROOT/'editor/asset-viewer.js'), str(path/'character.glb'), str(path/'samples.json')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_browser_validation_rejects_bad_controls_and_preserves_authorship(self):
        data = {'family': load_family('human-v0'), 'profile': load_profile('rpg-v0'), 'presets': presets()}
        bp = new_blueprint('imported', preset_id='male-b')
        bp['authorship'] = {'method': 'HUMAN_OR_AI_EXPLICIT_FIELDS', 'provenance': {'source': 'game-1'}}
        script = '''
const assert=require('node:assert/strict');require(process.argv[1]);
const input=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
assert.deepEqual(AXMBlueprint.normalize(input.bp,input.data),input.bp);
for(const controls of [{height:99},{height:true},{height:'1'},{hair:'invalid'},{skin:'<script>'},{unknown:1}]){
 assert.throws(()=>AXMBlueprint.normalize({...input.bp,controls},input.data));
}
assert.throws(()=>AXMBlueprint.normalize({...input.bp,family_version:'future'},input.data));
assert.throws(()=>AXMBlueprint.normalize({...input.bp,authorship:[]},input.data));
'''
        result = subprocess.run(['node','-e',script,str(ROOT/'editor/state.js')],input=json.dumps({'data':data,'bp':bp}),text=True,capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
