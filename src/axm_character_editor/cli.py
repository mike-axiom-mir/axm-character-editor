from __future__ import annotations

import argparse
import json
from pathlib import Path

from .blueprint import (
    BlueprintError,
    build_receipt,
    catalog,
    load_blueprint,
    new_blueprint,
    write_blueprint,
)
from .human_asset import HumanAssetError, build_package, verify_glb_path
from .game_asset_verify import GameAssetVerificationError, verify_path as verify_deformation_path
from .human_face import HumanFaceError, face_summary, write_obj as write_face_obj
from .equipment import EquipmentContractError, compile_human_v0_equipment
from .observation import write_observation_pack


def _dump(value) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(prog="axm-character")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("catalog", help="Show installed families, presets and editor profiles")

    new = commands.add_parser("new", help="Create a deterministic character blueprint")
    new.add_argument("id")
    new.add_argument("--family", default="human-v0")
    new.add_argument("--preset", default="female-a")
    new.add_argument("--profile", default="rpg-v0")
    new.add_argument("--out", required=True)

    validate = commands.add_parser("validate", help="Validate and normalize a blueprint")
    validate.add_argument("blueprint")

    receipt = commands.add_parser("receipt", help="Show signatures and current build truth")
    receipt.add_argument("blueprint")

    face = commands.add_parser(
        "face-proof",
        help="Write the Aura-derived human-v0 face geometry as an OBJ proof",
    )
    face.add_argument("blueprint")
    face.add_argument("--out", required=True)

    build = commands.add_parser(
        "build",
        help="Build a structural rigged GLB candidate package from a character blueprint",
    )
    build.add_argument("blueprint")
    build.add_argument("output_dir")
    build.add_argument("--buffer-backend", choices=("builtin", "form-engine"), default="builtin",
                       help="Explicit binary buffer provider; form-engine must be installed separately")

    verify = commands.add_parser(
        "verify-glb",
        help="Re-open the generated GLB and verify its structural skin/clip contract",
    )
    verify.add_argument("glb")

    deform = commands.add_parser(
        "verify-deformation",
        help="Independently decode the GLB, play its skin/clips and sample actual exported vertices",
    )
    deform.add_argument("glb")

    equipment = commands.add_parser(
        "equipment",
        help="Show the semantic garment slots and attachment sockets for a character Blueprint",
    )
    equipment.add_argument("blueprint")
    observe = commands.add_parser(
        "observe",
        help="Render a dependency-free visual observation sheet from an exported GLB",
    )
    observe.add_argument("glb")
    observe.add_argument("output_dir")

    web = commands.add_parser("serve", help="Open the detailed browser character editor with the local builder")
    web.add_argument("--port", type=int, default=8765)

    args = parser.parse_args()
    try:
        if args.command == "serve":
            from .editor_server import serve
            serve(args.port)
        elif args.command == "catalog":
            _dump(catalog())
        elif args.command == "new":
            value = new_blueprint(
                args.id,
                family_id=args.family,
                preset_id=args.preset or None,
                profile_id=args.profile or None,
            )
            write_blueprint(value, Path(args.out))
            _dump(value)
        elif args.command == "validate":
            _dump(load_blueprint(args.blueprint))
        elif args.command == "receipt":
            _dump(build_receipt(load_blueprint(args.blueprint)))
        elif args.command == "face-proof":
            blueprint = load_blueprint(args.blueprint)
            if blueprint["family"] != "human-v0":
                raise HumanFaceError("face-proof currently supports human-v0 only")
            path = write_face_obj(blueprint["controls"], Path(args.out))
            _dump({"path": str(path), **face_summary(blueprint["controls"])})
        elif args.command == "build":
            _dump(build_package(load_blueprint(args.blueprint), Path(args.output_dir), buffer_backend=args.buffer_backend))
        elif args.command == "verify-glb":
            _dump(verify_glb_path(Path(args.glb)))
        elif args.command == "verify-deformation":
            _dump(verify_deformation_path(Path(args.glb)))
        elif args.command == "equipment":
            blueprint = load_blueprint(args.blueprint)
            if blueprint["family"] != "human-v0":
                raise HumanAssetError("equipment currently supports human-v0 only")
            from .human_asset import body_metrics, skeleton
            _dump(compile_human_v0_equipment(
                blueprint["controls"],
                body_metrics(blueprint["controls"]),
                joint_names={row["id"] for row in skeleton(blueprint["controls"])},
            ))
        elif args.command == "observe":
            _dump(write_observation_pack(Path(args.glb), Path(args.output_dir)))
    except (
        BlueprintError,
        HumanFaceError,
        HumanAssetError,
        EquipmentContractError,
        GameAssetVerificationError,
        FileExistsError,
        json.JSONDecodeError,
    ) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
