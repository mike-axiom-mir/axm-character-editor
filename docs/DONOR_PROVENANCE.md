# Donor provenance

Character Editor keeps source lineage explicit. Donor material is used as evidence
and construction ancestry, not as a hidden runtime dependency.

## Aura revision 2 — exact uploaded face donor

Mike supplied the original `Aura-Android.zip` package used to produce the face
shown in the earlier `1000000969.mp4` clip.

Exact package identity:

- `Aura-Android.zip` SHA-256:
  `61592614d97b26dd768d9d6e37365af192d5fff1f660f4ca99566d1bc9e87c04`
- packaged `Aura/Aura.mp4` SHA-256:
  `78e65019a27b9c830bbc7fc23cc392728987e4d81fcbb31de48f929504ff664d`
- earlier uploaded `1000000969.mp4` SHA-256:
  `78e65019a27b9c830bbc7fc23cc392728987e4d81fcbb31de48f929504ff664d`

The identical movie hashes establish that the supplied Aura package is the source
package for the exact visual Mike selected as a useful face-quality starting point.

Relevant packaged source:

| Source | SHA-256 |
| --- | --- |
| `Aura/source/build_aura.py` | `8bbd744af128d9adfbb525f4b925e52266182591aa9f98b44e17d981c63c537f` |
| `Aura/source/upgrade_aura.py` | `4c33838e3ed7fff0c5a83468ecc03849a23c2603b574397f2b1acd8284cf620a` |
| `Aura/source/render_revision.py` | `dec2434fc07638afad246d076af21e4001bd0b0fd56c94a1fd0ed4fa85a19fec` |
| packaged source `LICENSE` | `c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4` |

Aura's helper copy of `axm_blender_forge.py` has the same Git blob
`3cd1a19102df018ce4964de46d7e1eb4cabe7ac0` as UC's
`tools/blender/axm_blender_forge.py` at the pinned UC commit below.

The Character Editor adaptation does **not** copy Aura's android body, scene,
object hierarchy or one-off animation. It adapts the continuous face profile,
local facial-volume equations and separate lip/eye construction into
`src/axm_character_editor/human_face.py`, parameterized by the existing
`human-v0` controls. See `AURA_FACE_EXTRACTION.md`.

Aura itself remains what its package says it is: a stylized procedural android
scene, not a photoreal human, game-optimized mesh or retargetable humanoid rig.

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

Useful inherited ideas: explicit Blueprint → deterministic scene plan, bounded
anatomy controls, separate geometry/appearance/behavior identities, editable
source output and creator-parts retention.

The donor still builds the older stylized rigid-part doll family. It is not
imported as the Character Editor runtime.

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

The current UC body also contains a generic pure-Python character-motion route:

- `src/axm_uc/character_recipe.py` blob
  `3512b75ec26603390811a080a7cd25dad53ad301`
- `src/axm_uc/character_motion.py` blob
  `8ebf5cdfa0f3dfbc828a11faefa4d4e949af0fc7`
- `src/axm_uc/character_performance.py` blob
  `0f5a6db409e67b6c48d82af00ef0cba1ed401b56`

Useful inherited ideas: standard glTF skins, inverse bind matrices,
`JOINTS_0`/`WEIGHTS_0`, explicit clips, body-relative fitting, normalized
weights, fresh-byte validation, smooth deformation methods, and separation
between structural proof and visual/game acceptance.

Character Editor's `human_asset.py` is a standalone adaptation. It does not
import UC at runtime.

## Odd Shift Duo package

Mike also supplied the historical `Odd-Shift-Duo.blend` and
`Odd-Shift-Duo-Package.zip`. They corroborate the Avatar Machine recovery lane
and remain useful regression evidence, but they are not the visual donor selected
for `human-v0`: Aura revision 2 is.

## Adaptation rule

Do not turn donor directories, chat uploads, UC, Avatar Machine or MorphTile into
hidden runtime dependencies.

Needed construction is adapted into first-class Character Editor modules with
tests. Source identities stay recorded so later repair can distinguish an AXM
adaptation from invented history.
