#!/usr/bin/env python3
"""
Extract text inside manual:{...} fields from \cite commands in all YML files
and write them to resources/manual_cites.txt.

Use --presets to also append readily formatted preset citations from
code_extra/bib_preset.yml.
"""

import argparse
import os
import re

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT = os.path.join(ROOT, "resources", "manual_cites.txt")
BIB_PRESET = os.path.join(ROOT, "code_extra", "bib_preset.yml")


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


def one_line(text):
    """Collapse whitespace so tab-separated output stays one row per citation."""
    return " ".join(str(text).split())


def extract_ready_formatted_presets():
    """Return (formatted citation, preset name) rows from bib_preset.yml."""
    with open(BIB_PRESET, encoding="utf-8") as f:
        presets = yaml.safe_load(f)

    rows = []
    for preset_name, preset in presets.items():
        ready_formatted = preset.get("_ready_formatted")
        if ready_formatted is None:
            continue

        if isinstance(ready_formatted, dict):
            formatted = ready_formatted.get("flm")
        else:
            formatted = ready_formatted

        if formatted:
            rows.append((one_line(formatted), preset_name))

    return rows


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--presets",
    action="store_true",
    help="also append preset citations from code_extra/bib_preset.yml",
)
args = parser.parse_args()

all_cites = set()

for dirpath, dirnames, filenames in os.walk(ROOT):
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
    if args.presets:
        preset_rows = sorted(extract_ready_formatted_presets(), key=lambda row: row[0].lower())
        for formatted, preset_name in preset_rows:
            f.write(f"{formatted}\t{preset_name}\n")

if args.presets:
    print(
        f"Wrote {len(sorted_cites)} unique manual citations and "
        f"{len(preset_rows)} preset citations to {OUTPUT}"
    )
else:
    print(f"Wrote {len(sorted_cites)} unique manual citations to {OUTPUT}")
