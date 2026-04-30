#!/usr/bin/env python3

# Print all recursive ancestors of a given code_id as a flat list,
# using the parent relations defined in the EC Zoo YAML code files.

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


def build_code_to_parents_map(codes_dir: str) -> tuple[dict[str, list[str]], set[str]]:
    code_to_parents: dict[str, list[str]] = {}
    known_code_ids: set[str] = set()

    for root, _, files in os.walk(codes_dir):
        for file_name in files:
            if not file_name.endswith((".yml", ".yaml")):
                continue

            file_path = os.path.join(root, file_name)
            code_id, parents = parse_code_metadata(file_path)
            if not code_id:
                continue

            known_code_ids.add(code_id)
            code_to_parents[code_id] = parents

    return code_to_parents, known_code_ids


def find_recursive_ancestors(code_id: str, code_to_parents: dict[str, list[str]]) -> list[str]:
    visited: set[str] = set()
    ordered_ancestors: list[str] = []

    def visit(child_id: str) -> None:
        for parent_id in code_to_parents.get(child_id, []):
            if parent_id in visited:
                continue

            visited.add(parent_id)
            ordered_ancestors.append(parent_id)
            visit(parent_id)

    visit(code_id)
    return ordered_ancestors


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    default_codes_dir = str(script_dir.parent.parent / "codes")

    parser = argparse.ArgumentParser(
        description="Print all recursive ancestors of a given code_id.",
    )
    parser.add_argument("code_id", help="Code identifier to search above.")
    parser.add_argument(
        "--codes-dir",
        default=default_codes_dir,
        help="Directory containing EC Zoo YAML code files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    code_to_parents, known_code_ids = build_code_to_parents_map(args.codes_dir)

    if args.code_id not in known_code_ids:
        print(f"Unknown code_id: {args.code_id}", file=sys.stderr)
        return 1

    for parent_id in find_recursive_ancestors(args.code_id, code_to_parents):
        print(parent_id)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
