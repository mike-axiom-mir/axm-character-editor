from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "axm_character_editor" / "data"
TEMPLATE = ROOT / "editor" / "template.html"


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def build(out: Path) -> Path:
    family = read(DATA / "families" / "human-v0.json")
    profile = read(DATA / "profiles" / "rpg-v0.json")
    presets = [
        read(path)
        for path in sorted((DATA / "presets").glob("human-*.json"))
    ]
    payload = json.dumps(
        {"family": family, "profile": profile, "presets": presets},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).replace("</", "<\\/")
    source = TEMPLATE.read_text(encoding="utf-8")
    marker = "__AXM_EDITOR_DATA__"
    if source.count(marker) != 1:
        raise RuntimeError("editor template must contain exactly one data marker")
    result = source.replace(marker, payload)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result, encoding="utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="dist/character-editor.html")
    args = parser.parse_args()
    path = build((ROOT / args.out).resolve())
    print(path)


if __name__ == "__main__":
    main()
