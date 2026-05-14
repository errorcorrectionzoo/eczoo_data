#!/usr/bin/env python3

# Check whether direct children are also descendants through another
# parent-child chain.  Such direct child relations are redundant because the
# child is already reachable below the parent through at least one intermediate
# code.

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict, deque
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


def build_parent_to_children_map(codes_dir: str) -> tuple[dict[str, list[str]], set[str]]:
    parent_to_children: dict[str, list[str]] = defaultdict(list)
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
                parent_to_children[parent_id].append(code_id)

    for children in parent_to_children.values():
        children.sort()

    return parent_to_children, known_code_ids


def find_alternate_child_path(
    code_id: str,
    child_id: str,
    parent_to_children: dict[str, list[str]],
) -> list[str] | None:
    """Return a code_id -> ... -> child_id path that skips the direct edge."""
    direct_children = parent_to_children.get(code_id, [])
    queue: deque[list[str]] = deque(
        [code_id, other_child_id]
        for other_child_id in direct_children
        if other_child_id != child_id
    )
    seen = {code_id, child_id}

    while queue:
        path = queue.popleft()
        current_id = path[-1]

        if current_id == child_id:
            return path

        if current_id in seen:
            continue
        seen.add(current_id)

        for next_id in parent_to_children.get(current_id, []):
            if next_id in seen and next_id != child_id:
                continue
            queue.append(path + [next_id])

    return None


def find_redundant_direct_children(
    code_id: str,
    parent_to_children: dict[str, list[str]],
) -> dict[str, list[str]]:
    redundant_paths: dict[str, list[str]] = {}

    for child_id in parent_to_children.get(code_id, []):
        path = find_alternate_child_path(code_id, child_id, parent_to_children)
        if path is not None:
            redundant_paths[child_id] = path

    return redundant_paths


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    default_codes_dir = str(script_dir.parent.parent / "codes")

    parser = argparse.ArgumentParser(
        description=(
            "Check whether direct children are also descendants through "
            "another parent-child chain."
        ),
    )
    parser.add_argument(
        "code_id",
        nargs="?",
        help=(
            "Code identifier whose direct children to check. If omitted, "
            "check all code IDs."
        ),
    )
    parser.add_argument(
        "--codes-dir",
        default=default_codes_dir,
        help="Directory containing EC Zoo YAML code files.",
    )
    return parser.parse_args()


def report_redundant_paths(code_id: str, redundant_paths: dict[str, list[str]]) -> None:
    print(f"\n{code_id}")
    for child_id, path in sorted(redundant_paths.items()):
        print(f"  {child_id}: " + " -> ".join(path))


def main() -> int:
    args = parse_args()
    parent_to_children, known_code_ids = build_parent_to_children_map(args.codes_dir)

    if args.code_id and args.code_id not in known_code_ids:
        print(f"Unknown code_id: {args.code_id}", file=sys.stderr)
        return 1

    if args.code_id:
        redundant_paths = find_redundant_direct_children(
            args.code_id,
            parent_to_children,
        )

        if not redundant_paths:
            print(f"No redundant direct children found for {args.code_id}.")
            return 0

        report_redundant_paths(args.code_id, redundant_paths)
        print(f"\nTotal redundant direct children: {len(redundant_paths)}")
        return 0

    found_any = False
    total_redundant_children = 0
    total_parent_codes = 0

    for code_id in sorted(known_code_ids):
        redundant_paths = find_redundant_direct_children(
            code_id,
            parent_to_children,
        )
        if not redundant_paths:
            continue

        found_any = True
        total_parent_codes += 1
        total_redundant_children += len(redundant_paths)
        report_redundant_paths(code_id, redundant_paths)

    if not found_any:
        print("No redundant direct children found.")
        return 0

    print(
        f"\nTotal redundant direct children: {total_redundant_children} "
        f"across {total_parent_codes} code IDs"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
