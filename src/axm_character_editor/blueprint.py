from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any

BLUEPRINT_SCHEMA = "axm.character.blueprint/v0.1"
FAMILY_SCHEMA = "axm.character.family/v0.1"
PRESET_SCHEMA = "axm.character.preset/v0.1"
PROFILE_SCHEMA = "axm.character.editor-profile/v0.1"

_DATA = Path(__file__).resolve().parent / "data"


class BlueprintError(ValueError):
    pass


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BlueprintError(f"missing character-editor data file: {path.name}") from exc
    except json.JSONDecodeError as exc:
        raise BlueprintError(f"invalid JSON in {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise BlueprintError(f"{path.name} must contain a JSON object")
    return value


def _digest(value: Any) -> str:
    body = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BlueprintError(f"{where} must be a non-empty string")
    return value.strip()


def _catalog_dir(name: str, schema: str) -> list[dict[str, Any]]:
    root = _DATA / name
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        row = _json(path)
        if row.get("schema") != schema:
            raise BlueprintError(f"{path.name} has unsupported schema {row.get('schema')!r}")
        rows.append(row)
    return rows


def families() -> list[dict[str, Any]]:
    return _catalog_dir("families", FAMILY_SCHEMA)


def presets() -> list[dict[str, Any]]:
    return _catalog_dir("presets", PRESET_SCHEMA)


def profiles() -> list[dict[str, Any]]:
    return _catalog_dir("profiles", PROFILE_SCHEMA)


def catalog() -> dict[str, Any]:
    return {
        "schema": "axm.character.catalog/v0.1",
        "families": [
            {
                "id": row["id"],
                "label": row["label"],
                "version": row["version"],
                "status": row["status"],
            }
            for row in families()
        ],
        "presets": [
            {
                "id": row["id"],
                "label": row["label"],
                "family": row["family"],
            }
            for row in presets()
        ],
        "profiles": [
            {
                "id": row["id"],
                "label": row["label"],
                "family": row["family"],
            }
            for row in profiles()
        ],
    }


def load_family(family_id: str) -> dict[str, Any]:
    family_id = _text(family_id, "family id")
    for row in families():
        if row.get("id") == family_id:
            return copy.deepcopy(row)
    raise BlueprintError(f"unknown character family {family_id!r}")


def load_preset(preset_id: str, family_id: str | None = None) -> dict[str, Any]:
    preset_id = _text(preset_id, "preset id")
    for row in presets():
        if row.get("id") == preset_id and (family_id is None or row.get("family") == family_id):
            return copy.deepcopy(row)
    suffix = f" for family {family_id!r}" if family_id else ""
    raise BlueprintError(f"unknown character preset {preset_id!r}{suffix}")


def load_profile(profile_id: str, family_id: str | None = None) -> dict[str, Any]:
    profile_id = _text(profile_id, "profile id")
    for row in profiles():
        if row.get("id") == profile_id and (family_id is None or row.get("family") == family_id):
            return copy.deepcopy(row)
    suffix = f" for family {family_id!r}" if family_id else ""
    raise BlueprintError(f"unknown editor profile {profile_id!r}{suffix}")


def _control_map(family: dict[str, Any]) -> dict[str, dict[str, Any]]:
    controls = family.get("controls")
    if not isinstance(controls, list) or not controls:
        raise BlueprintError("family.controls must be a non-empty list")
    result: dict[str, dict[str, Any]] = {}
    for index, spec in enumerate(controls):
        if not isinstance(spec, dict):
            raise BlueprintError(f"family.controls[{index}] must be an object")
        cid = _text(spec.get("id"), f"family.controls[{index}].id")
        if cid in result:
            raise BlueprintError(f"duplicate family control id {cid!r}")
        result[cid] = spec
    return result


def _hex_color(value: Any, where: str) -> str:
    value = _text(value, where).lower()
    if len(value) != 7 or value[0] != "#" or any(ch not in "0123456789abcdef" for ch in value[1:]):
        raise BlueprintError(f"{where} must be #RRGGBB")
    return value


def _normalize_control(value: Any, spec: dict[str, Any], where: str) -> Any:
    kind = spec.get("type")
    if kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise BlueprintError(f"{where} must be numeric")
        number = float(value)
        low, high = float(spec["min"]), float(spec["max"])
        if not math.isfinite(number) or not low <= number <= high:
            raise BlueprintError(f"{where} must be between {low} and {high}")
        return round(number, 6)
    if kind == "choice":
        value = _text(value, where)
        choices = spec.get("choices")
        if not isinstance(choices, list) or value not in choices:
            raise BlueprintError(f"{where} must be one of {choices}")
        return value
    if kind == "color":
        return _hex_color(value, where)
    if kind == "boolean":
        if not isinstance(value, bool):
            raise BlueprintError(f"{where} must be true or false")
        return value
    raise BlueprintError(f"unsupported control type {kind!r} for {spec.get('id')!r}")


def _defaults(family: dict[str, Any]) -> dict[str, Any]:
    return {
        cid: _normalize_control(spec.get("default"), spec, f"default.{cid}")
        for cid, spec in _control_map(family).items()
    }


def new_blueprint(
    character_id: str,
    *,
    family_id: str = "human-v0",
    preset_id: str | None = "female-a",
    profile_id: str | None = "rpg-v0",
) -> dict[str, Any]:
    family = load_family(family_id)
    controls = _defaults(family)
    selected_preset = None
    if preset_id:
        preset = load_preset(preset_id, family_id)
        overrides = preset.get("controls", {})
        if not isinstance(overrides, dict):
            raise BlueprintError("preset.controls must be an object")
        controls.update(copy.deepcopy(overrides))
        selected_preset = preset["id"]
    rig_profiles = family.get("rig_profiles", [])
    if not rig_profiles:
        raise BlueprintError(f"family {family_id!r} has no rig profile declaration")
    blueprint = {
        "schema": BLUEPRINT_SCHEMA,
        "id": _text(character_id, "character id"),
        "family": family_id,
        "family_version": family["version"],
        "preset": selected_preset,
        "editor_profile": profile_id,
        "rig_profile": rig_profiles[0]["id"],
        "controls": controls,
        "authorship": {
            "method": "HUMAN_OR_AI_EXPLICIT_FIELDS",
            "note": "Same blueprint contract for human editor, program, or AI caller.",
        },
    }
    return validate_blueprint(blueprint)


def validate_blueprint(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BlueprintError("blueprint must be an object")
    data = copy.deepcopy(value)
    if data.get("schema") != BLUEPRINT_SCHEMA:
        raise BlueprintError(f"blueprint.schema must be {BLUEPRINT_SCHEMA!r}")

    character_id = _text(data.get("id"), "blueprint.id")
    family_id = _text(data.get("family"), "blueprint.family")
    family = load_family(family_id)
    if data.get("family_version") not in (None, family["version"]):
        raise BlueprintError(
            f"blueprint.family_version {data.get('family_version')!r} does not match installed "
            f"{family_id!r} version {family['version']!r}"
        )

    specs = _control_map(family)
    supplied = data.get("controls")
    if not isinstance(supplied, dict):
        raise BlueprintError("blueprint.controls must be an object")
    unknown = sorted(set(supplied) - set(specs))
    if unknown:
        raise BlueprintError(f"unsupported controls for {family_id}: {unknown}")

    normalized = _defaults(family)
    for cid, raw in supplied.items():
        normalized[cid] = _normalize_control(raw, specs[cid], f"blueprint.controls.{cid}")

    preset_id = data.get("preset")
    if preset_id is not None:
        load_preset(_text(preset_id, "blueprint.preset"), family_id)

    profile_id = data.get("editor_profile")
    if profile_id is not None:
        profile = load_profile(_text(profile_id, "blueprint.editor_profile"), family_id)
        visible = profile.get("visible_controls", [])
        missing = sorted(set(visible) - set(specs))
        if missing:
            raise BlueprintError(f"editor profile references missing family controls: {missing}")

    rig_profile = _text(data.get("rig_profile"), "blueprint.rig_profile")
    rig_ids = {row.get("id") for row in family.get("rig_profiles", [])}
    if rig_profile not in rig_ids:
        raise BlueprintError(f"blueprint.rig_profile must be one of {sorted(rig_ids)}")

    authorship = copy.deepcopy(data.get("authorship", {"method": "HUMAN_OR_AI_EXPLICIT_FIELDS"}))
    if not isinstance(authorship, dict):
        raise BlueprintError("blueprint.authorship must be an object")

    return {
        "schema": BLUEPRINT_SCHEMA,
        "id": character_id,
        "family": family_id,
        "family_version": family["version"],
        "preset": preset_id,
        "editor_profile": profile_id,
        "rig_profile": rig_profile,
        "controls": normalized,
        "authorship": authorship,
    }


def signature_bundle(value: Any) -> dict[str, str]:
    blueprint = validate_blueprint(value)
    family = load_family(blueprint["family"])
    specs = _control_map(family)
    channels: dict[str, dict[str, Any]] = {}
    for cid, raw in blueprint["controls"].items():
        channel = specs[cid].get("channel", "other")
        channels.setdefault(channel, {})[cid] = raw
    return {
        "blueprint_sha256": _digest(blueprint),
        **{
            f"{channel}_sha256": _digest(
                {
                    "family": blueprint["family"],
                    "family_version": blueprint["family_version"],
                    "controls": controls,
                }
            )
            for channel, controls in sorted(channels.items())
        },
    }


def build_receipt(value: Any) -> dict[str, Any]:
    blueprint = validate_blueprint(value)
    family = load_family(blueprint["family"])
    rig = next(row for row in family["rig_profiles"] if row["id"] == blueprint["rig_profile"])
    candidate_ready = (
        blueprint["family"] == "human-v0"
        and family["build_status"] == "STRUCTURAL_RIGGED_GLB_CANDIDATE_BUILDER_AVAILABLE"
    )
    return {
        "schema": "axm.character.blueprint-receipt/v0.1",
        "id": blueprint["id"],
        "family": blueprint["family"],
        "signatures": signature_bundle(blueprint),
        "blueprint_status": "VALIDATED",
        "rig_status": rig["status"],
        "asset_build_status": family["build_status"],
        "game_asset_candidate_ready": candidate_ready,
        "game_asset_ready": False,
        "truth": (
            "The blueprint/editor state is deterministic and validated. "
            "human-v0 can now build a structurally verified rigged GLB candidate, "
            "but target-RPG import, visual deformation acceptance, clothing fit and "
            "runtime performance have not yet been proven; game_asset_ready remains false."
        ),
    }


def load_blueprint(path: str | Path) -> dict[str, Any]:
    return validate_blueprint(json.loads(Path(path).read_text(encoding="utf-8")))


def write_blueprint(value: Any, path: str | Path) -> dict[str, Any]:
    blueprint = validate_blueprint(value)
    Path(path).write_text(json.dumps(blueprint, indent=2) + "\n", encoding="utf-8")
    return blueprint
