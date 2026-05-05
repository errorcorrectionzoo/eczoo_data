#!/usr/bin/env python3
"""Extract cited non-IEEE DOIs from YAML files under ``codes/``.

The output file contains tab-separated rows of DOI, citation count, and any
existing metadata columns 3-5 preserved from the previous output.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent
CODES_DIR = ROOT / "codes"
OUTPUT_PATH = ROOT / "resources" / "non_ieee_dois.txt"
EXCLUDED_DOI_PATHS = [
    ROOT / "resources" / "book_dois.txt",
    ROOT / "resources" / "book_chapter_dois.txt",
]

# Match doi:10.XXXX/... entries inside a cite block until the next comma/brace/space.
DOI_PATTERN = re.compile(r"doi:(10\.[^,\}\s]+)", re.IGNORECASE)
IEEE_PREFIX = "10.1109/"
TRAILING_PUNCT = re.compile(r"[.,;:'\"\]\}]+$")


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


def normalize_doi(raw: str) -> str:
    return TRAILING_PUNCT.sub("", raw.strip())


def read_existing_metadata() -> tuple[dict[str, str], dict[str, list[str]]]:
    """Return existing DOI casing and metadata columns 3-5 keyed by lowercase DOI."""
    doi_casing: dict[str, str] = {}
    metadata: dict[str, list[str]] = {}

    if not OUTPUT_PATH.exists():
        return doi_casing, metadata

    for line in OUTPUT_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        doi = normalize_doi(parts[0])
        doi_key = doi.lower()
        doi_casing[doi_key] = doi
        metadata[doi_key] = parts[2:5]

    return doi_casing, metadata


def read_excluded_dois() -> set[str]:
    """Return DOI keys that are tracked in specialized DOI resource files."""
    excluded: set[str] = set()

    for path in EXCLUDED_DOI_PATHS:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            excluded.add(normalize_doi(line.split("\t")[0]).lower())

    return excluded


def extract_non_ieee_doi_counts() -> tuple[Counter[str], dict[str, str]]:
    doi_counts: Counter[str] = Counter()
    doi_casing: dict[str, str] = {}
    excluded_dois = read_excluded_dois()

    for yml_path in sorted(CODES_DIR.rglob("*.yml")):
        content = yml_path.read_text(encoding="utf-8")
        uncommented_content = "\n".join(
            line for line in content.splitlines() if not re.match(r"^\s*#", line)
        )
        for cite_contents in iter_cite_contents(uncommented_content):
            for match in DOI_PATTERN.findall(cite_contents):
                doi = normalize_doi(match)
                if doi and not doi.lower().startswith(IEEE_PREFIX):
                    doi_key = doi.lower()
                    if doi_key in excluded_dois:
                        continue
                    doi_counts[doi_key] += 1
                    doi_casing.setdefault(doi_key, doi)

    return doi_counts, doi_casing


def main() -> int:
    existing_doi_casing, metadata = read_existing_metadata()
    doi_counts, extracted_doi_casing = extract_non_ieee_doi_counts()

    rows = []
    for doi_key, count in doi_counts.items():
        doi = extracted_doi_casing.get(doi_key, existing_doi_casing.get(doi_key, doi_key))
        rows.append((doi, count, metadata.get(doi_key, [])))

    rows.sort(key=lambda row: (-row[1], row[0].lower()))

    lines = [
        "\t".join([doi, str(count), *extra]).rstrip("\t")
        for doi, count, extra in rows
    ]
    OUTPUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} non-IEEE DOIs to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
