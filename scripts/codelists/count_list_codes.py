#!/usr/bin/env python3

# Count the number of codes in each codelist under codelists/descendants/ and
# codelists/features/ (or any directory passed via --lists-dir).
#
# Each select entry is a condition group. Within a group all conditions are
# ANDed; between groups they are ORed.  Supported per-group keys:
#
#   descendant_of: X     – candidates = descendants of X (not X itself)
#   cousin_of: X         – candidates = cousin-neighbours of X (both directions)
#   property_set: a.b    – candidates = codes whose YAML has the dotted key set
#   domain: D            – candidates = codes whose file lives in domain D
#                          (classical_domain | quantum_domain |
#                           classical_into_quantum_domain)
#   not_descendant_of: X – remove X and its descendants from this group's result
#
# A group with only not_descendant_of and no positive selector becomes a global
# exclusion applied to the union of all other groups.

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _domain_from_path(file_path: str, codes_dir: str) -> str:
    rel = os.path.relpath(file_path, codes_dir).replace("\\", "/")
    top = rel.split("/")[0]
    if top == "classical":
        return "classical_domain"
    if top == "quantum":
        return "quantum_domain"
    if top == "classical_into_quantum":
        return "classical_into_quantum_domain"
    return "other"


# ---------------------------------------------------------------------------
# Parse code YAML files
# ---------------------------------------------------------------------------

# Top-level keys whose content should NOT be treated as property paths.
_SKIP_L0 = frozenset({
    "code_id", "name", "introduced", "alternative_codes",
    "relations", "_meta", "template_code",
})

# Keys directly under features: that we recognise as property paths.
_FEATURES_SUBKEYS = frozenset({
    "rate", "decoders", "encoders", "fault_tolerance", "transversal_gates",
    "threshold", "code_capacity_threshold", "magic_scaling_exponent",
    "magic_states", "single_shot_threshold", "other_thresholds",
})


def _parse_code_file(
    file_path: str, codes_dir: str
) -> tuple[str | None, list[str], list[str], frozenset[str], str]:
    """Return (code_id, parent_ids, cousin_ids, prop_paths, domain)."""
    code_id: str | None = None
    parents: list[str] = []
    cousins: list[str] = []
    props: set[str] = set()

    # relation-parsing state
    in_relations = in_parents = in_cousins = False

    # property-parsing state
    l0_key: str | None = None          # current indent-0 section key
    l1_key: str | None = None          # current indent-2 sub-key (under l0)
    l0_is_prop = False                 # whether l0 contributes to prop paths

    with open(file_path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.split("#", 1)[0].rstrip("\n")
            if not line.strip():
                continue

            stripped = line.lstrip(" ")
            indent = len(line) - len(stripped)

            # ----------------------------------------------------------------
            # indent 0 → top-level keys
            # ----------------------------------------------------------------
            if indent == 0:
                in_relations = in_parents = in_cousins = False
                l1_key = None

                if stripped.startswith("code_id:"):
                    code_id = _strip_quotes(stripped.split(":", 1)[1])
                    l0_key = None
                    l0_is_prop = False
                elif stripped.startswith("relations:"):
                    in_relations = True
                    l0_key = None
                    l0_is_prop = False
                elif ":" in stripped:
                    raw_key = stripped.split(":", 1)[0].strip()
                    rest = stripped.split(":", 1)[1].strip()
                    if raw_key in _SKIP_L0:
                        l0_key = None
                        l0_is_prop = False
                    else:
                        l0_key = raw_key
                        l0_is_prop = True
                        # inline value at l0
                        if rest and rest not in ("|", "|-", ">", ">-"):
                            props.add(l0_key)
                continue

            # ----------------------------------------------------------------
            # Relations parsing (existing logic)
            # ----------------------------------------------------------------
            if in_relations:
                if indent == 2:
                    in_parents = stripped.startswith("parents:")
                    in_cousins = stripped.startswith("cousins:")
                elif indent >= 4 and stripped.startswith("- code_id:"):
                    cid = _strip_quotes(stripped.split(":", 1)[1])
                    if cid:
                        if in_parents:
                            parents.append(cid)
                        elif in_cousins:
                            cousins.append(cid)
                continue

            # ----------------------------------------------------------------
            # Property-path detection (indent 2 and 4+)
            # ----------------------------------------------------------------
            if not l0_is_prop or l0_key is None:
                continue

            if indent == 2:
                l1_key = None
                if stripped.startswith("- "):
                    # List item directly under l0 → l0 is non-empty
                    props.add(l0_key)
                elif ":" in stripped:
                    sub_key = stripped.split(":", 1)[0].strip()
                    rest = stripped.split(":", 1)[1].strip()
                    l1_key = sub_key
                    if rest and rest not in ("|", "|-", ">", ">-"):
                        # inline value → l0.sub_key is set
                        props.add(f"{l0_key}.{sub_key}")
                        props.add(l0_key)

            elif indent >= 4:
                if l1_key and stripped:
                    # Any content under l1 → l0.l1 is set
                    props.add(f"{l0_key}.{l1_key}")
                    props.add(l0_key)
                elif stripped.startswith("- ") and l1_key is None:
                    # List item at indent 4 under l0 (no l1) → l0 is set
                    props.add(l0_key)

    domain = _domain_from_path(file_path, codes_dir)
    return code_id, parents, cousins, frozenset(props), domain


# ---------------------------------------------------------------------------
# Build all lookup maps from the codes directory
# ---------------------------------------------------------------------------

def build_maps(codes_dir: str) -> tuple[
    dict[str, list[str]],          # parent_to_children
    dict[str, set[str]],           # cousin_outgoing  (X → set it declares)
    dict[str, set[str]],           # cousin_incoming  (X → set that declare X)
    dict[str, frozenset[str]],     # code → property paths set
    dict[str, str],                # code → domain string
    set[str],                      # known code_ids
]:
    p2c: dict[str, list[str]] = defaultdict(list)
    cout: dict[str, set[str]] = defaultdict(set)
    cin: dict[str, set[str]] = defaultdict(set)
    code_props: dict[str, frozenset[str]] = {}
    code_domain: dict[str, str] = {}
    known: set[str] = set()

    for root, _, files in os.walk(codes_dir):
        for fname in files:
            if not fname.endswith((".yml", ".yaml")):
                continue
            fpath = os.path.join(root, fname)
            code_id, parents, cousins, props, domain = _parse_code_file(
                fpath, codes_dir
            )
            if not code_id:
                continue
            known.add(code_id)
            code_props[code_id] = props
            code_domain[code_id] = domain
            for p in parents:
                p2c[p].append(code_id)
            for c in cousins:
                cout[code_id].add(c)
                cin[c].add(code_id)

    for children in p2c.values():
        children.sort()

    return p2c, cout, cin, code_props, code_domain, known


def _descendants(roots: list[str], p2c: dict[str, list[str]]) -> set[str]:
    result: set[str] = set()
    pending = list(roots)
    while pending:
        cid = pending.pop()
        for child in p2c.get(cid, []):
            if child not in result:
                result.add(child)
                pending.append(child)
    return result


# ---------------------------------------------------------------------------
# Parse codelist YAML files into condition groups
# ---------------------------------------------------------------------------

_SELECTORS = ("descendant_of", "not_descendant_of", "cousin_of",
              "property_set", "domain")


def _parse_codelist(file_path: str) -> tuple[str, list[dict[str, list[str]]]]:
    """Return (title, [condition_group, ...]).

    Each condition_group maps selector keys to a list of values.  A key may
    appear more than once in a single YAML entry (e.g. two descendant_of lines
    under the same bullet); each occurrence is appended rather than overwritten.
    Multiple keys within one group are ANDed; groups are ORed.
    Commented-out lines are silently ignored.
    """
    title = Path(file_path).stem
    groups: list[dict[str, list[str]]] = []

    in_codes = in_select = False
    reading_title = False
    title_lines: list[str] = []
    current_group: dict[str, list[str]] | None = None

    def _add_to_group(group: dict[str, list[str]], sel: str, val: str) -> None:
        group.setdefault(sel, []).append(val)

    with open(file_path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.split("#", 1)[0].rstrip("\n")
            content = line.strip()
            stripped = line.lstrip(" ")
            indent = len(line) - len(stripped)

            # title block scalar
            if reading_title:
                if indent >= 2 and content:
                    title_lines.append(content)
                    continue
                else:
                    reading_title = False
                    if title_lines:
                        title = " ".join(title_lines)

            if not content:
                continue

            if indent == 0:
                # Flush any open group
                if current_group is not None:
                    groups.append(current_group)
                    current_group = None
                in_codes = in_select = False

                if stripped.startswith("title:"):
                    rest = stripped[len("title:"):].strip()
                    if rest in ("|", "|-", ""):
                        reading_title = True
                        title_lines = []
                    else:
                        title = _strip_quotes(rest)
                elif stripped.startswith("codes:"):
                    in_codes = True
                continue

            if not in_codes:
                continue

            if indent == 2:
                if not stripped.startswith("select:") and current_group is not None:
                    groups.append(current_group)
                    current_group = None
                in_select = stripped.startswith("select:")
                continue

            if not in_select:
                continue

            if indent == 4 and stripped.startswith("- "):
                # New condition group
                if current_group is not None:
                    groups.append(current_group)
                current_group = {}
                inline = stripped[2:]  # strip "- "
                for sel in _SELECTORS:
                    if inline.startswith(f"{sel}:"):
                        val = _strip_quotes(inline[len(sel) + 1:])
                        if val:
                            _add_to_group(current_group, sel, val)
                        break

            elif indent >= 6 and current_group is not None:
                # Continuation keys within the same group (duplicate keys accumulate)
                for sel in _SELECTORS:
                    if stripped.startswith(f"{sel}:"):
                        val = _strip_quotes(stripped[len(sel) + 1:])
                        if val:
                            _add_to_group(current_group, sel, val)
                        break

    if current_group is not None:
        groups.append(current_group)
    if reading_title and title_lines:
        title = " ".join(title_lines)

    return title, groups


# ---------------------------------------------------------------------------
# Count codes for one list
# ---------------------------------------------------------------------------

_POSITIVE_SELECTORS = frozenset({"descendant_of", "cousin_of", "property_set", "domain"})


def count_codes(
    groups: list[dict[str, list[str]]],
    p2c: dict[str, list[str]],
    cout: dict[str, set[str]],
    cin: dict[str, set[str]],
    code_props: dict[str, frozenset[str]],
    code_domain: dict[str, str],
    known: set[str],
) -> tuple[int, list[str]]:
    """Return (count, warnings)."""
    accumulated: set[str] = set()
    global_exclude: set[str] = set()
    warnings: list[str] = []

    for group in groups:
        has_positive = any(k in group for k in _POSITIVE_SELECTORS)

        if not has_positive:
            # Standalone not_descendant_of → global exclusion
            for ndo in group.get("not_descendant_of", []):
                if ndo not in known:
                    warnings.append(f"unknown code_id '{ndo}' in not_descendant_of")
                else:
                    global_exclude.add(ndo)
                    global_exclude |= _descendants([ndo], p2c)
            continue

        # --- Positive selectors (ANDed; repeated keys are also ANDed) ---
        candidates: set[str] | None = None

        def _intersect(s: set[str]) -> set[str]:
            nonlocal candidates
            candidates = s if candidates is None else candidates & s
            return candidates

        for cid in group.get("descendant_of", []):
            if cid not in known:
                warnings.append(f"unknown code_id '{cid}' in descendant_of")
                candidates = set()
            else:
                _intersect(_descendants([cid], p2c))

        for cid in group.get("cousin_of", []):
            if cid not in known:
                warnings.append(f"unknown code_id '{cid}' in cousin_of")
                _intersect(set())
            else:
                _intersect(cout.get(cid, set()) | cin.get(cid, set()))

        for prop in group.get("property_set", []):
            _intersect({c for c, ps in code_props.items() if prop in ps})

        for dom in group.get("domain", []):
            _intersect({c for c, d in code_domain.items() if d == dom})

        if candidates is None:
            candidates = set()

        # --- Local not_descendant_of filter ---
        for ndo in group.get("not_descendant_of", []):
            if not candidates:
                break
            if ndo not in known:
                warnings.append(f"unknown code_id '{ndo}' in not_descendant_of")
            else:
                candidates -= {ndo} | _descendants([ndo], p2c)

        accumulated |= candidates

    return len(accumulated - global_exclude), warnings


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Count codes in each codelist under codelists/descendants/ "
            "and codelists/features/ (or a custom --lists-dir)."
        ),
    )
    parser.add_argument(
        "--sort",
        choices=["file", "title", "count"],
        default="file",
        help="Sort output by this column (default: file).",
    )
    parser.add_argument(
        "--reverse",
        action="store_true",
        help="Reverse the sort order.",
    )
    parser.add_argument(
        "--lists-dir",
        default=None,
        help=(
            "Directory (or comma-separated list of directories) to scan for "
            "codelist YAML files.  Defaults to codelists/descendants and "
            "codelists/features relative to the repo root."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent.parent
    codes_dir = str(repo_root / "codes")

    if args.lists_dir:
        lists_dirs = [Path(d.strip()) for d in args.lists_dir.split(",")]
    else:
        lists_dirs = [
            repo_root / "codelists" / "descendants",
            repo_root / "codelists" / "features",
        ]

    print("Building code maps…", file=sys.stderr)
    p2c, cout, cin, code_props, code_domain, known = build_maps(codes_dir)

    list_files: list[Path] = []
    for ld in lists_dirs:
        list_files.extend(sorted(ld.rglob("*.yml")))

    if not list_files:
        print(f"No YAML files found under {lists_dirs}", file=sys.stderr)
        return 1

    rows: list[tuple[str, str, int]] = []
    all_warnings: list[tuple[str, list[str]]] = []

    for lf in list_files:
        title, groups = _parse_codelist(str(lf))
        count, warnings = count_codes(
            groups, p2c, cout, cin, code_props, code_domain, known
        )
        rel = str(lf.relative_to(repo_root))
        rows.append((rel, title, count))
        if warnings:
            all_warnings.append((rel, warnings))

    key_fn = {
        "file": lambda r: r[0],
        "title": lambda r: r[1],
        "count": lambda r: r[2],
    }
    rows.sort(key=key_fn[args.sort], reverse=args.reverse)

    col_path = max(len(r[0]) for r in rows)
    col_title = max(len(r[1]) for r in rows)
    fmt = f"{{:<{col_path}}}  {{:<{col_title}}}  {{:>5}}"
    header = fmt.format("File", "Title", "Count")
    print(header)
    print("-" * len(header))
    for rel, title, count in rows:
        print(fmt.format(rel, title, count))

    if all_warnings:
        print("\nWarnings:", file=sys.stderr)
        for rel, warns in all_warnings:
            for w in warns:
                print(f"  {rel}: {w}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
