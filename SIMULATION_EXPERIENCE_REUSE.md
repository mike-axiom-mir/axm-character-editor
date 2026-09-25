# Explore character construction and deformation cases

Status: proposed applications of an existing method; documentation only.
Inspected source: `f32f002bd95cb965e0cb003c10170e4a37573131`.

[Shared method and measured neural example](https://github.com/mike-axiom-mir/axm-state-research/blob/main/docs/SIMULATION_AS_REUSABLE_EXPERIENCE.md).

The current [blueprint](src/axm_character_editor/blueprint.py),
[human asset builder](src/axm_character_editor/human_asset.py) and
[export verifier](src/axm_character_editor/game_asset_verify.py) are useful
sources for small deterministic construction trials.

## First useful experiment

Choose a bounded set of valid human-v0 body controls and declared equipment
combinations. Compare the present presets with candidate controls on development
cases, reserving different valid combinations and animation sample times for
evaluation. Export the actual GLB and independently decode it through the
existing verifier; do not score only the builder's in-memory arrays.

Check finite geometry, declared bounds, skin/joint relationships, pose continuity
and the verifier's supported deformation criteria. Record unsupported criteria
as gaps. Preserve failing blueprints and exact builder/export versions so a
repair can be reproduced.

Retain the blueprint, controls, bindings and construction recipe as the reusable
body. A mesh export alone loses some of the causes that made the asset editable.

## Acceptance boundary

Use fresh Blender/game-engine imports and representative rendered poses before
claiming visual or game-asset readiness. Numeric checks do not establish anatomy,
clothing fit, topology quality or aesthetics. Current candidate readiness and
actual game-asset readiness remain distinct.

This note adds no new character family, cloth simulator, neural dependency or
game-engine acceptance result. The active editor/body implementation lane
remains separate.
