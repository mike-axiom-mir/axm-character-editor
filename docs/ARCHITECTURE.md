# AXM Character Editor architecture

## Purpose

AXM Character Editor is a standalone character-authoring machine. The first installed family is `human-v0`, but **human is not a core assumption**.

The stable direction is:

human / AI / program
→ explicit character blueprint
→ family pack
→ build adapter
→ editable source + portable game asset
→ independent verification

The RPG is consumer #1. MorphTile and later AXM games may consume the same machine without becoming runtime dependencies.

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
- later: mesh/morph/material/attachment builders and verification rules.

A game/editor profile owns only **which installed controls are shown**. Hiding a control never deletes it from the family and never silently rewrites an existing character.

## Character continuity

Existing characters are source data, not disposable render output.

A future schema migration must preserve the old appearance by default. Newly introduced controls receive compatibility defaults until a person intentionally edits them.

No editor upgrade is allowed to silently "improve" an existing character.

## Current truth boundary

Implemented now:

- family-neutral `axm.character.blueprint/v0.1`;
- deterministic validation and signatures;
- `human-v0` control pack;
- four human starting presets;
- RPG starter editor profile;
- offline editor template;
- import/export of character blueprints;
- exact donor snapshots from Avatar Machine and UC.

Held now:

- production human topology;
- morph-target realization;
- smooth skin binding;
- generic humanoid rig extraction;
- clothing deformation/fitting;
- GLB game-asset export from this repo;
- target-engine playability.

The editor preview is explicitly schematic until those held stages are earned.
