#!/usr/bin/env python3
"""Report YML files whose first description paragraph violates style checks.

By default, this reports files whose first description paragraph contains a
LaTeX align environment. Optional flags can add length-based heuristics.
The script scans all .yml/.yaml files under the repository root.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from typing import Iterable


ALIGN_RE = re.compile(r"\\begin\{align\*?\}|\\begin\{aligned\}", re.IGNORECASE)
SENTENCE_RE = re.compile(r"[.!?](?:\s|$)")


@dataclass
class Violation:
    path: str
    reasons: list[str]
    first_paragraph: str


def iter_yaml_files(root: str) -> Iterable[str]:
    for dirpath, dirnames, filenames in os.walk(root):
        if ".git" in dirnames:
            dirnames.remove(".git")
        for filename in filenames:
            if filename.endswith((".yml", ".yaml")):
                yield os.path.join(dirpath, filename)


def _line_indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _strip_wrapping_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def extract_description_text(content: str) -> str | None:
    lines = content.splitlines()
    for idx, line in enumerate(lines):
        m = re.match(r"^(\s*)description:\s*(.*)$", line)
        if not m:
            continue

        desc_indent = len(m.group(1))
        rest = m.group(2).strip()

        if rest and not rest.startswith(("|", ">")):
            return _strip_wrapping_quotes(rest)

        if rest and rest.startswith(("|", ">")):
            block_lines: list[str] = []
            for follow in lines[idx + 1 :]:
                if follow.strip() == "":
                    block_lines.append("")
                    continue
                if _line_indent(follow) <= desc_indent:
                    break
                block_lines.append(follow)

            nonempty = [ln for ln in block_lines if ln.strip()]
            if not nonempty:
                return ""
            common_indent = min(_line_indent(ln) for ln in nonempty)
            dedented = [ln[common_indent:] if ln.strip() else "" for ln in block_lines]
            return "\n".join(dedented).rstrip()

        # Handles `description:` with no value.
        return ""
    return None


def first_paragraph(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    parts = re.split(r"\n\s*\n+", stripped)
    return parts[0].strip()


def sentence_count(text: str) -> int:
    return len(SENTENCE_RE.findall(text))


def analyze_file(path: str, repo_root: str, max_sentences: int, max_chars: int) -> Violation | None:
    with open(path, encoding="utf-8") as f:
        content = f.read()

    desc = extract_description_text(content)
    if desc is None:
        return None

    para = first_paragraph(desc)
    reasons: list[str] = []

    if para and ALIGN_RE.search(para):
        reasons.append("contains align environment")

    if para and max_sentences > 0:
        sentences = sentence_count(para)
        if sentences > max_sentences:
            reasons.append(f"has {sentences} sentences (max {max_sentences})")

    if para and max_chars > 0:
        if len(para) > max_chars:
            reasons.append(f"has {len(para)} characters (max {max_chars})")

    if not reasons:
        return None

    rel_path = os.path.relpath(path, repo_root)
    compact_para = " ".join(para.split())
    return Violation(path=rel_path, reasons=reasons, first_paragraph=compact_para)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Find YML files whose first description paragraph contains align equations."
    )
    parser.add_argument(
        "--max-sentences",
        type=int,
        default=0,
        help=(
            "Optional sentence-count heuristic. Set >0 to also flag first paragraphs "
            "with more than this many sentences (default: 0 = disabled)."
        ),
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=0,
        help=(
            "Optional length heuristic. Set >0 to also flag first paragraphs with more "
            "than this many characters (default: 0 = disabled)."
        ),
    )
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)

    violations: list[Violation] = []
    for path in iter_yaml_files(repo_root):
        violation = analyze_file(path, repo_root, args.max_sentences, args.max_chars)
        if violation:
            violations.append(violation)

    violations.sort(key=lambda v: v.path)

    if not violations:
        print("No incorrect first description paragraphs found.")
        return 0

    print(f"Found {len(violations)} file(s) with incorrect first description paragraph:")
    for violation in violations:
        reason_text = "; ".join(violation.reasons)
        print(f"- {violation.path}: {reason_text}")
        if violation.first_paragraph:
            print(f"  First paragraph: {violation.first_paragraph}")

    return 1


if __name__ == "__main__":
    sys.exit(main())
