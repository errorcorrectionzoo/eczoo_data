#!/usr/bin/env python3

# Count the cousin relations of a given code_id.
#
# Prints three counts:
#   outgoing – cousins explicitly listed on the given code
#   incoming – other codes that list the given code as their cousin
#   total    – size of the union (unique codes in either direction)

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def parse_code_metadata(file_path: str) -> tuple[str | None, list[str], list[str]]:
    """Return (code_id, parent_ids, cousin_ids) parsed from a YAML code file."""
    code_id = None
    parents: list[str] = []
    cousins: list[str] = []

    in_relations = False
    in_parents = False
    in_cousins = False

    with open(file_path, "r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.split("#", 1)[0].rstrip("\n")
            if not line.strip():
                continue

            stripped = line.lstrip(" ")
            indent = len(line) - len(stripped)

            if indent == 0:
                in_relations = False
                in_parents = False
                in_cousins = False

                if stripped.startswith("code_id:"):
                    code_id = _strip_quotes(stripped.split(":", 1)[1])
                elif stripped.startswith("relations:"):
                    in_relations = True
                continue

            if not in_relations:
                continue

            if indent == 2:
                in_parents = stripped.startswith("parents:")
                in_cousins = stripped.startswith("cousins:")
                continue

            if indent >= 4 and stripped.startswith("- code_id:"):
                target_id = _strip_quotes(stripped.split(":", 1)[1])
                if not target_id:
                    continue
                if in_parents:
                    parents.append(target_id)
                elif in_cousins:
                    cousins.append(target_id)

    return code_id, parents, cousins


def build_maps(
    codes_dir: str,
) -> tuple[dict[str, list[str]], dict[str, list[str]], set[str]]:
    """Return (outgoing, incoming, known_ids) cousin maps."""
    outgoing: dict[str, list[str]] = defaultdict(list)   # code -> cousins it declares
    incoming: dict[str, list[str]] = defaultdict(list)   # code -> codes that declare it as cousin
    known: set[str] = set()

    for root, _, files in os.walk(codes_dir):
        for fname in files:
            if not fname.endswith((".yml", ".yaml")):
                continue
            code_id, _, cousins = parse_code_metadata(os.path.join(root, fname))
            if not code_id:
                continue
            known.add(code_id)
            for c in cousins:
                outgoing[code_id].append(c)
                incoming[c].append(code_id)

    return outgoing, incoming, known


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    default_codes_dir = str(script_dir.parent.parent / "codes")

    parser = argparse.ArgumentParser(
        description="Count the cousin relations of a given code_id.",
    )
    parser.add_argument("code_id", help="Code identifier to inspect.")
    parser.add_argument(
        "--codes-dir",
        default=default_codes_dir,
        help="Directory containing EC Zoo YAML code files.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Also print each cousin code_id.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    outgoing, incoming, known = build_maps(args.codes_dir)

    if args.code_id not in known:
        print(f"Unknown code_id: {args.code_id}", file=sys.stderr)
        return 1

    out_set = set(outgoing.get(args.code_id, []))
    in_set = set(incoming.get(args.code_id, []))
    total = out_set | in_set

    print(f"outgoing (declared by {args.code_id}): {len(out_set)}")
    print(f"incoming (others declaring {args.code_id}): {len(in_set)}")
    print(f"total unique: {len(total)}")

    if args.list:
        print("\n--- outgoing ---")
        for c in sorted(out_set):
            print(f"  {c}")
        print("--- incoming ---")
        for c in sorted(in_set):
            print(f"  {c}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
