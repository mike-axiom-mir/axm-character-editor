# AXM Character Editor

Standalone, family-neutral character authoring foundation for AXM games and tools.

The first installed family is **`human-v0`** because the first RPG needs a usable human character creator now. Human is not a permanent core assumption: later character families may expose completely different controls, rigs and builders while reusing the same Blueprint/editor/versioning machinery.

## Open the editor

For the current foundation build, open:

`dist/character-editor.html`

It is one offline HTML file. No account, cloud service, CDN or AI is required.

Current editor capabilities:

- four starting presets: Female A / B and Male A / B;
- bounded body and face sliders;
- skin, eye and hair colour;
- starter hair/clothing choices;
- live schematic preview;
- Blueprint import/export;
- RPG-specific editor profile that limits visible controls without deleting underlying capability.

**Truth boundary:** the editor and Blueprint state are real, but the current preview is schematic. This repository does **not yet claim a production human mesh, smooth skin, verified humanoid rig, or playable GLB export.**

## Blueprint core

The shared contract is:

`axm.character.blueprint/v0.1`

A human editor, program or AI writes the same explicit fields. The core validates them deterministically and maintains separate signatures for geometry, appearance and equipment state.

Example:

~~~bash
python -m pip install -e .
axm-character catalog
axm-character new player-001 --preset female-a --out player.character.json
axm-character validate player.character.json
axm-character receipt player.character.json
~~~

The receipt intentionally reports the production asset build as **HOLD** until the Blender/game-asset lane is actually integrated and verified.

## Rebuild the one-file editor

~~~bash
python tools/build_editor.py
~~~

This regenerates `dist/character-editor.html` from the installed `human-v0` family, presets and RPG editor profile.

## Direction

The first useful v0.1 finish line is:

**create a human in the editor → save/reopen the exact Blueprint → build a smooth-skinned rigged asset → fresh-import verify it → use two distinct generated characters in the first RPG with the same animation system.**

The editor may grow inside a shipped game over time. Old characters remain unchanged unless their user deliberately edits them; new controls must receive compatibility defaults rather than silently rewriting older characters.

See:

- `docs/ARCHITECTURE.md`
- `docs/ROADMAP.md`
- `docs/DONOR_PROVENANCE.md`
- `blender/README.md`

## Recovered AXM donors

Exact source snapshots are retained under `donors/` from:

- **AXM Avatar Machine** — deterministic Blueprint/compiler/builder work;
- **AXM Universal Creation** — smooth-skin/motion/export and fresh-import verification work.

They are pinned by repository commit and source blob in `docs/DONOR_PROVENANCE.md`. Donor directories are evidence/reference, **not hidden runtime dependencies**.

## Test

~~~bash
python -m pip install -e .
python -m unittest discover -s tests -v
python tools/build_editor.py
~~~

GitHub CI runs the same core tests and editor build without uploading workflow artifacts.

## Licensing

Machine/workshop code: **PolyForm Noncommercial 1.0.0** plus `CREATOR_OUTPUT_PERMISSION.md`.

Creator Output can be used commercially under the permission terms. Third-party or future imported character packs keep their own rights and provenance.
