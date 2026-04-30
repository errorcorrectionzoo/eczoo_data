#!/usr/bin/env python3

"""Print all recursive children of a given EC Zoo code_id.

This script scans the YAML files under ../codes, builds the reverse mapping
from parent code_id to child code_id, and prints every descendant of the
requested code_id exactly once.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict


def _strip_quotes(value: str) -> str:
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
                    code_id = _strip_quotes(stripped.split(":", 1)[1])
                elif stripped.startswith("relations:"):
                    in_relations = True

                continue

            if not in_relations:
                continue

            if indent == 2:
                in_parents = stripped.startswith("parents:")
                continue

            if in_parents and indent >= 4 and stripped.startswith("- code_id:"):
                parent_id = _strip_quotes(stripped.split(":", 1)[1])
                if parent_id:
                    parents.append(parent_id)

    return code_id, parents


def build_parent_to_children_map(codes_dir: str) -> tuple[dict[str, set[str]], set[str]]:
    parent_to_children: dict[str, set[str]] = defaultdict(set)
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
            for parent_id in parents:
                parent_to_children[parent_id].add(code_id)

    return parent_to_children, known_code_ids


def find_recursive_children(code_id: str, parent_to_children: dict[str, set[str]]) -> list[str]:
    visited: set[str] = set()
    ordered_children: list[str] = []

    def visit(parent_id: str) -> None:
        for child_id in sorted(parent_to_children.get(parent_id, set())):
            if child_id in visited:
                continue

            visited.add(child_id)
            ordered_children.append(child_id)
            visit(child_id)

    visit(code_id)
    return ordered_children


def parse_args() -> argparse.Namespace:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_codes_dir = os.path.normpath(os.path.join(script_dir, "..", "codes"))

    parser = argparse.ArgumentParser(
        description="Print all recursive children of a given code_id.",
    )
    parser.add_argument("code_id", help="Code identifier to search below.")
    parser.add_argument(
        "--codes-dir",
        default=default_codes_dir,
        help="Directory containing EC Zoo YAML code files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    parent_to_children, known_code_ids = build_parent_to_children_map(args.codes_dir)

    if args.code_id not in known_code_ids:
        print(f"Unknown code_id: {args.code_id}", file=sys.stderr)
        return 1

    for child_id in find_recursive_children(args.code_id, parent_to_children):
        print(child_id)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())