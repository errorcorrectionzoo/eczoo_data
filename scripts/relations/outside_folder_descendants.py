#!/usr/bin/env python3

"""List codes outside a kingdom root code's folder that are direct descendants of it.

A code C is a "direct descendant" of root R if:
  1. C lives outside R's folder tree.
  2. There exists an upward parent path from C to R that passes through no
     other root code.
  3. C's home root (the root code whose folder contains C's file) does NOT
     already have R as a root ancestor.  Condition 3 ensures that codes which
     are indirect descendants of R via their own kingdom's root code are not
     flagged — e.g. qubit codes are indirect descendants of galois_into_galois
     via qubits_into_qubits, so they are not reported for galois_into_galois.

The script reads kingdoms and root codes from codetree/kingdoms.yml, infers
each root code's folder from where its YAML file lives, then reports every
code that satisfies all three conditions above.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import deque
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------

def load_kingdoms(kingdoms_file: Path) -> dict[str, list[str]]:
    """Return mapping kingdom_id -> list of root code_ids."""
    data = yaml.safe_load(kingdoms_file.read_text())
    result: dict[str, list[str]] = {}
    for _domain, kingdoms in data["kingdoms_by_domain_id"].items():
        for k in kingdoms:
            result[k["kingdom_id"]] = [r["code_id"] for r in k.get("root_codes", [])]
    return result


def load_codes(codes_dir: Path) -> dict[str, dict]:
    """Return mapping code_id -> {path: Path, parents: list[str]}."""
    code_data: dict[str, dict] = {}
    for path in codes_dir.rglob("*.yml"):
        try:
            data = yaml.safe_load(path.read_text())
        except yaml.YAMLError:
            continue
        if not isinstance(data, dict) or "code_id" not in data:
            continue
        cid = data["code_id"]
        parents = [
            p["code_id"]
            for p in (data.get("relations") or {}).get("parents") or []
            if isinstance(p, dict) and "code_id" in p
        ]
        code_data[cid] = {"path": path, "parents": parents}
    return code_data


# ---------------------------------------------------------------------------
# Ancestry
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Ancestry
# ---------------------------------------------------------------------------

def build_home_root_map(
    code_data: dict[str, dict], root_folders: dict[str, Path]
) -> dict[str, str | None]:
    """Return mapping code_id -> home_root_id (or None if not in any root folder)."""
    home: dict[str, str | None] = {}
    for cid, info in code_data.items():
        folder = info["path"].parent
        home[cid] = None
        for rc, rc_folder in root_folders.items():
            try:
                folder.relative_to(rc_folder)
                home[cid] = rc
                break
            except ValueError:
                pass
    return home


def build_root_ancestor_sets(
    root_set: set[str], code_data: dict[str, dict]
) -> dict[str, set[str]]:
    """For each root code, return the set of root codes that are its ancestors
    (reachable by following parent edges through root codes only)."""
    ancestors: dict[str, set[str]] = {}
    for rc in root_set:
        visited: set[str] = set()
        queue: deque[str] = deque([rc])
        while queue:
            node = queue.popleft()
            if node in visited:
                continue
            visited.add(node)
            for p in code_data.get(node, {}).get("parents", []):
                if p in root_set:
                    queue.append(p)
        visited.discard(rc)
        ancestors[rc] = visited
    return ancestors


def find_direct_path(
    code_id: str,
    target_root: str,
    root_set: set[str],
    code_data: dict[str, dict],
) -> list[str] | None:
    """Return a shortest path [code_id, ..., target_root] that passes through
    no other root code, or None if no such path exists."""
    queue: deque[list[str]] = deque([[code_id]])
    visited: set[str] = {code_id}
    while queue:
        path = queue.popleft()
        node = path[-1]
        for parent in code_data.get(node, {}).get("parents", []):
            if parent == target_root:
                return path + [parent]
            if parent in visited:
                continue
            if parent in root_set:
                continue  # do not cross other root codes
            visited.add(parent)
            queue.append(path + [parent])
    return None


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def find_outside_direct_descendants(
    kingdoms: dict[str, list[str]],
    code_data: dict[str, dict],
) -> dict[str, list[tuple[str, list[str]]]]:
    """For each root code, return codes outside its folder that are direct
    descendants.

    Returns mapping  root_code_id -> [(child_code_id, graph_path), ...]
    sorted alphabetically, where graph_path is [child_code_id, ..., root_code_id].
    """
    root_set: set[str] = {rc for roots in kingdoms.values() for rc in roots}

    # Map each root code to its folder.
    root_folders: dict[str, Path] = {}
    for rc in root_set:
        if rc in code_data:
            root_folders[rc] = code_data[rc]["path"].parent
        else:
            print(f"WARNING: root code '{rc}' not found in code files", file=sys.stderr)

    # For each code, which root's folder does it live in?
    home_root = build_home_root_map(code_data, root_folders)

    # For each root R, which root codes are its ancestors (in root-only graph)?
    root_ancestors = build_root_ancestor_sets(root_set, code_data)

    results: dict[str, list[tuple[str, list[str]]]] = {}
    for rc, folder in sorted(root_folders.items()):
        # Root codes H whose home kingdom is already a descendant of rc:
        # skip codes whose home root H has rc as a root ancestor.
        outside: list[tuple[str, list[str]]] = []
        for cid, info in code_data.items():
            if cid == rc:
                continue
            # Must be outside the root's folder tree.
            try:
                info["path"].parent.relative_to(folder)
                continue  # inside folder — skip
            except ValueError:
                pass
            # If C's home root already descends from rc (via root-to-root edges),
            # then C is an indirect descendant of rc through its own kingdom root
            # and should not be flagged.
            hr = home_root.get(cid)
            if hr is not None and rc in root_ancestors.get(hr, set()):
                continue
            path = find_direct_path(cid, rc, root_set, code_data)
            if path is not None:
                outside.append((cid, path))
        if outside:
            results[rc] = sorted(outside, key=lambda t: t[0])
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent.parent

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--codes-dir",
        default=str(repo_root / "codes"),
        help="Directory containing EC Zoo YAML code files (default: ../codes relative to script).",
    )
    parser.add_argument(
        "--kingdoms-file",
        default=str(repo_root / "codetree" / "kingdoms.yml"),
        help="Path to kingdoms.yml (default: ../codetree/kingdoms.yml relative to script).",
    )
    parser.add_argument(
        "--root",
        metavar="CODE_ID",
        help="Restrict output to a single root code.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        default=False,
        help=(
            "Include outside descendants that are themselves root codes. "
            "By default these are omitted because root-to-root edges are "
            "expected structural connections, not misplacements."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    codes_dir = Path(args.codes_dir)
    kingdoms_file = Path(args.kingdoms_file)

    if not codes_dir.is_dir():
        print(f"Error: codes directory not found: {codes_dir}", file=sys.stderr)
        return 1
    if not kingdoms_file.is_file():
        print(f"Error: kingdoms file not found: {kingdoms_file}", file=sys.stderr)
        return 1

    kingdoms = load_kingdoms(kingdoms_file)
    code_data = load_codes(codes_dir)
    results = find_outside_direct_descendants(kingdoms, code_data)

    root_set: set[str] = {rc for roots in kingdoms.values() for rc in roots}

    if args.root:
        if args.root not in results:
            print(f"No outside direct descendants found for root code '{args.root}'.")
            return 0
        results = {args.root: results[args.root]}

    # By default strip entries that are themselves root codes (structural edges).
    if not args.all:
        filtered: dict[str, list[tuple[str, list[str]]]] = {}
        for rc, items in results.items():
            non_root = [(cid, p) for cid, p in items if cid not in root_set]
            if non_root:
                filtered[rc] = non_root
        results = filtered

    if not results:
        print("No outside direct descendants found.")
        return 0

    for rc, items in sorted(results.items()):
        print(f"\n[{rc}]")
        for cid, graph_path in items:
            print(f"  {' -> '.join(graph_path)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
