#!/usr/bin/env python3
"""Append arXiv reference counts to an ID list.

Each non-empty line in the input file is treated as an arXiv ID record. The
first whitespace-delimited token is used as the ID, which makes the script safe
to re-run on files that already have a second count column.
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CODES_DIR = ROOT / "codes"
ARXIV_PATTERN = re.compile(r"arxiv:([^,\}\s]+)", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Append a tab-separated reference count to each arXiv ID listed in "
            "an input file."
        )
    )
    parser.add_argument(
        "input_path",
        type=Path,
        help="Path to the input file containing one arXiv ID per line.",
    )
    parser.add_argument(
        "--codes-dir",
        type=Path,
        default=DEFAULT_CODES_DIR,
        help=f"Directory containing YAML files to scan (default: {DEFAULT_CODES_DIR}).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output path. Defaults to rewriting the input file in place.",
    )
    return parser.parse_args()


def normalize_arxiv_id(raw_id: str) -> str:
    return raw_id.strip().rstrip(".,;:)'\"]")


def iter_input_ids(input_path: Path) -> list[str]:
    ids: list[str] = []

    for raw_line in input_path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        ids.append(stripped.split()[0])

    return ids


def count_arxiv_references(codes_dir: Path) -> Counter[str]:
    counts: Counter[str] = Counter()

    for yml_path in sorted(codes_dir.rglob("*.yml")) + sorted(codes_dir.rglob("*.yaml")):
        text = yml_path.read_text(encoding="utf-8")
        uncommented_text = "\n".join(
            line for line in text.splitlines() if not re.match(r"^\s*#", line)
        )

        for match in ARXIV_PATTERN.findall(uncommented_text):
            normalized = normalize_arxiv_id(match)
            if normalized:
                counts[normalized.lower()] += 1

    return counts


def build_output_lines(arxiv_ids: list[str], counts: Counter[str]) -> list[str]:
    return [f"{arxiv_id}\t{counts[arxiv_id.lower()]}" for arxiv_id in arxiv_ids]


def main() -> int:
    args = parse_args()
    input_path = args.input_path.resolve()
    codes_dir = args.codes_dir.resolve()
    output_path = (args.output or args.input_path).resolve()

    arxiv_ids = iter_input_ids(input_path)
    counts = count_arxiv_references(codes_dir)
    output_lines = build_output_lines(arxiv_ids, counts)

    output_path.write_text("\n".join(output_lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(output_lines)} rows to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
