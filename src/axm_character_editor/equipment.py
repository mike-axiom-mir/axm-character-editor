from __future__ import annotations

"""Semantic equipment slots and attachment sockets for AXM characters.

Garment slots describe things that normally deform with the body. Attachment
sockets describe rigid or independently simulated things that follow a joint.
The character Blueprint remains independent from what a particular game equips.
"""

from typing import Any

EQUIPMENT_SCHEMA = "axm.character.equipment-contract/v0.1"
SOCKET_SCHEMA = "axm.character.socket/v0.1"


class EquipmentContractError(ValueError):
    pass


def _slot(
    slot_id: str,
    *,
    mode: str,
    regions: list[str],
    accepts: list[str],
    default_socket: str | None = None,
) -> dict[str, Any]:
    row = {
        "id": slot_id,
        "mode": mode,
        "regions": regions,
        "accepts": accepts,
    }
    if default_socket is not None:
        row["default_socket"] = default_socket
    return row


def _socket(
    socket_id: str,
    parent_joint: str,
    translation: tuple[float, float, float],
    *,
    accepts: list[str],
    purpose: str,
) -> dict[str, Any]:
    return {
        "schema": SOCKET_SCHEMA,
        "id": socket_id,
        "parent_joint": parent_joint,
        "translation": [round(float(v), 6) for v in translation],
        "rotation": [0.0, 0.0, 0.0, 1.0],
        "forward": [0.0, 0.0, 1.0],
        "up": [0.0, 1.0, 0.0],
        "accepts": accepts,
        "purpose": purpose,
    }


def compile_human_v0_equipment(
    controls: dict[str, Any],
    metrics: Any,
    *,
    joint_names: set[str] | None = None,
) -> dict[str, Any]:
    """Compile the default human-v0 equipment interface.

    Metrics are deliberately duck-typed so the generic equipment contract does
    not depend on the human geometry implementation.
    """
    s = float(metrics.scale)
    shoulder = float(metrics.shoulder_half)
    hip = float(metrics.hip_half)
    hand = float(metrics.hand_len)
    torso = float(metrics.torso_h)

    slots = [
        _slot("body", mode="skinned", regions=["torso", "neck"], accepts=["body-layer", "body-armor", "undersuit"]),
        _slot("top", mode="skinned", regions=["torso", "upper-arms"], accepts=["shirt", "tunic", "jacket", "chest-armor"]),
        _slot("bottom", mode="skinned", regions=["pelvis", "upper-legs"], accepts=["trousers", "shorts", "skirt", "leg-armor"]),
        _slot("feet", mode="skinned", regions=["feet", "ankles"], accepts=["shoes", "boots", "sandals", "foot-armor"]),
        _slot("hands", mode="skinned", regions=["hands", "wrists"], accepts=["gloves", "gauntlets", "hand-armor"]),
        _slot(
            "headwear",
            mode="hybrid",
            regions=["head"],
            accepts=["hat", "helmet", "mask", "head-accessory"],
            default_socket="head",
        ),
        _slot(
            "outerwear",
            mode="hybrid",
            regions=["shoulders", "back"],
            accepts=["cape", "cloak", "coat", "poncho"],
            default_socket="cape.L",
        ),
    ]

    sockets = [
        _socket("head", "Head", (0, .105*s, 0), accepts=["hat", "helmet", "head-accessory"], purpose="top/head rigid attachment"),
        _socket("face", "Head", (0, .025*s, .105*s), accepts=["mask", "visor", "face-accessory"], purpose="face-front attachment"),
        _socket("neck", "Neck", (0, .025*s, .045*s), accepts=["necklace", "collar", "scarf-anchor"], purpose="neck accessory anchor"),
        _socket("chest", "Chest", (0, .015*s, .135*s), accepts=["chest-item", "badge", "front-pack"], purpose="front torso attachment"),
        _socket("back.center", "Chest", (0, -.035*torso, -.145*s), accepts=["backpack", "tank", "large-back-item"], purpose="general backpack/back item"),
        _socket("back.upper", "Chest", (0, .095*torso, -.145*s), accepts=["shield", "long-weapon", "tool", "back-holster"], purpose="upper-back stow point"),
        _socket("back.lower", "Spine", (0, -.035*torso, -.125*s), accepts=["pouch", "bedroll", "lower-back-item"], purpose="lower-back equipment"),
        _socket("weapon.back", "Chest", (0, .055*torso, -.165*s), accepts=["rifle", "sword", "staff", "axe", "long-weapon"], purpose="generic long-weapon back stow"),
        _socket("waist", "Pelvis", (0, .055*s, .115*s), accepts=["belt-item", "pouch", "front-holster"], purpose="waist/front belt attachment"),
        _socket("hip.L", "Pelvis", (-.85*hip, 0, .01*s), accepts=["pouch", "holster", "tool", "side-item"], purpose="left hip attachment"),
        _socket("hip.R", "Pelvis", (.85*hip, 0, .01*s), accepts=["pouch", "holster", "tool", "side-item"], purpose="right hip attachment"),
        _socket("weapon.hip.L", "Pelvis", (-1.02*hip, -.015*s, 0), accepts=["pistol", "knife", "sword", "holstered-weapon"], purpose="left weapon holster"),
        _socket("weapon.hip.R", "Pelvis", (1.02*hip, -.015*s, 0), accepts=["pistol", "knife", "sword", "holstered-weapon"], purpose="right weapon holster"),
        _socket("shoulder.L", "Chest", (-.82*shoulder, .095*torso, 0), accepts=["pauldron", "shoulder-item", "strap"], purpose="left shoulder equipment"),
        _socket("shoulder.R", "Chest", (.82*shoulder, .095*torso, 0), accepts=["pauldron", "shoulder-item", "strap"], purpose="right shoulder equipment"),
        _socket("cape.L", "Chest", (-.48*shoulder, .105*torso, -.105*s), accepts=["cape-anchor", "cloak-anchor"], purpose="left deformable cape/cloak root"),
        _socket("cape.R", "Chest", (.48*shoulder, .105*torso, -.105*s), accepts=["cape-anchor", "cloak-anchor"], purpose="right deformable cape/cloak root"),
        _socket("wrist.L", "Hand.L", (0, 0, 0), accepts=["bracelet", "watch", "wrist-item"], purpose="left wrist attachment"),
        _socket("wrist.R", "Hand.R", (0, 0, 0), accepts=["bracelet", "watch", "wrist-item"], purpose="right wrist attachment"),
        _socket("hand.L", "Hand.L", (-.20*hand, 0, 0), accepts=["held-item", "weapon", "tool"], purpose="left palm/hand attachment"),
        _socket("hand.R", "Hand.R", (.20*hand, 0, 0), accepts=["held-item", "weapon", "tool"], purpose="right palm/hand attachment"),
        _socket("grip.L", "Hand.L", (-.34*hand, 0, .015*s), accepts=["weapon-grip", "tool-grip"], purpose="left primary/secondary grip target"),
        _socket("grip.R", "Hand.R", (.34*hand, 0, .015*s), accepts=["weapon-grip", "tool-grip"], purpose="right primary/secondary grip target"),
        _socket("item.L", "Hand.L", (-.34*hand, 0, .025*s), accepts=["held-item", "consumable", "tool"], purpose="generic left held-item target"),
        _socket("item.R", "Hand.R", (.34*hand, 0, .025*s), accepts=["held-item", "consumable", "tool"], purpose="generic right held-item target"),
    ]

    if joint_names is not None:
        missing = sorted({row["parent_joint"] for row in sockets} - set(joint_names))
        if missing:
            raise EquipmentContractError(f"equipment sockets reference missing joints: {missing}")

    slot_ids = [row["id"] for row in slots]
    socket_ids = [row["id"] for row in sockets]
    if len(slot_ids) != len(set(slot_ids)) or len(socket_ids) != len(set(socket_ids)):
        raise EquipmentContractError("equipment slot/socket ids must be unique")

    return {
        "schema": EQUIPMENT_SCHEMA,
        "family": "human-v0",
        "coordinate_system": {
            "units": "metres",
            "up": "+Y",
            "forward": "+Z",
            "socket_transform": "parent-joint-local TRS",
        },
        "slots": slots,
        "sockets": sockets,
        "weapon_attachment": {
            "character_targets": ["grip.L", "grip.R", "weapon.back", "weapon.hip.L", "weapon.hip.R"],
            "asset_rule": (
                "A weapon/tool may declare one primary_grip transform and an optional "
                "secondary_grip transform. Games align the asset primary grip to one "
                "character grip socket and may solve the opposite hand toward the "
                "secondary grip without changing the character Blueprint."
            ),
        },
        "cape_and_back_rule": (
            "Backpacks and stowed rigid items attach to back.* sockets. Capes/cloaks "
            "may use cape.L/cape.R as roots, but their visible cloth remains independently "
            "skinned or simulated; the sockets are anchors, not a rigid-cloth substitute."
        ),
        "growth_rule": (
            "New optional slots/sockets may be added with stable names and neutral absence. "
            "Existing character Blueprints are not rewritten merely because the contract grows."
        ),
    }


def validate_equipment_contract(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema") != EQUIPMENT_SCHEMA:
        raise EquipmentContractError(f"equipment contract must use {EQUIPMENT_SCHEMA}")
    slots = value.get("slots")
    sockets = value.get("sockets")
    if not isinstance(slots, list) or not isinstance(sockets, list):
        raise EquipmentContractError("equipment contract requires slot and socket lists")
    if len({row.get("id") for row in slots}) != len(slots):
        raise EquipmentContractError("duplicate equipment slot id")
    if len({row.get("id") for row in sockets}) != len(sockets):
        raise EquipmentContractError("duplicate equipment socket id")
    for row in sockets:
        if row.get("schema") != SOCKET_SCHEMA:
            raise EquipmentContractError("socket schema mismatch")
        if not isinstance(row.get("parent_joint"), str):
            raise EquipmentContractError("socket parent_joint must be text")
        translation = row.get("translation")
        rotation = row.get("rotation")
        if not isinstance(translation, list) or len(translation) != 3:
            raise EquipmentContractError("socket translation must contain three numbers")
        if not isinstance(rotation, list) or len(rotation) != 4:
            raise EquipmentContractError("socket rotation must contain four numbers")
    return value
