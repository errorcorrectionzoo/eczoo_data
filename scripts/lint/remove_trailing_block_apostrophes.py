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
    """Return (indent, True) if line starts a YAML block scalar, else (_, False)."""
    if not line.strip() or line.lstrip().startswith("#"):
        return 0, False

    indent = len(line) - len(line.lstrip(" "))
    text = line.strip()

    # Match "key: |", "key: >", including optional chomping/indent indicators.
    if ":" not in text:
        return indent, False

    _, rhs = text.split(":", 1)
    rhs = rhs.strip()
    if not rhs:
        return indent, False

    if rhs[0] not in "|>":
        return indent, False

    if len(rhs) > 1:
        # Allow optional YAML modifiers after | or > (e.g., |-, >+, |2).
        for ch in rhs[1:]:
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


def fix_file(path: str) -> List[Change]:
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()

    changes: List[Change] = []
    in_block = False
    block_indent = 0

    for i, line in enumerate(lines):
        header_indent, starts_block = block_scalar_header(line)
        if starts_block:
            in_block = True
            block_indent = header_indent
            continue

        if not in_block:
            continue

        # End block when non-empty content dedents to block indentation or less.
        if line.strip():
            curr_indent = len(line) - len(line.lstrip(" "))
            if curr_indent <= block_indent:
                in_block = False
                # Re-check this same line as non-block content.
                continue

        # Inside block scalar content.
        if should_trim_apostrophe(line):
            old_line = line
            # Remove the final apostrophe before newline (if any).
            if line.endswith("\n"):
                new_line = line[:-2] + "\n"
            else:
                new_line = line[:-1]
            lines[i] = new_line
            changes.append(Change(i + 1, old_line.rstrip("\n"), new_line.rstrip("\n")))

    if changes:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(lines)

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

        # In dry-run mode, avoid writing: run detection on a copy of content.
        if args.apply:
            changes = fix_file(path)
        else:
            with open(path, encoding="utf-8") as f:
                original = f.readlines()

            # Simulate fix logic without writing.
            lines = original[:]
            changes = []
            in_block = False
            block_indent = 0

            for i, line in enumerate(lines):
                header_indent, starts_block = block_scalar_header(line)
                if starts_block:
                    in_block = True
                    block_indent = header_indent
                    continue

                if not in_block:
                    continue

                if line.strip():
                    curr_indent = len(line) - len(line.lstrip(" "))
                    if curr_indent <= block_indent:
                        in_block = False
                        continue

                if should_trim_apostrophe(line):
                    old_line = line
                    if line.endswith("\n"):
                        new_line = line[:-2] + "\n"
                    else:
                        new_line = line[:-1]
                    lines[i] = new_line
                    changes.append(Change(i + 1, old_line.rstrip("\n"), new_line.rstrip("\n")))

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
