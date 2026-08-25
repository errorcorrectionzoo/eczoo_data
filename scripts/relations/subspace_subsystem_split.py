#!/usr/bin/env python3

"""Check that the subspace and subsystem hierarchies are never mixed.

The zoo keeps the subspace and subsystem branches separate all the way up to
their respective kingdom root codes:

    qubits_into_qubits          vs  subsystem_qubits_into_qubits
    qudits_into_qudits          vs  subsystem_qudits_into_qudits
    galois_into_galois          vs  subsystem_galois_into_galois
    group_quantum               vs  subsystem_group_quantum

The two branches meet only ABOVE those roots, at the operator-algebra root
(oa_qubits_into_qubits / oaecc), which is the common generalization.  A
subsystem entry therefore must never take a subspace entry as a parent --
primary or secondary -- even when the two families are obvious counterparts,
and equally a subspace entry must never take a subsystem entry as a parent.

For example, a Majorana subsystem stabilizer code is NOT a child of the
`fermions` (Fermion code) family nor of `majorana_stab`, however natural that
reads: both are subspace entries.  The correct encoding is a cousin relation,
with the "a subsystem code with no gauge qubits is a subspace code" statement
carried in the cousin `detail`.

THE TEST IS PER CODE, over the sides of its own parents.  Each parent is
classified as sitting on the subspace side, the subsystem side, or neither
(a parent reaching both, or neither, is uninformative).  A code is reported
when its parents disagree, or when the code is itself one of the roots above
and takes a parent from the opposite side.

The diagnostic deliberately lists the parents on each side rather than naming
one to demote.  When a code has parents on both branches there is no purely
graph-theoretic way to tell which is the mistake, and guessing risks advising
the removal of the CORRECT parent.  Only the maintainer knows which side the
entry belongs to.

Reporting per code also keeps the output quiet: a descendant that merely
inherits a mixed ancestry has all of its own parents reaching both roots, so
it is classified as uninformative and is not reported.  Only the code where
the two branches actually meet is named.

Exits non-zero if violations are found.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


# (subspace root, subsystem root) pairs that must never both be reachable.
PAIRS = [
    ("qubits_into_qubits", "subsystem_qubits_into_qubits"),
    ("qudits_into_qudits", "subsystem_qudits_into_qudits"),
    ("galois_into_galois", "subsystem_galois_into_galois"),
    ("group_quantum", "subsystem_group_quantum"),
]


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


def reach_from(
    start: str, code_data: dict[str, dict], skip_edge: tuple[str, str] | None = None
) -> set[str]:
    """Codes reachable from `start` by parent edges, including `start` itself.

    `skip_edge` omits one (child, parent) edge, so a node's branch can be
    decided independently of the edge under test.
    """
    seen = {start}
    stack = [start]
    while stack:
        node = stack.pop()
        for parent in code_data.get(node, {}).get("parents", []):
            if skip_edge is not None and (node, parent) == skip_edge:
                continue
            if parent not in seen:
                seen.add(parent)
                stack.append(parent)
    return seen


def side(reach: set[str], subspace_root: str, subsystem_root: str) -> str | None:
    """Which branch a reach-set sits on: 'subspace', 'subsystem', or None."""
    has_space = subspace_root in reach
    has_system = subsystem_root in reach
    if has_space and not has_system:
        return "subspace"
    if has_system and not has_space:
        return "subsystem"
    return None


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent.parent

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codes-dir", default=str(repo_root / "codes"))
    args = parser.parse_args()

    codes_dir = Path(args.codes_dir)
    if not codes_dir.is_dir():
        print(f"Error: codes directory not found: {codes_dir}", file=sys.stderr)
        return 1

    code_data = load_codes(codes_dir)
    parent_reach = {cid: reach_from(cid, code_data) for cid in code_data}

    # For each code, classify each parent as subspace-side / subsystem-side.
    violations: list[tuple[str, list[str], list[str], set[str]]] = []
    root_side = {}
    for subspace_root, subsystem_root in PAIRS:
        root_side[subspace_root] = ("subspace", subspace_root, subsystem_root)
        root_side[subsystem_root] = ("subsystem", subspace_root, subsystem_root)

    for cid in sorted(code_data):
        space_parents: set[str] = set()
        system_parents: set[str] = set()
        mixed_pairs: set[str] = set()
        for parent in code_data[cid]["parents"]:
            if parent not in code_data:
                continue
            for subspace_root, subsystem_root in PAIRS:
                s_side = side(parent_reach[parent], subspace_root, subsystem_root)
                if s_side == "subspace":
                    space_parents.add(parent)
                    mixed_pairs.add(f"{subsystem_root} with {subspace_root}")
                elif s_side == "subsystem":
                    system_parents.add(parent)
                    mixed_pairs.add(f"{subsystem_root} with {subspace_root}")

        own = root_side.get(cid)
        if own is not None:
            own_side = own[0]
            offenders = space_parents if own_side == "subsystem" else system_parents
            if offenders:
                violations.append(
                    (cid, sorted(space_parents), sorted(system_parents), mixed_pairs)
                )
            continue

        if space_parents and system_parents:
            violations.append(
                (cid, sorted(space_parents), sorted(system_parents), mixed_pairs)
            )

    if not violations:
        print("No subspace/subsystem hierarchy mixing found.")
        return 0

    print(f"Found {len(violations)} code(s) mixing the two hierarchies:")
    for cid, space_parents, system_parents, mixed_pairs in violations:
        print(f"\n  {cid} mixes {', '.join(sorted(mixed_pairs))}")
        print(f"    {code_data[cid]['path']}")
        print(f"    subspace-side parent(s):  {', '.join(space_parents) or '(none)'}")
        print(f"    subsystem-side parent(s): {', '.join(system_parents) or '(none)'}")
        print("    fix: keep the parents on the entry's own side and demote the")
        print("         others to cousins; the two branches must never mix.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
