# Aura face extraction into human-v0

## Why Aura

The uploaded Aura revision 2 package is the exact source behind the earlier
character video selected as the face-quality starting point. Matching SHA-256
digests prove the packaged movie and the earlier uploaded movie are identical.

Rather than treating that render as an aesthetic reference and rebuilding from
memory, Character Editor recovers its actual construction logic.

## What was adapted

Aura revision 2 constructs its face from:

- an authored vertical head profile;
- smooth cubic interpolation between profile stations;
- local Gaussian volumes for the nose bridge/tip, nose wings, cheeks, eye sockets,
  brow, muzzle and chin;
- separately constructed upper/lower lip surfaces;
- explicit sclera, iris and pupil geometry;
- dermal/material intent separate from facial geometry.

`src/axm_character_editor/human_face.py` translates that construction into
metres, Y-up, +Z-forward coordinates and maps it to the existing editor controls:

- `head_width`
- `head_depth`
- `jaw_width`
- `chin_size`
- `eye_size`
- `eye_spacing`
- `nose_width`
- `nose_projection`
- `mouth_width`

This is actual geometry variation, not a UI-only slider facade.

## Deliberate change: stable topology

Aura revision 2 dynamically omitted face polygons inside its eye apertures.
That is useful for the authored android scene but would make a morph/editor family
harder to keep index-compatible.

The Character Editor face shell therefore retains one deterministic index layout
across bounded `human-v0` controls. Eye geometry remains separate. This is an
intentional adaptation, not a claim that the output is byte-equivalent to Aura.

Stable topology means a preset can change geometry while keeping the same face-shell
vertex/triangle correspondence, which is the foundation needed for later:

- named morph targets;
- corrective shapes;
- richer facial animation;
- compatible clothing/accessory anchors;
- old-character continuity.

## What was not copied

The following Aura-specific construction is not the `human-v0` body:

- android torso and mechanical limbs;
- Aura's object-parent animation hierarchy;
- robotic shell materials and maintenance details;
- one-off scene/camera/studio setup;
- Aura's authored greeting animation.

The first Character Editor full-body candidate instead uses a small shared
humanoid rig and real glTF skin weights. Aura is the face donor, not the character
format.

## Current evidence

The face recipe is deterministic and renderer-neutral. Tests check:

- all four starter presets use the same face-shell topology;
- face controls change real vertex positions;
- generated coordinates remain finite;
- the construction can be emitted as an OBJ geometry proof.

The full `human-v0` builder then includes these parts in a rigged GLB candidate.

## Current boundary

This extraction establishes reusable face construction and structural mesh
continuity. It does not establish:

- photorealism;
- human anatomical correctness;
- final game art quality;
- facial expression deformation;
- final UV/texturing;
- RPG-engine import or performance.

Those are separate growth stages rather than hidden claims attached to the donor.

## Quality-floor transplant

The first reusable adaptation preserved Aura's profile equations but simplified several
visual layers. The current quality-floor pass restores the high-value parts that made
the donor visibly stronger:

- outward face-shell winding and normals;
- denser stable face-shell sampling;
- absolute dermal `COLOR_0` variation on a neutral face material;
- almond sclera surfaces;
- limbal ring, iris, pupil and catchlight layers;
- upper/lower eyelid rims and lashline;
- shaped brows;
- nose ala, columella and recessed dark nostril detail;
- mouth seam and philtrum detail;
- outer/inner ear geometry;
- an open Aura-style scalp shell instead of the old full ellipsoid hair cap.

The old ellipsoid hair cap literally covered the facial geometry and the original face
shell winding produced inward normals. Those were implementation regressions, not
limits of the Aura construction. Both now have regression tests.

This still does not copy the Android body or one-off studio scene. The face workflow
is transplanted into the reusable human-v0 Blueprint/rig/GLB path.
