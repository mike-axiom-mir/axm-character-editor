# Human-v0 equipment slots and attachment sockets

Every generated human-v0 character carries a semantic equipment contract. The
first survival test does not need to use all of it; the purpose is to give later
games one stable default instead of inventing incompatible attachment names.

## Two different mechanisms

### Garment/equipment slots

Slots describe things whose visible geometry normally follows or deforms with the
body.

Current defaults:

- body — undersuit, body layer, body armor
- top — shirt, tunic, jacket, chest armor
- bottom — trousers, shorts, skirt, leg armor
- feet — shoes, boots, sandals, foot armor
- hands — gloves, gauntlets
- headwear — hat/helmet/mask; may be rigid or skinned
- outerwear — cape/cloak/coat/poncho; may combine anchors with skin/cloth

A slot is semantic. It is not a single transform.

### Attachment sockets

Sockets are named parent-joint-local transforms emitted as actual empty glTF nodes
inside character.glb. A game may discover them from node extras instead of keeping
a private hard-coded skeleton map.

Core sockets include:

- head, face, neck, chest
- back.center, back.upper, back.lower
- waist
- hip.L / hip.R
- shoulder.L / shoulder.R
- cape.L / cape.R
- wrist.L / wrist.R
- hand.L / hand.R
- grip.L / grip.R
- item.L / item.R
- weapon.back
- weapon.hip.L / weapon.hip.R

The socket positions scale with the generated character proportions.

## Backpacks and capes

A backpack, tank or rigid carried prop can attach directly to back.center,
back.upper or back.lower.

A cape or cloak is different: cape.L and cape.R are roots/anchors. The visible
cloth should remain independently skinned or simulated. The socket contract does
not turn cloth into a rigid board on the character's back.

## Weapons and tools

The character exposes grip.L and grip.R plus stow locations on the back and hips.

A weapon/tool asset may later declare:

- primary_grip — the transform aligned to the selected character grip socket
- optional secondary_grip — a target used to position/solve the opposite hand

That allows one-handed swords/pistols and two-handed rifles/staffs/axes to share
one character contract without baking weapon-specific hand positions into the
character Blueprint.

## Persistence

Equipment is game/world state, not part of the base character identity merely
because a compatible slot/socket exists.

A world may therefore retain:

character Blueprint
+ character GLB
+ equipment-contract.json
+ equipped-item state

and later swap or improve the attached asset while preserving the same character.

## Growth rule

New optional slots/sockets can be added later with stable names and neutral
absence. Existing saved characters do not need an aesthetic rewrite when the
contract grows.
