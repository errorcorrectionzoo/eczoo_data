#!/usr/bin/env python3
r"""Check every stabilizer tableau displayed in a code entry against the entry's [[n,k,d]] name.

The description of every code entry under codes/ is scanned for displayed Pauli tableaux:

* ``\begin{smallmatrix} ... \end{smallmatrix}`` and ``\begin{array}{...} ... \end{array}`` blocks whose cells are all
  I, X, Y or Z (rows separated by ``\\``, cells by ``&``);
* sentences of the form "cyclic permutations (or shifts) of the ... Pauli string \(P\)", read as all cyclic shifts of P.

For each tableau the script computes, exactly:

* n, and k = n - rank (the rows must commute);
* the stabilizer weight distribution A_j, by enumerating all 2^(n-k) stabilizer elements;
* the normalizer weight distribution B_j, by the quaternary MacWilliams identity B(x,y) = A(x+3y, x-y) / 2^(n-k);
* the distance d = min{ j >= 1 : B_j > A_j } (for k = 0, the minimum nonzero stabilizer weight), the number
  B_d - A_d of minimum-weight logical operators, and purity (A_j = 0 for 0 < j < d).

It then compares each tableau whose length matches the n in the entry's ``name`` with that [[n,k,d]], and checks a
(non)degeneracy claim made through the rule-6 link ``\hyperref[topic:quantum-weight-enumerator]{pure}`` (or
``{impure}``).  On a distance mismatch it searches for a minimum-weight logical operator and prints it as a witness.

Two explicit lists cover presentation conventions, so that nothing is waved through silently:

* ``DOUBLED_ROWS``: entries whose single-type tableau lists each support once for BOTH an X-type and a Z-type
  generator (the entry says so in prose); they are checked under that reading.
* ``GAUGE_TABLEAUX``: entries that display gauge generators of a subsystem code; their non-commuting tableaux are
  skipped.  A non-commuting tableau anywhere else is an error.

A coverage floor guards against silent no-ops: if fewer than ``--min-tableaux`` tableaux or ``--min-checks`` name
checks are found (for example because the repository root was mis-resolved or the entry format changed), the script
exits with status 2.  Pauli-like blocks that could not be parsed (signed rows, qudit powers, ...) are listed.

Computed values check transcriptions and claims; they are not a citable source (AGENTS.md rule 11).

Usage (from the repository root):
    python3 scripts/params/check_tableaux.py              # check the whole repository
    python3 scripts/params/check_tableaux.py --list       # also print one line per tableau
    python3 scripts/params/check_tableaux.py --selftest   # brute-force self-test

Exit status: 0 all checks pass; 1 a mismatch, a violated pure/impure claim, or a non-commuting stabilizer tableau;
2 coverage floor not met or usage error.  Requires Python >= 3.10 and PyYAML.
"""

from __future__ import annotations

import argparse
import itertools
import os
import re
import sys
from math import comb

import yaml

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DOUBLED_ROWS = {"stab_18_4_4", "stab_20_8_4", "stab_22_8_4"}
GAUGE_TABLEAUX = {"bacon_shor_4", "bacon_shor_9", "bravyi_bacon_shor_6"}
MIN_TABLEAUX = 50
MIN_CHECKS = 45
WITNESS_CAP = 3_000_000      # candidate Paulis examined by the witness search

NAME_RE = re.compile(r"\[\[\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\]\]")
BLOCK_RE = re.compile(r"\\begin\{(smallmatrix|array)\}(\{[^}]*\})?(.*?)\\end\{\1\}", re.S)
CYC_RE = re.compile(r"cyclic (?:permutations|shifts) of the [^.]*?Pauli string \\\(([IXYZ]+)\\\)")
PURE_LINK = r"\hyperref[topic:quantum-weight-enumerator]{pure}"
IMPURE_LINK = r"\hyperref[topic:quantum-weight-enumerator]{impure}"
PAULI_CELL = re.compile(r"^[+-]?\s*[IXYZ]$")


# ---------------------------------------------------------------------------------------------------- parsing
def parse_tableaux(text: str) -> tuple[list[list[str]], list[str]]:
    """Return (tableaux, unparsed): each tableau is a list of equal-length I/X/Y/Z strings; unparsed lists the first
    row of every block that looks like a Pauli tableau but could not be read."""
    tabs, unparsed = [], []
    for m in BLOCK_RE.finditer(text):
        rows = [r for r in re.split(r"\\\\", m.group(3)) if r.strip()]
        table, ok, pauli_like, cells_total = [], True, 0, 0
        for r in rows:
            cells = [c.strip() for c in r.split("&")]
            cells_total += len(cells)
            pauli_like += sum(1 for c in cells if PAULI_CELL.match(c))
            if not cells or any(c not in ("I", "X", "Y", "Z") for c in cells):
                ok = False
            else:
                table.append("".join(cells))
        if ok and table and len({len(t) for t in table}) == 1:
            tabs.append(table)
        elif cells_total and pauli_like >= 0.5 * cells_total:
            unparsed.append(rows[0].strip()[:60] if rows else "")
    for m in CYC_RE.finditer(text):
        p = m.group(1)
        tabs.append([p[len(p) - i:] + p[:len(p) - i] for i in range(len(p))])
    return tabs, unparsed


def doubled(table: list[str]) -> list[str]:
    """Read each row's support as both a Z-type and an X-type generator."""
    return ["".join("Z" if c != "I" else "I" for c in t) for t in table] + \
           ["".join("X" if c != "I" else "I" for c in t) for t in table]


def is_single_type(table: list[str]) -> bool:
    return all(set(t) <= {"I", "Z"} for t in table) or all(set(t) <= {"I", "X"} for t in table)


# ---------------------------------------------------------------------------------------------------- algebra
def symplectic(table: list[str]) -> list[tuple[int, int]]:
    out = []
    for s in table:
        x = sum(1 << i for i, c in enumerate(s) if c in "XY")
        z = sum(1 << i for i, c in enumerate(s) if c in "ZY")
        out.append((x, z))
    return out


def anticommute(a: tuple[int, int], b: tuple[int, int]) -> int:
    return ((a[0] & b[1]).bit_count() + (a[1] & b[0]).bit_count()) & 1


def echelon(vectors: list[int]) -> dict[int, int]:
    piv: dict[int, int] = {}
    for v in vectors:
        while v:
            p = v.bit_length() - 1
            if p in piv:
                v ^= piv[p]
            else:
                piv[p] = v
                break
    return piv


def in_span(piv: dict[int, int], v: int) -> bool:
    while v:
        p = v.bit_length() - 1
        if p not in piv:
            return False
        v ^= piv[p]
    return True


def quaternary_macwilliams(A: list[int], n: int, r: int) -> list[int]:
    """B_j = 2^-r sum_w A_w K_j(w), with the quaternary Krawtchouk polynomial K_j(w)."""
    B = []
    for j in range(n + 1):
        tot = sum(a * sum((-1) ** s * 3 ** (j - s) * comb(w, s) * comb(n - w, j - s) for s in range(j + 1))
                  for w, a in enumerate(A) if a)
        if tot % (1 << r):
            raise ArithmeticError("MacWilliams transform is not integral")
        B.append(tot >> r)
    if B[0] != 1 or sum(B) != 1 << (2 * n - r) or any(b < a for a, b in zip(A, B)):
        raise ArithmeticError("MacWilliams sanity checks failed")
    return B


def analyse(table: list[str]) -> dict:
    """Exact parameters of the stabilizer code generated by the rows of `table`."""
    n = len(table[0])
    G = symplectic(table)
    if any(anticommute(G[i], G[j]) for i in range(len(G)) for j in range(i + 1, len(G))):
        return {"commute": False, "n": n}
    piv = echelon([x | (z << n) for x, z in G])
    basis = list(piv.values())
    r = len(basis)
    k = n - r
    mask = (1 << n) - 1
    A = [0] * (n + 1)
    A[0] = 1
    cur = 0
    for i in range(1, 1 << r):                  # reflected Gray code over the stabilizer group
        cur ^= basis[(i & -i).bit_length() - 1]
        A[((cur & mask) | (cur >> n)).bit_count()] += 1
    B = quaternary_macwilliams(A, n, r)
    if k == 0:
        d = min((w for w in range(1, n + 1) if A[w]), default=0)
        n_min = A[d] if d else 0
    else:
        d = next(j for j in range(1, n + 1) if B[j] > A[j])
        n_min = B[d] - A[d]
    return {"commute": True, "n": n, "k": k, "d": d, "pure": all(A[w] == 0 for w in range(1, d)),
            "n_min_logicals": n_min, "A": A, "B": B, "_G": G, "_piv": piv}


def find_witness(res: dict, weight: int, cap: int = WITNESS_CAP) -> str | None:
    """A Pauli of the given weight that commutes with all generators and is not a stabilizer (None if the search
    would exceed `cap` candidates)."""
    n, G, piv = res["n"], res["_G"], res["_piv"]
    if comb(n, weight) * 3 ** weight > cap:
        return None
    for qubits in itertools.combinations(range(n), weight):
        for letters in itertools.product("XYZ", repeat=weight):
            x = z = 0
            for q, c in zip(qubits, letters):
                if c in "XY":
                    x |= 1 << q
                if c in "ZY":
                    z |= 1 << q
            if not any(anticommute((x, z), g) for g in G) and not in_span(piv, x | (z << n)):
                s = ["I"] * n
                for q, c in zip(qubits, letters):
                    s[q] = c
                return "".join(s)
    return None


# ---------------------------------------------------------------------------------------------------- checking
def iter_code_files(root: str):
    codes = os.path.join(root, "codes")
    for dirpath, dirnames, filenames in os.walk(codes):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for fname in sorted(filenames):
            if fname.endswith((".yml", ".yaml")):
                yield os.path.join(dirpath, fname)


def fmt(res: dict | None) -> str:
    if not res:
        return "-"
    if not res["commute"]:
        return "noncommuting"
    return f"[[{res['n']},{res['k']},{res['d']}]]"


def check_repo(root: str, list_all: bool, min_tableaux: int, min_checks: int) -> int:
    files = n_tab = n_checks = n_doubled = n_pure_checks = n_gauge = 0
    entries_with_tab = set()
    failures, unparsed_all, lines = [], [], []
    for path in iter_code_files(root):
        files += 1
        with open(path, encoding="utf-8") as f:
            try:
                entry = yaml.safe_load(f)
            except yaml.YAMLError as exc:
                failures.append(f"{os.path.relpath(path, root)}: YAML error: {exc}")
                continue
        if not isinstance(entry, dict):
            continue
        desc = entry.get("description") or ""
        tabs, unparsed = parse_tableaux(desc)
        rel = os.path.relpath(path, root)
        unparsed_all += [f"{rel}: {u}" for u in unparsed]
        if not tabs:
            continue
        code_id = str(entry.get("code_id", ""))
        entries_with_tab.add(code_id)
        m = NAME_RE.search(str(entry.get("name", "")))
        claim = tuple(map(int, m.groups())) if m else None
        claims_pure = PURE_LINK in desc
        claims_impure = IMPURE_LINK in desc
        for idx, tab in enumerate(tabs):
            n_tab += 1
            res = analyse(tab)
            use = res
            note = ""
            if not res["commute"]:
                if code_id in GAUGE_TABLEAUX:
                    n_gauge += 1
                    note = "gauge generators, skipped"
                else:
                    failures.append(f"{rel} tableau {idx}: rows do not commute (not a stabilizer group)")
                    note = "NONCOMMUTING"
            elif claim and res["n"] == claim[0]:
                n_checks += 1
                if code_id in DOUBLED_ROWS and is_single_type(tab):
                    use = analyse(doubled(tab))
                    n_doubled += 1
                    note = "doubled-row reading"
                got = (use["n"], use["k"], use["d"]) if use["commute"] else None
                if got != claim:
                    wit = find_witness(use, use["d"]) if (use["commute"] and use["k"] and use["d"] < claim[2]) else None
                    failures.append(
                        f"{rel} tableau {idx}: name says [[{claim[0]},{claim[1]},{claim[2]}]], tableau gives {fmt(use)}"
                        + (f" with {use['n_min_logicals']} minimum-weight logicals" if use["commute"] else "")
                        + (f"; witness logical {wit}" if wit else ""))
                    note = (note + "; " if note else "") + "MISMATCH"
                else:
                    note = (note + "; " if note else "") + "ok"
                if use["commute"] and (claims_pure or claims_impure):
                    n_pure_checks += 1
                    if claims_pure and not use["pure"]:
                        failures.append(f"{rel} tableau {idx}: entry says pure, but the tableau has a stabilizer of "
                                        f"weight below d={use['d']}")
                    if claims_impure and use["pure"]:
                        failures.append(f"{rel} tableau {idx}: entry says impure, but the tableau is pure")
            else:
                note = "no [[n,k,d]] of this length in the name"
            if list_all:
                lines.append(f"  {code_id:34s} #{idx} {fmt(res):16s} name {str(claim or '-'):14s} "
                             f"pure={res.get('pure', '-')!s:5s} {note}")
    if list_all:
        print("\n".join(lines))
    print(f"Scanned {files} code files under {root}: {n_tab} tableaux in {len(entries_with_tab)} entries; "
          f"{n_checks} name checks ({n_doubled} under the doubled-row reading), {n_pure_checks} pure/impure checks, "
          f"{n_gauge} gauge tableaux skipped, {len(unparsed_all)} unparsed Pauli-like blocks.")
    for u in unparsed_all:
        print(f"  unparsed: {u}")
    for fail in failures:
        print(f"  FAIL {fail}")
    if n_tab < min_tableaux or n_checks < min_checks:
        print(f"Coverage floor not met ({n_tab} < {min_tableaux} tableaux or {n_checks} < {min_checks} name checks): "
              f"check the repository root and the tableau format.")
        return 2
    if failures:
        print(f"{len(failures)} failure(s).")
        return 1
    print("All displayed tableaux agree with their entries.")
    return 0


# ---------------------------------------------------------------------------------------------------- self-test
def brute_force(table: list[str]) -> tuple[int, bool, int]:
    """(d, pure, number of minimum-weight logicals) by enumerating all 4^n Paulis (small n only)."""
    n = len(table[0])
    G = symplectic(table)
    piv = echelon([x | (z << n) for x, z in G])
    k = n - len(piv)
    logicals: dict[int, int] = {}
    stabs: dict[int, int] = {}
    for x in range(1 << n):
        for z in range(1 << n):
            if (x | z) == 0 or any(anticommute((x, z), g) for g in G):
                continue
            w = (x | z).bit_count()
            bucket = stabs if in_span(piv, x | (z << n)) else logicals
            bucket[w] = bucket.get(w, 0) + 1
    if k == 0:                                  # stabilizer state: minimum nonzero stabilizer weight
        d = min(stabs)
        return d, True, stabs[d]
    d = min(logicals)
    return d, all(w >= d for w in stabs), logicals[d]


def selftest() -> int:
    cyc = lambda p: [p[len(p) - i:] + p[:len(p) - i] for i in range(len(p))]
    steane = ["IIIXXXX", "IXXIIXX", "XIXIXIX", "IIIZZZZ", "IZZIIZZ", "ZIZIZIZ"]
    shor = ["ZZIIIIIII", "IZZIIIIII", "IIIZZIIII", "IIIIZZIII", "IIIIIIZZI", "IIIIIIIZZ", "XXXXXXIII", "IIIXXXXXX"]
    cases = {"[[4,2,2]]": (["XXXX", "ZZZZ"], (4, 2, 2)), "[[5,1,3]]": (cyc("XZZXI"), (5, 1, 3)),
             "Steane [[7,1,3]]": (steane, (7, 1, 3)), "Shor [[9,1,3]] (impure)": (shor, (9, 1, 3)),
             "Bell pair [[2,0,2]]": (["XX", "ZZ"], (2, 0, 2))}
    ok = True
    for label, (tab, want) in cases.items():
        res = analyse(tab)
        got = (res["n"], res["k"], res["d"])
        bd, bpure, bmin = brute_force(tab)
        good = got == want and res["d"] == bd and res["pure"] == bpure and res["n_min_logicals"] == bmin
        ok &= good
        print(f"  {label:26s} {fmt(res):12s} pure={res['pure']!s:5s} min-logicals={res['n_min_logicals']:<5d} "
              f"brute force: d={bd} pure={bpure}  {'ok' if good else 'FAIL'}")
    # the pure [[11,1,5]] (arXiv:quant-ph/0406063) and the distance-3 tableau this check caught in stab_11_1_5
    g11 = ["XIIIIZZZIXX", "IXIIIZZYZIY", "IIXIIZZXXZI", "IIIXIZYIXXY", "IIIIXZXIZZX", "IIZIIXYIYZZ", "IZZIIIXZIXZ",
           "IZIIZIZXXIZ", "ZZZIZIIZXZX", "IZIZIIZIZXX"]
    old = ["ZZZZZZIIIII", "XXXXXXIIIII", "IIIZXYYYYXZ", "IIIXYZZZZYX", "ZYXIIIZYXII", "XZYIIIXZYII", "IIIZYXXYZII",
           "IIIXZYZXYII", "ZXYIIIZZZXY", "YZXIIIYYYZX"]
    r1, r2 = analyse(g11), analyse(old)
    good = (r1["k"], r1["d"], r1["pure"], r1["n_min_logicals"]) == (1, 5, True, 198)
    ok &= good
    print(f"  {'pure [[11,1,5]]':26s} {fmt(r1):12s} pure={r1['pure']!s:5s} min-logicals={r1['n_min_logicals']:<5d} "
          f"{'ok' if good else 'FAIL'}")
    wit = find_witness(r2, r2["d"])
    good = (r2["k"], r2["d"], r2["n_min_logicals"]) == (1, 3, 3) and wit is not None
    ok &= good
    print(f"  {'old stab_11_1_5 tableau':26s} {fmt(r2):12s} witness {wit}  {'ok (caught)' if good else 'FAIL'}")
    # parser: array + smallmatrix + cyclic sentence + a signed (unparsed) block; doubled reading
    text = (r"\begin{align}\begin{array}{cccc} X & X & X & X \\ Z & Z & Z & Z \end{array}\end{align}"
            r" and \(\left(\begin{smallmatrix} X & Z \\ Z & X \end{smallmatrix}\right)\)"
            r" generated by cyclic permutations of the weight-four Pauli string \(XZZXI\)."
            r" \begin{array}{cc} -X & X \\ Z & Z \end{array}")
    tabs, unparsed = parse_tableaux(text)
    good = len(tabs) == 3 and len(unparsed) == 1 and analyse(tabs[2])["d"] == 3
    good &= fmt(analyse(doubled(["XXXX"]))) == "[[4,2,2]]"
    ok &= good
    print(f"  {'parser + doubled reading':26s} {len(tabs)} tableaux, {len(unparsed)} unparsed  {'ok' if good else 'FAIL'}")
    print("selftest", "passed" if ok else "FAILED")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="print one line per tableau")
    ap.add_argument("--selftest", action="store_true", help="run the brute-force self-test and exit")
    ap.add_argument("--root", default=REPO_ROOT, help="repository root (default: this repository)")
    ap.add_argument("--min-tableaux", type=int, default=MIN_TABLEAUX, help="coverage floor on parsed tableaux")
    ap.add_argument("--min-checks", type=int, default=MIN_CHECKS, help="coverage floor on name checks")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not os.path.isdir(os.path.join(args.root, "codes")):
        print(f"No codes/ directory under {args.root}.")
        return 2
    return check_repo(args.root, args.list, args.min_tableaux, args.min_checks)


if __name__ == "__main__":
    sys.exit(main())
