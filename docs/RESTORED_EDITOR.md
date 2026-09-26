# Restored character editor foundation

The main editor now connects the richer human-v0 work to a useful authoring loop:
edit Blueprint → build GLB locally → display that GLB → export the same bytes or
a verified game package. Future game adapters can consume the Blueprint, shared
rig, clips and named equipment sockets without depending on this editor UI.

## Source integration

- Main equipment/socket foundation: `d52f50d1d899353e6ad62a5d0181e164968a26d8`.
- Aura face quality floor, PR #11: `7244f16d31d5dab93900ac17229170918cd56d0d`.
- 3D editor/body/observation work, PR #8: `7cdd8cbe2d2458327ae7575331c8356f5ff4660f`.

Integration retains the newer Aura scalp and face materials, the fuller body
forms, both the equipment and observation package outputs, and both CLI commands.
The live renderer consumes standard POSITION/NORMAL/COLOR_0/JOINTS_0/WEIGHTS_0
accessors and encoded rotations. Tests compare its three animation palettes with
Python's independent exported-GLB decoder.

## Visual direction

Keep the existing quiet olive studio, with the character as the central subject.
Full body and face framing serve different authoring decisions. Keep controls
explicit, show all installed capabilities by default, and distinguish a rebuilding
or offline sketch from the current export. No stock avatar imagery substitutes
for rendered geometry.

## Local builder and extension points

`axm-character serve` binds only to loopback. It serves one generated HTML document
and accepts bounded, validated Blueprint JSON at `/api/preview` and `/api/package`.
Requests require the per-launch token in that page; foreign Host/Origin values
are rejected. It does not expose arbitrary filesystem paths, run user code, or
upload assets. Preview builds are serialized and cache four character states.

The browser keeps the latest edit when builds overlap, releases replaced GPU
buffers, and groups slider changes into undo steps. Import validation is atomic.
The Python builder remains the validation/export authority. The static HTML stays
usable for offline blueprint editing with a clearly labelled approximate sketch.

The browser viewer intentionally supports the exported human-v0 subset, including
18 joints and LINEAR quaternion tracks. A future family or material/animation
extension needs corresponding renderer capability tests; unsupported features
must not be silently treated as implemented.

## Remaining quality work

The current body, hands, hair and clothing remain procedural starter assets. This
change restores their strongest available construction; it does not make them
finished production characters. Target-engine import, clothing fit, facial
animation, UV/textures and runtime performance still require evidence.

The inherited SVG observation sheet is a coarse software review surface and
samples triangles; it is not the full-detail viewport or a visual acceptance gate.
The browser smoke job exercises the running app, downloads actual GLB/ZIP outputs,
and records bounded JPEG views in its logs without requiring artifact storage.
