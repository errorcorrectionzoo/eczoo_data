#!/usr/bin/env python3
"""Append DOI reference counts to a DOI list and sort by count descending.

Each non-empty line in the input file is treated as a DOI record. The first
whitespace-delimited token is used as the DOI, which makes the script safe to
re-run on files that already have a second count column.
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CODES_DIR = ROOT / "codes"
DOI_PATTERN = re.compile(r"doi:([^\s,\}\]\)]+)", re.IGNORECASE)
TRAILING_PUNCT = re.compile(r"[.,;:'\"\]\}]+$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Append a tab-separated reference count to each DOI listed in an "
            "input file, then sort by count descending."
        )
    )
    parser.add_argument(
        "input_paths",
        type=Path,
        nargs="+",
        help="Path(s) to input file(s) containing one DOI per line.",
    )
    parser.add_argument(
        "--codes-dir",
        type=Path,
        default=DEFAULT_CODES_DIR,
        help=f"Directory containing YAML files to scan (default: {DEFAULT_CODES_DIR}).",
    )
    return parser.parse_args()


def normalize_doi(raw: str) -> str:
    return TRAILING_PUNCT.sub("", raw.strip())


def iter_input_ids(input_path: Path) -> list[tuple[str, str]]:
    """Return list of (doi, extra) where extra is any trailing column(s) beyond the DOI."""
    rows: list[tuple[str, str]] = []
    for raw_line in input_path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        parts = stripped.split("\t")
        doi = parts[0].strip()
        # Preserve any extra columns that are not a bare count (digits only)
        extra_parts = [p for p in parts[1:] if not p.strip().isdigit()]
        extra = "\t".join(extra_parts)
        rows.append((doi, extra))
    return rows


def count_doi_references(codes_dir: Path) -> Counter[str]:
    counts: Counter[str] = Counter()
    yml_files = sorted(codes_dir.rglob("*.yml")) + sorted(codes_dir.rglob("*.yaml"))
    for yml_path in yml_files:
        text = yml_path.read_text(encoding="utf-8")
        uncommented = "\n".join(
            line for line in text.splitlines() if not re.match(r"^\s*#", line)
        )
        for match in DOI_PATTERN.findall(uncommented):
            normalized = normalize_doi(match)
            if normalized:
                counts[normalized.lower()] += 1
    return counts


def build_output_lines(rows: list[tuple[str, str]], counts: Counter[str]) -> list[str]:
    scored = [(doi, counts[doi.lower()], extra) for doi, extra in rows]
    scored.sort(key=lambda r: r[1], reverse=True)
    return [
        f"{doi}\t{count}\t{extra}".rstrip("\t") if extra else f"{doi}\t{count}"
        for doi, count, extra in scored
    ]


def main() -> int:
    args = parse_args()
    codes_dir = args.codes_dir.resolve()

    print("Scanning YAML files for DOI references…")
    counts = count_doi_references(codes_dir)
    print(f"Found {len(counts)} unique DOIs across all YAML files.")

    for input_path in args.input_paths:
        input_path = input_path.resolve()
        rows = iter_input_ids(input_path)
        output_lines = build_output_lines(rows, counts)
        input_path.write_text("\n".join(output_lines) + "\n", encoding="utf-8")
        print(f"Wrote {len(output_lines)} rows to {input_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
