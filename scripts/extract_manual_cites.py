#!/usr/bin/env python3
"""
Extract text inside manual:{...} fields from \cite commands in all YML files,
and write them (sorted, deduplicated) to resources/manual_cites.txt.
"""

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(ROOT, "resources", "manual_cites.txt")


def extract_manual_cites(text):
    """Find all manual:{...} occurrences and return their inner text."""
    results = []
    search_from = 0
    while True:
        idx = text.find("manual:{", search_from)
        if idx == -1:
            break
        # Start after the opening brace of manual:{
        start = idx + len("manual:{")
        depth = 1
        pos = start
        while pos < len(text) and depth > 0:
            if text[pos] == "{":
                depth += 1
            elif text[pos] == "}":
                depth -= 1
            pos += 1
        inner = text[start : pos - 1]
        results.append(inner)
        search_from = pos
    return results


all_cites = set()

for dirpath, dirnames, filenames in os.walk(ROOT):
    # Skip the scripts directory itself and other non-content dirs
    for fname in filenames:
        if not fname.endswith(".yml"):
            continue
        fpath = os.path.join(dirpath, fname)
        # Skip the bib_preset file
        if os.path.relpath(fpath, ROOT) == os.path.join("code_extra", "bib_preset.yml"):
            continue
        with open(fpath, encoding="utf-8") as f:
            content = f.read()
        for cite in extract_manual_cites(content):
            all_cites.add(cite.strip())

sorted_cites = sorted(all_cites, key=lambda s: s.lower())

with open(OUTPUT, "w", encoding="utf-8") as f:
    for cite in sorted_cites:
        f.write(cite + "\n")

print(f"Wrote {len(sorted_cites)} unique manual citations to {OUTPUT}")
