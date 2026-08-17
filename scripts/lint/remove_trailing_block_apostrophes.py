#!/usr/bin/env python3
"""
Remove stray trailing apostrophes from YAML block-scalar paragraph lines.

This targets artifacts introduced when a value was converted from a quoted
scalar to a block scalar ("|" or ">"), leaving behind a dangling closing
single quote at end-of-line.

By default, runs in dry-run mode and prints candidate edits.
Use --apply to rewrite files.
"""

import argparse
import os
from dataclasses import dataclass
from typing import List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass
class Change:
    line_no: int
    old_line: str
    new_line: str


def block_scalar_header(line: str) -> Tuple[int, bool]:
    """Return (indent, True) if line starts a YAML block scalar, else (_, False).

    All three spellings the zoo uses are recognised:

        description: |      a mapping value
        - |                 a bare LIST ITEM, e.g. under features.transversal_gates
        - detail: |         a mapping nested inside a list item

    The list-item forms have no key before the indicator, so requiring a ``:``
    used to miss them -- and those are exactly where long multi-paragraph
    feature and relation entries live.
    """
    if not line.strip() or line.lstrip().startswith("#"):
        return 0, False

    indent = len(line) - len(line.lstrip(" "))
    text = line.strip()

    # Peel off any leading list-item dashes ("- ", and nested "- - ").
    while text.startswith("-") and (len(text) == 1 or text[1] in " \t"):
        text = text[1:].strip()
        if not text:
            return indent, False  # a bare "-" opens nothing

    # What remains is either "key: <indicator>" or a bare "<indicator>".
    if ":" in text:
        key, rhs = text.split(":", 1)
        if "|" in key or ">" in key:
            return indent, False  # the colon came after the indicator
        rhs = rhs.strip()
    else:
        rhs = text

    if not rhs or rhs[0] not in "|>":
        return indent, False

    # Allow YAML modifiers after | or > (e.g. |-, >+, |2) and a trailing comment.
    for ch in rhs[1:].split("#", 1)[0].strip():
        if ch not in "-+0123456789":
            return indent, False

    return indent, True


def should_trim_apostrophe(line: str) -> bool:
    """
    Heuristic for quote leftovers in block-scalar content.

    Trim only if line ends with a single quote but is not itself a quoted scalar.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return False
    if not stripped.endswith("'"):
        return False
    if stripped.startswith("'"):
        return False
    return True


def detect_changes(lines: List[str]) -> List[Change]:
    """Find the trailing-apostrophe fixes for ``lines`` (does not mutate it).

    Block membership is decided BEFORE header detection: a content line inside a
    block scalar is never re-examined as a possible header, so prose that merely
    looks like ``- |...`` cannot confuse the scanner.
    """
    changes: List[Change] = []
    in_block = False
    block_indent = 0

    for i, line in enumerate(lines):
        if in_block:
            if not line.strip():
                continue  # blank lines stay inside the block
            curr_indent = len(line) - len(line.lstrip(" "))
            if curr_indent > block_indent:
                if should_trim_apostrophe(line):
                    new_line = (line[:-2] + "\n") if line.endswith("\n") else line[:-1]
                    changes.append(
                        Change(i + 1, line.rstrip("\n"), new_line.rstrip("\n"))
                    )
                continue
            # Dedented to the header's level or less: the block is over. Fall
            # through so this same line can open a new one.
            in_block = False

        header_indent, starts_block = block_scalar_header(line)
        if starts_block:
            in_block = True
            block_indent = header_indent

    return changes


def apply_changes(lines: List[str], changes: List[Change]) -> List[str]:
    out = list(lines)
    for ch in changes:
        i = ch.line_no - 1
        out[i] = ch.new_line + ("\n" if lines[i].endswith("\n") else "")
    return out


def fix_file(path: str, apply: bool = True) -> List[Change]:
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()

    changes = detect_changes(lines)
    if changes and apply:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(apply_changes(lines, changes))
    return changes


def iter_yaml_files(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fname in filenames:
            if fname.endswith(".yml") or fname.endswith(".yaml"):
                yield os.path.join(dirpath, fname)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Rewrite files in place. Without this flag, run as dry-run.",
    )
    parser.add_argument(
        "--root",
        default=ROOT,
        help="Repository root to scan (default: project root).",
    )
    args = parser.parse_args()

    total_files = 0
    total_changes = 0

    for path in iter_yaml_files(args.root):
        total_files += 1
        changes = fix_file(path, apply=args.apply)

        if changes:
            rel = os.path.relpath(path, args.root)
            print(f"{rel}")
            for ch in changes:
                print(f"  L{ch.line_no}")
                print(f"    - {ch.old_line}")
                print(f"    + {ch.new_line}")
            total_changes += len(changes)

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(
        f"\n[{mode}] Scanned {total_files} YAML files; "
        f"found {total_changes} trailing apostrophe fix(es)."
    )


if __name__ == "__main__":
    main()
