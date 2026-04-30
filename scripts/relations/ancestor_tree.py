#!/usr/bin/env python3

# Print a tree of all recursive ancestors of a given code_id,
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


def print_ancestor_tree(
    code_id: str,
    code_to_parents: dict[str, list[str]],
    prefix: str = "",
    is_last: bool = True,
    seen: set[str] | None = None,
    root: bool = False,
) -> None:
    if seen is None:
        seen = set()

    connector = "" if root else ("└── " if is_last else "├── ")
    already_seen = code_id in seen

    label = code_id + (" [see above]" if already_seen else "")
    print(prefix + connector + label)

    if already_seen:
        return

    seen.add(code_id)

    parents = code_to_parents.get(code_id, [])
    child_prefix = prefix if root else (prefix + ("    " if is_last else "│   "))

    for i, parent_id in enumerate(parents):
        print_ancestor_tree(
            parent_id,
            code_to_parents,
            prefix=child_prefix,
            is_last=(i == len(parents) - 1),
            seen=seen,
        )


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    default_codes_dir = str(script_dir.parent.parent / "codes")

    parser = argparse.ArgumentParser(
        description="Print a tree of all recursive ancestors of a given code_id.",
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

    print_ancestor_tree(args.code_id, code_to_parents, root=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
