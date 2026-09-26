from __future__ import annotations

"""Pure-Python human-v0 rigged GLB candidate builder.

This combines the Aura-derived face recipe with a bounded human body, one shared
humanoid skeleton, normalized skin weights, and a small starter clip library.
It does not require Blender.

Coordinates: metres, Y-up, +Z forward.
"""

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import struct
from typing import Any, Iterable

from .human_face import build_face_parts
from .equipment import SOCKET_SCHEMA, compile_human_v0_equipment, validate_equipment_contract

GLB_SCHEMA = "axm.character.game-asset/v0.1"
RIG_ID = "axm-humanoid-rig-v0"


class HumanAssetError(ValueError):
    pass


def _num(v: Any, default: float = 1.0) -> float:
    if v is None:
        return default
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)):
        raise HumanAssetError("control must be finite numeric")
    return float(v)


def _hex_rgb(value: str, default: str) -> tuple[float, float, float, float]:
    value = value if isinstance(value, str) else default
    if len(value) != 7 or not value.startswith("#"):
        value = default
    try:
        rgb = tuple(int(value[i:i+2], 16) / 255 for i in (1, 3, 5))
    except ValueError:
        rgb = tuple(int(default[i:i+2], 16) / 255 for i in (1, 3, 5))
    return (*rgb, 1.0)


def _quat(axis: tuple[float, float, float], degrees: float) -> list[float]:
    length = math.sqrt(sum(v*v for v in axis))
    if length <= 0:
        raise HumanAssetError("zero quaternion axis")
    half = math.radians(degrees) * 0.5
    s = math.sin(half) / length
    return [axis[0]*s, axis[1]*s, axis[2]*s, math.cos(half)]


def _qmul(a: list[float], b: list[float]) -> list[float]:
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    q = [
        aw*bx + ax*bw + ay*bz - az*by,
        aw*by - ax*bz + ay*bw + az*bx,
        aw*bz + ax*by - ay*bx + az*bw,
        aw*bw - ax*bx - ay*by - az*bz,
    ]
    n = math.sqrt(sum(v*v for v in q))
    if n <= 1e-12:
        raise HumanAssetError("quaternion composition collapsed")
    return [v/n for v in q]


def _compose(*quaternions: list[float]) -> list[float]:
    result = [0.0, 0.0, 0.0, 1.0]
    for q in quaternions:
        result = _qmul(result, q)
    return result


def _normalize_weights(rows: list[dict[str, float]]) -> list[dict[str, float]]:
    out = []
    for row in rows:
        items = [(k, float(v)) for k, v in row.items() if v > 0]
        items.sort(key=lambda item: (-item[1], item[0]))
        items = items[:4]
        total = sum(v for _, v in items)
        if total <= 0:
            raise HumanAssetError("empty skin row")
        out.append({k: v / total for k, v in items})
    return out


@dataclass(frozen=True)
class BodyMetrics:
    scale: float
    foot_h: float
    lower_leg: float
    upper_leg: float
    pelvis_h: float
    torso_h: float
    neck_h: float
    head_h: float
    hip_y: float
    chest_y: float
    neck_y: float
    head_y: float
    shoulder_half: float
    hip_half: float
    upper_arm: float
    forearm: float
    hand_len: float
    build: float


def body_metrics(controls: dict[str, Any]) -> BodyMetrics:
    scale = _num(controls.get("height"), 1.0)
    leg = _num(controls.get("leg_length"), 1.0)
    torso = _num(controls.get("torso_length"), 1.0)
    arm = _num(controls.get("arm_length"), 1.0)
    head = _num(controls.get("head_scale"), 1.0)
    build = _num(controls.get("build"), 1.0)
    foot_h = .06 * scale
    lower_leg = .40 * leg * scale
    upper_leg = .40 * leg * scale
    pelvis_h = .14 * scale
    torso_h = .40 * torso * scale
    neck_h = .08 * scale
    head_h = .264 * head * scale
    hip_y = foot_h + lower_leg + upper_leg
    chest_y = hip_y + pelvis_h + torso_h * .68
    neck_y = hip_y + pelvis_h + torso_h
    head_y = neck_y + neck_h + head_h * .50
    shoulder_half = .20 * _num(controls.get("shoulder_width"), 1.0) * build * scale
    hip_half = .145 * _num(controls.get("hip_width"), 1.0) * build * scale
    return BodyMetrics(
        scale=scale,
        foot_h=foot_h,
        lower_leg=lower_leg,
        upper_leg=upper_leg,
        pelvis_h=pelvis_h,
        torso_h=torso_h,
        neck_h=neck_h,
        head_h=head_h,
        hip_y=hip_y,
        chest_y=chest_y,
        neck_y=neck_y,
        head_y=head_y,
        shoulder_half=shoulder_half,
        hip_half=hip_half,
        upper_arm=.30*arm*scale,
        forearm=.265*arm*scale,
        hand_len=.16*arm*scale,
        build=build,
    )


def skeleton(controls: dict[str, Any]) -> list[dict[str, Any]]:
    m = body_metrics(controls)
    ankle_y = m.foot_h
    knee_y = ankle_y + m.lower_leg
    hip_y = m.hip_y
    pelvis_y = hip_y + m.pelvis_h * .45
    spine_y = hip_y + m.pelvis_h + m.torso_h * .28
    chest_y = m.chest_y
    neck_y = m.neck_y
    head_y = m.head_y
    shoulder_y = chest_y + m.torso_h * .10
    rows = [
        ("Root", None, (0.0, 0.0, 0.0)),
        ("Pelvis", "Root", (0.0, pelvis_y, 0.0)),
        ("Spine", "Pelvis", (0.0, spine_y-pelvis_y, 0.0)),
        ("Chest", "Spine", (0.0, chest_y-spine_y, 0.0)),
        ("Neck", "Chest", (0.0, neck_y-chest_y, 0.0)),
        ("Head", "Neck", (0.0, head_y-neck_y, 0.0)),
        ("UpperArm.L", "Chest", (-m.shoulder_half, shoulder_y-chest_y, 0.0)),
        ("Forearm.L", "UpperArm.L", (-m.upper_arm, 0.0, 0.0)),
        ("Hand.L", "Forearm.L", (-m.forearm, 0.0, 0.0)),
        ("UpperArm.R", "Chest", (m.shoulder_half, shoulder_y-chest_y, 0.0)),
        ("Forearm.R", "UpperArm.R", (m.upper_arm, 0.0, 0.0)),
        ("Hand.R", "Forearm.R", (m.forearm, 0.0, 0.0)),
        ("Thigh.L", "Pelvis", (-m.hip_half*.45, hip_y-pelvis_y, 0.0)),
        ("Shin.L", "Thigh.L", (0.0, -m.upper_leg, 0.0)),
        ("Foot.L", "Shin.L", (0.0, -m.lower_leg, 0.0)),
        ("Thigh.R", "Pelvis", (m.hip_half*.45, hip_y-pelvis_y, 0.0)),
        ("Shin.R", "Thigh.R", (0.0, -m.upper_leg, 0.0)),
        ("Foot.R", "Shin.R", (0.0, -m.lower_leg, 0.0)),
    ]
    world: dict[str, tuple[float, float, float]] = {}
    result = []
    for jid, parent, translation in rows:
        if parent is None:
            w = translation
        else:
            pw = world[parent]
            w = tuple(pw[i] + translation[i] for i in range(3))
        world[jid] = w
        result.append({
            "id": jid,
            "parent": parent,
            "translation": list(translation),
            "world": list(w),
        })
    return result


def _triangulate_quad(a: int, b: int, c: int, d: int) -> list[tuple[int, int, int]]:
    return [(a, b, c), (a, c, d)]


def _loft_y(
    name: str,
    rings: list[tuple[float, float, float, dict[str, float]]],
    *,
    segments: int = 40,
    material_role: str,
) -> dict[str, Any]:
    positions: list[tuple[float, float, float]] = []
    triangles: list[tuple[int, int, int]] = []
    weights: list[dict[str, float]] = []
    for y, rx, rz, row in rings:
        for i in range(segments):
            a = math.tau * i / segments
            positions.append((rx*math.cos(a), y, rz*math.sin(a)))
            weights.append(dict(row))
    for j in range(len(rings)-1):
        for i in range(segments):
            a=j*segments+i
            b=j*segments+(i+1)%segments
            c=(j+1)*segments+(i+1)%segments
            d=(j+1)*segments+i
            triangles.extend(_triangulate_quad(a,b,c,d))
    return {
        "id": name,
        "positions": positions,
        "triangles": triangles,
        "weights": _normalize_weights(weights),
        "material_role": material_role,
    }


def _tube_x(
    name: str,
    rings: list[tuple[float, float, float, float, dict[str, float]]],
    *,
    segments: int = 28,
    material_role: str,
) -> dict[str, Any]:
    positions=[]
    triangles=[]
    weights=[]
    for x,y,ry,rz,row in rings:
        for i in range(segments):
            a=math.tau*i/segments
            positions.append((x,y+ry*math.cos(a),rz*math.sin(a)))
            weights.append(dict(row))
    for j in range(len(rings)-1):
        for i in range(segments):
            a=j*segments+i
            b=j*segments+(i+1)%segments
            c=(j+1)*segments+(i+1)%segments
            d=(j+1)*segments+i
            triangles.extend(_triangulate_quad(a,b,c,d))
    return {
        "id":name,
        "positions":positions,
        "triangles":triangles,
        "weights":_normalize_weights(weights),
        "material_role":material_role,
    }


def _tube_y(
    name: str,
    x: float,
    rings: list[tuple[float, float, float, dict[str, float]]],
    *,
    segments: int = 28,
    material_role: str,
) -> dict[str, Any]:
    positions=[]
    triangles=[]
    weights=[]
    for y,rx,rz,row in rings:
        for i in range(segments):
            a=math.tau*i/segments
            positions.append((x+rx*math.cos(a),y,rz*math.sin(a)))
            weights.append(dict(row))
    for j in range(len(rings)-1):
        for i in range(segments):
            a=j*segments+i
            b=j*segments+(i+1)%segments
            c=(j+1)*segments+(i+1)%segments
            d=(j+1)*segments+i
            triangles.extend(_triangulate_quad(a,b,c,d))
    return {
        "id":name,
        "positions":positions,
        "triangles":triangles,
        "weights":_normalize_weights(weights),
        "material_role":material_role,
    }


def _ellipsoid(
    name: str,
    center: tuple[float,float,float],
    radii: tuple[float,float,float],
    weight: dict[str,float],
    material_role: str,
    *,
    lon: int=32,
    lat: int=16,
) -> dict[str, Any]:
    cx,cy,cz=center
    rx,ry,rz=radii
    positions=[]
    triangles=[]
    weights=[]
    for j in range(lat+1):
        phi=math.pi*j/lat
        sy=math.cos(phi)
        ring=math.sin(phi)
        for i in range(lon):
            t=math.tau*i/lon
            positions.append((cx+rx*ring*math.cos(t),cy+ry*sy,cz+rz*ring*math.sin(t)))
            weights.append(dict(weight))
    for j in range(lat):
        for i in range(lon):
            a=j*lon+i
            b=j*lon+(i+1)%lon
            c=(j+1)*lon+(i+1)%lon
            d=(j+1)*lon+i
            if j:
                triangles.append((a,b,d))
            if j!=lat-1:
                triangles.append((b,c,d))
    return {
        "id":name,
        "positions":positions,
        "triangles":triangles,
        "weights":_normalize_weights(weights),
        "material_role":material_role,
    }


def _translate_part(
    part: dict[str, Any],
    offset: tuple[float,float,float],
    scale: float,
    joint: str,
) -> dict[str, Any]:
    ox,oy,oz=offset
    result = {
        "id":part["part"],
        "positions":[(ox+x*scale,oy+y*scale,oz+z*scale) for x,y,z in part["positions"]],
        "triangles":list(part["triangles"]),
        "weights":[{joint:1.0} for _ in part["positions"]],
        "material_role":part["material_role"],
    }
    if "colors" in part:
        result["colors"] = [tuple(row) for row in part["colors"]]
    return result


def _hair_end_phi(style: str, angle: float) -> float:
    front=max(0.0,math.sin(angle))
    if style=="short":
        return 1.78-.70*front**.42
    if style=="swept":
        return 2.05-.98*front**.38+.16*math.cos(angle)*front
    if style=="bob":
        return 2.34-1.30*front**.35+.07*math.cos(angle)*front
    return 2.38-1.25*front**.35+.06*math.cos(angle)*front


def _hair_shell(
    name: str,
    center: tuple[float,float,float],
    radii: tuple[float,float,float],
    *,
    style: str,
    joint: str = "Head",
    radial_segments: int = 96,
    vertical_segments: int = 28,
) -> dict[str, Any]:
    """Open scalp/hair shell adapted from Aura's swept-bob construction.

    Unlike the old full ellipsoid cap, this intentionally leaves the face open.
    """
    cx,cy,cz=center
    rx,ry,rz=radii
    positions=[]
    triangles=[]
    weights=[]
    for j in range(vertical_segments+1):
        t=j/vertical_segments
        for i in range(radial_segments):
            a=math.tau*i/radial_segments
            front=max(0.0,math.sin(a))
            end_phi=_hair_end_phi(style,a)
            phi=.025+(end_phi-.025)*t
            x=cx+rx*math.sin(phi)*math.cos(a)
            y=cy+ry*math.cos(phi)
            z=cz+rz*math.sin(phi)*math.sin(a)
            # Slight asymmetry keeps the cap from reading as a perfect helmet.
            if style in ("swept","bob","long") and front>0:
                x-=.010*rx/radii[0]*front*(1-t)*math.sin(a*.5)
            positions.append((x,y,z))
            weights.append({joint:1.0})
    for j in range(vertical_segments):
        for i in range(radial_segments):
            a=j*radial_segments+i
            b=j*radial_segments+(i+1)%radial_segments
            c=(j+1)*radial_segments+(i+1)%radial_segments
            d=(j+1)*radial_segments+i
            # Match the outward winding used by the ellipsoid helper.
            if j:
                triangles.append((a,b,d))
            triangles.append((b,c,d))
    return {
        "id":name,
        "positions":positions,
        "triangles":triangles,
        "weights":_normalize_weights(weights),
        "material_role":"hair",
    }


def _hair_strands(
    name: str,
    center: tuple[float,float,float],
    radii: tuple[float,float,float],
    *,
    style: str,
    joint: str = "Head",
    strands: int = 56,
    samples: int = 14,
) -> dict[str, Any]:
    """Sparse raised ribbon strands over the Aura-style scalp shell."""
    cx,cy,cz=center
    rx,ry,rz=radii
    positions=[]
    triangles=[]
    weights=[]
    half_angle=(math.tau/strands)*.055
    offset=.0014
    for strand in range(strands):
        a=math.tau*(strand+.37)/strands
        base=len(positions)
        for j in range(samples):
            t=.035+.93*j/(samples-1)
            end_phi=_hair_end_phi(style,a)
            phi=.025+(end_phi-.025)*t
            for side in (-1,1):
                aa=a+side*half_angle
                x=cx+(rx+offset)*math.sin(phi)*math.cos(aa)
                y=cy+(ry+offset)*math.cos(phi)
                z=cz+(rz+offset)*math.sin(phi)*math.sin(aa)
                positions.append((x,y,z))
                weights.append({joint:1.0})
        for j in range(samples-1):
            a0=base+j*2
            b0=a0+2
            triangles.extend(_triangulate_quad(a0,b0,b0+1,a0+1))
    return {
        "id":name,
        "positions":positions,
        "triangles":triangles,
        "weights":_normalize_weights(weights),
        "material_role":"hair_highlight",
    }


def build_parts(controls: dict[str, Any]) -> list[dict[str, Any]]:
    m=body_metrics(controls)
    build=m.build
    pelvis_y=m.hip_y+m.pelvis_h*.45
    spine_y=m.hip_y+m.pelvis_h+m.torso_h*.28
    chest_y=m.chest_y
    neck_y=m.neck_y
    shoulder_y=chest_y+m.torso_h*.10
    top_choice=controls.get("top","simple-shirt")
    bottom_choice=controls.get("bottom","trousers")
    shoes_choice=controls.get("shoes","boots")

    core=_loft_y("body-core",[
        (m.hip_y-m.pelvis_h*.08,m.hip_half*.88,.105*build*m.scale,{"Pelvis":1}),
        (pelvis_y,m.hip_half,.125*build*m.scale,{"Pelvis":1}),
        (spine_y,.145*build*m.scale,.105*build*m.scale,{"Pelvis":.30,"Spine":.70}),
        (chest_y,m.shoulder_half*.78,.125*build*m.scale,{"Spine":.25,"Chest":.75}),
        (shoulder_y,m.shoulder_half*.90,.120*build*m.scale,{"Chest":1}),
        (neck_y,.060*m.scale,.055*m.scale,{"Chest":.15,"Neck":.85}),
    ],material_role="top")
    parts=[core]

    if top_choice == "tunic":
        parts.append(_loft_y("tunic-lower",[
            (m.hip_y-m.pelvis_h*.18,m.hip_half*1.05,.125*build*m.scale,{"Pelvis":1}),
            (m.hip_y+m.pelvis_h*.55,m.hip_half*1.10,.135*build*m.scale,{"Pelvis":.85,"Spine":.15}),
            (spine_y,m.hip_half*.92,.120*build*m.scale,{"Pelvis":.35,"Spine":.65}),
        ],material_role="top",segments=44))
    elif top_choice == "jacket":
        parts.append(_loft_y("jacket-shell",[
            (m.hip_y+m.pelvis_h*.30,m.hip_half*1.02,.132*build*m.scale,{"Pelvis":.75,"Spine":.25}),
            (spine_y,.153*build*m.scale,.114*build*m.scale,{"Pelvis":.25,"Spine":.75}),
            (chest_y,m.shoulder_half*.82,.134*build*m.scale,{"Spine":.20,"Chest":.80}),
            (shoulder_y,m.shoulder_half*.94,.130*build*m.scale,{"Chest":1}),
        ],material_role="top",segments=44))

    neck_head_scale=_num(controls.get("head_scale"),1.0)*m.scale
    neck_top=max(
        neck_y+m.neck_h*.72,
        m.head_y-.126*neck_head_scale,
    )
    parts.append(_loft_y("neck",[
        (neck_y-.012*m.scale,.050*m.scale,.046*m.scale,{"Chest":.20,"Neck":.80}),
        (neck_y+.030*m.scale,.046*m.scale,.043*m.scale,{"Neck":1.0}),
        (neck_top,.041*m.scale,.040*m.scale,{"Neck":.35,"Head":.65}),
    ],material_role="skin",segments=36))

    upper_r=.050*build*m.scale
    fore_r=.043*build*m.scale
    hand_r=.045*build*m.scale
    upper_arm_role="top" if top_choice=="jacket" else "skin"
    for suffix,sign in (("L",-1),("R",1)):
        sx=sign*m.shoulder_half
        ex=sign*(m.shoulder_half+m.upper_arm)
        wx=sign*(m.shoulder_half+m.upper_arm+m.forearm)
        hx=sign*(m.shoulder_half+m.upper_arm+m.forearm+m.hand_len*.55)
        ua=f"UpperArm.{suffix}"
        fa=f"Forearm.{suffix}"
        ha=f"Hand.{suffix}"
        parts.append(_tube_x(f"upper-arm-{suffix.lower()}",[
            (sx,shoulder_y,upper_r,upper_r,{ua:1}),
            (sign*(m.shoulder_half+m.upper_arm*.78),shoulder_y,upper_r*.88,upper_r*.88,{ua:.75,fa:.25}),
            (ex,shoulder_y,upper_r*.84,upper_r*.84,{ua:.45,fa:.55}),
        ],material_role=upper_arm_role))
        parts.append(_tube_x(f"forearm-{suffix.lower()}",[
            (ex,shoulder_y,fore_r*1.02,fore_r*1.02,{ua:.25,fa:.75}),
            (sign*(m.shoulder_half+m.upper_arm+m.forearm*.78),shoulder_y,fore_r,fore_r,{fa:.80,ha:.20}),
            (wx,shoulder_y,fore_r*.82,fore_r*.82,{fa:.35,ha:.65}),
            (hx,shoulder_y,hand_r*.72,hand_r*.50,{ha:1}),
        ],material_role="skin"))
        parts.append(_ellipsoid(
            f"hand-{suffix.lower()}",
            (sign*(abs(hx)+m.hand_len*.20),shoulder_y,0),
            (m.hand_len*.28,.035*m.scale,.055*m.scale),
            {ha:1},
            "skin",
            lon=24,
            lat=10,
        ))

    ankle_y=m.foot_h
    knee_y=ankle_y+m.lower_leg
    hip_y=m.hip_y
    leg_r=.066*build*m.scale
    upper_leg_role="bottom" if bottom_choice in ("trousers","shorts") else "skin"
    lower_leg_role="bottom" if bottom_choice=="trousers" else "skin"
    for suffix,sign in (("L",-1),("R",1)):
        x=sign*m.hip_half*.45
        th=f"Thigh.{suffix}"
        sh=f"Shin.{suffix}"
        ft=f"Foot.{suffix}"
        parts.append(_tube_y(f"upper-leg-{suffix.lower()}",x,[
            (hip_y,leg_r,leg_r*.88,{th:1}),
            (knee_y+m.upper_leg*.20,leg_r*.88,leg_r*.82,{th:.75,sh:.25}),
            (knee_y,leg_r*.82,leg_r*.78,{th:.45,sh:.55}),
        ],material_role=upper_leg_role))
        parts.append(_tube_y(f"lower-leg-{suffix.lower()}",x,[
            (knee_y,leg_r*.79,leg_r*.76,{th:.22,sh:.78}),
            (ankle_y+m.lower_leg*.22,leg_r*.72,leg_r*.70,{sh:.82,ft:.18}),
            (ankle_y,leg_r*.58,leg_r*.62,{sh:.35,ft:.65}),
        ],material_role=lower_leg_role))
        foot_y=m.foot_h*.52 if shoes_choice!="sandals" else m.foot_h*.38
        foot_ry=m.foot_h*(.52 if shoes_choice=="boots" else .40 if shoes_choice=="shoes" else .25)
        foot_rz=.130*m.scale if shoes_choice=="boots" else .118*m.scale if shoes_choice=="shoes" else .110*m.scale
        parts.append(_ellipsoid(
            f"foot-{suffix.lower()}",
            (x,foot_y,.065*m.scale),
            (.072*m.scale,foot_ry,foot_rz),
            {ft:1},
            "shoes",
            lon=28,
            lat=10,
        ))
        if shoes_choice=="boots":
            parts.append(_tube_y(f"boot-cuff-{suffix.lower()}",x,[
                (ankle_y-.005*m.scale,leg_r*.65,leg_r*.68,{ft:1}),
                (ankle_y+.105*m.scale,leg_r*.72,leg_r*.72,{sh:.25,ft:.75}),
            ],material_role="shoes",segments=28))

    if bottom_choice=="skirt":
        parts.append(_loft_y("skirt-shell",[
            (m.hip_y-m.upper_leg*.22,m.hip_half*1.22,.145*build*m.scale,{"Pelvis":.85,"Thigh.L":.075,"Thigh.R":.075}),
            (m.hip_y+m.pelvis_h*.10,m.hip_half*1.13,.140*build*m.scale,{"Pelvis":1}),
            (pelvis_y,m.hip_half*1.06,.130*build*m.scale,{"Pelvis":1}),
        ],material_role="bottom",segments=48))

    head_scale=_num(controls.get("head_scale"),1.0)*m.scale
    for face_part in build_face_parts(controls):
        parts.append(_translate_part(face_part,(0,m.head_y,0),head_scale,"Head"))

    hair=controls.get("hair","short")
    if hair != "none":
        head_width=_num(controls.get("head_width"),1.0)
        head_depth=_num(controls.get("head_depth"),1.0)
        hw=.101*head_width*head_scale
        hh=.138*head_scale
        hd=.104*head_depth*head_scale
        cy=m.head_y+.018*head_scale
        parts.append(_hair_shell(
            "hair-cap",
            (0,cy,-.006*head_scale),
            (hw,hh,hd),
            style=hair,
        ))
        parts.append(_hair_strands(
            "hair-strands",
            (0,cy,-.006*head_scale),
            (hw,hh,hd),
            style=hair,
        ))

        if hair=="swept":
            parts.append(_ellipsoid(
                "hair-swept-fringe",
                (-.032*head_scale,m.head_y+.080*head_scale,.070*head_scale),
                (.050*head_scale,.022*head_scale,.016*head_scale),
                {"Head":1},
                "hair",
                lon=30,
                lat=8,
            ))

        if hair in ("bob","long"):
            top_y=m.head_y+.020*head_scale
            bottom_y=(
                m.head_y-.105*head_scale
                if hair=="bob"
                else m.head_y-.245*head_scale
            )
            side_h=(top_y-bottom_y)*.54
            side_y=(top_y+bottom_y)*.5
            for suffix,sign in (("L",-1),("R",1)):
                parts.append(_ellipsoid(
                    f"hair-side-{suffix.lower()}",
                    (
                        sign*.091*head_width*head_scale,
                        side_y,
                        -.022*head_depth*head_scale,
                    ),
                    (
                        .015*head_scale,
                        side_h,
                        .030*head_depth*head_scale,
                    ),
                    {"Head":1},
                    "hair",
                    lon=26,
                    lat=12,
                ))
    return parts


def _vertex_normals(
    positions: list[tuple[float,float,float]],
    triangles: list[tuple[int,int,int]],
) -> list[tuple[float,float,float]]:
    normals=[[0.0,0.0,0.0] for _ in positions]
    for a,b,c in triangles:
        pa,pb,pc=positions[a],positions[b],positions[c]
        ux,uy,uz=(pb[i]-pa[i] for i in range(3))
        vx,vy,vz=(pc[i]-pa[i] for i in range(3))
        nx=uy*vz-uz*vy
        ny=uz*vx-ux*vz
        nz=ux*vy-uy*vx
        for idx in (a,b,c):
            normals[idx][0]+=nx
            normals[idx][1]+=ny
            normals[idx][2]+=nz
    out=[]
    for x,y,z in normals:
        length=math.sqrt(x*x+y*y+z*z)
        out.append((x/length,y/length,z/length) if length>1e-12 else (0.0,1.0,0.0))
    return out


def starter_clips() -> list[dict[str, Any]]:
    # Bind pose stays a T-pose for construction. Gameplay clips explicitly move
    # the arms out of that authoring pose so Idle is visibly character-like.
    left_down = _quat((0,0,1), 78)
    right_down = _quat((0,0,1), -78)

    idle={"name":"Idle","tracks":[
        {"joint":"Chest","path":"rotation","times":[0,1,2],"values":[
            _quat((1,0,0),0),_quat((1,0,0),1.5),_quat((1,0,0),0)
        ]},
        {"joint":"Head","path":"rotation","times":[0,1,2],"values":[
            _quat((0,1,0),-1),_quat((0,1,0),1),_quat((0,1,0),-1)
        ]},
        {"joint":"UpperArm.L","path":"rotation","times":[0,1,2],"values":[left_down,left_down,left_down]},
        {"joint":"UpperArm.R","path":"rotation","times":[0,1,2],"values":[right_down,right_down,right_down]},
    ]}

    walk={"name":"Walk","tracks":[]}
    times=[0,.5,1.0]

    def track(joint,axis,degrees):
        return {
            "joint":joint,
            "path":"rotation",
            "times":times,
            "values":[_quat(axis,degrees),_quat(axis,-degrees),_quat(axis,degrees)],
        }

    def arm_track(joint, down_degrees, swing_degrees):
        values=[]
        for swing in (swing_degrees,-swing_degrees,swing_degrees):
            values.append(_compose(_quat((0,0,1),down_degrees), _quat((0,1,0),swing)))
        return {"joint":joint,"path":"rotation","times":times,"values":values}

    walk["tracks"] += [
        track("Thigh.L",(1,0,0),24),
        track("Thigh.R",(1,0,0),-24),
        track("Shin.L",(1,0,0),-14),
        track("Shin.R",(1,0,0),14),
        arm_track("UpperArm.L",78,16),
        arm_track("UpperArm.R",-78,16),
    ]

    right_wave = _compose(_quat((0,0,1),-28), _quat((0,1,0),-12))
    wave={"name":"Wave","tracks":[
        {"joint":"UpperArm.L","path":"rotation","times":[0,.35,.8,1.25,1.6],"values":[
            left_down,left_down,left_down,left_down,left_down
        ]},
        {"joint":"UpperArm.R","path":"rotation","times":[0,.35,.8,1.25,1.6],"values":[
            right_down,right_wave,right_wave,right_wave,right_down
        ]},
        {"joint":"Forearm.R","path":"rotation","times":[0,.35,.65,.95,1.25,1.6],"values":[
            _quat((0,1,0),0),
            _quat((0,1,0),-58),
            _quat((0,1,0),-35),
            _quat((0,1,0),-70),
            _quat((0,1,0),-58),
            _quat((0,1,0),0),
        ]},
    ]}
    return [idle,walk,wave]

class _BufferBuilder:
    def __init__(self):
        self.data=bytearray()
        self.views=[]
        self.accessors=[]

    def _align(self,n=4):
        self.data.extend(b"\0"*((-len(self.data))%n))

    def accessor(
        self,
        rows: Iterable[Iterable[float|int]],
        kind: str,
        component: int,
        *,
        target: int|None=None,
        minmax: bool=False,
    ) -> int:
        rows=[list(r) for r in rows]
        widths={"SCALAR":1,"VEC2":2,"VEC3":3,"VEC4":4,"MAT4":16}
        width=widths[kind]
        if any(len(r)!=width for r in rows):
            raise HumanAssetError("accessor row width mismatch")
        fmt={5126:"f",5125:"I",5123:"H"}[component]
        self._align(4)
        start=len(self.data)
        for r in rows:
            self.data.extend(struct.pack("<"+fmt*width,*r))
        view={"buffer":0,"byteOffset":start,"byteLength":len(self.data)-start}
        if target is not None:
            view["target"]=target
        self.views.append(view)
        acc={
            "bufferView":len(self.views)-1,
            "componentType":component,
            "count":len(rows),
            "type":kind,
        }
        if minmax and rows:
            acc["min"]=[min(r[i] for r in rows) for i in range(width)]
            acc["max"]=[max(r[i] for r in rows) for i in range(width)]
        self.accessors.append(acc)
        return len(self.accessors)-1


def _material_table(
    controls: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str,int]]:
    skin_color=_hex_rgb(controls.get("skin"),"#c98f76")
    hair_color=_hex_rgb(controls.get("hair_color"),"#34221f")

    def tint(color, factors):
        return tuple(
            max(0.0,min(1.0,color[i]*factors[i]))
            for i in range(3)
        )+(color[3],)

    specs={
        "skin":{"color":skin_color,"metal":0.0,"rough":.46},
        "face_skin":{"color":(1.0,1.0,1.0,1.0),"metal":0.0,"rough":.44},
        "skin_detail":{"color":tint(skin_color,(.94,.90,.88)),"metal":0.0,"rough":.43},
        "eyelid":{"color":tint(skin_color,(.97,.91,.90)),"metal":0.0,"rough":.40},
        "lip":{"color":tint(skin_color,(.86,.48,.48)),"metal":0.0,"rough":.32},
        "mouth_seam":{"color":(.16,.035,.030,1), "metal":0.0,"rough":.36},
        "nostril":{"color":(.035,.012,.010,1), "metal":0.0,"rough":.42},
        "sclera":{"color":(.88,.92,.89,1), "metal":0.0,"rough":.20},
        "iris":{"color":_hex_rgb(controls.get("eyes"),"#5b3828"),"metal":.03,"rough":.18},
        "limbal":{"color":(.025,.018,.016,1), "metal":0.0,"rough":.18},
        "pupil":{"color":(.008,.006,.005,1), "metal":0.0,"rough":.14},
        "catchlight":{"color":(1.0,1.0,1.0,1), "metal":0.0,"rough":.06,"emissive":[.55,.55,.55]},
        "brow":{"color":tint(hair_color,(.68,.58,.54)),"metal":0.0,"rough":.46},
        "hair":{"color":hair_color,"metal":0.0,"rough":.40},
        "hair_highlight":{"color":tint(hair_color,(1.28,1.20,1.16)),"metal":0.0,"rough":.32},
        "top":{"color":(.20,.32,.34,1),"metal":0.0,"rough":.62},
        "bottom":{"color":(.12,.16,.18,1),"metal":0.0,"rough":.68},
        "shoes":{"color":(.06,.06,.055,1),"metal":.05,"rough":.58},
    }
    mats=[]
    index={}
    face_roles={
        "skin","face_skin","skin_detail","eyelid","lip","mouth_seam","nostril",
        "sclera","iris","limbal","pupil","catchlight","brow","hair","hair_highlight",
    }
    for role,spec in specs.items():
        index[role]=len(mats)
        mat={
            "name":role,
            "pbrMetallicRoughness":{
                "baseColorFactor":list(spec["color"]),
                "metallicFactor":spec["metal"],
                "roughnessFactor":spec["rough"],
            },
            "doubleSided":False,
            "extras":{
                "axm_material_role":role,
                "quality_source":"Aura revision 2 adaptation" if role in face_roles else "human-v0",
            },
        }
        if spec.get("emissive") is not None:
            mat["emissiveFactor"]=list(spec["emissive"])
        mats.append(mat)
    return mats,index


def build_glb(blueprint: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    from .blueprint import signature_bundle, validate_blueprint

    blueprint = validate_blueprint(blueprint)
    if blueprint.get("family") != "human-v0":
        raise HumanAssetError("human-v0 blueprint required")
    controls = blueprint["controls"]
    signatures = signature_bundle(blueprint)

    parts=build_parts(controls)
    metrics=body_metrics(controls)
    joints=skeleton(controls)
    joint_names={j["id"] for j in joints}
    equipment=compile_human_v0_equipment(controls,metrics,joint_names=joint_names)
    joint_order={j["id"]:i for i,j in enumerate(joints)}
    buf=_BufferBuilder()
    materials,mat_index=_material_table(controls)
    meshes=[]
    nodes=[]

    for part in parts:
        pos=part["positions"]
        tri=part["triangles"]
        norm=_vertex_normals(pos,tri)
        weights=part["weights"]
        jr=[]
        wr=[]
        for row in weights:
            items=sorted(
                ((joint_order[k],v) for k,v in row.items()),
                key=lambda x:x[0],
            )[:4]
            jr.append([i for i,_ in items]+[0]*(4-len(items)))
            wr.append([v for _,v in items]+[0.0]*(4-len(items)))
        pos_a=buf.accessor(pos,"VEC3",5126,target=34962,minmax=True)
        norm_a=buf.accessor(norm,"VEC3",5126,target=34962)
        joint_a=buf.accessor(jr,"VEC4",5123,target=34962)
        weight_a=buf.accessor(wr,"VEC4",5126,target=34962)
        color_a=None
        if part.get("colors") is not None:
            if len(part["colors"]) != len(pos):
                raise HumanAssetError("vertex colors must match part positions")
            color_a=buf.accessor(part["colors"],"VEC4",5126,target=34962)
        idx_a=buf.accessor(
            ([i] for t in tri for i in t),
            "SCALAR",
            5125,
            target=34963,
            minmax=True,
        )
        meshes.append({
            "name":part["id"],
            "primitives":[{
                "attributes":{
                    **{
                        "POSITION":pos_a,
                        "NORMAL":norm_a,
                        "JOINTS_0":joint_a,
                        "WEIGHTS_0":weight_a,
                    },
                    **({"COLOR_0":color_a} if color_a is not None else {}),
                },
                "indices":idx_a,
                "material":mat_index[part["material_role"]],
            }],
        })
        nodes.append({"name":part["id"],"mesh":len(meshes)-1,"skin":0})

    mesh_node_count=len(nodes)
    skeleton_offset=len(nodes)
    joint_node={j["id"]:skeleton_offset+i for i,j in enumerate(joints)}
    inverses=[]
    for j in joints:
        nodes.append({"name":j["id"],"translation":j["translation"]})
        x,y,z=j["world"]
        inverses.append([
            1,0,0,0,
            0,1,0,0,
            0,0,1,0,
            -x,-y,-z,1,
        ])
    for j in joints:
        if j["parent"] is not None:
            nodes[joint_node[j["parent"]]].setdefault("children",[]).append(joint_node[j["id"]])

    socket_node={}
    for socket in equipment["sockets"]:
        index=len(nodes)
        socket_node[socket["id"]]=index
        nodes.append({
            "name":"AXM_SOCKET_"+socket["id"],
            "translation":socket["translation"],
            "rotation":socket["rotation"],
            "extras":{
                "schema":SOCKET_SCHEMA,
                "id":socket["id"],
                "parent_joint":socket["parent_joint"],
                "accepts":socket["accepts"],
                "purpose":socket["purpose"],
            },
        })
        nodes[joint_node[socket["parent_joint"]]].setdefault("children",[]).append(index)

    inv_a=buf.accessor(inverses,"MAT4",5126)
    animations=[]
    for clip in starter_clips():
        samplers=[]
        channels=[]
        for tr in clip["tracks"]:
            inp=buf.accessor(([t] for t in tr["times"]),"SCALAR",5126,minmax=True)
            out=buf.accessor(tr["values"],"VEC4",5126)
            samplers.append({
                "input":inp,
                "output":out,
                "interpolation":"LINEAR",
            })
            channels.append({
                "sampler":len(samplers)-1,
                "target":{
                    "node":joint_node[tr["joint"]],
                    "path":"rotation",
                },
            })
        animations.append({
            "name":clip["name"],
            "samplers":samplers,
            "channels":channels,
        })

    scene_nodes=list(range(mesh_node_count))+[joint_node["Root"]]
    doc={
        "asset":{
            "version":"2.0",
            "generator":"AXM Character Editor human-v0",
        },
        "scene":0,
        "scenes":[{"nodes":scene_nodes}],
        "nodes":nodes,
        "meshes":meshes,
        "materials":materials,
        "skins":[{
            "name":RIG_ID,
            "joints":[joint_node[j["id"]] for j in joints],
            "skeleton":joint_node["Root"],
            "inverseBindMatrices":inv_a,
        }],
        "animations":animations,
        "bufferViews":buf.views,
        "accessors":buf.accessors,
        "buffers":[{"byteLength":0}],
        "extras":{
            "schema":GLB_SCHEMA,
            "blueprint_id":blueprint.get("id"),
            "family":"human-v0",
            "rig_profile":RIG_ID,
            "equipment":equipment,
            "socket_nodes":socket_node,
        },
    }

    buf._align(4)
    doc["buffers"][0]["byteLength"]=len(buf.data)
    raw=json.dumps(
        doc,
        sort_keys=True,
        separators=(",",":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    raw+=b" "*((-len(raw))%4)
    binary=bytes(buf.data)
    binary+=b"\0"*((-len(binary))%4)
    total=12+8+len(raw)+8+len(binary)
    body=(
        struct.pack("<4sII",b"glTF",2,total)
        +struct.pack("<I4s",len(raw),b"JSON")
        +raw
        +struct.pack("<I4s",len(binary),b"BIN\0")
        +binary
    )

    receipt={
        "schema":"axm.character.game-asset-build/v0.1",
        "id":blueprint.get("id"),
        "family":"human-v0",
        "rig":RIG_ID,
        "blueprint_sha256":signatures["blueprint_sha256"],
        "geometry_sha256":signatures.get("geometry_sha256"),
        "appearance_sha256":signatures.get("appearance_sha256"),
        "equipment_sha256":signatures.get("equipment_sha256"),
        "glb_bytes":len(body),
        "sha256":hashlib.sha256(body).hexdigest(),
        "parts":len(parts),
        "joints":len(joints),
        "vertices":sum(len(p["positions"]) for p in parts),
        "triangles":sum(len(p["triangles"]) for p in parts),
        "clips":[c["name"] for c in starter_clips()],
        "equipment_slots":len(equipment["slots"]),
        "attachment_sockets":len(equipment["sockets"]),
        "socket_ids":[row["id"] for row in equipment["sockets"]],
        "face_quality_floor":"AURA_REVISION_2_FEATURES_ADAPTED",
        "status":"STRUCTURAL_RIGGED_GLB_CANDIDATE",
        "target_engine_status":"HOLD_RPG_IMPORT_AND_VISUAL_DEFORMATION_REVIEW_NOT_YET_RUN",
        "truth":(
            "A real glTF 2.0 skin, normalized four-influence weights and starter "
            "clips are encoded. Target-engine import, visual deformation acceptance, "
            "clothing fit and runtime performance are separate pending checks."
        ),
    }
    return body,receipt


def parse_glb(body: bytes) -> tuple[dict[str, Any], bytes]:
    if len(body)<28:
        raise HumanAssetError("GLB too small")
    magic,version,length=struct.unpack_from("<4sII",body,0)
    if magic!=b"glTF" or version!=2 or length!=len(body):
        raise HumanAssetError("invalid GLB header")
    jlen,jtype=struct.unpack_from("<I4s",body,12)
    if jtype!=b"JSON":
        raise HumanAssetError("missing JSON chunk")
    raw=body[20:20+jlen]
    doc=json.loads(raw.decode("utf-8").rstrip(" \0"))
    off=20+jlen
    blen,btype=struct.unpack_from("<I4s",body,off)
    if btype!=b"BIN\0":
        raise HumanAssetError("missing BIN chunk")
    binary=body[off+8:off+8+blen]
    return doc,binary


def verify_glb(body: bytes) -> dict[str, Any]:
    doc,binary=parse_glb(body)
    skins=doc.get("skins",[])
    animations=doc.get("animations",[])
    meshes=doc.get("meshes",[])
    equipment=doc.get("extras",{}).get("equipment")
    try:
        validate_equipment_contract(equipment)
        equipment_ok=True
    except Exception:
        equipment_ok=False
    expected_socket_ids={
        row.get("id") for row in equipment.get("sockets",[])
    } if isinstance(equipment,dict) else set()
    observed_socket_ids={
        node.get("extras",{}).get("id")
        for node in doc.get("nodes",[])
        if node.get("extras",{}).get("schema")==SOCKET_SCHEMA
    }

    checks={
        "one_skin":len(skins)==1,
        "humanoid_joint_count":len(skins[0]["joints"])==18 if skins else False,
        "mesh_parts_present":len(meshes)>=10,
        "starter_clips":{a.get("name") for a in animations}=={"Idle","Walk","Wave"},
        "all_mesh_nodes_skinned":all(
            "skin" in n for n in doc.get("nodes",[]) if "mesh" in n
        ),
        "embedded_binary":len(binary)>0,
        "equipment_contract":equipment_ok,
        "equipment_socket_nodes":bool(expected_socket_ids) and observed_socket_ids==expected_socket_ids,
    }

    acc=doc["accessors"]
    views=doc["bufferViews"]
    max_error=0.0
    rows_checked=0
    for mesh in meshes:
        for primitive in mesh["primitives"]:
            ref=primitive["attributes"]["WEIGHTS_0"]
            a=acc[ref]
            v=views[a["bufferView"]]
            if a["componentType"]!=5126 or a["type"]!="VEC4":
                raise HumanAssetError("unexpected weights accessor")
            start=v.get("byteOffset",0)+a.get("byteOffset",0)
            stride=v.get("byteStride",16)
            for i in range(a["count"]):
                row=struct.unpack_from("<ffff",binary,start+i*stride)
                error=abs(sum(row)-1)
                max_error=max(max_error,error)
                rows_checked+=1
                if min(row)<-1e-6:
                    raise HumanAssetError("negative weight")
    checks["normalized_weights"]=max_error<=1e-5

    return {
        "schema":"axm.character.game-asset-verification/v0.1",
        "status":"PASS" if all(checks.values()) else "REVIEW_REQUIRED",
        "checks":checks,
        "weights_checked":rows_checked,
        "max_weight_sum_error":max_error,
        "nodes":len(doc.get("nodes",[])),
        "meshes":len(meshes),
        "animations":len(animations),
    }


def verify_glb_path(path: str|Path) -> dict[str, Any]:
    path=Path(path)
    return {
        **verify_glb(path.read_bytes()),
        "path":str(path),
        "sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def write_glb(
    blueprint: dict[str, Any],
    path: str|Path,
    *,
    replace: bool=False,
) -> dict[str, Any]:
    import os
    import tempfile

    path=Path(path)
    if path.suffix.lower() != ".glb":
        raise HumanAssetError("game asset output must use .glb")
    if path.exists() and not replace:
        raise FileExistsError(f"refusing to overwrite existing game asset: {path}")
    if path.exists() and not path.is_file():
        raise HumanAssetError("game asset destination exists and is not a file")

    body,receipt=build_glb(blueprint)
    verification=verify_glb(body)
    if verification["status"] != "PASS":
        raise HumanAssetError("generated GLB failed structural verification")

    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=f".{path.name}.axm-build-",dir=path.parent)
    try:
        with os.fdopen(fd,"wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

    observed=path.read_bytes()
    if observed!=body:
        raise HumanAssetError("published GLB bytes changed")
    return {**receipt,"verification":verification,"path":str(path)}


def build_package(
    blueprint: dict[str, Any],
    target: str|Path,
) -> dict[str, Any]:
    from .blueprint import validate_blueprint
    from .game_asset_verify import verify_path as verify_deformation_path

    blueprint = validate_blueprint(blueprint)
    target=Path(target)
    if target.exists():
        raise FileExistsError(f"refusing to overwrite existing character package: {target}")
    target.mkdir(parents=True)
    try:
        bp_path=target/"character.blueprint.json"
        bp_path.write_text(
            json.dumps(blueprint,indent=2,sort_keys=True)+"\n",
            encoding="utf-8",
        )
        receipt=write_glb(blueprint,target/"character.glb")
        equipment=compile_human_v0_equipment(
            blueprint["controls"],
            body_metrics(blueprint["controls"]),
            joint_names={row["id"] for row in skeleton(blueprint["controls"])},
        )
        (target/"equipment-contract.json").write_text(
            json.dumps(equipment,indent=2,sort_keys=True)+"\n",
            encoding="utf-8",
        )
        deformation=verify_deformation_path(target/"character.glb")
        if deformation["status"] != "SOFTWARE_DEFORMATION_PASS":
            raise HumanAssetError("generated GLB failed independent software deformation verification")
        (target/"deformation-verification.json").write_text(
            json.dumps(deformation,indent=2,sort_keys=True)+"\n",
            encoding="utf-8",
        )
        source_lock={
            "schema":"axm.character.source-lock/v0.1",
            "family":"human-v0",
            "rig_profile":RIG_ID,
            "aura_source_zip_sha256":"61592614d97b26dd768d9d6e37365af192d5fff1f660f4ca99566d1bc9e87c04",
            "aura_upgrade_source_sha256":"4c33838e3ed7fff0c5a83468ecc03849a23c2603b574397f2b1acd8284cf620a",
            "aura_helper_git_blob":"3cd1a19102df018ce4964de46d7e1eb4cabe7ac0",
            "uc_motion_direction_commit":"08cd56220b927ff03432122c4470031597f9f697",
            "truth":(
                "Aura supplies the face construction donor. Character Editor owns "
                "this adapted standalone GLB builder; UC runtime is not imported at "
                "execution time."
            ),
        }
        (target/"source-lock.json").write_text(
            json.dumps(source_lock,indent=2,sort_keys=True)+"\n",
            encoding="utf-8",
        )
        package_receipt={
            **receipt,
            "software_deformation_verification":deformation,
            "equipment_contract":equipment,
            "source_lock":source_lock,
            "outputs":[
                "character.blueprint.json",
                "character.glb",
                "source-lock.json",
                "equipment-contract.json",
                "deformation-verification.json",
                "build-receipt.json",
            ],
        }
        (target/"build-receipt.json").write_text(
            json.dumps(package_receipt,indent=2,sort_keys=True)+"\n",
            encoding="utf-8",
        )
        return package_receipt
    except Exception:
        import shutil
        shutil.rmtree(target,ignore_errors=True)
        raise
