from __future__ import annotations

"""Deterministic human-v0 face construction adapted from AXM Aura revision 2.

Aura's source used a dense profile surface plus explicit local facial volumes.
This module keeps that construction as the human-v0 quality floor and exposes it
through Character Editor controls without requiring Blender.

Coordinates returned here use metres, Y-up, +Z forward.
"""

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any, Iterable

FACE_MESH_SCHEMA = "axm.character.human-face-mesh/v0.2"
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


def _skin_rgb(controls: dict[str, Any]) -> tuple[float, float, float]:
    value = controls.get("skin", "#c98f76")
    if not isinstance(value, str) or len(value) != 7 or not value.startswith("#"):
        value = "#c98f76"
    try:
        return tuple(int(value[i:i+2], 16) / 255 for i in (1, 3, 5))
    except ValueError:
        return (201/255, 143/255, 118/255)


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
    values = {
        key: _finite_number(controls.get(key, default), key)
        for key, default in defaults.items()
    }
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


def _triangulate_quad(
    a: int, b: int, c: int, d: int
) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    return (a, b, c), (a, c, d)


def _part(
    name: str,
    material_role: str,
    positions: list[tuple[float, float, float]],
    triangles: list[tuple[int, int, int]],
    **extra: Any,
) -> dict[str, Any]:
    return {
        "schema": FACE_MESH_SCHEMA,
        "part": name,
        "material_role": material_role,
        "positions": positions,
        "triangles": triangles,
        **extra,
    }


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
            positions.append((
                cx + rx * ring * math.cos(theta),
                cy + ry * sy,
                cz + rz * ring * math.sin(theta),
            ))
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


def _donor_ribbon(
    name: str,
    material_role: str,
    points: list[tuple[float, float, float]],
    width: float,
) -> dict[str, Any]:
    positions: list[tuple[float, float, float]] = []
    triangles: list[tuple[int, int, int]] = []
    half = width * .5
    for x, y, z in points:
        positions.append(_to_gltf(x, y, z - half))
        positions.append(_to_gltf(x, y, z + half))
    for i in range(len(points) - 1):
        a = i * 2
        b = a + 2
        triangles.extend(_triangulate_quad(a, b, b + 1, a + 1))
    return _part(name, material_role, positions, triangles)


def _donor_disc(
    name: str,
    material_role: str,
    center: tuple[float, float, float],
    outer_radius: float,
    *,
    inner_radius: float = 0.0,
    segments: int = 48,
) -> dict[str, Any]:
    cx, cy, cz = center
    positions: list[tuple[float, float, float]] = []
    triangles: list[tuple[int, int, int]] = []
    if inner_radius <= 0:
        positions.append(_to_gltf(cx, cy, cz))
        for i in range(segments):
            a = math.tau * i / segments
            positions.append(_to_gltf(
                cx + outer_radius * math.cos(a),
                cy,
                cz + outer_radius * math.sin(a),
            ))
        for i in range(segments):
            triangles.append((0, 1 + i, 1 + (i + 1) % segments))
    else:
        for radius in (inner_radius, outer_radius):
            for i in range(segments):
                a = math.tau * i / segments
                positions.append(_to_gltf(
                    cx + radius * math.cos(a),
                    cy,
                    cz + radius * math.sin(a),
                ))
        for i in range(segments):
            a = i
            b = (i + 1) % segments
            c = segments + (i + 1) % segments
            d = segments + i
            triangles.extend(_triangulate_quad(a, b, c, d))
    return _part(name, material_role, positions, triangles)


def build_face_surface(
    controls: dict[str, Any],
    *,
    radial_segments: int = 160,
    vertical_segments: int = 132,
) -> dict[str, Any]:
    if radial_segments < 32 or radial_segments > 512 or radial_segments % 2:
        raise HumanFaceError("radial_segments must be an even integer from 32 through 512")
    if vertical_segments < 24 or vertical_segments > 440:
        raise HumanFaceError("vertical_segments must be from 24 through 440")
    p = parameters_from_controls(controls)
    skin_rgb = _skin_rgb(controls)
    positions: list[tuple[float, float, float]] = []
    colors: list[tuple[float, float, float, float]] = []
    indices: list[tuple[int, int, int]] = []
    for j in range(vertical_segments + 1):
        donor_z = (
            AURA_DONOR_Z_MIN
            + (AURA_DONOR_Z_MAX - AURA_DONOR_Z_MIN) * j / vertical_segments
        )
        rx, ry = _profile_dimensions(donor_z, p)
        for i in range(radial_segments):
            angle = math.tau * i / radial_segments
            x = rx * math.cos(angle)
            front = max(0.0, math.sin(angle))
            if front > 0:
                donor_y = _face_depth_y(x, donor_z, p)
            else:
                donor_y = -ry * math.sin(angle) + .011 * (1 - math.sin(angle))
            positions.append(_to_gltf(x, donor_y, donor_z))

            blush = (
                _gauss(x, -.054 * p.head_width, .022 * p.head_width)
                + _gauss(x, .054 * p.head_width, .022 * p.head_width)
            ) * _gauss(donor_z, 1.490, .020) * front
            under_eye = (
                _gauss(x, -.035 * p.eye_spacing * p.head_width, .023 * p.head_width)
                + _gauss(x, .035 * p.eye_spacing * p.head_width, .023 * p.head_width)
            ) * _gauss(donor_z, 1.505, .012) * front
            colors.append((
                min(1.0, skin_rgb[0] * (1.0 + .035 * blush)),
                max(0.0, skin_rgb[1] * (1.0 - .050 * blush - .015 * under_eye)),
                max(0.0, skin_rgb[2] * (1.0 - .035 * blush - .008 * under_eye)),
                1.0,
            ))

    for j in range(vertical_segments):
        for i in range(radial_segments):
            a = j * radial_segments + i
            b = j * radial_segments + (i + 1) % radial_segments
            c = (j + 1) * radial_segments + (i + 1) % radial_segments
            d = (j + 1) * radial_segments + i
            # The donor profile is authored outside-in relative to this grid.
            # Reverse the face-shell winding so exported normals point outward.
            indices.extend(tuple(reversed(tri)) for tri in _triangulate_quad(a, b, c, d))
    return _part(
        "face-shell",
        "face_skin",
        positions,
        indices,
        colors=colors,
        topology={
            "radial_segments": radial_segments,
            "vertical_segments": vertical_segments,
            "vertex_count": len(positions),
            "triangle_count": len(indices),
            "stable_across_controls": True,
        },
        donor={
            "name": "Aura revision 2 face construction",
            "source_sha256": "4c33838e3ed7fff0c5a83468ecc03849a23c2603b574397f2b1acd8284cf620a",
            "adaptation": (
                "dense profile/local facial volumes plus dermal vertex variation; "
                "face-shell topology remains stable across human-v0 controls"
            ),
        },
    )


def build_lips(
    controls: dict[str, Any],
    *,
    horizontal_segments: int = 96,
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
        result.append(_part(
            "upper-lip" if upper else "lower-lip",
            "lip",
            positions,
            triangles,
        ))
    return result


def build_mouth_details(controls: dict[str, Any]) -> list[dict[str, Any]]:
    p = parameters_from_controls(controls)
    seam = []
    for i in range(65):
        u = -1 + 2 * i / 64
        x = u * .027 * p.mouth_width
        z = 1.447 + .0033 * u*u
        donor_y = _face_depth_y(x, z, p) - .0031 * (1 - .35*abs(u))
        seam.append((x, donor_y, z))
    parts = [_donor_ribbon("mouth-seam", "mouth_seam", seam, .00105)]

    philtrum_w = .0065 * p.mouth_width
    for side in (-1, 1):
        points = []
        for i in range(7):
            t = i / 6
            x = side * philtrum_w * (1 - .38*t)
            z = 1.458 + .015*t
            donor_y = _face_depth_y(x, z, p) - .0009
            points.append((x, donor_y, z))
        parts.append(_donor_ribbon(
            f"philtrum-{'l' if side < 0 else 'r'}",
            "skin_detail",
            points,
            .0007,
        ))
    return parts


def build_nose_details(controls: dict[str, Any]) -> list[dict[str, Any]]:
    p = parameters_from_controls(controls)
    result = []
    nw = p.nose_width
    for side in (-1, 1):
        x = side * .0105 * nw
        z = 1.474
        donor_y = _face_depth_y(x, z, p) - .0016 * p.nose_projection
        center = _to_gltf(x, donor_y, z)
        ala_positions, ala_triangles = _uv_ellipsoid(
            center,
            (.0070*nw, .0048, .0042*p.nose_projection),
            lon=28,
            lat=12,
        )
        result.append(_part(
            f"nose-ala-{'l' if side < 0 else 'r'}",
            "skin_detail",
            ala_positions,
            ala_triangles,
        ))

        opening_center = _to_gltf(
            side * .0095 * nw,
            donor_y - .0030 * p.nose_projection,
            1.4725,
        )
        opening_positions, opening_triangles = _uv_ellipsoid(
            opening_center,
            (.0030*nw, .0015, .00085),
            lon=22,
            lat=8,
        )
        result.append(_part(
            f"nostril-{'l' if side < 0 else 'r'}",
            "nostril",
            opening_positions,
            opening_triangles,
        ))

    col_y = _face_depth_y(0, 1.468, p) - .0014 * p.nose_projection
    col_positions, col_triangles = _uv_ellipsoid(
        _to_gltf(0, col_y, 1.468),
        (.0038*nw, .0060, .0028*p.nose_projection),
        lon=24,
        lat=10,
    )
    result.append(_part(
        "nose-columella",
        "skin_detail",
        col_positions,
        col_triangles,
    ))
    return result


def build_ears(controls: dict[str, Any]) -> list[dict[str, Any]]:
    p = parameters_from_controls(controls)
    result = []
    for side in (-1, 1):
        x = side * .091 * p.head_width
        outer_center = _to_gltf(x, .010*p.head_depth, 1.525)
        outer_positions, outer_triangles = _uv_ellipsoid(
            outer_center,
            (.0125*p.head_width, .029, .0125*p.head_depth),
            lon=30,
            lat=14,
        )
        result.append(_part(
            f"ear-{'l' if side < 0 else 'r'}",
            "skin",
            outer_positions,
            outer_triangles,
        ))
        inner_center = _to_gltf(
            side * .094 * p.head_width,
            .002*p.head_depth,
            1.525,
        )
        inner_positions, inner_triangles = _uv_ellipsoid(
            inner_center,
            (.0060*p.head_width, .018, .0040*p.head_depth),
            lon=24,
            lat=10,
        )
        result.append(_part(
            f"ear-inner-{'l' if side < 0 else 'r'}",
            "skin_detail",
            inner_positions,
            inner_triangles,
        ))
    return result


def _eye_lid_point(
    p: FaceParameters,
    side: int,
    u: float,
    upper: bool,
) -> tuple[float, float, float]:
    cx = side * .035 * p.eye_spacing * p.head_width
    half_w = .0275 * p.eye_size * p.head_width
    x = cx + u * half_w
    arch = max(0.0, 1 - u*u) ** .70
    z = 1.526 + (.0105 if upper else -.0072) * p.eye_size * arch
    donor_y = _face_depth_y(x, z, p) - .0050 * p.head_depth
    return x, donor_y, z


def build_eyes(controls: dict[str, Any]) -> list[dict[str, Any]]:
    p = parameters_from_controls(controls)
    result = []
    center_z = 1.526
    for side in (-1, 1):
        cx = side * .035 * p.eye_spacing * p.head_width
        half_w = .0275 * p.eye_size * p.head_width

        positions: list[tuple[float, float, float]] = []
        triangles: list[tuple[int, int, int]] = []
        horizontal = 48
        vertical = 12
        for i in range(horizontal + 1):
            u = -1 + 2 * i / horizontal
            arch = max(0.0, 1 - u*u) ** .70
            lo = -.0072 * p.eye_size * arch
            hi = .0105 * p.eye_size * arch
            x = cx + u * half_w
            for j in range(vertical + 1):
                t = j / vertical
                z = center_z + lo + (hi-lo)*t
                donor_y = (
                    _face_depth_y(x, z, p)
                    - .0053 * p.head_depth
                    + .0011 * (2*t - 1) ** 2
                )
                positions.append(_to_gltf(x, donor_y, z))
        stride = vertical + 1
        for i in range(horizontal):
            for j in range(vertical):
                a = i * stride + j
                b = (i + 1) * stride + j
                c = (i + 1) * stride + j + 1
                d = i * stride + j + 1
                triangles.extend(_triangulate_quad(a, b, c, d))
        result.append(_part(
            f"eye-{'l' if side < 0 else 'r'}-sclera",
            "sclera",
            positions,
            triangles,
        ))

        eye_front = _face_depth_y(cx, center_z, p) - .0066 * p.head_depth
        iris_radius = .0090 * p.eye_size
        result.append(_donor_disc(
            f"eye-{'l' if side < 0 else 'r'}-limbal",
            "limbal",
            (cx, eye_front - .0008, center_z),
            iris_radius * 1.08,
            inner_radius=iris_radius * .88,
            segments=64,
        ))
        result.append(_donor_disc(
            f"eye-{'l' if side < 0 else 'r'}-iris",
            "iris",
            (cx, eye_front - .0016, center_z),
            iris_radius * .88,
            segments=64,
        ))
        result.append(_donor_disc(
            f"eye-{'l' if side < 0 else 'r'}-pupil",
            "pupil",
            (cx, eye_front - .0024, center_z),
            .00345 * p.eye_size,
            segments=48,
        ))
        result.append(_donor_disc(
            f"eye-{'l' if side < 0 else 'r'}-catchlight",
            "catchlight",
            (
                cx - .0030 * p.eye_size,
                eye_front - .0032,
                center_z + .0038 * p.eye_size,
            ),
            .00155 * p.eye_size,
            segments=24,
        ))

        for upper in (True, False):
            lid_points = [
                _eye_lid_point(p, side, -1 + 2*i/40, upper)
                for i in range(41)
            ]
            result.append(_donor_ribbon(
                f"eye-{'l' if side < 0 else 'r'}-{'upper' if upper else 'lower'}-lid",
                "eyelid",
                lid_points,
                .00165 if upper else .0012,
            ))
            if upper:
                lash_points = [
                    (x, y - .00085, z + .00025)
                    for x, y, z in lid_points[5:-5]
                ]
                result.append(_donor_ribbon(
                    f"eye-{'l' if side < 0 else 'r'}-lashline",
                    "brow",
                    lash_points,
                    .00075,
                ))

        brow_points = []
        for i in range(29):
            u = -1 + 2*i/28
            x = cx + u * .029 * p.head_width
            z = 1.558 + .0055 * (1-u*u) + side*u*.0012
            donor_y = _face_depth_y(x, z, p) - .0018
            brow_points.append((x, donor_y, z))
        result.append(_donor_ribbon(
            f"brow-{'l' if side < 0 else 'r'}",
            "brow",
            brow_points,
            .00215,
        ))
    return result


def build_face_parts(controls: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        build_face_surface(controls),
        *build_ears(controls),
        *build_lips(controls),
        *build_mouth_details(controls),
        *build_nose_details(controls),
        *build_eyes(controls),
    ]


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
        "schema": "axm.character.human-face-summary/v0.2",
        "parts": len(parts),
        "vertices": sum(len(part["positions"]) for part in parts),
        "triangles": sum(len(part["triangles"]) for part in parts),
        "bounds_m": bounds(parts),
        "topology_status": "STABLE_FACE_SHELL_INDEX_LAYOUT_WITHIN_HUMAN_V0",
        "quality_floor": "AURA_REVISION_2_GEOMETRY_FEATURES_ADAPTED",
        "features": [
            "dense-profile face shell",
            "dermal vertex variation",
            "separate sculpted lips and mouth seam",
            "nose ala/columella/recessed nostril detail",
            "almond sclera surfaces",
            "iris + limbal ring + pupil + catchlight",
            "upper/lower eyelid rims and lashline",
            "shaped brows",
            "outer/inner ear forms",
        ],
        "truth": (
            "Renderer-neutral deterministic face construction adapted from the exact "
            "uploaded Aura revision 2 source. This deliberately raises human-v0's "
            "default face construction toward the proven Aura quality floor while "
            "keeping the reusable character/GLB contract separate."
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
