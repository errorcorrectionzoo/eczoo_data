#!/usr/bin/env python3
r"""
Standardize manual_cites.txt second column:
1. \emph{}, \textit{} -> "..."
2. Author names: "Last, First Middle" at start of citation -> "F. M. Last"
3. Journal abbreviations -> full names
"""
import re
from pathlib import Path

INPUT = Path(__file__).resolve().parent.parent / "resources" / "manual_cites.txt"

# ---------------------------------------------------------------------------
# 1. LaTeX fixes
# ---------------------------------------------------------------------------

def fix_latex(text: str) -> str:
    # \emph{text}, \textit{text} -> "text"
    text = re.sub(r'\\(?:emph|textit)\{([^}]*)\}', r'"\1"', text)
    return text

# ---------------------------------------------------------------------------
# 2. Author name conversion
# ---------------------------------------------------------------------------

_CAP   = r'[A-ZÁÉÍÓÚÀÈÙÄÖÜÑČŠŽĆĐ]'
_LOW   = r'[a-záéíóúàèùäöüñčšžćđß\-]'
_ALPHA = r'[a-záéíóúàèùäöüñčšžćđß]'   # lowercase letters, no hyphen (for surname parts)

# Last name: one or two hyphenated words, no spaces
# e.g. "Smith"  "Duclos-Cianci"
_LAST_PAT = rf'{_CAP}{_ALPHA}+(?:-{_CAP}{_ALPHA}+)?'

# First token of given-name field (order matters — most specific first):
#   1. Hyphenated initial:      "K-M."       {_CAP}-{_CAP}.
#   2. Plain initial:           "E."         {_CAP}.
#   3. Compound hyphenated name "Kao-Yueh"   {_CAP}{_ALPHA}+-{_CAP}{_ALPHA}+
#   4. Full first name:         "Elwyn"      {_CAP}{_ALPHA}{2+}   (2+ alpha so "K-" won't match)
# Rest tokens: zero or more period-terminated tokens ("N." "Peter." etc.)
# Trailing \s* captures optional whitespace so we can preserve it.
_FNAME_PAT = (
    rf'(?:{_CAP}-{_CAP}\.|{_CAP}\.|{_CAP}{_ALPHA}+-{_CAP}{_ALPHA}+|{_CAP}{_ALPHA}{{2,}})'
    rf'(?:\s+{_CAP}{_LOW}*\.)*'    # rest (period-terminated)
    rf'\s*'                         # trailing space
)

# Negative lookbehinds:
#   [A-Z]\.  - preceded by an initial, e.g. "D. Bartoli," should NOT re-invert
#   [a-z]\   - preceded by a full-word name end, e.g. "Aaron Gulliver," should NOT invert
_INV_RE = re.compile(
    rf'(?<![A-Z]\. )(?<![A-Z]\.)(?<![a-z] )({_LAST_PAT}),\s+({_FNAME_PAT})'
)


def _parts_to_initials(given: str) -> str:
    """
    'John A.'  -> 'J. A.'
    'N. N.'    -> 'N. N.'
    'K-M.'     -> 'K.-M.'
    'Yu.'      -> 'Yu.'    (2-char abbreviations preserved)
    'Peter.'   -> 'P.'     (longer abbreviated names reduced)
    """
    tokens = re.split(r'\s+', given.strip())
    out = []
    for tok in tokens:
        if not tok:
            continue
        tok_clean = tok.strip('.,')
        if not tok_clean:
            continue
        # Hyphenated initial: "K-M" or "K-M." -> "K.-M."
        if re.fullmatch(r'[A-ZÁÉÍÓÚ]-[A-ZÁÉÍÓÚ]', tok_clean):
            parts = tok_clean.split('-')
            out.append('-'.join(p + '.' for p in parts))
        # Compound hyphenated full name: "Kao-Yueh" -> "K.-Y."
        elif '-' in tok_clean and re.fullmatch(rf'{_CAP}{_ALPHA}+-{_CAP}{_ALPHA}+', tok_clean):
            parts = tok_clean.split('-')
            out.append('-'.join(p[0].upper() + '.' for p in parts))
        # One-or-two-char abbreviation with period: "N." "Yu." -> keep as-is
        elif tok.endswith('.') and len(tok_clean) <= 2:
            out.append(tok_clean + '.')
        # Full name or longer abbreviated name -> reduce to first initial
        else:
            out.append(tok_clean[0].upper() + '.')
    return ' '.join(out)


def _author_reformat(m: re.Match) -> str:
    last  = m.group(1)
    given = m.group(2)
    # If given ended on a bare hyphen the regex ate only part of a compound name — skip
    if given.rstrip().endswith('-'):
        return m.group(0)
    trailing = ' ' if given.endswith(' ') else ''
    initials = _parts_to_initials(given.rstrip())
    return initials + ' ' + last + trailing


def _find_author_end(text: str) -> int:
    """
    Return index where the author list ends (exclusive), or -1 if unclear.
    Only handles two clear patterns:
      A) '. "Title'  - period-space-quote
      B) ' (YYYY).'  - year in parens within first 200 chars (author-year style)
    """
    # Pattern A: period followed by space and opening quote
    m = re.search(r'\.\s+"', text)
    if m:
        return m.start() + 1   # include the period

    # Pattern B: "(year)." within first ~200 chars of the line
    m = re.search(r'\s+\(\d{4}[a-z]?\)\.', text[:200])
    if m:
        return m.start()

    return -1


def convert_inverted_authors(text: str) -> str:
    """
    If citation starts with a SINGLE-word surname followed by a comma,
    detect the author/title boundary and convert 'Last, F. M.' patterns.
    Otherwise return text unchanged.
    """
    # Only trigger when the very first word (single word, no space) is a surname
    if not re.match(rf'^{_LAST_PAT},\s', text):
        return text

    end = _find_author_end(text)
    if end < 0:
        # No clear boundary found - leave unchanged to avoid corruption
        return text

    author_part = text[:end]
    rest_part   = text[end:]

    converted = _INV_RE.sub(_author_reformat, author_part)

    # Only normalise separators if conversion actually happened
    if converted != author_part:
        # Order matters: handle ", &" before plain "&", then resulting ", and"
        converted = re.sub(r',?\s+&\s+',  ' and ', converted)
        converted = re.sub(r',\s+and\s+', ' and ', converted)

    return converted + rest_part

# ---------------------------------------------------------------------------
# 3. Journal / venue abbreviation expansions
# ---------------------------------------------------------------------------

JOURNAL_MAP = [
    # PIT variants (lines 1-24 col2 already expanded; catches residual col1 copies)
    (r'Probl\.\s+Peredach(?:i\.|\.)\s*Inform(?:acii|\.)',
     "Problemy Peredachi Informatsii"),
    (r'Probl\.\s+Peredachi\s+Inf\.',
     "Problemy Peredachi Informatsii"),
    (r'Problemy\s+Peredachi\s+Informacii\b',
     "Problemy Peredachi Informatsii"),
    (r'Problems?\s+Inform\.\s+Transm(?:ission)?\.?',
     "Problems of Information Transmission"),
    (r'PROB\.\s+INFO\.\s+TRANSMISSION',
     "Problems of Information Transmission"),
    (r'Prob\.\s+Inf\.\s+Transmission',
     "Problems of Information Transmission"),
    (r'Probl\.\s+Inform\.\s+Transm\b',
     "Problems of Information Transmission"),
    # Soviet math (handle both abbreviated and already-spelled-out-but-wrong-case forms)
    (r'Soviet\s+[Pp]hysics\s+[Dd]okl(?:ady)?\.?', "Soviet Physics Doklady"),
    (r'Soviet\s+[Mm]ath(?:ematics)?\.\s+[Dd]okl(?:ady)?\.?', "Soviet Mathematics Doklady"),
    (r'Sov\.\s+Math\.\s+Dokl\.?',               "Soviet Mathematics Doklady"),
    # Russian journals
    (r'Dokl\.\s+Akad\.\s+Nauk\s+SSSR',         "Doklady Akademii Nauk SSSR"),
    (r'Trudy\s+Mat\.\s+Inst\.\s+Steklov\.',
     "Trudy Matematicheskogo Instituta imeni V. A. Steklova"),
    (r'Izv\.\s+Akad\.\s+Nauk\s+SSSR\s+Ser\.\s+Mat\.',
     "Izvestiya Akademii Nauk SSSR, Seriya Matematicheskaya"),
    (r'Izv\.\s+Math\.',                         "Izvestiya Mathematics"),
    (r'Algebra\s+i\s+Analiz\b',                 "Algebra i Analiz"),
    (r'Funktsional\.\s+Anal\.\s+i\s+Prilozhen\.',
     "Funktsional'nyi Analiz i ego Prilozheniya"),
    (r'Funkts?ional\.\s+Anal\.\s+i\s+Prilozhen\.',
     "Funktsional'nyi Analiz i ego Prilozheniya"),
    (r'Diskr\.\s+Mat\.',                        "Diskretnaya Matematika"),
    (r'Diskretn\.\s+Anal\.\s+Issled\.\s+Oper\.',
     "Diskretnyi Analiz i Issledovanie Operatsii"),
    (r'Probl\.\s+Kibernet\.',                   "Problemy Kibernetiki"),
    (r'Problemy\s+Kibernet\b(?!iki)',            "Problemy Kibernetiki"),
    (r'St\.\s+Petersburg\s+Math\.\s+J\.',       "St. Petersburg Mathematical Journal"),
    (r'Proc\.\s+Steklov\s+Inst\.\s+Math\.',
     "Proceedings of the Steklov Institute of Mathematics"),
    # Western journals
    (r'Philips\s+Res\.\s+Rep\.',                "Philips Research Reports"),
    (r'Autom\.\s+Remote\s+Control',             "Automation and Remote Control"),
    (r'Proc\.\s+IEEE\b',                        "Proceedings of the IEEE"),
    (r'Funct\.\s+Anal\.\s+Appl\.',              "Functional Analysis and Its Applications"),
    (r'Discrete\s+Math\.\s+Appl\.',             "Discrete Mathematics and Applications"),
]


def expand_journals(text: str) -> str:
    for pat, repl in JOURNAL_MAP:
        text = re.sub(pat, repl, text)
    return text

# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------

def transform(col2: str) -> str:
    col2 = fix_latex(col2)
    col2 = convert_inverted_authors(col2)
    col2 = expand_journals(col2)
    return col2


def process_line(line: str) -> str:
    line = line.rstrip('\n')
    if '\t' in line:
        col1, col2 = line.split('\t', 1)
    else:
        col1 = line
        col2 = line

    new_col2 = transform(col2)

    if new_col2 == col1:
        return col1          # nothing changed - no second column needed
    return col1 + '\t' + new_col2


def main():
    lines = INPUT.read_text(encoding='utf-8').splitlines()
    result = []
    changed = 0
    for raw in lines:
        out = process_line(raw)
        result.append(out)
        orig_col2 = raw.split('\t', 1)[1] if '\t' in raw else raw
        new_col2  = out.split('\t', 1)[1] if '\t' in out else out
        if new_col2 != orig_col2:
            changed += 1
    INPUT.write_text('\n'.join(result) + '\n', encoding='utf-8')
    print(f"Done - modified second column on {changed} lines (total {len(lines)} entries)")


if __name__ == '__main__':
    main()
