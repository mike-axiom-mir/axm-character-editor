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

    args = parser.parse_args()
    try:
        if args.command == "catalog":
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
    except BlueprintError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
