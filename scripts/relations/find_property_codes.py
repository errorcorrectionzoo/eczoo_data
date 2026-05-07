#!/usr/bin/env python3
"""
Identify "property codes" for each domain (classical, quantum, c-q).

A property code is one that is NOT a descendant of (and is not itself) any
kingdom root code listed in codetree/kingdoms.yml.  Kingdom membership is
determined by BFS from each root code following the child→parent edges in
reverse (i.e., traversing "downward" from roots to leaves).
"""

from __future__ import annotations

import sys
from collections import defaultdict, deque
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
KINGDOMS_FILE = REPO_ROOT / "codetree" / "kingdoms.yml"
CODES_DIR = REPO_ROOT / "codes"

DOMAIN_DIRS = {
    "classical": CODES_DIR / "classical",
    "quantum": CODES_DIR / "quantum",
    "classical_into_quantum": CODES_DIR / "classical_into_quantum",
}

# ---------------------------------------------------------------------------
# 1. Load all code YAML files
# ---------------------------------------------------------------------------

def load_codes():
    """Return (code_id -> file_path, parent_map, children_map)."""
    code_files: dict[str, Path] = {}
    parent_map: dict[str, list[str]] = defaultdict(list)   # code -> its parents
    children_map: dict[str, list[str]] = defaultdict(list) # code -> its children

    for yml_path in sorted(CODES_DIR.rglob("*.yml")):
        try:
            with yml_path.open() as fh:
                data = yaml.safe_load(fh)
        except Exception as exc:
            print(f"  [WARN] Could not parse {yml_path}: {exc}", file=sys.stderr)
            continue

        if not isinstance(data, dict) or "code_id" not in data:
            continue

        cid = data["code_id"]
        code_files[cid] = yml_path

        relations = data.get("relations") or {}
        for parent_entry in (relations.get("parents") or []):
            if isinstance(parent_entry, dict):
                pid = parent_entry.get("code_id")
            else:
                pid = str(parent_entry)
            if pid:
                parent_map[cid].append(pid)
                children_map[pid].append(cid)

    return code_files, parent_map, children_map


# ---------------------------------------------------------------------------
# 2. Load kingdom root codes per domain
# ---------------------------------------------------------------------------

def load_kingdoms():
    """Return dict: domain_id -> list of root code_ids."""
    with KINGDOMS_FILE.open() as fh:
        data = yaml.safe_load(fh)

    kingdoms_by_domain: dict[str, list[str]] = {}
    for domain_id, kingdoms in (data.get("kingdoms_by_domain_id") or {}).items():
        roots: list[str] = []
        for kingdom in (kingdoms or []):
            for rc in (kingdom.get("root_codes") or []):
                if isinstance(rc, dict):
                    roots.append(rc["code_id"])
                else:
                    roots.append(str(rc))
        kingdoms_by_domain[domain_id] = roots
    return kingdoms_by_domain


# ---------------------------------------------------------------------------
# 3. BFS to find all descendants of a set of root codes
# ---------------------------------------------------------------------------

def descendants(roots: list[str], children_map: dict[str, list[str]]) -> set[str]:
    """Return all codes reachable from roots by following child edges (downward)."""
    visited: set[str] = set(roots)
    queue = deque(roots)
    while queue:
        current = queue.popleft()
        for child in children_map.get(current, []):
            if child not in visited:
                visited.add(child)
                queue.append(child)
    return visited


# ---------------------------------------------------------------------------
# 4. Infer file-based domain for a code
# ---------------------------------------------------------------------------

def file_domain(code_id: str, code_files: dict[str, Path]) -> str:
    path = code_files.get(code_id)
    if path is None:
        return "unknown"
    for domain, ddir in DOMAIN_DIRS.items():
        try:
            path.relative_to(ddir)
            return domain
        except ValueError:
            pass
    return "other"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Loading code files …")
    code_files, parent_map, children_map = load_codes()
    print(f"  {len(code_files)} codes loaded.\n")

    print("Loading kingdoms …")
    kingdoms_by_domain = load_kingdoms()
    for domain, roots in kingdoms_by_domain.items():
        print(f"  {domain}: {len(roots)} root code(s): {roots}")
    print()

    # Collect all kingdom members (roots + all descendants) across every domain
    all_kingdom_members: set[str] = set()
    domain_kingdom_members: dict[str, set[str]] = {}
    for domain, roots in kingdoms_by_domain.items():
        members = descendants(roots, children_map)
        domain_kingdom_members[domain] = members
        all_kingdom_members |= members

    # Property codes: codes not in any kingdom tree
    property_codes = [c for c in code_files if c not in all_kingdom_members]

    # Count descendants for each property code (excluding itself)
    desc_count: dict[str, int] = {
        cid: len(descendants([cid], children_map)) - 1
        for cid in property_codes
    }

    print(f"Total codes:           {len(code_files)}")
    print(f"Total kingdom members: {len(all_kingdom_members)}")
    print(f"Total property codes:  {len(property_codes)}\n")

    by_file_domain: dict[str, list[str]] = defaultdict(list)
    for cid in property_codes:
        by_file_domain[file_domain(cid, code_files)].append(cid)

    domain_order = ["classical", "quantum", "classical_into_quantum", "other", "unknown"]
    for domain in domain_order:
        codes = by_file_domain.get(domain, [])
        if not codes:
            continue
        codes_sorted = sorted(codes, key=lambda c: desc_count[c], reverse=True)
        print(f"=== Property codes in '{domain}' domain ({len(codes)}) ===")
        for cid in codes_sorted:
            print(f"  {desc_count[cid]:<6}  {cid}")
        print()

    # Sanity: warn about root codes in kingdoms.yml that have no YAML file
    all_roots = {r for roots in kingdoms_by_domain.values() for r in roots}
    missing = all_roots - code_files.keys()
    if missing:
        print(f"[WARN] Kingdom root codes with no YAML file: {missing}")


if __name__ == "__main__":
    main()
