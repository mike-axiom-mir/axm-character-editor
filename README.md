# AXM Character Editor

Standalone, family-neutral character authoring for AXM games and tools.

The first installed family is **`human-v0`** because the first RPG needs a usable
human character creator now. Human is not a permanent core assumption: later
families may expose completely different controls, rigs and builders while
reusing the same Blueprint/editor/versioning machinery.

## Open the editor

The detailed editor is the default recommended starting point:

~~~bash
python -m pip install -e .
axm-character serve
~~~

Open the local address printed in your terminal (normally
`http://127.0.0.1:8765/`). No account, cloud service, CDN or AI is required.
Python builds your character locally; the browser displays those exact GLB bytes.

- Full creator controls by default, with an optional RPG essentials view;
- Female A / B and Male A / B starting presets;
- Aura-derived detailed face, skin vertex colours and fuller body forms;
- orbit/zoom, front/three-quarter/side cameras and a face close-up;
- actual Idle / Walk / Wave playback, pause and pose-time scrubbing;
- blueprint import/save, undo/redo and reset to your chosen starting preset;
- direct GLB download and a verified game-package ZIP with attachment sockets.

Import validation rejects unsupported or out-of-range values before changing the
current character. Imported authorship metadata and hidden profile controls survive
round trips. The last successful mesh stays visible while changes build, with its
out-of-date status shown and GLB download disabled until the new model arrives.

`dist/character-editor.html` remains a portable offline blueprint editor. Its
**shape sketch is approximate**, with simpler face/clothing and static poses;
use `axm-character serve` for the detailed exported model and game exports.
The GLB viewer supports the current human-v0 export subset, with studio lighting;
it is not a general-purpose glTF/PBR viewer or target-engine acceptance proof.

## Build the first real 3D candidate

The same exported Blueprint can now be compiled locally into a real embedded
glTF 2.0/GLB candidate.

~~~bash
python -m pip install -e .

axm-character new player-001 --preset female-a --out player.character.json
axm-character build player.character.json build/player-001
axm-character verify-glb build/player-001/character.glb
axm-character verify-deformation build/player-001/character.glb
axm-character observe build/player-001/character.glb build/player-001/observations
~~~

The package retains:

~~~text
build/player-001/
    character.blueprint.json
    character.glb
    source-lock.json
    equipment-contract.json
    deformation-verification.json
    observations/
        observation-sheet.svg
        visual-observation.json
    build-receipt.json
~~~

The current `human-v0` candidate includes:

- Aura-revision-2-derived facial geometry as the default quality floor;
- corrected outward face normals and an open Aura-style scalp/hair shell;
- almond eyes with eyelids/lashes/brows plus iris/limbal/pupil/catchlight layers;
- sculpted lips/mouth seam, nose ala/recessed nostrils and ear detail;
- portable absolute dermal vertex colour through standard glTF `COLOR_0`;
- bounded body geometry;
- real slider-driven geometry variation;
- small hair/clothing variants;
- one shared 18-joint humanoid skeleton;
- normalized skin weights;
- Idle / Walk / Wave starter clips;
- deterministic binary GLB output;
- independent standard-library replay of the exported skin and clips, sampling the
  actual encoded vertices rather than trusting the builder's in-memory geometry;
- a dependency-free five-view visual observation sheet generated from the actual
  published GLB and retained beside the asset.

A separate face geometry proof can also be exported:

~~~bash
axm-character face-proof player.character.json --out face.obj
~~~

## Equipment slots and sockets

Every human-v0 GLB now carries a default semantic equipment interface. Garments
use deformable/hybrid slots; backpacks, weapons, tools and accessories use named
attachment sockets that are emitted as actual glTF nodes.

~~~bash
axm-character equipment player.character.json
~~~

Useful defaults include body/top/bottom/feet/headwear slots plus back.center,
back.upper, cape.L/R, grip.L/R, item.L/R, weapon.back and left/right hip weapon
sockets.

See docs/EQUIPMENT_SOCKETS.md. The first game may use only a few of these; the
larger map is intentionally present as a stable growth surface.

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
`human-v0` family, presets and RPG profile, and refreshes the packaged HTML
used by installed copies of `axm-character serve`.

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
