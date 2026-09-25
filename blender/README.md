# Blender / host verification lane

Character Editor no longer depends on Blender to create its first structural
`human-v0` game-asset candidate.

The core Python builder can now emit an embedded glTF 2.0/GLB with:

- Aura-derived face geometry;
- bounded human body geometry;
- one shared 18-joint humanoid skeleton;
- normalized skin weights;
- Idle / Walk / Wave starter clips.

That is structural evidence, not final game acceptance.

## Why this directory still matters

Blender remains a useful **independent host** for the next gate:

1. fresh-import the generated GLB;
2. inspect shoulder/hip/knee/elbow deformation;
3. sample all starter clips;
4. inspect ground contact and mesh intersections;
5. compare several preset/proportion extremes;
6. export/reimport without relying on the generating code;
7. retain exact receipts and images/video for failures and repairs.

The retained UC donor verifier under `donors/uc/` is a useful starting point,
but it is character-specific and must be adapted rather than silently called as
if it already validates this new human body.

Until that host pass and the RPG import pass succeed,
`game_asset_ready` stays false even when the structural GLB verifier passes.
