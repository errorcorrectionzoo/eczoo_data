#!/usr/bin/env python3
"""
For every manual:{...} citation used in more than one file, create a preset
entry in bib_preset.yml and replace \cite{...,manual:{text},...} with
\cite{...,preset:KEY,...}.

Usage:
    python3 promote_manual_to_preset.py          # dry-run: print proposed keys
    python3 promote_manual_to_preset.py --apply  # actually modify files
"""

import os, re, sys, unicodedata, collections

APPLY = "--apply" in sys.argv
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRESET_FILE = os.path.join(ROOT, "code_extra", "bib_preset.yml")

def extract_manual_cites(text):
    results = []
    search_from = 0
    while True:
        idx = text.find("manual:{", search_from)
        if idx == -1:
            break
        start = idx + len("manual:{")
        depth = 1; pos = start
        while pos < len(text) and depth > 0:
            if text[pos] == "{": depth += 1
            elif text[pos] == "}": depth -= 1
            pos += 1
        results.append(text[start:pos - 1])
        search_from = pos
    return results

_Q = r'["\u201c\u201d]'
_KEY_STOPS = {
    'On','In','An','At','By','For','The','A','Codes','Code','Coding',
    'Decoding','Locality','Fault','Approximate','Compact','Common',
    'Self','Some','Bounds','Every','Multi','Low','Probabilistic',
    'Graph','Practical','Near','Class','Stable','Nonergodic','Uniform',
    'Introduction','Theory',
}
_CITE_KEY_OVERRIDES = {
    "The LMFDB Collaboration":                     "LMFDB",
    "S. T. Position.":                             "DDFspec09",
    "P. G\u00e1cs,":                               "Gacs89",
    "P. Charpin. Codes":                           "Charpin82",
    "M. Webster. The XP":                          "Webster23",
    "Y. Li. Codeword":                             "Li10",
    "D. Maurice. Codes":                           "Maurice21",
    "H. Weyl. The theory":                         "Weyl50",
    "F. A. Berazin. The method":                   "Berazin12",
    "C. Derby. Compact":                           "Derby23",
    "A. W. Cross. Fault-tolerant":                 "Cross09",
    "A. H. Stroud. Approximate":                   "Stroud71",
    "T. Gosset,":                                  "Gosset1900",
    "L. Schl\u00e4fli":                            "Schlafli1901",
    "S. Gopi. Locality":                           "Gopi18",
    "M. Heinrich. On":                             "Heinrich21",
    "E. Campbell, \u201cThe smallest":             "Campbell16",
    "V. V. Albert, private communication, 2025":   "albertPC25",
    "V. V. Albert, private communication, 2024":   "albertPC24",
    "V. V. Albert, \\href{https://boulderschool":  "albertBoulder21",
    "A. Kubica, private communication":            "kubicaPC19",
    "E. Knill, private communication":             "KnillPC98",
    "M. B. Hastings, LR codes":                    "HastingsLR14",
    "N. P. Breuckmann, private communication":     "BreuckmannPC22",
    "D. Browne, \\href":                           "BrowneNotes",
    "A. Leverrier, \\href":                        "LeverrierNotes",
    "R. B. Griffiths":                             "GriffithsGS",
    "M. Grassl, private communication":            "GrasslPC24",
    "G. V. Kalachev and P. A. Panteleev":          "KalachevPanteleev20",
    "M. Yu. Rosenbloom":                            "Rosenbloom97",
    "T. Kl\u00f8ve":                                "Klove81",
}

def to_ascii(s):
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return s.encode('ascii', 'ignore').decode('ascii')

def author_region_end(cite):
    indicators = [
        rf',\s*{_Q}', rf'\.\s*{_Q}', r'\.\s*\\emph\{', r'\.\s*\\href\{',
        r'\s+\(\d{4}\b', r',\s*\d{4}[,.]', r':\s+[A-Z][a-z]',
    ]
    end = len(cite)
    for pat in indicators:
        m = re.search(pat, cite)
        if m and m.start() > 0:
            end = min(end, m.start())
    return min(end, 200)

def first_author_lastname(cite):
    region = cite[:author_region_end(cite)]
    s = re.sub(r'^(?:[A-Z](?:-[A-Z])?\.[ \t]*)+', '', region.strip())
    m = re.match(r'([A-Z][a-z][\w-]*)', s)
    if m:
        lastname = m.group(1)
        if lastname not in _KEY_STOPS:
            return to_ascii(lastname)
    return "Unknown"

def extract_year(cite):
    m = re.search(r'\b(1[89]\d\d|20[012]\d)\b', cite)
    if not m:
        return ""
    year = m.group(1)
    return year if int(year) < 1910 else year[-2:]

def make_key(cite, used, existing):
    for prefix, key in _CITE_KEY_OVERRIDES.items():
        if cite.startswith(prefix):
            return key
    lastname = first_author_lastname(cite)
    year = extract_year(cite)
    base = lastname + year
    key = base
    suffix = ord('b')
    while key in used or key in existing:
        key = base + chr(suffix)
        suffix += 1
    return key

# Walk files
counts = collections.Counter()
file_contents = {}
for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if not d.startswith(".")]
    for fname in filenames:
        if not fname.endswith(".yml"): continue
        fpath = os.path.join(dirpath, fname)
        relpath = os.path.relpath(fpath, ROOT)
        if relpath == "code_extra/bib_preset.yml": continue
        with open(fpath, encoding="utf-8") as f:
            text = f.read()
        file_contents[fpath] = text
        for cite in set(extract_manual_cites(text)):
            counts[cite] += 1

multi_cited = {c: n for c, n in counts.items() if n > 1}
print(f"Found {len(multi_cited)} manual citations used in more than one file.\n")

with open(PRESET_FILE, encoding="utf-8") as f:
    preset_text = f.read()
existing_keys = set(re.findall(r'^([A-Za-z][A-Za-z0-9_-]+):', preset_text, re.MULTILINE))

used_keys = set()
cite_to_key = {}
for cite, count in sorted(multi_cited.items(), key=lambda x: -x[1]):
    key = make_key(cite, used_keys, existing_keys)
    used_keys.add(key)
    cite_to_key[cite] = key

print(f"{'KEY':<32}  {'FILES':>5}  CITATION (first 80 chars)")
print("-" * 122)
for cite, key in sorted(cite_to_key.items(), key=lambda x: -multi_cited[x[0]]):
    print(f"{key:<32}  {multi_cited[cite]:>5}  {cite[:80]}")

if not APPLY:
    print("\n(Dry run. Pass --apply to modify files.)")
    sys.exit(0)

# Append to bib_preset.yml
new_entries = []
for cite, key in sorted(cite_to_key.items(), key=lambda x: x[1]):
    new_entries.append(f"\n{key}:\n  _ready_formatted:\n    flm: >-\n      {cite}\n")

with open(PRESET_FILE, "a", encoding="utf-8") as f:
    f.write("\n# --- auto-promoted from manual citations ---\n")
    for e in new_entries:
        f.write(e)
print(f"\nAppended {len(new_entries)} entries to {os.path.relpath(PRESET_FILE, ROOT)}.")

# Replace in YML files
total = 0; changed = 0
for fpath, original in file_contents.items():
    if "manual:{" not in original: continue
    result = []; search_from = 0; n = 0; text = original
    while True:
        idx = text.find("manual:{", search_from)
        if idx == -1:
            result.append(text[search_from:]); break
        result.append(text[search_from:idx])
        start = idx + len("manual:{")
        depth = 1; pos = start
        while pos < len(text) and depth > 0:
            if text[pos] == "{": depth += 1
            elif text[pos] == "}": depth -= 1
            pos += 1
        inner = text[start:pos - 1]
        if inner in cite_to_key:
            result.append(f"preset:{cite_to_key[inner]}"); n += 1
        else:
            result.append(f"manual:{{{inner}}}")
        search_from = pos
    updated = "".join(result)
    if updated != original:
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(updated)
        print(f"  {os.path.relpath(fpath, ROOT)}  ({n})")
        changed += 1; total += n

print(f"\nDone. {total} replacement(s) in {changed} file(s).")
