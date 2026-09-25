# Donor provenance

The first Character Editor foundation retains exact source snapshots rather than reconstructing prior AXM work from memory.

## Avatar Machine donor

Repository: `mike-axiom-mir/axm-avatar-machine`  
Pinned commit: `59b09c1a5e07e424cf198cafa4d5b9133630afa8`

Retained snapshots:

- `donors/avatar-machine/blueprint_v1.py`
  - source: `src/axm_avatar_machine/blueprint.py`
  - source blob: `262926ad6cb9f7fda2218433aa57421737491a06`
- `donors/avatar-machine/build_blueprint_v1.py`
  - source: `blender/build_blueprint_v1.py`
  - source blob: `ca2b0479d7f56fc667b227fa8aae26b7d35bd414`

Useful inherited ideas: explicit Blueprint → deterministic scene plan, bounded anatomy controls, separate geometry/appearance/behavior identities, editable Blender output and creator-parts retention.

The donor still builds the old stylized rigid-part doll family. It is **not** imported as the Character Editor runtime.

## Universal Creation donor

Repository: `mike-axiom-mir/axm-universal-creation`  
Pinned commit: `08cd56220b927ff03432122c4470031597f9f697`

Retained snapshots:

- `donors/uc/verify_rigged_character.py`
  - source: `tools/blender/verify_rigged_character.py`
  - source blob: `c17245a0682fe8e4db8f6d42b84340184cbb49b2`
- `donors/uc/axm_hero_motion.py`
  - source: `tools/blender/axm_hero_motion.py`
  - source blob: `6e3eba614b4792911cd9feb1ee4ee85b0398c537`

Useful inherited ideas: smooth skin/weight handling, skeletal motion, GLB export, fresh-import playback checks, deformation sampling and source/output separation.

Those files are donor evidence. They may have UC-local dependencies and are **not claimed to execute standalone here**.

## Adaptation rule

Do not turn the donor directories into hidden dependencies.

Needed ideas/code are copied and adapted into first-class Character Editor modules with tests. Donor snapshots remain unchanged so future repair can compare the adaptation to its exact source.
