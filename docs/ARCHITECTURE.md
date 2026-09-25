# AXM Character Editor architecture

## Purpose

AXM Character Editor is a standalone character-authoring machine. The first
installed family is `human-v0`, but **human is not a core assumption**.

The stable direction is:

human / AI / program
→ explicit character blueprint
→ family pack
→ deterministic build adapter
→ portable game-asset candidate
→ independent host/game verification

The RPG is consumer #1. MorphTile and later AXM games may consume the same
machine without becoming runtime dependencies.

## Core boundary

The core owns:

- blueprint schema and deterministic normalization;
- family discovery;
- presets;
- editor profiles;
- channel-separated signatures;
- migration/version hooks;
- creator-output/provenance boundary;
- the human-facing editor shell.

A family owns:

- its controls and bounds;
- starting presets;
- compatible rig profile declarations;
- geometry/build adapters;
- material/equipment interpretation;
- family-specific verification rules.

A game/editor profile owns only **which installed controls are shown**. Hiding a
control never deletes it from the family and never silently rewrites an existing
character.

## Current human-v0 pipeline

`human-v0` now has a first executable production-shaped path:

explicit Blueprint
→ bounded body controls
→ Aura-derived stable face construction
→ starter body / hair / clothing geometry
→ shared `axm-humanoid-rig-v0`
→ normalized skin weights
→ Idle / Walk / Wave clips
→ embedded glTF 2.0 GLB
→ raw-byte structural verifier
→ independent skin/animation decoder
→ sampled exported-vertex deformation proof

The generated file is a **candidate**, not yet an accepted RPG character.

The browser remains a lightweight editor/preview. It exports the same Blueprint
consumed by the Python builder; it does not maintain a second character format.

## Character continuity

Existing characters are source data, not disposable render output.

A future schema migration must preserve old appearance by default. Newly
introduced controls receive compatibility defaults until a person intentionally
edits them.

No editor upgrade is allowed to silently "improve" an existing character.

## Current truth boundary

Implemented now:

- family-neutral `axm.character.blueprint/v0.1`;
- deterministic validation and channel signatures;
- `human-v0` control pack and four presets;
- RPG starter editor profile;
- offline editor and Blueprint import/export;
- exact Aura / Avatar Machine / UC lineage;
- Aura-derived reusable human-face construction;
- stable face-shell topology across bounded controls;
- first bounded human body / hair / clothing realization;
- 18-joint shared humanoid rig;
- normalized glTF skin weights;
- Idle / Walk / Wave starter clips;
- deterministic embedded GLB output;
- structural GLB re-open/weight/skin/clip verification;
- independent software evaluation of the exported joint hierarchy, inverse bind
  matrices, clips and actual deformed vertices;
- retained `deformation-verification.json` in each built character package.

Held now:

- final body topology/retopology acceptance;
- corrective deformation and facial animation;
- production UV/texturing;
- robust clothing fitting across control extremes;
- detailed hands/feet/hair;
- independent Blender/host fresh-import **visual** deformation review;
- RPG engine import and shared-animation runtime proof;
- measured game-runtime performance.

`game_asset_candidate_ready` may therefore be true while
`game_asset_ready` remains false.

The editor preview remains explicitly schematic; it is an editing surface, not a
claim that the SVG is the final asset.

## Visual observer loop

Every built human package now retains an observation surface generated from the
published GLB bytes themselves. The observation renderer reuses the independent
GLB decoder rather than the in-memory builder state, samples encoded Idle/Walk/Wave
poses and emits a five-view review sheet plus a digest-bound JSON receipt.

This creates a portable loop:

`Blueprint -> GLB -> independent deformation decode -> visual observation -> review -> repair`

The observation renderer is intentionally lightweight and renderer-neutral. It is
not evidence that Blender, Godot, Unity, Unreal or the target RPG will shade the
asset identically. Its job is continuity: a later chat, local tool or game-world
pipeline can see what the exact exported character looked like when that revision
was created and compare future revisions without inventing history.

The offline editor now uses a live local 3D viewport for interaction. The Python
GLB builder remains authoritative export; browser preview parity is an explicit
engineering target rather than an assumed identity.
