#!/usr/bin/env python3
"""Extract cited IEEE DOIs from YAML files under ``codes/``."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CODES_DIR = ROOT / "codes"
OUTPUT_PATH = ROOT / "resources" / "ieee_dois.txt"

# Match doi:10.1109/... entries inside a cite block until the next comma/brace/space.
IEEE_DOI_PATTERN = re.compile(r"doi:(10\.1109/[^,\}\s]+)", re.IGNORECASE)


def iter_cite_contents(text: str) -> list[str]:
    """Return ``\\cite{...}`` contents while handling nested braces."""
    cite_contents: list[str] = []
    index = 0

    while True:
        cite_start = text.find(r"\cite", index)
        if cite_start == -1:
            return cite_contents

        cursor = cite_start + len(r"\cite")

        if cursor < len(text) and text[cursor] == "[":
            bracket_depth = 1
            cursor += 1
            while cursor < len(text) and bracket_depth:
                if text[cursor] == "[":
                    bracket_depth += 1
                elif text[cursor] == "]":
                    bracket_depth -= 1
                cursor += 1

        if cursor >= len(text) or text[cursor] != "{":
            index = cite_start + len(r"\cite")
            continue

        cursor += 1
        contents_start = cursor
        brace_depth = 1

        while cursor < len(text) and brace_depth:
            if text[cursor] == "{":
                brace_depth += 1
            elif text[cursor] == "}":
                brace_depth -= 1
            cursor += 1

        if brace_depth == 0:
            cite_contents.append(text[contents_start : cursor - 1])

        index = cursor


def extract_ieee_dois() -> list[str]:
    ieee_dois: set[str] = set()

    for yml_path in sorted(CODES_DIR.rglob("*.yml")):
        content = yml_path.read_text(encoding="utf-8")
        uncommented_content = "\n".join(
            line for line in content.splitlines() if not re.match(r"^\s*#", line)
        )
        for cite_contents in iter_cite_contents(uncommented_content):
            for match in IEEE_DOI_PATTERN.findall(cite_contents):
                ieee_dois.add(match)

    return sorted(ieee_dois)


def main() -> int:
    ieee_dois = extract_ieee_dois()
    OUTPUT_PATH.write_text("\n".join(ieee_dois) + "\n", encoding="utf-8")
    print(f"Wrote {len(ieee_dois)} IEEE DOIs to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())