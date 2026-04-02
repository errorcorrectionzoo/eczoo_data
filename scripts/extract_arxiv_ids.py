#!/usr/bin/env python3
"""Extract cited arXiv IDs from YAML files under ``codes/``."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CODES_DIR = ROOT / "codes"
OUTPUT_PATH = ROOT / "scripts" / "arxiv_ids.txt"

# Match \cite{...} blocks, allowing line breaks inside the braces.
CITE_PATTERN = re.compile(r"\\cite(?:\[[^\]]*\])?\{(.*?)\}", re.DOTALL)
# Match arxiv:... or arXiv:... entries inside a cite block until the next comma/brace/space.
ARXIV_PATTERN = re.compile(r"arxiv:([^,\}\s]+)", re.IGNORECASE)


def extract_arxiv_ids() -> list[str]:
    arxiv_ids: set[str] = set()

    for yml_path in sorted(CODES_DIR.rglob("*.yml")):
        content = yml_path.read_text(encoding="utf-8")
        uncommented_content = "\n".join(
            line for line in content.splitlines() if not re.match(r"^\s*#", line)
        )
        for cite_contents in CITE_PATTERN.findall(uncommented_content):
            for match in ARXIV_PATTERN.findall(cite_contents):
                if re.search(r"\d", match):
                    arxiv_ids.add(match)

    return sorted(arxiv_ids)


def main() -> int:
    arxiv_ids = extract_arxiv_ids()
    OUTPUT_PATH.write_text("\n".join(arxiv_ids) + "\n", encoding="utf-8")
    print(f"Wrote {len(arxiv_ids)} arXiv IDs to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
