# Character Editor roadmap

## v0.1 target

The first useful finish line is not "an editor page opens".

v0.1 is earned when:

1. a person opens the AXM Character Editor without Blender knowledge;
2. chooses one of several human starting presets;
3. changes a bounded set of body, face, hair and clothing controls;
4. saves and reopens the exact character blueprint;
5. builds a smooth-skinned, rigged portable game asset;
6. a fresh-import verifier proves the exported asset still has the expected skeleton, weights, scale and deformation;
7. the first RPG consumes two visibly different characters from the same animation system.

## Build sequence

### Foundation — current branch
- family-neutral Blueprint core;
- `human-v0`;
- presets;
- RPG profile;
- offline editor;
- donor recovery.

### Human production body
- choose/recover one stable editor-ready human topology;
- define morph-target contract;
- bind high-impact controls first;
- retain neutral source and morph provenance.

### Humanoid rig
- extract generic humanoid skeleton principles from UC;
- remove hero-specific cape/tool/charm bones;
- establish sockets and naming;
- smooth-skin the human body;
- verify shoulders, hips, knees, hands and feet.

### Appearance
- skin/eyes/hair material response;
- small hair library;
- starter clothing;
- clothing fit/deformation checks.

### Game asset
- editable Blender source;
- rigged GLB;
- manifest;
- verification receipt;
- RPG import proof.

## Later growth

New controls are additive. New family packs may be humanoid or completely different.

Likely future families include stylized/non-human characters such as the existing AXM bonsai character direction, but no non-human family is part of v0.1.
