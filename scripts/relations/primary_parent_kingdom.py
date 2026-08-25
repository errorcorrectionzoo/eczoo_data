#!/usr/bin/env python3

"""Check that every code's primary-parent chain stays inside its home kingdom.

The zoo's displayed hierarchy places each code under its PRIMARY parent (the
first entry in relations.parents).  A code whose primary parent belongs to a
different kingdom is therefore displayed outside its own kingdom, even though
the same parent would be perfectly fine as a secondary parent.  Example: a
purely-qubit code whose only or first parent is a Galois-qudit entry (e.g.
generalized_bicycle or lifted_product) silently leaves the qubit kingdom; the
fix is to promote an in-kingdom parent to the first slot and demote the
cross-kingdom one to secondary.

Note that outside_folder_descendants.py does NOT catch this: its condition 3
excuses any code whose home-kingdom root already descends from the foreign
root (qubit codes are Galois-qudit codes with q=2, so a qubit code hanging
off the Galois kingdom is excused there).  This script tests the placement
invariant directly.

HOMING IS BY KINGDOM, NOT BY ROOT CODE.  Several kingdoms have more than one
root code sharing a single folder -- codes/quantum/qudits holds both
qudits_into_qudits and subsystem_qudits_into_qudits, codes/quantum/qudits_galois
holds three Galois roots, and so on -- so a code's folder cannot identify a
unique root.  It does identify a unique kingdom, which is what this check is
about.  The subspace/subsystem distinction within a kingdom is a separate
invariant, enforced by subspace_subsystem_split.py.

For each code that lives inside some kingdom's folder, follow first-parent
edges.  A step to a parent whose home kingdom differs from the code's is a
violation, reported at the first such step.  Reaching a kingdom root of the
code's own kingdom, or a property code outside every kingdom folder, ends the
chain successfully.

Exits non-zero if violations are found.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


def load_kingdom_folders(
    kingdoms_file: Path, code_paths: dict[str, Path]
) -> tuple[dict[Path, str], set[str]]:
    """Return (folder -> kingdom_id, set of root code_ids).

    A folder maps to a kingdom only if every root sitting in it belongs to the
    same kingdom; otherwise the folder is ambiguous and is reported.
    """
    data = yaml.safe_load(kingdoms_file.read_text())
    folder_kingdoms: dict[Path, set[str]] = {}
    roots: set[str] = set()
    for _domain, kingdoms in data["kingdoms_by_domain_id"].items():
        for k in kingdoms:
            for r in k.get("root_codes", []):
                rc = r["code_id"]
                roots.add(rc)
                if rc in code_paths:
                    folder_kingdoms.setdefault(
                        code_paths[rc].parent, set()
                    ).add(k["kingdom_id"])

    folder_to_kingdom: dict[Path, str] = {}
    for folder, kids in sorted(folder_kingdoms.items()):
        if len(kids) > 1:
            print(
                f"WARNING: folder {folder} hosts roots of several kingdoms "
                f"({', '.join(sorted(kids))}); homing there is ambiguous",
                file=sys.stderr,
            )
        folder_to_kingdom[folder] = sorted(kids)[0]
    return folder_to_kingdom, roots


def load_codes(codes_dir: Path) -> dict[str, dict]:
    code_data: dict[str, dict] = {}
    for path in codes_dir.rglob("*.yml"):
        try:
            data = yaml.safe_load(path.read_text())
        except yaml.YAMLError:
            continue
        if not isinstance(data, dict) or "code_id" not in data:
            continue
        parents = [
            p["code_id"]
            for p in (data.get("relations") or {}).get("parents") or []
            if isinstance(p, dict) and "code_id" in p
        ]
        code_data[data["code_id"]] = {"path": path, "parents": parents}
    return code_data


def build_home_map(
    code_data: dict[str, dict], folder_to_kingdom: dict[Path, str]
) -> dict[str, str | None]:
    """Map each code to the kingdom of the deepest kingdom folder containing it."""
    home: dict[str, str | None] = {}
    for cid, info in code_data.items():
        folder = info["path"].parent
        best: str | None = None
        best_len = -1
        for kf, kingdom in sorted(folder_to_kingdom.items()):
            try:
                folder.relative_to(kf)
            except ValueError:
                continue
            if len(str(kf)) > best_len:
                best, best_len = kingdom, len(str(kf))
        home[cid] = best
    return home


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent.parent

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codes-dir", default=str(repo_root / "codes"))
    parser.add_argument(
        "--kingdoms-file", default=str(repo_root / "codetree" / "kingdoms.yml")
    )
    args = parser.parse_args()

    codes_dir = Path(args.codes_dir)
    kingdoms_file = Path(args.kingdoms_file)
    if not codes_dir.is_dir():
        print(f"Error: codes directory not found: {codes_dir}", file=sys.stderr)
        return 1
    if not kingdoms_file.is_file():
        print(f"Error: kingdoms file not found: {kingdoms_file}", file=sys.stderr)
        return 1

    code_data = load_codes(codes_dir)
    code_paths = {cid: info["path"] for cid, info in code_data.items()}
    folder_to_kingdom, roots = load_kingdom_folders(kingdoms_file, code_paths)
    home = build_home_map(code_data, folder_to_kingdom)

    violations: list[tuple[str, str, str, list[str]]] = []
    for cid in sorted(code_data):
        h = home.get(cid)
        if h is None or cid in roots:
            continue
        chain = [cid]
        seen = {cid}
        while True:
            parents = code_data.get(chain[-1], {}).get("parents", [])
            if not parents:
                break
            nxt = parents[0]
            chain.append(nxt)
            if nxt not in code_data or nxt in seen:
                break
            seen.add(nxt)
            hn = home.get(nxt)
            # Check the kingdom BEFORE deciding whether to stop: a foreign
            # kingdom root as primary parent is the most direct violation
            # there is, and must not be excused for being a root.
            if hn is not None and hn != h:
                violations.append((cid, nxt, hn, chain[:]))
                break
            if nxt in roots or hn is None:
                break  # reached own kingdom root, or a property code
    if not violations:
        print("No cross-kingdom primary-parent chains found.")
        return 0

    print(f"Found {len(violations)} cross-kingdom primary-parent chain(s):")
    for cid, offender, offender_kingdom, chain in violations:
        print(
            f"\n  {cid} (kingdom {home[cid]}) leaves it at "
            f"'{offender}' (kingdom {offender_kingdom})"
        )
        print(f"    {code_data[cid]['path']}")
        print(f"    {' -> '.join(chain)}")
        print(
            f"    fix: promote an in-kingdom parent of '{chain[-2]}' to first, "
            f"demoting '{offender}' to secondary"
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
