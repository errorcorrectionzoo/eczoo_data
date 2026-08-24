#!/usr/bin/env python3
r"""Standardize malformed citation locators in YAML files.

This rewrites prose patterns like

    Ch. 9 of Ref. \cite{foo}
    see section 2.2.1 Ref. \cite{foo}
    (\cite{foo}, Ch. 27)
    Appx. A of Ref. \cite{foo}

into LaTeX locator form

    \cite[Ch. 9]{foo}
    see \cite[Sec. 2.2.1]{foo}
    \cite[Ch. 27]{foo}
    \cite[Appx. A]{foo}

A locator is only ever a structured reference (7, 2.2.1, III, II.A, A, 3a,
"4.1 and 4.2"), never free prose, so sentences like "many examples of X are
given in Ref. \cite{y}" are left alone.

By default, the script reports proposed changes. Pass ``--write`` to update files.
Pass ``--selftest`` to run the built-in rewrite / false-positive tests.
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

# A cite key may itself contain braces, e.g. \cite{manual:{A. Author, "Title", 2024}}.
# Allow one level of nesting so such keys are matched (and rewritten) in full.
CITE_RE = r"\\cite\{(?:[^{}]|\{[^{}]*\})+\}"

# A locator is a structured reference (7, 2.2.1, III, II.A, A, 3a, 152-160,
# "4.1 and 4.2") -- never free prose. Constraining it to these atoms is what
# keeps ordinary sentences such as "many examples of X are given in Ref. \cite{y}"
# from being parsed as <kind="examples", locator="of X are given in">.
# (?-i: ...) keeps the atom case-sensitive even though the surrounding patterns
# are compiled with re.IGNORECASE. Without it, [A-Z][a-z]? matches English words
# like "in" and "of", which is how prose slipped through as a locator.
_LOCATOR_ATOM = (
    r"(?-i:(?:[0-9]+|[IVXLCDM]+|[A-Z])(?:\.(?:[0-9]+|[IVXLCDM]+|[A-Z]))*[a-z]?)"
)
_LOCATOR_SEP = r"(?:\s*[,&]\s*|\s*[-–]\s*|\s+(?:and|to)\s+)"
LOCATOR_VALUE_RE = rf"{_LOCATOR_ATOM}(?:{_LOCATOR_SEP}{_LOCATOR_ATOM})*"


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
        "cor": ("Corr.", "Corrs."),
        "cors": ("Corr.", "Corrs."),
        "corr": ("Corr.", "Corrs."),
        "corrs": ("Corr.", "Corrs."),
        "corollary": ("Corr.", "Corrs."),
        "corollaries": ("Corr.", "Corrs."),
        "ex": ("Exam.", "Exams."),
        "exs": ("Exam.", "Exams."),
        "exam": ("Exam.", "Exams."),
        "exams": ("Exam.", "Exams."),
        "example": ("Exam.", "Exams."),
        "examples": ("Exam.", "Exams."),
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
        "app": ("Appx.", "Appxs."),
        "apps": ("Appx.", "Appxs."),
        "appx": ("Appx.", "Appxs."),
        "appxs": ("Appx.", "Appxs."),
        "appendix": ("Appx.", "Appxs."),
        "appendices": ("Appx.", "Appxs."),
        "def": ("Def.", "Defs."),
        "defs": ("Def.", "Defs."),
        "definition": ("Def.", "Defs."),
        "definitions": ("Def.", "Defs."),
        "rem": ("Rem.", "Rems."),
        "rems": ("Rem.", "Rems."),
        "remark": ("Rem.", "Rems."),
        "remarks": ("Rem.", "Rems."),
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
    match = re.fullmatch(r"\\cite\{((?:[^{}]|\{[^{}]*\})+)\}", cite)
    if not match:
        return cite
    return f"\\cite[{locator}]{{{match.group(1)}}}"


def _strip_wrapping_cite_parentheses(text: str) -> str:
    inner = r"\\cite(?:\[[^]]*\])?\{(?:[^{}]|\{[^{}]*\})+\}"
    wrapped_cite_re = re.compile(rf"\(({inner}(?:{inner})*)\)")
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
    r"Appxs?\.?|App(?:s|end(?:ix|ices))?\.?|"
    r"Defs?\.?|Definitions?|"
    r"Rems?\.?|Remarks?|"
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


SELFTEST_REWRITES = [
    # (input, expected output) -- prose that really does carry a locator
    (r"Ch. 9 of Ref. \cite{foo}", r"\cite[Ch. 9]{foo}"),
    (r"see section 2.2.1 Ref. \cite{foo}", r"see \cite[Sec. 2.2.1]{foo}"),
    (r"(\cite{foo}, Ch. 27)", r"\cite[Ch. 27]{foo}"),
    (r"Thms. 4.1 and 4.2 of Ref. \cite{foo}", r"\cite[Thms. 4.1 and 4.2]{foo}"),
    (r"Sec. II.A of Ref. \cite{foo}", r"\cite[Sec. II.A]{foo}"),
    (r"Appendix B of Ref. \cite{foo}", r"\cite[Appx. B]{foo}"),
]

SELFTEST_UNCHANGED = [
    # Ordinary prose in which a locator keyword happens to appear. Every one of
    # these was mangled by the pre-2026-08 locator regex, which let the locator
    # group swallow arbitrary words.
    r"Examples in Ref. \cite{arxiv:2410.18713} are the tessellations",
    r"In the three explicit examples of Ref. \cite{arxiv:2410.18713}, errors are correctable",
    r"another example of monodromy under the notion of parallel transport introduced in Ref. \cite{arxiv:1309.7062}.",
    r"Many examples have been found by computer algebra programs. Ref. \cite{arxiv:1007.1697} gives examples",
    r"A table of non-stabilizer Knill codes is available in Ref. \cite{manual:{A. Klappenecker, Title, 4(2), 152-160 (2004)}}.",
    r"Some upper and lower bounds on parameters and many examples of 2BGA codes are given in Ref. \cite{arxiv:2306.16400}.",
    # Already in locator form: must be left alone.
    r"\cite[Sec. IV]{arxiv:1234.5678}",
    r"\cite[Ch. 1, pg. 13]{doi:10.1007/978-1-4757-6568-7}",
]


def run_selftest() -> int:
    failures = 0
    for text, expected in SELFTEST_REWRITES:
        got = standardize_text(text)
        if got != expected:
            failures += 1
            print(f"REWRITE FAIL\n  in:       {text}\n  expected: {expected}\n  got:      {got}")
    for text in SELFTEST_UNCHANGED:
        got = standardize_text(text)
        if got != text:
            failures += 1
            print(f"FALSE POSITIVE\n  in:  {text}\n  got: {got}")
    total = len(SELFTEST_REWRITES) + len(SELFTEST_UNCHANGED)
    print(f"selftest: {total - failures}/{total} passed")
    return 1 if failures else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="rewrite files in place")
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="run the built-in rewrite/false-positive tests and exit",
    )
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
    if args.selftest:
        return run_selftest()
    files = expand_paths(args.paths)
    changed = process_files(write=args.write, files=files)
    mode = "updated" if args.write else "would update"
    print(f"{mode} {changed} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())