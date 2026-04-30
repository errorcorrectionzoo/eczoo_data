#!/usr/bin/env python3
"""Standardize malformed citation locators in YAML files.

This rewrites prose patterns like

    Ch. 9 of Ref. \cite{foo}
    see section 2.2.1 Ref. \cite{foo}
    (\cite{foo}, Ch. 27)

into LaTeX locator form

    \cite[Ch. 9]{foo}
    see \cite[Sec. 2.2.1]{foo}
    (\cite[Ch. 27]{foo})

By default, the script reports proposed changes. Pass ``--write`` to update files.
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CODES_DIR = ROOT / "codes"

CITE_RE = r"\\cite\{[^}]+\}"
LOCATOR_VALUE_RE = r"[A-Za-z0-9().,\-–/ ]+?"


@dataclass(frozen=True)
class CitationPattern:
    name: str
    regex: re.Pattern[str]
    replacement: str


def _needs_plural(locator_value: str) -> bool:
    lowered = locator_value.lower()
    return any(token in lowered for token in (" and ", ",", "&"))


def _abbrev(kind: str, locator_value: str) -> str:
    plural = _needs_plural(locator_value)
    kind_key = kind.lower().strip().rstrip(".")
    mapping = {
        "ch": ("Ch.", "Chs."),
        "chs": ("Ch.", "Chs."),
        "chapter": ("Ch.", "Chs."),
        "chap": ("Ch.", "Chs."),
        "chapters": ("Ch.", "Chs."),
        "sec": ("Sec.", "Secs."),
        "secs": ("Sec.", "Secs."),
        "section": ("Sec.", "Secs."),
        "sections": ("Sec.", "Secs."),
        "thm": ("Thm.", "Thms."),
        "thms": ("Thm.", "Thms."),
        "theorem": ("Thm.", "Thms."),
        "theorems": ("Thm.", "Thms."),
        "lemma": ("Lemma", "Lemmas"),
        "lem": ("Lemma", "Lemmas"),
        "lemmas": ("Lemma", "Lemmas"),
        "prop": ("Prop.", "Props."),
        "props": ("Prop.", "Props."),
        "proposition": ("Prop.", "Props."),
        "propositions": ("Prop.", "Props."),
        "cor": ("Cor.", "Cors."),
        "cors": ("Cor.", "Cors."),
        "corr": ("Cor.", "Cors."),
        "corollary": ("Cor.", "Cors."),
        "corollaries": ("Cor.", "Cors."),
        "ex": ("Ex.", "Exs."),
        "exs": ("Ex.", "Exs."),
        "exam": ("Ex.", "Exs."),
        "example": ("Ex.", "Exs."),
        "examples": ("Ex.", "Exs."),
        "fig": ("Fig.", "Figs."),
        "figs": ("Fig.", "Figs."),
        "figure": ("Fig.", "Figs."),
        "figures": ("Fig.", "Figs."),
        "table": ("Table", "Tables"),
        "tables": ("Table", "Tables"),
        "eq": ("Eq.", "Eqs."),
        "eqs": ("Eq.", "Eqs."),
        "equation": ("Eq.", "Eqs."),
        "equations": ("Eq.", "Eqs."),
        "app": ("App.", "Apps."),
        "apps": ("App.", "Apps."),
        "appendix": ("App.", "Apps."),
        "appendices": ("App.", "Apps."),
        "pg": ("pg.", "pp."),
        "page": ("pg.", "pp."),
        "pages": ("pg.", "pp."),
    }
    singular, plural_form = mapping[kind_key]
    return plural_form if plural else singular


def _normalize_locator(kind: str, locator_value: str) -> str:
    locator = locator_value.strip()
    locator = re.sub(r"\s+", " ", locator)
    locator = re.sub(r"\s*([,;])\s*", r"\1 ", locator)
    locator = re.sub(r"\s+([.)])", r"\1", locator)
    locator = re.sub(r"\s+", " ", locator).strip()
    return f"{_abbrev(kind, locator)} {locator}"


def _inject_locator(cite: str, locator: str) -> str:
    match = re.fullmatch(r"\\cite\{([^}]+)\}", cite)
    if not match:
        return cite
    return f"\\cite[{locator}]{{{match.group(1)}}}"


def _strip_wrapping_cite_parentheses(text: str) -> str:
    wrapped_cite_re = re.compile(
        r"\((\\cite(?:\[[^]]*\])?\{[^}]+\}(?:\\cite(?:\[[^]]*\])?\{[^}]+\})*)\)"
    )
    return wrapped_cite_re.sub(r"\1", text)


def _replace_locator_with_cite(match: re.Match[str]) -> str:
    prefix = match.groupdict().get("prefix", "") or ""
    kind = match.group("kind")
    locator = _normalize_locator(kind, match.group("locator"))
    cite = match.group("cite")
    suffix = match.groupdict().get("suffix", "") or ""
    return f"{prefix}{_inject_locator(cite, locator)}{suffix}"


LOCATOR_KIND_RE = (
    r"Ch(?:apter)?s?\.?|Secs?\.?|Sections?|"
    r"Thm(?:s)?\.?|Theorems?|"
    r"Lemmas?|Lem\.?|"
    r"Prop(?:s)?\.?|Propositions?|"
    r"Cor(?:s)?\.?|Corollaries?|"
    r"Ex(?:s|am(?:ples?)?)?\.?|Examples?|"
    r"Fig(?:s|ures?)?\.?|"
    r"Tables?|"
    r"Eq(?:s|uations?)?\.?|"
    r"App(?:s|end(?:ix|ices))?\.?|"
    r"pg\.?|pages?"
)


PATTERNS = [
    CitationPattern(
        name="locator before ref cite",
        regex=re.compile(
            rf"(?P<prefix>\b(?:see(?: also)?\s+)?)"
            rf"(?P<kind>{LOCATOR_KIND_RE})\s+"
            rf"(?P<locator>{LOCATOR_VALUE_RE})\s+"
            rf"(?:of\s+)?Refs?\.\s+"
            rf"(?P<cite>{CITE_RE})",
            re.IGNORECASE,
        ),
        replacement="callable",
    ),
    CitationPattern(
        name="ref cite followed by locator",
        regex=re.compile(
            rf"(?P<prefix>\b(?:see(?: also)?\s+)?)Refs?\.\s+"
            rf"(?P<cite>{CITE_RE}),\s+"
            rf"(?P<kind>{LOCATOR_KIND_RE})\s+"
            rf"(?P<locator>{LOCATOR_VALUE_RE})(?P<suffix>\b)",
            re.IGNORECASE,
        ),
        replacement="callable",
    ),
    CitationPattern(
        name="bare cite followed by locator",
        regex=re.compile(
            rf"(?P<cite>{CITE_RE}),\s+"
            rf"(?P<kind>{LOCATOR_KIND_RE})\s+"
            rf"(?P<locator>{LOCATOR_VALUE_RE})(?P<suffix>\b)",
            re.IGNORECASE,
        ),
        replacement="callable",
    ),
    CitationPattern(
        name="bare cite in parens followed by locator",
        regex=re.compile(
            rf"\((?P<cite>{CITE_RE}),\s+"
            rf"(?P<kind>{LOCATOR_KIND_RE})\s+"
            rf"(?P<locator>{LOCATOR_VALUE_RE})\)",
            re.IGNORECASE,
        ),
        replacement="paren",
    ),
    CitationPattern(
        name="locator of cite without ref",
        regex=re.compile(
            rf"(?P<prefix>\b(?:in|from|of|see(?: also)?|as introduced in|introduced in)\s+)"
            rf"(?P<kind>{LOCATOR_KIND_RE})\s+"
            rf"(?P<locator>{LOCATOR_VALUE_RE})\s+of\s+"
            rf"(?P<cite>{CITE_RE})",
            re.IGNORECASE,
        ),
        replacement="callable",
    ),
]


def _apply_pattern(text: str, pattern: CitationPattern) -> str:
    if pattern.replacement == "callable":
        return pattern.regex.sub(_replace_locator_with_cite, text)
    if pattern.replacement == "paren":
        def repl(match: re.Match[str]) -> str:
            locator = _normalize_locator(match.group("kind"), match.group("locator"))
            cite = match.group("cite")
            return _inject_locator(cite, locator)

        return pattern.regex.sub(repl, text)
    raise ValueError(f"Unknown replacement mode: {pattern.replacement}")


def standardize_text(text: str) -> str:
    updated = text
    for pattern in PATTERNS:
        updated = _apply_pattern(updated, pattern)
    updated = _strip_wrapping_cite_parentheses(updated)
    return updated


def iter_yaml_files(root: Path):
    yield from sorted(root.rglob("*.yml"))


def diff_text(path: Path, old: str, new: str) -> str:
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=str(path),
            tofile=str(path),
            n=1,
        )
    )


def process_files(write: bool, files: list[Path] | None = None) -> int:
    changed = 0
    targets = files if files is not None else list(iter_yaml_files(CODES_DIR))
    for path in targets:
        original = path.read_text(encoding="utf-8")
        updated = standardize_text(original)
        if updated == original:
            continue
        changed += 1
        if write:
            path.write_text(updated, encoding="utf-8")
        else:
            sys.stdout.write(diff_text(path, original, updated))
    return changed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="rewrite files in place")
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="optional YAML files or directories to process",
    )
    return parser.parse_args()


def expand_paths(paths: list[Path]) -> list[Path]:
    if not paths:
        return list(iter_yaml_files(CODES_DIR))

    expanded: list[Path] = []
    for raw_path in paths:
        path = raw_path if raw_path.is_absolute() else ROOT / raw_path
        if path.is_dir():
            expanded.extend(sorted(path.rglob("*.yml")))
        elif path.suffix == ".yml":
            expanded.append(path)
    return expanded


def main() -> int:
    args = parse_args()
    files = expand_paths(args.paths)
    changed = process_files(write=args.write, files=files)
    mode = "updated" if args.write else "would update"
    print(f"{mode} {changed} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())