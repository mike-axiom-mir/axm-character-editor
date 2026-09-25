# AXM Character Editor

Standalone, family-neutral character authoring for AXM games and tools.

The first installed family is **`human-v0`** because the first RPG needs a usable
human character creator now. Human is not a permanent core assumption: later
families may expose completely different controls, rigs and builders while
reusing the same Blueprint/editor/versioning machinery.

## Open the editor

Open:

`dist/character-editor.html`

It is one offline HTML file. No account, cloud service, CDN or AI is required.

Current editor capabilities:

- Female A / B and Male A / B starting presets;
- bounded body and face controls;
- skin, eye and hair colour;
- starter hair/clothing choices;
- live schematic preview;
- Blueprint import/export;
- RPG-specific editor profile that limits visible controls without deleting
  underlying capability.

**The browser preview is intentionally schematic.** It is not the generated 3D
asset.

## Build the first real 3D candidate

The same exported Blueprint can now be compiled locally into a real embedded
glTF 2.0/GLB candidate.

~~~bash
python -m pip install -e .

axm-character new player-001 --preset female-a --out player.character.json
axm-character build player.character.json build/player-001
axm-character verify-glb build/player-001/character.glb
axm-character verify-deformation build/player-001/character.glb
~~~

The package retains:

~~~text
build/player-001/
    character.blueprint.json
    character.glb
    source-lock.json
    deformation-verification.json
    build-receipt.json
~~~

The current `human-v0` candidate includes:

- Aura-revision-2-derived facial geometry;
- bounded body geometry;
- real slider-driven geometry variation;
- small hair/clothing variants;
- one shared 18-joint humanoid skeleton;
- normalized skin weights;
- Idle / Walk / Wave starter clips;
- deterministic binary GLB output;
- independent standard-library replay of the exported skin and clips, sampling the
  actual encoded vertices rather than trusting the builder's in-memory geometry.

A separate face geometry proof can also be exported:

~~~bash
axm-character face-proof player.character.json --out face.obj
~~~

## Truth boundary

The repository now has a **structurally verified rigged GLB candidate builder**.

That is deliberately different from saying the character is game-ready.

The package now earns `SOFTWARE_DEFORMATION_PASS` only after a second decoder
re-opens the binary GLB, evaluates its joint hierarchy, inverse bind matrices,
animation channels and skin weights, and observes real exported-vertex movement.

Still pending:

- independent Blender/engine fresh-import **visual** deformation review;
- final topology/visual acceptance;
- robust clothing fitting;
- corrective shapes/facial animation;
- production UV/texturing;
- target RPG import;
- shared game-animation runtime proof;
- measured runtime performance.

For that reason:

- `game_asset_candidate_ready = true`
- `game_asset_ready = false`

until the remaining gates are actually demonstrated.

## Blueprint core

The shared source contract is:

`axm.character.blueprint/v0.1`

A human editor, program or AI writes the same explicit fields. The core validates
them deterministically and maintains separate signatures for geometry, appearance
and equipment state.

~~~bash
axm-character catalog
axm-character validate player.character.json
axm-character receipt player.character.json
~~~

The Blueprint remains the durable character identity. Later editor versions may
expose more controls without silently rewriting an older character.

## Aura source recovery

Mike supplied the original Aura package used for the earlier human-like face
video. The packaged movie is byte-identical to the earlier uploaded movie, so
the adaptation is grounded in the actual construction source rather than a
visual reconstruction.

See:

- `docs/AURA_FACE_EXTRACTION.md`
- `docs/DONOR_PROVENANCE.md`
- `donors/aura/SOURCE_LOCK.json`

Aura supplies the selected face-construction ancestry. Its android body,
one-off hierarchy and authored scene are not the Character Editor human body.

## Rebuild the one-file editor

~~~bash
python tools/build_editor.py
~~~

This regenerates `dist/character-editor.html` from the installed
`human-v0` family, presets and RPG profile.

## Acceptance direction

The next finish line is:

**editor → exact Blueprint → rigged GLB candidate → independent fresh-import
deformation proof → two different generated humans running through the same RPG
animation system.**

After that, quality grows without replacing the character format.

## Test

~~~bash
python -m pip install -e .
python -m unittest discover -s tests -v
python tools/build_editor.py
~~~

GitHub CI runs the core tests and editor build without uploading workflow
artifacts.

## Licensing

Machine/workshop code: **PolyForm Noncommercial 1.0.0** plus
`CREATOR_OUTPUT_PERMISSION.md`.

Creator Output can be used commercially under the permission terms. Third-party
or future imported packs keep their own rights and provenance.

## Reusable simulation method

[Simulation experience and reuse](SIMULATION_EXPERIENCE_REUSE.md) connects the shared method to this repository, with existing machinery, proposed experiments and explicit evidence limits.
