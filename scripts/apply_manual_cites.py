#!/usr/bin/env python3
"""
Apply edited manual citations from resources/manual_cites.txt to all YML files.

For each line in manual_cites.txt where col1 != col2, replace every occurrence
of  \cite{manual:{col1}  with  \cite{manual:{col2}  (preserving surrounding
content and any trailing citations after a comma inside the same \cite{}).
"""

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CITES_FILE = os.path.join(ROOT, "resources", "manual_cites.txt")

# ---------------------------------------------------------------------------
# Load replacements: {original_inner_text: edited_inner_text}
# ---------------------------------------------------------------------------
replacements = {}
with open(CITES_FILE, encoding="utf-8") as f:
    for line in f:
        line = line.rstrip("\n")
        if "\t" not in line:
            continue
        col1, col2 = line.split("\t", 1)
        if col1 != col2:
            replacements[col1] = col2

print(f"Loaded {len(replacements)} replacements.")

# ---------------------------------------------------------------------------
# Apply to all YML files
# ---------------------------------------------------------------------------
def apply_replacements(text: str, replacements: dict) -> str:
    """Replace inner text of manual:{...} occurrences in text."""
    result = []
    search_from = 0
    while True:
        idx = text.find("manual:{", search_from)
        if idx == -1:
            result.append(text[search_from:])
            break
        # Append everything up to this manual:{
        result.append(text[search_from:idx + len("manual:{")])
        start = idx + len("manual:{")
        # Use bracket matching to find the inner text
        depth = 1
        pos = start
        while pos < len(text) and depth > 0:
            if text[pos] == "{":
                depth += 1
            elif text[pos] == "}":
                depth -= 1
            pos += 1
        inner = text[start : pos - 1]
        closing = text[pos - 1]  # the final "}"
        if inner in replacements:
            result.append(replacements[inner])
        else:
            result.append(inner)
        result.append(closing)
        search_from = pos
    return "".join(result)


changed_files = 0
changed_instances = 0

for dirpath, dirnames, filenames in os.walk(ROOT):
    # Skip hidden dirs and scripts/resources dirs
    dirnames[:] = [d for d in dirnames if not d.startswith(".")]
    for fname in filenames:
        if not fname.endswith(".yml"):
            continue
        fpath = os.path.join(dirpath, fname)
        with open(fpath, encoding="utf-8") as f:
            original = f.read()
        updated = apply_replacements(original, replacements)
        if updated != original:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(updated)
            # Count how many replacements happened in this file
            n = sum(original.count(f"manual:{{{k}}}") for k in replacements if k in original)
            print(f"  {os.path.relpath(fpath, ROOT)}  ({n} change(s))")
            changed_files += 1
            changed_instances += n

print(f"\nDone. {changed_instances} replacement(s) in {changed_files} file(s).")
