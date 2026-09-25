from __future__ import annotations

"""Deterministic human-v0 face construction adapted from AXM Aura revision 2.

Aura's source used a dense profile surface plus explicit local facial volumes. This
module keeps that useful construction idea but exposes it through Character Editor
controls and a renderer-neutral mesh recipe. No Blender dependency is required.

Coordinates returned here use metres, Y-up, +Z forward.
"""

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any, Iterable

FACE_MESH_SCHEMA = "axm.character.human-face-mesh/v0.1"
AURA_DONOR_Z_MIN = 1.381
AURA_DONOR_Z_MAX = 1.645
AURA_DONOR_Z_CENTER = (AURA_DONOR_Z_MIN + AURA_DONOR_Z_MAX) * 0.5

_AURA_PROFILE = (
    (1.381, .004, .030),
    (1.390, .025, .047),
    (1.405, .041, .063),
    (1.425, .058, .070),
    (1.450, .071, .074),
    (1.477, .079, .077),
    (1.500, .087, .079),
    (1.525, .086, .080),
    (1.550, .083, .080),
    (1.580, .081, .078),
    (1.610, .068, .065),
    (1.636, .035, .037),
    (1.645, .001, .003),
)


class HumanFaceError(ValueError):
    pass


@dataclass(frozen=True)
class FaceParameters:
    head_width: float
    head_depth: float
    jaw_width: float
    chin_size: float
    eye_size: float
    eye_spacing: float
    nose_width: float
    nose_projection: float
    mouth_width: float


def _gauss(x: float, center: float, width: float) -> float:
    return math.exp(-((x - center) / width) ** 2)


def _interp_profile(z: float, column: int) -> float:
    profile = _AURA_PROFILE
    for i in range(len(profile) - 1):
        if profile[i][0] <= z <= profile[i + 1][0]:
            a, b = profile[i], profile[i + 1]
            t = (z - a[0]) / (b[0] - a[0])
            prev = profile[max(0, i - 1)]
            nxt = profile[min(len(profile) - 1, i + 2)]
            m0 = (b[column] - prev[column]) / (b[0] - prev[0])
            m1 = (nxt[column] - a[column]) / (nxt[0] - a[0])
            return (
                (2 * t**3 - 3 * t*t + 1) * a[column]
                + (t**3 - 2*t*t + t) * (b[0] - a[0]) * m0
                + (-2*t**3 + 3*t*t) * b[column]
                + (t**3 - t*t) * (b[0] - a[0]) * m1
            )
    return profile[0 if z < profile[0][0] else -1][column]


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HumanFaceError(f"{label} must be numeric")
    value = float(value)
    if not math.isfinite(value):
        raise HumanFaceError(f"{label} must be finite")
    return value


def parameters_from_controls(controls: dict[str, Any]) -> FaceParameters:
    if not isinstance(controls, dict):
        raise HumanFaceError("controls must be an object")
    defaults = {
        "head_width": 1.0,
        "head_depth": 1.0,
        "jaw_width": 1.0,
        "chin_size": 1.0,
        "eye_size": 1.0,
        "eye_spacing": 1.0,
        "nose_width": 1.0,
        "nose_projection": 1.0,
        "mouth_width": 1.0,
    }
    values = {key: _finite_number(controls.get(key, default), key) for key, default in defaults.items()}
    for key, value in values.items():
        if not 0.5 <= value <= 1.6:
            raise HumanFaceError(f"{key} is outside the supported construction range")
    return FaceParameters(**values)


def _profile_dimensions(z: float, p: FaceParameters) -> tuple[float, float]:
    rx = _interp_profile(z, 1)
    ry = _interp_profile(z, 2)
    jaw = 1.0 + (p.jaw_width - 1.0) * _gauss(z, 1.425, .050)
    chin_width = 1.0 + (p.chin_size - 1.0) * _gauss(z, 1.397, .025) * .34
    return rx * p.head_width * jaw * chin_width, ry * p.head_depth


def _face_depth_y(x: float, z: float, p: FaceParameters) -> float:
    rx, ry = _profile_dimensions(z, p)
    u = min(.999, abs(x) / max(.001, rx))
    base = -ry * max(.001, 1 - u*u) ** .32

    nw = p.nose_width
    nose = p.nose_projection * (
        .023 * _gauss(x, 0, .010 * nw) * _gauss(z, 1.481, .011)
        + .014 * _gauss(x, 0, .0085 * nw) * _gauss(z, 1.508, .025)
    )
    wings = p.nose_projection * .006 * (
        _gauss(x, -.011 * nw, .008 * nw)
        + _gauss(x, .011 * nw, .008 * nw)
    ) * _gauss(z, 1.476, .007)

    eye_x = .035 * p.eye_spacing * p.head_width
    eye_w = .024 * p.eye_size * p.head_width
    cheeks = .007 * (
        _gauss(x, -.05 * p.head_width, .025 * p.head_width)
        + _gauss(x, .05 * p.head_width, .025 * p.head_width)
    ) * _gauss(z, 1.491, .020)
    sockets = .008 * (
        _gauss(x, -eye_x, eye_w)
        + _gauss(x, eye_x, eye_w)
    ) * _gauss(z, 1.525, .018 * p.eye_size)
    brows = .003 * (
        _gauss(x, -eye_x, .031 * p.head_width)
        + _gauss(x, eye_x, .031 * p.head_width)
    ) * _gauss(z, 1.551, .010)
    muzzle = .006 * _gauss(x, 0, .035 * p.mouth_width) * _gauss(z, 1.453, .015)
    chin = .003 * p.chin_size * _gauss(x, 0, .028 * p.jaw_width) * _gauss(z, 1.414, .011)
    return base - nose - wings - cheeks + sockets - brows - muzzle - chin


def _to_gltf(x: float, donor_y: float, donor_z: float) -> tuple[float, float, float]:
    return (x, donor_z - AURA_DONOR_Z_CENTER, -donor_y)


def _triangulate_quad(a: int, b: int, c: int, d: int) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    return (a, b, c), (a, c, d)


def build_face_surface(
    controls: dict[str, Any],
    *,
    radial_segments: int = 128,
    vertical_segments: int = 110,
) -> dict[str, Any]:
    if radial_segments < 32 or radial_segments > 512 or radial_segments % 2:
        raise HumanFaceError("radial_segments must be an even integer from 32 through 512")
    if vertical_segments < 24 or vertical_segments > 440:
        raise HumanFaceError("vertical_segments must be from 24 through 440")
    p = parameters_from_controls(controls)
    positions: list[tuple[float, float, float]] = []
    indices: list[tuple[int, int, int]] = []
    for j in range(vertical_segments + 1):
        donor_z = AURA_DONOR_Z_MIN + (AURA_DONOR_Z_MAX - AURA_DONOR_Z_MIN) * j / vertical_segments
        rx, ry = _profile_dimensions(donor_z, p)
        for i in range(radial_segments):
            angle = math.tau * i / radial_segments
            x = rx * math.cos(angle)
            if math.sin(angle) > 0:
                donor_y = _face_depth_y(x, donor_z, p)
            else:
                donor_y = -ry * math.sin(angle) + .011 * (1 - math.sin(angle))
            positions.append(_to_gltf(x, donor_y, donor_z))
    for j in range(vertical_segments):
        for i in range(radial_segments):
            a = j * radial_segments + i
            b = j * radial_segments + (i + 1) % radial_segments
            c = (j + 1) * radial_segments + (i + 1) % radial_segments
            d = (j + 1) * radial_segments + i
            indices.extend(_triangulate_quad(a, b, c, d))
    return {
        "schema": FACE_MESH_SCHEMA,
        "part": "face-shell",
        "material_role": "skin",
        "positions": positions,
        "triangles": indices,
        "topology": {
            "radial_segments": radial_segments,
            "vertical_segments": vertical_segments,
            "vertex_count": len(positions),
            "triangle_count": len(indices),
            "stable_across_controls": True,
        },
        "donor": {
            "name": "Aura revision 2 face construction",
            "source_sha256": "4c33838e3ed7fff0c5a83468ecc03849a23c2603b574397f2b1acd8284cf620a",
            "adaptation": "profile surface and local facial-volume equations parameterized for human-v0; topology mask removed so morph controls retain one index layout",
        },
    }


def build_lips(
    controls: dict[str, Any],
    *,
    horizontal_segments: int = 64,
    depth_segments: int = 8,
) -> list[dict[str, Any]]:
    if horizontal_segments < 16 or horizontal_segments > 256:
        raise HumanFaceError("horizontal_segments must be from 16 through 256")
    if depth_segments < 2 or depth_segments > 24:
        raise HumanFaceError("depth_segments must be from 2 through 24")
    p = parameters_from_controls(controls)
    result = []
    for upper in (True, False):
        positions: list[tuple[float, float, float]] = []
        triangles: list[tuple[int, int, int]] = []
        for i in range(horizontal_segments + 1):
            u = -1 + 2 * i / horizontal_segments
            x = u * .027 * p.mouth_width
            center = 1.447 + .0033 * u*u
            h = (.0038 if upper else .0050) * (1 - u*u) ** .65
            if upper:
                h += .0013 * (
                    _gauss(x, -.007 * p.mouth_width, .004 * p.mouth_width)
                    + _gauss(x, .007 * p.mouth_width, .004 * p.mouth_width)
                )
            for j in range(depth_segments + 1):
                t = j / depth_segments
                z = center + (1 if upper else -1) * h * t
                donor_y = (
                    _face_depth_y(x, z, p)
                    - .0005
                    - .0022 * (1 - u*u) * math.sin(math.pi * (t*.7 + .15))
                )
                positions.append(_to_gltf(x, donor_y, z))
        stride = depth_segments + 1
        for i in range(horizontal_segments):
            for j in range(depth_segments):
                a = i * stride + j
                b = (i + 1) * stride + j
                c = (i + 1) * stride + j + 1
                d = i * stride + j + 1
                triangles.extend(_triangulate_quad(a, b, c, d))
        result.append({
            "schema": FACE_MESH_SCHEMA,
            "part": "upper-lip" if upper else "lower-lip",
            "material_role": "lip",
            "positions": positions,
            "triangles": triangles,
        })
    return result


def _uv_ellipsoid(
    center: tuple[float, float, float],
    radii: tuple[float, float, float],
    *,
    lon: int = 32,
    lat: int = 16,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    cx, cy, cz = center
    rx, ry, rz = radii
    positions: list[tuple[float, float, float]] = []
    triangles: list[tuple[int, int, int]] = []
    for j in range(lat + 1):
        phi = math.pi * j / lat
        sy = math.cos(phi)
        ring = math.sin(phi)
        for i in range(lon):
            theta = math.tau * i / lon
            positions.append((cx + rx * ring * math.cos(theta), cy + ry * sy, cz + rz * ring * math.sin(theta)))
    for j in range(lat):
        for i in range(lon):
            a = j * lon + i
            b = j * lon + (i + 1) % lon
            c = (j + 1) * lon + (i + 1) % lon
            d = (j + 1) * lon + i
            if j != 0:
                triangles.append((a, b, d))
            if j != lat - 1:
                triangles.append((b, c, d))
    return positions, triangles


def build_eyes(controls: dict[str, Any]) -> list[dict[str, Any]]:
    p = parameters_from_controls(controls)
    result = []
    eye_x = .035 * p.eye_spacing * p.head_width
    eye_y = .013
    forward = .057 * p.head_depth
    size = p.eye_size
    for side, x in (("L", -eye_x), ("R", eye_x)):
        sclera_positions, sclera_triangles = _uv_ellipsoid(
            (x, eye_y, forward),
            (.024 * size * p.head_width, .021 * size, .021 * size * p.head_depth),
        )
        result.append({
            "schema": FACE_MESH_SCHEMA,
            "part": f"eye-{side.lower()}-sclera",
            "material_role": "sclera",
            "positions": sclera_positions,
            "triangles": sclera_triangles,
        })
        iris_positions, iris_triangles = _uv_ellipsoid(
            (x, eye_y, forward + .0205 * size * p.head_depth),
            (.0092 * size, .0092 * size, .0012),
            lon=32,
            lat=8,
        )
        result.append({
            "schema": FACE_MESH_SCHEMA,
            "part": f"eye-{side.lower()}-iris",
            "material_role": "iris",
            "positions": iris_positions,
            "triangles": iris_triangles,
        })
        pupil_positions, pupil_triangles = _uv_ellipsoid(
            (x, eye_y, forward + .0216 * size * p.head_depth),
            (.0036 * size, .0036 * size, .0008),
            lon=24,
            lat=6,
        )
        result.append({
            "schema": FACE_MESH_SCHEMA,
            "part": f"eye-{side.lower()}-pupil",
            "material_role": "pupil",
            "positions": pupil_positions,
            "triangles": pupil_triangles,
        })
    return result


def build_face_parts(controls: dict[str, Any]) -> list[dict[str, Any]]:
    return [build_face_surface(controls), *build_lips(controls), *build_eyes(controls)]


def bounds(parts: Iterable[dict[str, Any]]) -> dict[str, list[float]]:
    positions = [p for part in parts for p in part["positions"]]
    if not positions:
        raise HumanFaceError("face recipe produced no positions")
    return {
        "min": [min(p[i] for p in positions) for i in range(3)],
        "max": [max(p[i] for p in positions) for i in range(3)],
    }


def face_summary(controls: dict[str, Any]) -> dict[str, Any]:
    parts = build_face_parts(controls)
    return {
        "schema": "axm.character.human-face-summary/v0.1",
        "parts": len(parts),
        "vertices": sum(len(part["positions"]) for part in parts),
        "triangles": sum(len(part["triangles"]) for part in parts),
        "bounds_m": bounds(parts),
        "topology_status": "STABLE_INDEX_LAYOUT_WITHIN_HUMAN_V0",
        "truth": (
            "Renderer-neutral deterministic face construction adapted from the exact "
            "uploaded Aura revision 2 source; this is geometry evidence, not yet a "
            "target-engine-approved full-body game asset."
        ),
    }


def write_obj(controls: dict[str, Any], path: str | Path) -> Path:
    path = Path(path)
    parts = build_face_parts(controls)
    lines = [
        "# AXM Character Editor human-v0 Aura-derived face proof",
        "# metres; Y-up; +Z forward",
    ]
    offset = 0
    for part in parts:
        lines.append(f"o {part['part']}")
        for x, y, z in part["positions"]:
            lines.append(f"v {x:.9f} {y:.9f} {z:.9f}")
        for a, b, c in part["triangles"]:
            lines.append(f"f {a+1+offset} {b+1+offset} {c+1+offset}")
        offset += len(part["positions"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
