#!/usr/bin/env python3
"""List preset citations with their usage counts across YAML code files."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent.parent
BIB_PRESET_PATH = ROOT / "code_extra" / "bib_preset.yml"
CODES_DIR = ROOT / "codes"
OUTPUT_PATH = ROOT / "resources" / "preset_cite_counts.txt"

PRESET_PATTERN = re.compile(r"preset:(\w+)")


def load_preset_keys() -> list[str]:
    with BIB_PRESET_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return list(data.keys())


def count_preset_citations() -> Counter:
    counts: Counter = Counter()

    for yml_path in sorted(CODES_DIR.rglob("*.yml")):
        content = yml_path.read_text(encoding="utf-8")
        uncommented = "\n".join(
            line for line in content.splitlines() if not re.match(r"^\s*#", line)
        )
        for key in PRESET_PATTERN.findall(uncommented):
            counts[key] += 1

    return counts


def main() -> int:
    preset_keys = load_preset_keys()
    counts = count_preset_citations()

    rows = sorted(
        ((key, counts.get(key, 0)) for key in preset_keys),
        key=lambda row: row[1],
        reverse=True,
    )

    lines = [f"{key}\t{count}" for key, count in rows]
    OUTPUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(lines)} presets to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
