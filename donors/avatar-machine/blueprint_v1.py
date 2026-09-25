from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .material_response import compile_blender_response_binding, validate_surface_selection, resolve_surface_selection

BLUEPRINT_SCHEMA = "axm.avatar.blueprint/v1"
SCENE_PLAN_SCHEMA = "axm.avatar.scene-plan/v1"
COMPILER_VERSION = "doll-blueprint-v1"

STYLE_FAMILY = "stylized-doll"
MATERIAL_FINISHES = {"matte", "semi-real", "glossy"}
HAIR_CHOICES = {"none", "cap", "swept", "bob", "mohawk"}
FACIAL_HAIR_CHOICES = {"none", "stubble", "beard"}
EYE_CHOICES = {"round", "narrow"}
MOUTH_CHOICES = {"neutral", "smile", "pucker"}
TOP_CHOICES = {"tee", "hoodie", "jacket", "polo"}
BOTTOM_CHOICES = {"trousers", "jeans", "shorts"}
ACCESSORY_CHOICES = {"none", "headphones", "glasses", "pin"}
ANIMATION_BEATS = {"idle", "walk", "wave", "celebrate"}

PROPORTION_BOUNDS = {
    "height": (0.75, 1.35),
    "head": (0.75, 1.35),
    "torso_width": (0.7, 1.4),
    "limb_length": (0.75, 1.3),
}

ANATOMY_BOUNDS = {
    "head_width": (0.75, 1.35),
    "head_depth": (0.75, 1.35),
    "eye_spacing": (0.65, 1.45),
    "eye_size": (0.65, 1.35),
    "nose_size": (0.0, 1.4),
    "nose_projection": (0.6, 1.6),
    "ear_size": (0.0, 1.4),
    "jaw_width": (0.0, 1.4),
    "mouth_width": (0.65, 1.5),
    "shoulder_width": (0.75, 1.4),
    "hip_width": (0.75, 1.35),
    "limb_thickness": (0.7, 1.35),
    "hand_size": (0.7, 1.4),
    "foot_size": (0.7, 1.4),
}

ANATOMY_DEFAULTS = {
    "head_width": 1.0,
    "head_depth": 1.0,
    "eye_spacing": 1.0,
    "eye_size": 1.0,
    "nose_size": 0.0,
    "nose_projection": 1.0,
    "ear_size": 0.0,
    "jaw_width": 0.0,
    "mouth_width": 1.0,
    "shoulder_width": 1.0,
    "hip_width": 1.0,
    "limb_thickness": 1.0,
    "hand_size": 1.0,
    "foot_size": 1.0,
}


class BlueprintError(ValueError):
    pass


def _digest(value: Any) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _require_dict(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BlueprintError(f"{where} must be an object")
    return value


def _require_string(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BlueprintError(f"{where} must be a non-empty string")
    return value.strip()


def _hex_color(value: Any, where: str) -> str:
    value = _require_string(value, where)
    if len(value) != 7 or value[0] != "#" or any(ch not in "0123456789abcdefABCDEF" for ch in value[1:]):
        raise BlueprintError(f"{where} must be #RRGGBB")
    return value.lower()


def _choice(value: Any, choices: set[str], where: str) -> str:
    value = _require_string(value, where)
    if value not in choices:
        raise BlueprintError(f"{where} must be one of {sorted(choices)}")
    return value


def _bounded_number(value: Any, bounds: tuple[float, float], where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BlueprintError(f"{where} must be numeric")
    value = float(value)
    if not math.isfinite(value) or not bounds[0] <= value <= bounds[1]:
        raise BlueprintError(f"{where} must be between {bounds[0]} and {bounds[1]}")
    return round(value, 6)


def _position(value: Any, where: str) -> list[float]:
    if not isinstance(value, list) or len(value) != 3:
        raise BlueprintError(f"{where} must be [x, y, z]")
    result = []
    for index, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(float(item)):
            raise BlueprintError(f"{where}[{index}] must be a finite number")
        result.append(round(float(item), 6))
    return result


def validate_blueprint(value: Any) -> dict[str, Any]:
    data = copy.deepcopy(_require_dict(value, "blueprint"))
    if data.get("schema") != BLUEPRINT_SCHEMA:
        raise BlueprintError(f"blueprint.schema must be {BLUEPRINT_SCHEMA!r}")
    data["id"] = _require_string(data.get("id"), "blueprint.id")

    style = _require_dict(data.get("style"), "blueprint.style")
    if style.get("family") != STYLE_FAMILY:
        raise BlueprintError(
            f"blueprint.style.family must be {STYLE_FAMILY!r}; broader avatar profile families are not implemented"
        )
    style["material_finish"] = _choice(
        style.get("material_finish", "semi-real"), MATERIAL_FINISHES, "blueprint.style.material_finish"
    )

    characters = data.get("characters")
    if not isinstance(characters, list) or not 1 <= len(characters) <= 4:
        raise BlueprintError("blueprint.characters must contain between 1 and 4 characters")
    seen: set[str] = set()
    normalized_characters = []
    for index, raw in enumerate(characters):
        char = _require_dict(raw, f"characters[{index}]")
        char_id = _require_string(char.get("id"), f"characters[{index}].id")
        if char_id in seen:
            raise BlueprintError(f"duplicate character id {char_id!r}")
        seen.add(char_id)

        proportions = _require_dict(char.get("proportions"), f"characters[{index}].proportions")
        normalized_proportions = {
            key: _bounded_number(proportions.get(key, 1.0), bounds, f"characters[{index}].proportions.{key}")
            for key, bounds in PROPORTION_BOUNDS.items()
        }

        anatomy = _require_dict(char.get("anatomy", {}), f"characters[{index}].anatomy")
        unknown_anatomy = sorted(set(anatomy) - set(ANATOMY_BOUNDS))
        if unknown_anatomy:
            raise BlueprintError(
                f"characters[{index}].anatomy has unsupported controls: {unknown_anatomy}"
            )
        normalized_anatomy = {
            key: _bounded_number(
                anatomy.get(key, ANATOMY_DEFAULTS[key]),
                bounds,
                f"characters[{index}].anatomy.{key}",
            )
            for key, bounds in ANATOMY_BOUNDS.items()
        }

        palette = _require_dict(char.get("palette"), f"characters[{index}].palette")
        normalized_palette = {
            key: _hex_color(palette.get(key), f"characters[{index}].palette.{key}")
            for key in ("skin", "primary", "secondary", "hair", "shoes")
        }
        surface_raw = char.get("surface_families", {})
        if not isinstance(surface_raw, dict) or set(surface_raw) - set(normalized_palette):
            raise BlueprintError(
                f"characters[{index}].surface_families may only name {sorted(normalized_palette)}"
            )
        try:
            normalized_surfaces = {
                role: validate_surface_selection(selection)
                for role, selection in surface_raw.items()
            }
        except ValueError as exc:
            raise BlueprintError(f"characters[{index}].surface_families: {exc}") from exc

        features = _require_dict(char.get("features"), f"characters[{index}].features")
        normalized_features = {
            "hair": _choice(features.get("hair", "none"), HAIR_CHOICES, f"characters[{index}].features.hair"),
            "facial_hair": _choice(
                features.get("facial_hair", "none"), FACIAL_HAIR_CHOICES,
                f"characters[{index}].features.facial_hair"
            ),
            "eyes": _choice(features.get("eyes", "round"), EYE_CHOICES, f"characters[{index}].features.eyes"),
            "mouth": _choice(features.get("mouth", "neutral"), MOUTH_CHOICES, f"characters[{index}].features.mouth"),
        }

        wardrobe = _require_dict(char.get("wardrobe"), f"characters[{index}].wardrobe")
        normalized_wardrobe = {
            "top": _choice(wardrobe.get("top", "tee"), TOP_CHOICES, f"characters[{index}].wardrobe.top"),
            "bottom": _choice(
                wardrobe.get("bottom", "trousers"), BOTTOM_CHOICES, f"characters[{index}].wardrobe.bottom"
            ),
            "accessory": _choice(
                wardrobe.get("accessory", "none"), ACCESSORY_CHOICES, f"characters[{index}].wardrobe.accessory"
            ),
        }

        normalized_characters.append({
            "id": char_id,
            "proportions": normalized_proportions,
            "anatomy": normalized_anatomy,
            "palette": normalized_palette,
            "surface_families": normalized_surfaces,
            "features": normalized_features,
            "wardrobe": normalized_wardrobe,
            "position": _position(char.get("position", [index * 1.8, 0, 0]), f"characters[{index}].position"),
        })

    rig = _require_dict(data.get("rig", {}), "blueprint.rig")
    if rig.get("preset", "rigid-doll-17-per-character") != "rigid-doll-17-per-character":
        raise BlueprintError("blueprint.rig.preset must be 'rigid-doll-17-per-character'")
    normalized_rig = {
        "preset": "rigid-doll-17-per-character",
        "shared_armature": bool(rig.get("shared_armature", True)),
    }
    if not normalized_rig["shared_armature"]:
        raise BlueprintError("Doll Blueprint v1 currently implements one shared armature only")

    beats = data.get("animation_beats", ["idle"])
    if not isinstance(beats, list) or not beats or len(beats) > 8:
        raise BlueprintError("blueprint.animation_beats must be a non-empty list of at most 8 beats")
    normalized_beats = []
    for index, beat in enumerate(beats):
        if isinstance(beat, str):
            name, frame = beat, 1 + index * 36
        else:
            beat = _require_dict(beat, f"animation_beats[{index}]")
            name = beat.get("name")
            frame = beat.get("frame", 1 + index * 36)
        name = _choice(name, ANIMATION_BEATS, f"animation_beats[{index}].name")
        if isinstance(frame, bool) or not isinstance(frame, int) or frame < 1 or frame > 10000:
            raise BlueprintError(f"animation_beats[{index}].frame must be an integer from 1 to 10000")
        normalized_beats.append({"name": name, "frame": frame})

    return {
        "schema": BLUEPRINT_SCHEMA,
        "id": data["id"],
        "style": {"family": STYLE_FAMILY, "material_finish": style["material_finish"]},
        "characters": normalized_characters,
        "rig": normalized_rig,
        "animation_beats": normalized_beats,
        "authorship": copy.deepcopy(data.get("authorship", {"method": "HUMAN_OR_AI_EXPLICIT_FIELDS"})),
    }


def load_blueprint(path: str | Path) -> dict[str, Any]:
    return validate_blueprint(json.loads(Path(path).read_text(encoding="utf-8")))


def _finish_values(finish: str) -> tuple[float, float]:
    return {
        "matte": (0.0, 0.72),
        "semi-real": (0.08, 0.46),
        "glossy": (0.18, 0.25),
    }[finish]


def _material_table(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    metallic, roughness = _finish_values(blueprint["style"]["material_finish"])
    result = []
    for char in blueprint["characters"]:
        cid = char["id"]
        for role, color in char["palette"].items():
            m, r = metallic, roughness
            if role == "skin":
                m, r = 0.0, max(0.38, roughness)
            elif role == "shoes":
                m, r = min(0.25, metallic + 0.08), min(0.6, roughness + 0.08)
            material = {
                "id": f"{cid}:{role}",
                "color": color,
                "metallic": round(m, 4),
                "roughness": round(r, 4),
            }
            selection = char.get("surface_families", {}).get(role)
            if selection is not None:
                response = resolve_surface_selection(selection, color)
                material["response_family"] = response["family"]
                material["response_variant"] = response["variant"]
                material["response"] = response["response"]
                material["active_organs"] = response["active_organs"]
                material["response_evidence"] = response["evidence"]
                binding = compile_blender_response_binding(response["response"])
                material["blender_response_binding"] = binding
                material["response_renderer_binding"] = binding["status"]
                material["metallic"] = round(float(response["response"].get("metallic", material["metallic"])), 4)
                material["roughness"] = round(float(response["response"].get("roughness", material["roughness"])), 4)
                if "specular" in response["response"]:
                    material["specular"] = round(float(response["response"]["specular"]), 4)
            result.append(material)
        result.append({"id": f"{cid}:eye", "color": "#f5f5f2", "metallic": 0.0, "roughness": 0.35})
        result.append({"id": f"{cid}:pupil", "color": "#171717", "metallic": 0.0, "roughness": 0.5})
        result.append({"id": f"{cid}:mouth", "color": "#6f2735", "metallic": 0.0, "roughness": 0.5})
    return result


def _bone_specs(char: dict[str, Any]) -> list[dict[str, Any]]:
    cid = char["id"]
    px, py, pz = char["position"]
    h = char["proportions"]["height"]
    limb = char["proportions"]["limb_length"]
    torso = char["proportions"]["torso_width"]
    anatomy = char["anatomy"]
    hip_z = pz + 1.0 * h
    chest_z = pz + 1.72 * h
    neck_z = pz + 2.18 * h
    head_z = pz + 2.55 * h
    bones = []

    def add(name, head, tail, parent=None):
        bones.append({
            "name": f"{cid}_{name}",
            "head": [round(v, 6) for v in head],
            "tail": [round(v, 6) for v in tail],
            "parent": f"{cid}_{parent}" if parent else None,
        })

    add("root", (px, py, pz + 0.02), (px, py, pz + 0.26 * h))
    add("pelvis", (px, py, hip_z), (px, py, pz + 1.3 * h), "root")
    add("spine", (px, py, pz + 1.3 * h), (px, py, chest_z), "pelvis")
    add("neck", (px, py, chest_z), (px, py, neck_z), "spine")
    add("head", (px, py, neck_z), (px, py, pz + 3.05 * h), "neck")
    leg_x = 0.18 * torso * anatomy["hip_width"]
    shoulder_x = 0.48 * torso * anatomy["shoulder_width"]
    for side, sign in (("L", -1), ("R", 1)):
        lx = px + sign * leg_x
        add(f"{side}_thigh", (lx, py, hip_z + 0.08 * h), (lx, py, pz + 0.62 * h), "pelvis")
        add(f"{side}_shin", (lx, py, pz + 0.62 * h), (lx, py, pz + 0.22 * h), f"{side}_thigh")
        add(f"{side}_foot", (lx, py, pz + 0.22 * h), (lx, py - 0.26 * limb, pz + 0.12 * h), f"{side}_shin")
        ax = px + sign * shoulder_x
        add(f"{side}_upperarm", (ax, py, chest_z - 0.05 * h), (ax, py, pz + 1.38 * h), "spine")
        add(f"{side}_forearm", (ax, py, pz + 1.38 * h), (ax, py, pz + 1.00 * h), f"{side}_upperarm")
        add(f"{side}_hand", (ax, py, pz + 1.00 * h), (ax, py, pz + 0.82 * h), f"{side}_forearm")
    return bones


def _objects_for_character(char: dict[str, Any]) -> list[dict[str, Any]]:
    cid = char["id"]
    px, py, pz = char["position"]
    p = char["proportions"]
    a = char["anatomy"]
    h, head_scale, torso_w, limb = p["height"], p["head"], p["torso_width"], p["limb_length"]
    head_w, head_d = a["head_width"], a["head_depth"]
    shoulder_w, hip_w = a["shoulder_width"], a["hip_width"]
    limb_thickness = a["limb_thickness"]
    skin = f"{cid}:skin"
    primary = f"{cid}:primary"
    secondary = f"{cid}:secondary"
    hair = f"{cid}:hair"
    shoes = f"{cid}:shoes"
    objects: list[dict[str, Any]] = []

    def add(name, primitive, material, bone, **params):
        objects.append({
            "id": f"{cid}:{name}",
            "primitive": primitive,
            "material": material,
            "bone": f"{cid}_{bone}",
            **params,
        })

    # Core body.
    add("pelvis", "ellipsoid", secondary, "pelvis",
        location=[px, py, pz + 1.12*h], scale=[0.36*torso_w*hip_w, 0.26, 0.28*h])
    add("torso", "ellipsoid", primary, "spine",
        location=[px, py, pz + 1.70*h], scale=[0.48*torso_w, 0.31, 0.60*h])
    add("neck", "cylinder", skin, "neck",
        location=[px, py, pz + 2.27*h], radius=0.16*torso_w, depth=0.30*h, rotation=[0,0,0])
    add("head", "ellipsoid", skin, "head",
        location=[px, py, pz + 2.72*h],
        scale=[0.42*head_scale*head_w, 0.37*head_scale*head_d, 0.48*head_scale*h])

    for side, sign in (("L", -1), ("R", 1)):
        lx = px + sign*0.18*torso_w*hip_w
        ax = px + sign*0.48*torso_w*shoulder_w
        add(f"{side}-thigh", "cylinder_between", secondary, f"{side}_thigh",
            start=[lx, py, pz+1.08*h], end=[lx, py, pz+0.64*h], radius=0.17*torso_w*limb_thickness)
        add(f"{side}-shin", "cylinder_between", secondary, f"{side}_shin",
            start=[lx, py, pz+0.62*h], end=[lx, py, pz+0.25*h], radius=0.145*torso_w*limb_thickness)
        add(f"{side}-foot", "ellipsoid", shoes, f"{side}_foot",
            location=[lx, py-0.12*limb*a["foot_size"], pz+0.15*h],
            scale=[0.20*torso_w*a["foot_size"], 0.30*limb*a["foot_size"], 0.13*h*a["foot_size"]])
        add(f"{side}-upperarm", "cylinder_between", primary, f"{side}_upperarm",
            start=[ax, py, pz+2.00*h], end=[ax, py, pz+1.42*h], radius=0.15*torso_w*limb_thickness)
        add(f"{side}-forearm", "cylinder_between", primary, f"{side}_forearm",
            start=[ax, py, pz+1.39*h], end=[ax, py, pz+1.03*h], radius=0.135*torso_w*limb_thickness)
        add(f"{side}-hand", "ellipsoid", skin, f"{side}_hand",
            location=[ax, py-0.015, pz+0.92*h],
            scale=[0.16*torso_w*a["hand_size"], 0.13*a["hand_size"], 0.19*h*a["hand_size"]])

    # Face / high-leverage anatomy controls.
    eye_z = pz + 2.84*h
    eye_y = py - 0.35*head_scale*head_d
    eye_scale = [
        0.105*head_scale*a["eye_size"],
        0.045*a["eye_size"],
        0.085*head_scale*a["eye_size"],
    ]
    if char["features"]["eyes"] == "narrow":
        eye_scale[2] *= 0.62
    for side, sign in (("L", -1), ("R", 1)):
        ex = px + sign*0.16*head_scale*head_w*a["eye_spacing"]
        add(f"{side}-eye", "ellipsoid", f"{cid}:eye", "head",
            location=[ex, eye_y, eye_z], scale=eye_scale)
        add(f"{side}-pupil", "ellipsoid", f"{cid}:pupil", "head",
            location=[ex, eye_y-0.04*a["eye_size"], eye_z],
            scale=[0.035*a["eye_size"],0.02*a["eye_size"],0.045*a["eye_size"]])

    if a["nose_size"] > 0:
        add("nose", "ellipsoid", skin, "head",
            location=[
                px,
                py - 0.39*head_d - 0.055*a["nose_projection"],
                pz + 2.68*h,
            ],
            scale=[
                0.07*head_scale*a["nose_size"],
                0.055*a["nose_size"]*a["nose_projection"],
                0.11*head_scale*h*a["nose_size"],
            ])

    if a["jaw_width"] > 0:
        add("jaw", "ellipsoid", skin, "head",
            location=[px, py+0.015, pz+2.51*h],
            scale=[
                0.29*head_scale*a["jaw_width"],
                0.31*head_scale*head_d,
                0.18*head_scale*h,
            ])

    if a["ear_size"] > 0:
        for side, sign in (("L", -1), ("R", 1)):
            add(f"{side}-ear", "ellipsoid", skin, "head",
                location=[
                    px + sign*0.43*head_scale*head_w,
                    py,
                    pz + 2.73*h,
                ],
                scale=[
                    0.065*head_scale*a["ear_size"],
                    0.045*head_d,
                    0.12*head_scale*h*a["ear_size"],
                ])

    mouth = char["features"]["mouth"]
    if mouth == "pucker":
        for sign in (-1, 1):
            add(f"mouth-{sign}", "ellipsoid", f"{cid}:mouth", "head",
                location=[px+sign*0.045*a["mouth_width"], py-0.39*head_d, pz+2.55*h],
                scale=[0.065*a["mouth_width"],0.025,0.045])
    else:
        width = (0.18 if mouth == "smile" else 0.13) * a["mouth_width"]
        add("mouth", "box", f"{cid}:mouth", "head",
            location=[px, py-0.39*head_d, pz+2.55*h], dimensions=[width,0.025,0.035], rotation=[0,0,0])

    facial_hair = char["features"]["facial_hair"]
    if facial_hair != "none":
        scale_z = 0.23 if facial_hair == "beard" else 0.15
        add("facial-hair", "ellipsoid", hair, "head",
            location=[px, py-0.055*head_d, pz+2.54*h],
            scale=[0.35*head_scale*head_w,0.34*head_scale*head_d,scale_z*head_scale])

    hair_style = char["features"]["hair"]
    if hair_style != "none":
        if hair_style in {"cap", "bob"}:
            add("hair", "ellipsoid", hair, "head",
                location=[px, py+0.01, pz+2.97*h],
                scale=[0.43*head_scale*head_w,0.39*head_scale*head_d,0.25*head_scale])
        elif hair_style == "swept":
            add("hair", "ellipsoid", hair, "head",
                location=[px+0.06*head_w, py+0.01, pz+3.00*h],
                scale=[0.46*head_scale*head_w,0.38*head_scale*head_d,0.22*head_scale],
                rotation=[0,0,-0.18])
        elif hair_style == "mohawk":
            add("hair", "box", hair, "head",
                location=[px, py, pz+3.17*h], dimensions=[0.14,0.34,0.38*head_scale], rotation=[0,0,0])

    top = char["wardrobe"]["top"]
    if top == "jacket":
        for sign in (-1,1):
            add(f"jacket-{sign}", "box", secondary, "spine",
                location=[px+sign*0.29*torso_w*shoulder_w, py-0.02, pz+1.72*h],
                dimensions=[0.23*torso_w*shoulder_w,0.60,1.0*h], rotation=[0,sign*0.10,0])
    elif top == "hoodie":
        add("hood", "torus", secondary, "neck",
            location=[px,py+0.06,pz+2.21*h], major_radius=0.28*torso_w, minor_radius=0.055,
            rotation=[math.pi/2,0,0], scale=[1,1,0.72])
    elif top == "polo":
        add("collar", "box", secondary, "spine",
            location=[px,py-0.30,pz+2.18*h], dimensions=[0.34*torso_w,0.04,0.16], rotation=[0,0,0])

    bottom = char["wardrobe"]["bottom"]
    if bottom == "shorts":
        add("shorts", "box", primary, "pelvis",
            location=[px,py,pz+1.02*h], dimensions=[0.72*torso_w*hip_w,0.48,0.32*h], rotation=[0,0,0])

    accessory = char["wardrobe"]["accessory"]
    if accessory == "headphones":
        add("headphones", "torus", secondary, "neck",
            location=[px,py,pz+2.28*h], major_radius=0.34*head_scale*head_w, minor_radius=0.05,
            rotation=[math.pi/2,0,0], scale=[1,1,0.72])
    elif accessory == "glasses":
        for sign in (-1,1):
            add(f"glasses-{sign}", "torus", secondary, "head",
                location=[px+sign*0.16*head_scale*head_w*a["eye_spacing"],py-0.38*head_d,eye_z],
                major_radius=0.115*a["eye_size"], minor_radius=0.012,
                rotation=[math.pi/2,0,0], scale=[1,1,1])
    elif accessory == "pin":
        add("pin", "torus", f"{cid}:hair", "spine",
            location=[px+0.23*torso_w,py-0.32,pz+2.02*h], major_radius=0.055, minor_radius=0.012,
            rotation=[math.pi/2,0,0], scale=[1,1,1])

    return objects


def _animation(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    keys: list[dict[str, Any]] = []
    for char in blueprint["characters"]:
        cid = char["id"]
        for beat in blueprint["animation_beats"]:
            frame, name = beat["frame"], beat["name"]

            def key(bone: str, offset: int, rotation: tuple[float,float,float]):
                keys.append({
                    "frame": frame + offset,
                    "bone": f"{cid}_{bone}",
                    "rotation_euler": [round(v, 6) for v in rotation],
                })

            if name == "idle":
                key("spine", 0, (0.02, 0, -0.03))
                key("head", 12, (0, 0.04, 0.03))
                key("spine", 24, (-0.02, 0, 0.03))
            elif name == "walk":
                key("L_thigh", 0, (0.48,0,0)); key("R_thigh", 0, (-0.48,0,0))
                key("L_thigh", 12, (-0.48,0,0)); key("R_thigh", 12, (0.48,0,0))
                key("L_thigh", 24, (0.48,0,0)); key("R_thigh", 24, (-0.48,0,0))
            elif name == "wave":
                key("R_upperarm", 0, (-0.25,0,1.05))
                key("R_forearm", 8, (0,0,0.72))
                key("R_forearm", 16, (0,0,1.02))
                key("R_forearm", 24, (0,0,0.72))
            elif name == "celebrate":
                key("L_upperarm", 0, (0,0,-1.1)); key("R_upperarm", 0, (0,0,1.1))
                key("spine", 12, (0,0.05,0.12))
                key("L_upperarm", 24, (0,0,-1.28)); key("R_upperarm", 24, (0,0,1.28))
    return sorted(keys, key=lambda item: (item["frame"], item["bone"]))


def compile_blueprint(value: Any) -> dict[str, Any]:
    blueprint = validate_blueprint(value)
    bones = [bone for char in blueprint["characters"] for bone in _bone_specs(char)]
    objects = [obj for char in blueprint["characters"] for obj in _objects_for_character(char)]
    materials = _material_table(blueprint)
    animation = _animation(blueprint)

    geometry_basis = {
        "bones": bones,
        "objects": [
            {key: item[key] for key in item if key != "material"}
            for item in objects
        ],
    }
    behavior_basis = {"animation": animation}
    appearance_basis = {"materials": materials, "assignments": [item["material"] for item in objects]}
    plan = {
        "schema": SCENE_PLAN_SCHEMA,
        "compiler": COMPILER_VERSION,
        "blueprint_id": blueprint["id"],
        "blueprint_sha256": _digest(blueprint),
        "truth_boundary": {
            "profile_family": STYLE_FAMILY,
            "reference_interpretation_required": False,
            "smooth_skinning": False,
            "deformation": "RIGID_BONE_PARENTING",
        },
        "scene": {
            "fps": 24,
            "frame_start": 1,
            "frame_end": max((beat["frame"] + 24 for beat in blueprint["animation_beats"]), default=72),
            "camera": {"location": [0, -10.5, 3.1], "lens": 52},
            "background": "#20242c",
        },
        "materials": materials,
        "bones": bones,
        "objects": objects,
        "animation": animation,
        "geometry_signature": _digest(geometry_basis),
        "behavior_signature": _digest(behavior_basis),
        "appearance_signature": _digest(appearance_basis),
    }
    plan["plan_sha256"] = _digest(plan)
    return plan


def compile_blueprint_file(input_path: str | Path, output_path: str | Path) -> dict[str, Any]:
    blueprint = load_blueprint(input_path)
    plan = compile_blueprint(blueprint)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    return plan
