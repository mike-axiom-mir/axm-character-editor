from __future__ import annotations

"""Dependency-free visual observation sheets for exported Character Editor GLBs.

The renderer deliberately consumes the published GLB bytes through the independent
``game_asset_verify.Asset`` decoder. It is a review surface, not the production
renderer. Its job is to keep visual evidence beside the asset that caused it.
"""

import hashlib
import html
import json
import math
from pathlib import Path
from typing import Any

from .game_asset_verify import Asset, GameAssetVerificationError

OBSERVATION_SCHEMA = "axm.character.visual-observation/v0.1"


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _rgb(factor: list[float] | tuple[float, ...] | None, fallback=(0.55, 0.58, 0.56)) -> tuple[float, float, float]:
    if not isinstance(factor, (list, tuple)) or len(factor) < 3:
        return fallback
    return tuple(_clamp(float(v), 0.0, 1.0) for v in factor[:3])


def _hex(rgb: tuple[float, float, float], shade: float = 1.0) -> str:
    vals = [round(_clamp(v * shade, 0.0, 1.0) * 255) for v in rgb]
    return "#%02x%02x%02x" % tuple(vals)


def _sub(a, b):
    return [a[i] - b[i] for i in range(3)]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _unit(v):
    length = math.sqrt(sum(x * x for x in v))
    if length <= 1e-12:
        return [0.0, 0.0, 1.0]
    return [x / length for x in v]


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _rotate_y(p, yaw: float, center_y: float) -> list[float]:
    x, y, z = p
    c, s = math.cos(yaw), math.sin(yaw)
    return [x * c - z * s, y - center_y, x * s + z * c]


def _material_rows(asset: Asset) -> list[tuple[tuple[float, float, float], int | None]]:
    materials = asset.doc.get("materials", [])
    meshes = asset.doc.get("meshes", [])
    rows: list[tuple[tuple[float, float, float], int | None]] = []
    for node in asset.nodes:
        if "mesh" not in node:
            continue
        mesh = meshes[node["mesh"]]
        for primitive in mesh.get("primitives", []):
            ref = primitive.get("material")
            color = (0.55, 0.58, 0.56)
            if isinstance(ref, int) and 0 <= ref < len(materials):
                pbr = materials[ref].get("pbrMetallicRoughness", {})
                color = _rgb(pbr.get("baseColorFactor"))
            rows.append((color, ref if isinstance(ref, int) else None))
    return rows


def _render_panel(
    asset: Asset,
    *,
    label: str,
    clip: str | None,
    time_s: float,
    yaw_degrees: float,
    x0: int,
    y0: int,
    width: int,
    height: int,
    max_triangles: int = 10500,
) -> tuple[str, dict[str, Any]]:
    deformed = asset.deformed_vertices(clip, time_s)
    records = asset.mesh_records()
    material_rows = _material_rows(asset)
    if not (len(deformed) == len(records) == len(material_rows)):
        raise GameAssetVerificationError("observation primitive ordering drifted")
    pts = [p for mesh in deformed for p in mesh]
    low = [min(p[i] for p in pts) for i in range(3)]
    high = [max(p[i] for p in pts) for i in range(3)]
    center_y = (low[1] + high[1]) * 0.5
    model_h = max(0.1, high[1] - low[1])
    camera_distance = max(2.3, model_h * 1.62)
    focal = min(width, height) * 1.66
    yaw = math.radians(yaw_degrees)
    light = _unit([-0.7, 1.1, 1.4])
    total_triangles = sum(len(r["indices"]) // 3 for r in records)
    stride = max(1, math.ceil(total_triangles / max_triangles))
    polygons = []
    seen = 0
    kept = 0
    for prim_index, (points, record, matrow) in enumerate(zip(deformed, records, material_rows)):
        cam = [_rotate_y(p, yaw, center_y) for p in points]
        color = matrow[0]
        indices = record["indices"]
        for k in range(0, len(indices), 3):
            seen += 1
            if (seen - 1) % stride:
                continue
            ia, ib, ic = indices[k:k + 3]
            a, b, c = cam[ia], cam[ib], cam[ic]
            za, zb, zc = camera_distance - a[2], camera_distance - b[2], camera_distance - c[2]
            if min(za, zb, zc) <= 0.08:
                continue
            pa = [x0 + width * .5 + a[0] * focal / za, y0 + height * .53 - a[1] * focal / za]
            pb = [x0 + width * .5 + b[0] * focal / zb, y0 + height * .53 - b[1] * focal / zb]
            pc = [x0 + width * .5 + c[0] * focal / zc, y0 + height * .53 - c[1] * focal / zc]
            normal = _unit(_cross(_sub(b, a), _sub(c, a)))
            shade = _clamp(.54 + .58 * abs(_dot(normal, light)), .48, 1.12)
            polygons.append(((za + zb + zc) / 3, pa, pb, pc, _hex(color, shade)))
            kept += 1
    polygons.sort(key=lambda row: row[0], reverse=True)
    body = [
        f'<g id="{html.escape(label.lower().replace(" ", "-"))}">',
        f'<rect x="{x0}" y="{y0}" width="{width}" height="{height}" rx="22" fill="#171c17" stroke="#313b30"/>',
        f'<ellipse cx="{x0 + width/2:.1f}" cy="{y0 + height*.89:.1f}" rx="{width*.23:.1f}" ry="{height*.025:.1f}" fill="#070907" opacity=".48"/>',
    ]
    for _, pa, pb, pc, fill in polygons:
        body.append(
            f'<polygon points="{pa[0]:.1f},{pa[1]:.1f} {pb[0]:.1f},{pb[1]:.1f} {pc[0]:.1f},{pc[1]:.1f}" fill="{fill}"/>'
        )
    body += [
        f'<rect x="{x0 + 18}" y="{y0 + 16}" width="{min(width-36, 168)}" height="28" rx="5" fill="#0d110d" stroke="#3c493a"/>',
        f'<text x="{x0 + 30}" y="{y0 + 35}" fill="#dce5d6" font-family="system-ui,sans-serif" font-size="12" letter-spacing="1.2">{html.escape(label.upper())}</text>',
        '</g>',
    ]
    return "\n".join(body), {
        "label": label,
        "clip": clip,
        "time_s": time_s,
        "yaw_degrees": yaw_degrees,
        "source_triangles": total_triangles,
        "rendered_triangles": kept,
        "triangle_stride": stride,
        "bounds_m": {"min": low, "max": high},
    }


def render_observation_sheet(body: bytes, *, width: int = 1500, height: int = 1080) -> tuple[str, dict[str, Any]]:
    asset = Asset(body)
    panels = [
        ("Front idle", "Idle", .55, 0.0),
        ("Three-quarter idle", "Idle", .55, -35.0),
        ("Side idle", "Idle", .55, -90.0),
        ("Walk mid", "Walk", .25, -35.0),
        ("Wave peak", "Wave", .82, -35.0),
    ]
    margin = 28
    gap = 18
    top_h = 590
    top_w = (width - 2 * margin - 2 * gap) // 3
    lower_w = (width - 2 * margin - gap) // 2
    rows = []
    metadata = []
    for i, (label, clip, t, yaw) in enumerate(panels):
        if i < 3:
            x = margin + i * (top_w + gap)
            y = 94
            w, h = top_w, top_h
        else:
            x = margin + (i - 3) * (lower_w + gap)
            y = 94 + top_h + gap
            w, h = lower_w, height - y - margin
        svg, meta = _render_panel(
            asset,
            label=label,
            clip=clip,
            time_s=t,
            yaw_degrees=yaw,
            x0=x,
            y0=y,
            width=w,
            height=h,
        )
        rows.append(svg)
        metadata.append(meta)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'\
        '<rect width="100%" height="100%" fill="#0d100d"/>'
        '<text x="28" y="42" fill="#f0f3eb" font-family="system-ui,sans-serif" font-size="22" font-weight="700">AXM CHARACTER EDITOR · ACTUAL EXPORTED GLB OBSERVATION</text>'
        '<text x="28" y="68" fill="#91a08d" font-family="system-ui,sans-serif" font-size="12">Independent GLB decode · encoded skin + clips · review surface, not production renderer</text>'
        + "\n".join(rows)
        + '</svg>'
    )
    receipt = {
        "schema": OBSERVATION_SCHEMA,
        "source_sha256": asset.sha256,
        "sheet": "observation-sheet.svg",
        "panels": metadata,
        "truth": (
            "Dependency-free perspective review generated from the published GLB through the independent decoder. "
            "It preserves source identity and encoded deformation, but visual quality still needs human/machine review and target-engine evidence."
        ),
    }
    return svg, receipt


def write_observation_pack(glb_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    glb_path = Path(glb_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    body = glb_path.read_bytes()
    svg, receipt = render_observation_sheet(body)
    (output_dir / "observation-sheet.svg").write_text(svg, encoding="utf-8")
    receipt = {**receipt, "glb_path": glb_path.name, "glb_sha256": hashlib.sha256(body).hexdigest()}
    (output_dir / "visual-observation.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt
