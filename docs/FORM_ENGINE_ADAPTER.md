# First Form Engine caller

`build_glb`, `write_glb` and `build_package` accept the keyword-only argument
`buffer_backend="form-engine"`. The CLI exposes it as
`axm-character build ... --buffer-backend form-engine`.

The default stays `builtin`, and no Form Engine dependency is imported on that
path. The browser studio currently uses the builtin writer. An explicit switch
makes experimentation and rollback easy while the shared engine matures.

Only buffer/accessor packing moves across this boundary. The scene writer's
private `_align` call is translated to Form Engine's public `align()` by a small
adapter. Blueprint identity, human controls, geometry, materials, rig/skin,
attachment nodes and animations all remain Character Editor responsibilities.

The Form Engine must provide `axm.form.gltf-buffer/v0.1`. Missing or incompatible
implementations produce a clear error. Successful optional builds add provider,
implementation fingerprint and donor ancestry to the receipt and source lock;
none of that provider metadata is put into GLB bytes or Blueprint identity.

Tests compare every byte and every existing receipt field for all four presets,
then independently replay the emitted skin/animations. A package test checks the
source lock and unchanged GLB on disk. Form Engine's additional six-case proof
includes numeric control extremes and changed equipment. CI installs a specific
Form Engine commit for the integration job; changing it requires rerunning proof.

This is a working G1 extraction, not migration of the complete character backend.
Next candidates are generic vertex normals and static mesh/material/node assembly.
