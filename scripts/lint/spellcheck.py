#!/usr/bin/env python3
"""Spell-check plain-English text in ECC Zoo YAML files using codespell.

LaTeX math environments, citation macros, and cross-reference commands are
stripped before checking so only genuine prose reaches the spell checker.

Usage:
  python scripts/lint/spellcheck.py                         # check all codes/
  python scripts/lint/spellcheck.py codes/quantum/qubits/   # specific subtree
  python scripts/lint/spellcheck.py --wordlist extra.txt    # extra word whitelist
  python scripts/lint/spellcheck.py --codespell /path/to/codespell

The codespell executable is found automatically; see resolve_codespell().

Exit status: 0 clean, 1 spelling issues found, 2 codespell unavailable.
"""

import argparse
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_CODES_PATH = os.path.join(ROOT, "codes")
DEFAULT_WORDLIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spellcheck_wordlist.txt")


# ---------------------------------------------------------------------------
# LaTeX stripping
# ---------------------------------------------------------------------------

# Complete environments: \begin{foo}...\end{foo} — remove entirely.
_ENV_RE = re.compile(r'\\begin\{[^}]*\}.*?\\end\{[^}]*\}', re.DOTALL)

# Inline math: \(...\)
_INLINE_MATH_RE = re.compile(r'\\\(.*?\\\)', re.DOTALL)

# Display math: \[...\]
_DISPLAY_MATH_RE = re.compile(r'\\\[.*?\\\]', re.DOTALL)

# Two-argument commands where we keep the second (text) argument.
_HREF_RE = re.compile(r'\\href\{[^}]*\}\{([^}]*)\}')
_HYPERREF_RE = re.compile(r'\\hyperref\[[^\]]*\]\{([^}]*)\}')

# One-argument commands to remove entirely (argument discarded).
# Note: \cite is handled separately via _remove_cite() for nested-brace safety.
_DISCARD_RE = re.compile(
    r'\\(?:url|label|ref|eqref|footnote|hfill|vspace|hspace)\{[^}]*\}'
)

# Formatting/structural commands: keep the argument text.
_KEEP_ARG_RE = re.compile(
    r'\\(?:textbf|textit|emph|term|subsection\*?|paragraph|section\*?|'
    r'caption|text)\{([^}]*)\}'
)

# Remaining bare commands like \nonumber, \alpha, \leq, etc.
_BARE_CMD_RE = re.compile(r'\\[A-Za-z]+\*?')

# Double apostrophes — YAML quoting artifact.
_DOUBLE_APOS_RE = re.compile(r"''")


def _remove_cite(text: str) -> str:
    r"""Remove \cite{...} with balanced-brace matching (handles nested braces)."""
    result: list[str] = []
    i = 0
    while i < len(text):
        idx = text.find('\\cite', i)
        if idx == -1:
            result.append(text[i:])
            break
        result.append(text[i:idx])
        i = idx + 5  # advance past \cite
        # Skip optional locator: \cite[Ch. 1]{...}
        if i < len(text) and text[i] == '[':
            while i < len(text) and text[i] != ']':
                i += 1
            if i < len(text):
                i += 1
        if i >= len(text) or text[i] != '{':
            result.append(' ')
            continue
        depth = 0
        while i < len(text):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    i += 1
                    break
            i += 1
        result.append(' ')
    return ''.join(result)


def strip_latex(text: str) -> str:
    """Strip LaTeX markup from *text*, leaving readable prose."""
    text = _ENV_RE.sub(' ', text)
    text = _INLINE_MATH_RE.sub(' ', text)
    text = _DISPLAY_MATH_RE.sub(' ', text)
    text = _HREF_RE.sub(r'\1', text)
    text = _HYPERREF_RE.sub(r'\1', text)
    text = _remove_cite(text)
    text = _DISCARD_RE.sub(' ', text)
    text = _KEEP_ARG_RE.sub(r'\1', text)
    text = _BARE_CMD_RE.sub(' ', text)
    text = _DOUBLE_APOS_RE.sub("'", text)
    return text


# ---------------------------------------------------------------------------
# YAML prose extraction
# ---------------------------------------------------------------------------

def _collect_strings(obj, chunks: list) -> None:
    """Recursively collect all string leaves from a YAML value."""
    if isinstance(obj, str):
        chunks.append(obj)
    elif isinstance(obj, list):
        for item in obj:
            _collect_strings(item, chunks)
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect_strings(v, chunks)


# Top-level prose fields.
_TOP_PROSE_FIELDS = (
    "name", "short_name", "alternative_names",
    "description", "protection",
)

# Fields that are dicts or lists of strings/dicts.
_NESTED_PROSE_FIELDS = ("features", "realizations", "notes")


def extract_prose(data: dict) -> str:
    """Return all plain-text prose from a parsed YAML code entry."""
    chunks: list[str] = []

    for field in _TOP_PROSE_FIELDS:
        val = data.get(field)
        if val:
            _collect_strings(val, chunks)

    for field in _NESTED_PROSE_FIELDS:
        val = data.get(field)
        if val:
            _collect_strings(val, chunks)

    # From relations, only the human-written "detail" sub-field.
    relations = data.get("relations") or {}
    if isinstance(relations, dict):
        for key in ("parents", "cousins"):
            for item in relations.get(key) or []:
                if isinstance(item, dict):
                    detail = item.get("detail")
                    if detail:
                        _collect_strings(detail, chunks)

    return "\n".join(chunks)


# ---------------------------------------------------------------------------
# File iteration
# ---------------------------------------------------------------------------

def iter_yaml_files(root: str):
    if os.path.isfile(root):
        if root.endswith(".yml") or root.endswith(".yaml"):
            yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for fname in sorted(filenames):
            if fname.endswith(".yml") or fname.endswith(".yaml"):
                yield os.path.join(dirpath, fname)


# ---------------------------------------------------------------------------
# Locating codespell
# ---------------------------------------------------------------------------

INSTALL_HINT = """\
Error: codespell not found.

Install it, for example with one of:
    pipx install codespell
    pip install --user codespell
    python3 -m venv .venv && .venv/bin/pip install codespell

Or point this script at an existing copy:
    scripts/lint/spellcheck.py --codespell /path/to/codespell
    CODESPELL=/path/to/codespell scripts/lint/spellcheck.py\
"""


def _is_exe(path: str) -> bool:
    return bool(path) and os.path.isfile(path) and os.access(path, os.X_OK)


def resolve_codespell(explicit: str | None = None) -> list[str] | None:
    """Return the argv prefix that runs codespell, or None if unavailable.

    Searched in order: an explicit --codespell value, the CODESPELL environment
    variable, PATH, a codespell next to the running interpreter (so that
    ``.venv/bin/python spellcheck.py`` works without activating anything), the
    codespell_lib module importable by the running interpreter, and finally a
    virtualenv inside the repo.  An explicit choice is never silently replaced
    by a fallback: if it is unusable, this returns None so the caller can say so.
    """
    chosen = explicit or os.environ.get("CODESPELL")
    if chosen:
        if _is_exe(chosen):
            return [chosen]
        found = shutil.which(chosen)
        return [found] if found else None

    found = shutil.which("codespell")
    if found:
        return [found]

    interpreter_dir = os.path.dirname(os.path.abspath(sys.executable))
    for name in ("codespell", "codespell.exe"):
        sibling = os.path.join(interpreter_dir, name)
        if _is_exe(sibling):
            return [sibling]

    if importlib.util.find_spec("codespell_lib") is not None:
        return [sys.executable, "-m", "codespell_lib"]

    for sub in (".venv", "venv"):
        for bindir, name in (("bin", "codespell"), ("Scripts", "codespell.exe")):
            cand = os.path.join(ROOT, sub, bindir, name)
            if _is_exe(cand):
                return [cand]

    return None


# ---------------------------------------------------------------------------
# Mapping findings back to source lines
# ---------------------------------------------------------------------------

# A codespell finding reads "mispelling ==> misspelling" or, with several
# suggestions, "Linke ==> Linked, Link, Links".  The flagged text precedes "==>".
_FLAGGED_RE = re.compile(r'^(.*?)\s*==>')

_WHITESPACE_RE = re.compile(r'\s+')

# path -> source lines, so a file with several findings is read only once.
_SOURCE_CACHE: dict[str, list[str]] = {}


def flagged_text(message: str) -> str:
    """Return the text codespell flagged, given its ``word ==> fix`` message."""
    m = _FLAGGED_RE.match(message)
    return m.group(1).strip() if m else ""


def _source_lines(path: str) -> list[str]:
    if path not in _SOURCE_CACHE:
        try:
            with open(path, encoding="utf-8") as f:
                _SOURCE_CACHE[path] = f.readlines()
        except OSError:
            _SOURCE_CACHE[path] = []
    return _SOURCE_CACHE[path]


def locate_in_source(path: str, phrase: str) -> list[int]:
    r"""Return the 1-based lines of *path* on which *phrase* appears.

    codespell only ever sees the temp file of extracted, LaTeX-stripped prose,
    so the line numbers it reports bear no relation to the original YAML.  A
    line map cannot be threaded through extraction either: fields are visited
    out of order, YAML folds multi-line scalars into one line, and whole math
    environments are deleted.  So we look the flagged text back up in the
    source instead.  Whitespace within a multi-word finding is matched loosely,
    since a folded line break arrives here as a single space.
    """
    words = [re.escape(w) for w in _WHITESPACE_RE.split(phrase) if w]
    if not words:
        return []
    body = r'\s+'.join(words)
    lines = _source_lines(path)
    # Prefer an exact-case hit; fall back to case-insensitive.
    for flags in (0, re.IGNORECASE):
        pattern = re.compile(rf'(?<![A-Za-z]){body}(?![A-Za-z])', flags)
        hits = [i + 1 for i, line in enumerate(lines) if pattern.search(line)]
        if hits:
            return hits
        # A folded line break can split a multi-word phrase across two lines.
        text = "".join(lines)
        m = pattern.search(text)
        if m:
            return [text.count("\n", 0, m.start()) + 1]
    return []


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def load_prose(path: str) -> str:
    """Parse a YAML file and return LaTeX-stripped prose text."""
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            return ""
        raw = extract_prose(data)
    except Exception:
        # On parse errors fall back to raw text (still useful).
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    return strip_latex(raw)


def run_spellcheck(search_path: str, wordlist: str | None,
                   codespell_cmd: list[str]) -> int:
    """
    Write cleaned prose for each YAML file into a temp dir, run codespell,
    and print results mapped back to original paths.  Returns error count.
    """
    yaml_files = list(iter_yaml_files(search_path))
    if not yaml_files:
        print(f"No YAML files found under {search_path}", file=sys.stderr)
        return 0

    # Use directory as base for relative paths.
    base = search_path if os.path.isdir(search_path) else os.path.dirname(search_path)

    error_count = 0

    with tempfile.TemporaryDirectory(prefix="eczoo_spell_") as tmpdir:
        # Map temp path → original path so we can rewrite codespell output.
        path_map: dict[str, str] = {}

        for orig_path in yaml_files:
            rel = os.path.relpath(orig_path, base)
            tmp_path = os.path.join(tmpdir, rel + ".txt")
            os.makedirs(os.path.dirname(tmp_path), exist_ok=True)
            prose = load_prose(orig_path)
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(prose)
            path_map[os.path.normpath(tmp_path)] = orig_path

        cmd = [*codespell_cmd, tmpdir]
        if wordlist and os.path.isfile(wordlist):
            cmd += ["--ignore-words", wordlist]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
        except OSError as exc:
            print(f"Error: could not run {cmd[0]}: {exc}", file=sys.stderr)
            raise SystemExit(2)
        output = result.stdout + result.stderr

        # (file, flagged text) -> findings already reported, so repeats of one
        # typo walk through its successive source lines.
        seen_counts: dict[tuple[str, str], int] = {}

        for line in output.splitlines():
            # codespell line format:  /path/to/file.txt:N: word ==> correction
            # Its N indexes the stripped-prose temp file, so it is discarded in
            # favour of the real line found by locate_in_source().
            colon_parts = line.split(":", 2)
            if len(colon_parts) < 3:
                continue
            tmp_path_raw = os.path.normpath(colon_parts[0])
            message = colon_parts[2].strip()

            orig = path_map.get(tmp_path_raw)
            if orig is None:
                print(line)
                error_count += 1
                continue

            rel = os.path.relpath(orig, ROOT)
            phrase = flagged_text(message)
            hits = locate_in_source(orig, phrase)
            if not hits:
                # Stripping can join or split words, so the flagged text is not
                # always literally present; report the file without a line.
                print(f"{rel}: {message}")
            else:
                # codespell emits one finding per occurrence, so hand the n-th
                # finding the n-th source line rather than repeating the first.
                nth = seen_counts.get((orig, phrase), 0)
                seen_counts[(orig, phrase)] = nth + 1
                print(f"{rel}:{hits[min(nth, len(hits) - 1)]}: {message}")
            error_count += 1

    return error_count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        nargs="?",
        default=DEFAULT_CODES_PATH,
        help="Directory to scan (default: codes/).",
    )
    parser.add_argument(
        "--wordlist",
        default=DEFAULT_WORDLIST,
        help="File of words to ignore, one per line.",
    )
    parser.add_argument(
        "--codespell",
        default=None,
        help="Path to the codespell executable (default: auto-detect; "
             "also settable via the CODESPELL environment variable).",
    )
    args = parser.parse_args()

    if not os.path.exists(args.path):
        print(f"Error: path not found: {args.path}", file=sys.stderr)
        sys.exit(1)

    codespell_cmd = resolve_codespell(args.codespell)
    if codespell_cmd is None:
        requested = args.codespell or os.environ.get("CODESPELL")
        if requested:
            print(f"Error: codespell not usable at {requested!r}.", file=sys.stderr)
        else:
            print(INSTALL_HINT, file=sys.stderr)
        sys.exit(2)

    count = run_spellcheck(args.path, args.wordlist, codespell_cmd)
    print(f"\nFound {count} spelling issue(s).")
    sys.exit(0 if count == 0 else 1)


if __name__ == "__main__":
    main()
