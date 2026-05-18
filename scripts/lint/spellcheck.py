#!/usr/bin/env python3
"""Spell-check plain-English text in ECC Zoo YAML files using codespell.

LaTeX math environments, citation macros, and cross-reference commands are
stripped before checking so only genuine prose reaches the spell checker.

Usage:
  python scripts/lint/spellcheck.py                         # check all codes/
  python scripts/lint/spellcheck.py codes/quantum/qubits/   # specific subtree
  python scripts/lint/spellcheck.py --wordlist extra.txt    # extra word whitelist
"""

import argparse
import os
import re
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


def run_spellcheck(search_path: str, wordlist: str | None) -> int:
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

        cmd = ["codespell", tmpdir]
        if wordlist and os.path.isfile(wordlist):
            cmd += ["--ignore-words", wordlist]

        result = subprocess.run(cmd, capture_output=True, text=True)
        output = result.stdout + result.stderr

        for line in output.splitlines():
            # codespell line format:  /path/to/file.txt:N: word ==> correction
            colon_parts = line.split(":", 2)
            if len(colon_parts) < 3:
                continue
            tmp_path_raw = os.path.normpath(colon_parts[0])
            lineno = colon_parts[1].strip()
            message = colon_parts[2].strip()

            orig = path_map.get(tmp_path_raw)
            if orig:
                rel = os.path.relpath(orig, ROOT)
                print(f"{rel}:{lineno}: {message}")
            else:
                print(line)
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
    args = parser.parse_args()

    if not os.path.exists(args.path):
        print(f"Error: path not found: {args.path}", file=sys.stderr)
        sys.exit(1)

    count = run_spellcheck(args.path, args.wordlist)
    print(f"\nFound {count} spelling issue(s).")
    sys.exit(0 if count == 0 else 1)


if __name__ == "__main__":
    main()
