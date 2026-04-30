#!/usr/bin/env python3
"""Check for duplicate or conflicting relations between codes.

Two kinds of problems are detected:

1. **Duplicate cousin relations** – Code A lists code B as a cousin *and*
   code B also lists code A as a cousin.  Only one side needs the entry.

2. **Duplicate parent/cousin relations** – Code A lists code B as a parent
   *and* code B (or code A) also lists the other as a cousin.  A pair of
   codes should be related by at most one relation type.

The script scans all .yml/.yaml files under the repository root and exits
with a non-zero status if any violations are found.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

import yaml


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class CodeEntry:
    code_id: str
    path: str
    parents: list[str] = field(default_factory=list)
    cousins: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# File discovery & parsing
# ---------------------------------------------------------------------------

def iter_yaml_files(root: str) -> Iterable[str]:
    for dirpath, dirnames, filenames in os.walk(root):
        if ".git" in dirnames:
            dirnames.remove(".git")
        for filename in filenames:
            if filename.endswith((".yml", ".yaml")):
                yield os.path.join(dirpath, filename)


def load_code_entry(path: str) -> CodeEntry | None:
    """Parse a single YAML file and return a CodeEntry, or None if not a code file."""
    with open(path, encoding="utf-8") as fh:
        try:
            data = yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            print(f"WARNING: could not parse {path}: {exc}", file=sys.stderr)
            return None

    if not isinstance(data, dict):
        return None

    code_id = data.get("code_id")
    if not code_id:
        return None

    relations = data.get("relations") or {}
    parents: list[str] = []
    cousins: list[str] = []

    for entry in relations.get("parents") or []:
        if isinstance(entry, dict) and entry.get("code_id"):
            parents.append(entry["code_id"])

    for entry in relations.get("cousins") or []:
        if isinstance(entry, dict) and entry.get("code_id"):
            cousins.append(entry["code_id"])

    return CodeEntry(code_id=code_id, path=path, parents=parents, cousins=cousins)


# ---------------------------------------------------------------------------
# Violation types
# ---------------------------------------------------------------------------

@dataclass
class Violation:
    kind: str          # "duplicate_cousin" | "parent_and_cousin"
    code_a: str
    path_a: str
    code_b: str
    path_b: str
    description: str


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_relations(entries: list[CodeEntry]) -> list[Violation]:
    # Build lookup: code_id -> entry
    by_id: dict[str, CodeEntry] = {}
    for entry in entries:
        if entry.code_id in by_id:
            # Duplicate code_id – not our job to report here, just keep first
            pass
        else:
            by_id[entry.code_id] = entry

    violations: list[Violation] = []

    # Canonical pair key: frozenset of two ids
    seen_cousin_pairs: set[frozenset] = set()
    seen_parent_pairs: set[frozenset] = set()  # directed: (child, parent)

    # Collect all cousin pairs and parent pairs
    cousin_pairs: dict[frozenset, list[tuple[str, str]]] = defaultdict(list)
    # (child_id, parent_id) -> path of child
    parent_pairs: dict[tuple[str, str], str] = {}

    for entry in entries:
        for parent_id in entry.parents:
            parent_pairs[(entry.code_id, parent_id)] = entry.path

        for cousin_id in entry.cousins:
            key = frozenset([entry.code_id, cousin_id])
            cousin_pairs[key].append((entry.code_id, entry.path))

    # 1. Duplicate cousin relations: both A->B and B->A listed as cousins
    for pair_key, occurrences in cousin_pairs.items():
        if len(occurrences) >= 2:
            ids = list(pair_key)
            code_a, code_b = ids[0], ids[1]
            path_a = by_id[code_a].path if code_a in by_id else occurrences[0][1]
            path_b = by_id[code_b].path if code_b in by_id else occurrences[1][1]
            violations.append(Violation(
                kind="duplicate_cousin",
                code_a=code_a,
                path_a=path_a,
                code_b=code_b,
                path_b=path_b,
                description=(
                    f"Both '{code_a}' and '{code_b}' list each other as cousins. "
                    "Keep the relation in only one file."
                ),
            ))

    # 2. Parent-and-cousin conflict: A is parent of B but also listed as cousin
    #    Covers both directions:
    #      - (child, parent) in parent_pairs AND pair is also in cousin_pairs
    cousin_pair_set = set(cousin_pairs.keys())

    for (child_id, parent_id), child_path in parent_pairs.items():
        pair_key = frozenset([child_id, parent_id])
        if pair_key in cousin_pair_set:
            path_a = child_path
            path_b = by_id[parent_id].path if parent_id in by_id else "?"
            violations.append(Violation(
                kind="parent_and_cousin",
                code_a=child_id,
                path_a=path_a,
                code_b=parent_id,
                path_b=path_b,
                description=(
                    f"'{parent_id}' is listed as a parent of '{child_id}', "
                    f"but the two codes are also related by a cousin relation. "
                    "Use only one relation type between a pair of codes."
                ),
            ))

    return violations


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def report(violations: list[Violation], *, verbose: bool = False) -> None:
    if not violations:
        print("No duplicate relation violations found.")
        return

    dup_cousin = [v for v in violations if v.kind == "duplicate_cousin"]
    parent_cousin = [v for v in violations if v.kind == "parent_and_cousin"]

    if dup_cousin:
        print(f"\n=== Duplicate cousin relations ({len(dup_cousin)}) ===")
        for v in dup_cousin:
            print(f"\n  {v.description}")
            if verbose:
                print(f"    {v.code_a}: {v.path_a}")
                print(f"    {v.code_b}: {v.path_b}")

    if parent_cousin:
        print(f"\n=== Parent–cousin conflicts ({len(parent_cousin)}) ===")
        for v in parent_cousin:
            print(f"\n  {v.description}")
            if verbose:
                print(f"    {v.code_a}: {v.path_a}")
                print(f"    {v.code_b}: {v.path_b}")

    print(f"\nTotal violations: {len(violations)}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=os.path.join(os.path.dirname(__file__), "..", ".."),
        help="Repository root (default: two levels above this script)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Also print file paths for each violation",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = os.path.realpath(args.root)
    codes_dir = os.path.join(root, "codes")

    if not os.path.isdir(codes_dir):
        print(f"ERROR: codes directory not found at {codes_dir}", file=sys.stderr)
        return 2

    entries: list[CodeEntry] = []
    for path in iter_yaml_files(codes_dir):
        entry = load_code_entry(path)
        if entry is not None:
            entries.append(entry)

    print(f"Loaded {len(entries)} code entries from {codes_dir}")

    violations = check_relations(entries)
    report(violations, verbose=args.verbose)

    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
