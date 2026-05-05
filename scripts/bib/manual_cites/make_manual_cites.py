#!/usr/bin/env python3
"""
Create resources/manual_cites.txt with two tab-separated columns:
  col1: original citation text (from manual_cites.txt)
  col2: edited version with full first/middle names abbreviated to initials

Run this script whenever manual_cites.txt is regenerated, then review
manual_cites.txt and make manual corrections before running apply_manual_cites.py.
"""

import re
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT = os.path.join(ROOT, "resources", "manual_cites.txt")
OUTPUT = os.path.join(ROOT, "resources", "manual_cites.txt")

# Capitalized words that are NOT person given names
STOP = {
    # Articles, prepositions, conjunctions
    'The', 'On', 'In', 'An', 'At', 'By', 'For', 'And', 'Or', 'But', 'With',
    'From', 'To', 'Of', 'As', 'Is', 'It', 'Its', 'No', 'Not', 'All', 'Any',
    'New', 'Old', 'Also', 'Here', 'When', 'That', 'This', 'These', 'Those',
    # Academic venue / publication words
    'Annual', 'International', 'National', 'Conference', 'Workshop', 'Symposium',
    'Proceedings', 'Journal', 'Transactions', 'Letters', 'Report', 'Technical',
    'Research', 'Laboratory', 'University', 'Institute', 'Department', 'School',
    'Press', 'Book', 'Volume', 'Issue', 'Part', 'Chapter', 'Lecture', 'Lectures',
    'Seminar', 'Tutorial', 'Bulletin', 'Preprint', 'Draft', 'Manuscript',
    'Published', 'Unpublished', 'Available', 'Accessed', 'Online',
    # Common title words
    'Introduction', 'Survey', 'Review', 'Note', 'Notes', 'Remark', 'Remarks',
    'Problem', 'Problems', 'Solution', 'Solutions', 'Bound', 'Bounds',
    'Method', 'Methods', 'Algorithm', 'Algorithms', 'Application', 'Applications',
    'Analysis', 'Construction', 'Constructions', 'Characterization',
    'Classification', 'Generalization', 'Extension', 'Theory', 'Practice',
    'Approach', 'Coding', 'Decoding', 'Encoding', 'Error', 'Correction',
    'Detection', 'Recovery', 'Information', 'Communication', 'Computation',
    'Computing', 'Quantum', 'Classical', 'Digital', 'Linear', 'Nonlinear',
    'Algebraic', 'Geometric', 'Binary', 'Ternary', 'Cyclic', 'Perfect',
    'Optimal', 'Uniform', 'Random', 'Code', 'Codes', 'Graph', 'Groups',
    'Lattice', 'Space', 'Sphere', 'Block', 'Channel', 'Network', 'System',
    'Model', 'Design', 'Signal', 'Signals', 'Sequence', 'Sequences',
    'Structure', 'Structures', 'Property', 'Properties', 'Pattern', 'Patterns',
    'Torus', 'Surface', 'Manifold', 'Variety', 'Topics', 'Elements',
    'Basics', 'Foundations', 'Principles', 'Concepts', 'Fundamentals',
    'Advanced', 'Modern', 'Applied', 'Pure', 'Theoretical', 'Practical',
    'Minimum', 'Maximum', 'Near', 'Approximate', 'Exact',
    'Efficient', 'Reliable', 'Robust', 'Secure', 'Stable',
    'Compact', 'Dense', 'Sparse', 'Short', 'Long', 'High', 'Low',
    'Strong', 'Weak', 'Hard', 'Soft', 'Simple', 'Complex', 'Fast',
    'First', 'Second', 'Third', 'Fourth', 'Fifth',
    'Multiple', 'Single', 'Finite', 'Infinite', 'General', 'Special',
    'Extended', 'Generalized', 'Modified', 'Improved',
    'Distributed', 'Parallel', 'Sequential', 'Adaptive', 'Compressed',
    # Nationality / organisation / place adjectives
    'American', 'European', 'Russian', 'Soviet', 'French', 'German', 'Dutch',
    'British', 'Japanese', 'Chinese', 'Italian', 'Swedish', 'Finnish',
    'Mathematical', 'Physical', 'Statistical', 'Engineering', 'Computer',
    'Cambridge', 'Oxford', 'Princeton', 'Stanford', 'Harvard', 'Cornell',
    'Springer', 'Elsevier', 'Wiley', 'Kluwer',
    # Named-after adjectives used as common nouns in math/CS
    'Euclidean', 'Boolean', 'Gaussian', 'Hamming', 'Shannon', 'Turing',
    'Fourier', 'Hilbert', 'Galois', 'Stirling', 'Fibonacci', 'Cayley',
    'Steiner', 'Goppa', 'Reed', 'Solomon',
    # Months
    'January', 'February', 'March', 'April', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
    # Additional common words that appear after 'and' in titles/venues
    'Their', 'Data', 'Coherent', 'Combinatorial', 'Technology', 'Technologies',
    'Sciences', 'Systems', 'Operations', 'Techniques', 'Aspects', 'Related',
    'Computing', 'Processing', 'Capture', 'Acquisition', 'Storage',
    # Surname particles (not given names)
    'Von', 'Van', 'Der', 'Den', 'Sur', 'Les',
}


def is_full_given_name(word: str) -> bool:
    """True if word looks like an unabbreviated given name (not already an initial)."""
    return bool(re.match(r'^[A-Z][a-z]{2,}$', word)) and word not in STOP


def to_initial(word: str) -> str:
    return word[0] + '.'


# Known multi-letter abbreviations that should NOT be split by fix_run_together_initials.
# We protect them BEFORE expansion and restore AFTER, so only run-together person
# initials (which originally have NO spaces) are affected.
# Each entry: (pattern_to_find_in_original, placeholder, original_form)
_PROTECT_ABBREVS = [
    # Order matters: longer patterns first to avoid partial matches
    (r'\bU\.S\.S\.R\.', '_PH_USSR_', 'U.S.S.R.'),
    (r'\bU\.P\.C\.', '_PH_UPC_', 'U.P.C.'),
    (r'\bM\.I\.T\.', '_PH_MIT_', 'M.I.T.'),
    (r'\bU\.S\.', '_PH_US_', 'U.S.'),
    (r'\bU\.K\.', '_PH_UK_', 'U.K.'),
    # N.S. = "New Series" in journal names, usually inside (N.S.)
    (r'\bN\.S\.', '_PH_NS_', 'N.S.'),
]


def fix_run_together_initials(s: str) -> str:
    """X.Y. -> X. Y. for person initials only, protecting known non-person abbreviations."""
    # Step 1: protect known abbreviations that appear WITHOUT spaces in the original
    for pattern, placeholder, _ in _PROTECT_ABBREVS:
        s = re.sub(pattern, placeholder, s)
    # Step 2: expand any remaining run-together initials (these are person initials)
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r'\b([A-Z])\.([A-Z]\.)', r'\1. \2', s)
    # Step 3: restore protected abbreviations to their original forms
    for _, placeholder, original in _PROTECT_ABBREVS:
        s = s.replace(placeholder, original)
    return s


def find_author_region_end(s: str) -> int:
    """
    Return the index where the author region likely ends.
    We look for strong indicators that a title or venue string has begun.
    Only abbreviate names before this point.
    """
    # Match both ASCII " and Unicode curly left/right double-quotes
    Q = r'["\u201c\u201d]'

    # Strong title/venue start indicators (in order of reliability)
    indicators = [
        rf',\s*{Q}',             # , "Title...  (ASCII or curly quote)
        rf'\.\s*{Q}',            # . "Title...
        r'\.\s*\\emph\{',        # . \emph{Title}
        r'\.\s*\\href\{',        # . \href{url}
        r'\s+\(\d{4}\b',         # (year)
        r',\s*\d{4}[,.]',        # , year.  or  , year,
        r':\s+[A-Z][a-z]',       # : Subtitle  (colon introduces subtitle/description)
    ]
    end = len(s)
    for pat in indicators:
        m = re.search(pat, s)
        if m and m.start() > 0:
            end = min(end, m.start())
    # Never go beyond 250 chars (generous upper bound for an author list)
    return min(end, 250)


def abbreviate_in_author_region(region: str) -> str:
    """
    Within the author region, abbreviate full given names.

    Safe positions:
      1. At the very start of the string (first given name)
      2. After ' and ' (subsequent author given names)

    We deliberately do NOT touch names after ', ' because commas also appear
    in addresses, journal names, etc. — the risk of false positives is too high.
    """
    def maybe_abbrev(word: str) -> str:
        return to_initial(word) if is_full_given_name(word) else word

    # Position 1: full given name at start of string, followed by a space
    region = re.sub(
        r'^([A-Z][a-z]{2,})(?=\s)',
        lambda m: maybe_abbrev(m.group(1)),
        region,
    )

    # Position 2: after ' and ' (repeatedly, to catch 3rd+ authors)
    prev = None
    while prev != region:
        prev = region
        region = re.sub(
            r'(\band\s+)([A-Z][a-z]{2,})(?=\s)',
            lambda m: m.group(1) + maybe_abbrev(m.group(2)),
            region,
        )

    return region


def abbreviate_names(s: str) -> str:
    s = fix_run_together_initials(s)
    end = find_author_region_end(s)
    return abbreviate_in_author_region(s[:end]) + s[end:]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
with open(INPUT, encoding='utf-8') as f:
    lines = [line.rstrip('\n') for line in f]

with open(OUTPUT, 'w', encoding='utf-8') as f:
    for original in lines:
        edited = abbreviate_names(original)
        f.write(original + '\t' + edited + '\n')

changed = sum(1 for line in lines if abbreviate_names(line) != line)
print(f"Wrote {len(lines)} entries to {OUTPUT}  ({changed} lines changed)")
