# Character Editor roadmap

## v0.1 finish line

The first useful finish line is not "an editor page opens" and it is not merely
"a GLB exists".

v0.1 is earned when:

1. a person opens the AXM Character Editor without Blender knowledge;
2. chooses one of several human starting presets;
3. changes bounded body, face, hair and clothing controls;
4. saves and reopens the exact character Blueprint;
5. builds a rigged portable game-asset candidate;
6. an independent fresh-import pass checks the exported skeleton, weights, scale,
   clips and visible deformation;
7. the first RPG consumes two visibly different generated humans through the same
   game animation system.

Steps 1–5 now have an executable first slice. Steps 6–7 remain the acceptance
boundary.

## Delivered foundation

- family-neutral Blueprint core;
- `human-v0`;
- four starting presets;
- RPG editor profile;
- offline one-file editor;
- deterministic source signatures;
- donor recovery and exact source locks;
- no-cloud / no-AI default operation.

## Delivered first human construction slice

- Aura revision 2 identified by exact movie/package hashes;
- Aura face profile/local-volume construction adapted into bounded controls;
- stable face-shell topology across presets;
- first reusable body geometry;
- hair/top/bottom/shoe choices that change real output parts;
- `axm-humanoid-rig-v0` with 18 joints;
- normalized glTF `JOINTS_0` / `WEIGHTS_0`;
- Idle / Walk / Wave clips;
- deterministic embedded GLB output;
- package retention:
  - `character.blueprint.json`
  - `character.glb`
  - `source-lock.json`
  - `build-receipt.json`;
- structural raw-byte GLB verification;
- independent standard-library skin/animation playback over the published GLB;
- sampled actual exported-vertex motion, metre scale, ground height and loop closure;
- retained software deformation receipt.

## Next gate — independent host / visual deformation proof

The software-side independence rung now exists: a separate decoder reopens the
published GLB and proves its encoded clips actually deform its encoded vertices.

The remaining acceptance gate must use an independent 3D host rather than trusting
software playback alone:

- fresh import;
- shoulder / elbow / hip / knee sampling;
- extreme preset/proportion combinations;
- ground-contact review;
- mesh-intersection review;
- clip playback;
- output/reimport comparison;
- retained failure receipts and visual evidence.

The existing UC Blender verifier is a donor, not an automatic PASS: adapt it to
the new rig and body.

## Next gate — first RPG integration

- load two different Character Editor GLBs;
- bind both to the same semantic animation system;
- prove idle/walk/action selection;
- preserve Blueprint identity with the imported character;
- measure load/runtime cost;
- keep a deterministic fallback if a candidate fails import.

## Quality growth after the first RPG proof

The first human body is deliberately a starting body, not the forever body.

Grow it without changing the Blueprint root:

- stronger connected body topology / retopology;
- better shoulder, hip, hand and foot forms;
- corrective shapes;
- richer face controls and expressions;
- improved skin/eye/hair material response;
- UVs and texture sets;
- more hairstyles;
- clothing fit/deformation;
- LODs;
- accessory sockets;
- richer shared animation libraries.

## Later families

New controls are additive. New family packs may be humanoid or completely
different. The existing AXM bonsai character direction is a useful future
non-human validation case, but no non-human family is part of this first RPG gate.

## Post-v0.1 stress test — small globe survival sandbox

After the Character Editor earns its first game-ready human gate, use a deliberately
small survival sandbox on the existing small-globe/world foundation as a consumer
stress test rather than immediately expanding content breadth.

The sandbox should prove:

- two or more Character Editor humans spawn from retained Blueprints;
- the same shared animation contract drives them in-world;
- locally created assets can be added to the world without rewriting characters;
- equipment/material/appearance changes produce explicit new character revisions;
- a character can evolve after creation while retaining its original Blueprint,
  source lock, build receipt and visual observation baseline;
- world saves reference portable character/asset identities rather than trapping
  their sources inside one game;
- before/after observation sheets expose visual drift when an asset evolves;
- failures can roll back the character or asset revision without rolling back the
  whole world.

Keep the game small enough that Character Editor, asset creation, import, evolution,
world-state interaction and observation are the experiment. Content volume is not
the target of this rung.
