#!/usr/bin/env python3

# For every code in the EC Zoo, check whether its primary parent is also a
# direct parent of any of the code's secondary parents.  If so, the primary
# parent relation is redundant and could be removed (it is already implied by
# the secondary parent chain).  Only codes with at least one such redundancy
# are printed.

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def parse_code_metadata(file_path: str) -> tuple[str | None, list[str]]:
    code_id = None
    parents: list[str] = []
    in_relations = False
    in_parents = False

    with open(file_path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.split("#", 1)[0].rstrip("\n")
            if not line.strip():
                continue

            stripped = line.lstrip(" ")
            indent = len(line) - len(stripped)

            if indent == 0:
                in_relations = False
                in_parents = False

                if stripped.startswith("code_id:"):
                    code_id = strip_quotes(stripped.split(":", 1)[1])
                elif stripped.startswith("relations:"):
                    in_relations = True

                continue

            if not in_relations:
                continue

            if indent == 2:
                in_parents = stripped.startswith("parents:")
                continue

            if in_parents and indent >= 4 and stripped.startswith("- code_id:"):
                parent_id = strip_quotes(stripped.split(":", 1)[1])
                if parent_id:
                    parents.append(parent_id)

    return code_id, parents


def build_code_to_parents_map(codes_dir: str) -> dict[str, list[str]]:
    code_to_parents: dict[str, list[str]] = {}

    for root, _, files in os.walk(codes_dir):
        for file_name in files:
            if not file_name.endswith((".yml", ".yaml")):
                continue

            file_path = os.path.join(root, file_name)
            code_id, parents = parse_code_metadata(file_path)
            if not code_id:
                continue

            code_to_parents[code_id] = parents

    return code_to_parents


def find_redundant_primary(
    code_id: str, code_to_parents: dict[str, list[str]]
) -> list[str]:
    """Return secondary parents of code_id whose own parents include the primary parent."""
    parents = code_to_parents.get(code_id, [])
    if len(parents) < 2:
        return []
    primary = parents[0]
    return [s for s in parents[1:] if primary in code_to_parents.get(s, [])]


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    default_codes_dir = str(script_dir.parent.parent / "codes")

    parser = argparse.ArgumentParser(
        description=(
            "List all codes whose primary parent is also a direct parent of "
            "at least one of their secondary parents (redundant primary parent)."
        ),
    )
    parser.add_argument(
        "--codes-dir",
        default=default_codes_dir,
        help="Directory containing EC Zoo YAML code files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    code_to_parents = build_code_to_parents_map(args.codes_dir)

    found_any = False
    for code_id in sorted(code_to_parents):
        hits = find_redundant_primary(code_id, code_to_parents)
        if not hits:
            continue
        primary = code_to_parents[code_id][0]
        found_any = True
        for s in hits:
            print(f"{code_id}: primary '{primary}' is also a parent of secondary '{s}'")

    if not found_any:
        print("No redundant primary parents found.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
