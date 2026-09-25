# Blender production lane — currently held

This directory is intentionally not populated with a fake new human builder.

The repository retains exact donor snapshots in `donors/`. The next production pass should adapt, not import:

1. Avatar Machine's explicit Blueprint/scene-plan pattern.
2. UC's smooth-skin, motion/export and fresh-import verifier patterns.
3. A stable human base topology and morph-target source.

The first accepted adapter must emit at minimum:

- editable `.blend`;
- rigged `.glb`;
- character manifest;
- source/morph state;
- build receipt;
- fresh-import verification receipt.

Until that exists and passes, `human-v0.build_status` remains
`HOLD_PRODUCTION_MESH_SKIN_RIG_EXPORT_NOT_INTEGRATED`.
