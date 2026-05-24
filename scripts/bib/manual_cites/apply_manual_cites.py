#!/usr/bin/env python3
"""
Apply edited manual citations and preset promotions from resources/manual_cites.txt
to all YML files.

For each tab-separated line where col1 != col2:
  - col2 is a bare word (preset key): replace  manual:{col1}  with just  col2,
    dropping the manual:{} wrapper so the cite becomes a normal preset cite.
  - col2 is a citation string: replace the inner text of  manual:{col1}  with
    col2, keeping the manual:{} wrapper.
"""

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
CITES_FILE = os.path.join(ROOT, "resources", "manual_cites.txt")

# ---------------------------------------------------------------------------
# Load replacements
# ---------------------------------------------------------------------------
# text_replacements: inner_text -> new_inner_text  (keep manual:{} wrapper)
# preset_promotions: inner_text -> preset_key      (strip manual:{} wrapper)
text_replacements = {}
preset_promotions = {}

_PRESET_KEY = re.compile(r'[A-Za-z]\w*$')

with open(CITES_FILE, encoding="utf-8") as f:
    for line in f:
        line = line.rstrip("\n")
        if "\t" not in line:
            continue
        col1, col2 = line.split("\t", 1)
        if col1 == col2:
            continue
        if _PRESET_KEY.fullmatch(col2):
            preset_promotions[col1] = col2
        else:
            text_replacements[col1] = col2

print(
    f"Loaded {len(text_replacements)} text replacements "
    f"and {len(preset_promotions)} preset promotions."
)

# ---------------------------------------------------------------------------
# Apply to all YML files
# ---------------------------------------------------------------------------
def apply_replacements(text: str) -> str:
    """Replace manual:{...} occurrences according to both replacement tables."""
    result = []
    search_from = 0
    while True:
        idx = text.find("manual:{", search_from)
        if idx == -1:
            result.append(text[search_from:])
            break
        start = idx + len("manual:{")
        # Bracket-match to find the end of manual:{...}
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

        if inner in preset_promotions:
            # Drop the manual:{} wrapper; emit everything before "manual:{"
            # then just the preset key (no closing brace).
            result.append(text[search_from:idx])
            result.append(preset_promotions[inner])
        elif inner in text_replacements:
            # Keep manual:{} wrapper, swap inner text.
            result.append(text[search_from:idx + len("manual:{")])
            result.append(text_replacements[inner])
            result.append(closing)
        else:
            result.append(text[search_from:idx + len("manual:{")])
            result.append(inner)
            result.append(closing)

        search_from = pos
    return "".join(result)


changed_files = 0
changed_instances = 0

for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if not d.startswith(".")]
    for fname in filenames:
        if not fname.endswith(".yml"):
            continue
        fpath = os.path.join(dirpath, fname)
        with open(fpath, encoding="utf-8") as f:
            original = f.read()
        updated = apply_replacements(original)
        if updated != original:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(updated)
            n = sum(
                original.count(f"manual:{{{k}}}")
                for k in (*text_replacements, *preset_promotions)
                if k in original
            )
            print(f"  {os.path.relpath(fpath, ROOT)}  ({n} change(s))")
            changed_files += 1
            changed_instances += n

print(f"\nDone. {changed_instances} replacement(s) in {changed_files} file(s).")
