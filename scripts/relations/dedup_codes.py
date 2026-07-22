#!/usr/bin/env python3
"""Certified CSS-code equivalence / database dedup.

The stabilizer weight enumerator is invariant under local Clifford and qubit
permutation, so *different* enumerators prove inequivalence.  Equal enumerators
prove nothing -- which is why this is a two-stage procedure and not a hash:

  1. bucket codes by the invariant (exact `2^{n-k}` enumeration when
     `n-k <= exact_cap`, otherwise the truncated weight-`<= w` multiset, which is
     invariant for the same reason);
  2. inside a bucket, run an actual **permutation-equivalence test** on the
     coloured Tanner graph via nauty (`pynauty`), which returns a certificate;
  3. deduplicate only certified-equivalent pairs.  Everything else stays.

Scope of the certificate: this certifies CSS **permutation** equivalence, i.e.,
the two check presentations are related by a single qubit permutation applied to
both `C_X` and `C_Z` (with the X-checks permuted among themselves and the
Z-checks among themselves; the X/Z blocks are NOT swapped).  Two consequences:
  * Equal certificate PROVES permutation equivalence (sound merge direction).
  * The certificate is a property of the given generator presentation, not of the
    rowspace: the same code presented with a different (row-equivalent) generating
    set may get a different certificate.  So an unequal certificate proves the two
    *presentations* are not permutation-isomorphic, NOT that the codes are
    inequivalent.  Feed reduced/canonical generators if you want the negative
    direction to be meaningful.
Full local-Clifford equivalence is strictly coarser and is NOT claimed -- codes
left separate here may still be LC-equivalent, which is the safe direction: a
missed merge costs time, a wrong merge would transplant a verdict onto a code
that does not have it.

Usage:
  dedup_codes.py --selftest              # built-in equivalence assertions
  dedup_codes.py --json codes.json       # dedup a list of codes
      where codes.json is [{"label","n","CX":[[..]],"CZ":[[..]]}, ...]
      or {"label": {"n","CX","CZ"}, ...}
"""
import json, sys, argparse
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent


# ------------------------------------------------------------------ invariants
def stab_weight_enumerator(CX, CZ, n, exact_cap=18, chunk_bits=16):
    """multiset of support weights of all 2^{n-k} stabilizer elements.

    Returns (kind, tuple).  `kind` is "exact" or "truncated"; the truncated form
    keeps only weights <= w and is still an LC+permutation invariant, because a
    weight-<=w element maps to a weight-<=w element.

    The exact path is CHUNKED: materialising all `2^m` vectors at once is
    `2^m x 2n` bytes -- 800 MB at m=24 -- which is a memory bomb, not a hash."""
    rows = np.concatenate([np.concatenate([CX, np.zeros_like(CX)], axis=1),
                           np.concatenate([np.zeros_like(CZ), CZ], axis=1)])
    m = rows.shape[0]
    if m <= exact_cap:
        lo = min(chunk_bits, m)
        base = np.zeros((1, 2 * n), dtype=np.uint8)
        for r in rows[:lo]:                        # 2^lo vectors, bounded
            base = np.concatenate([base, base ^ r[None, :]], axis=0)
        counts = {}
        hi = rows[lo:]
        for mask in range(1 << (m - lo)):          # stream the high bits
            off = np.zeros(2 * n, dtype=np.uint8)
            mm, bi = mask, 0
            while mm:
                if mm & 1:
                    off = off ^ hi[bi]
                mm >>= 1
                bi += 1
            blk = base ^ off[None, :]
            sup = (blk[:, :n] | blk[:, n:]).sum(axis=1)
            vals, cnts = np.unique(sup, return_counts=True)
            for v, c in zip(vals.tolist(), cnts.tolist()):
                counts[v] = counts.get(v, 0) + c
        return "exact", tuple(sorted(counts.items()))
    # truncated: low-weight elements only, by bounded-depth combination search
    w = 8
    seen = {}
    base = [r for r in rows]
    from itertools import combinations
    for depth in range(1, 4):
        for comb in combinations(range(m), depth):
            v = np.zeros(2 * n, dtype=np.uint8)
            for i in comb:
                v ^= base[i]
            sw = int((v[:n] | v[n:]).sum())
            if sw <= w:
                seen[sw] = seen.get(sw, 0) + 1
    return "truncated", tuple(sorted(seen.items()))


# ---------------------------------------------------- certified equivalence
def css_graph(CX, CZ, n):
    """coloured graph whose automorphisms/isomorphisms are exactly the
    simultaneous permutations of C_X and C_Z (qubits one colour class, X checks
    another, Z checks a third)."""
    import pynauty
    mx, mz = CX.shape[0], CZ.shape[0]
    N = n + mx + mz
    adj = defaultdict(list)
    for i, r in enumerate(CX):
        for q in np.flatnonzero(r):
            adj[n + i].append(int(q))
    for i, r in enumerate(CZ):
        for q in np.flatnonzero(r):
            adj[n + mx + i].append(int(q))
    colours = [set(range(n)), set(range(n, n + mx)),
               set(range(n + mx, n + mx + mz))]
    colours = [c for c in colours if c]
    return pynauty.Graph(N, directed=False, adjacency_dict=dict(adj),
                         vertex_coloring=colours)


def canonical_certificate(CX, CZ, n):
    """nauty canonical form of the coloured graph: equal certificates PROVE
    permutation equivalence (of the check structure), unequal ones prove the
    codes are not permutation-equivalent in that presentation."""
    import pynauty
    g = css_graph(CX, CZ, n)
    lab = pynauty.canon_label(g)
    pos = {int(v): i for i, v in enumerate(lab)}
    mx = CX.shape[0]
    edges = []
    for i, r in enumerate(CX):
        for q in np.flatnonzero(r):
            edges.append((pos[n + i], pos[int(q)], 0))
    for i, r in enumerate(CZ):
        for q in np.flatnonzero(r):
            edges.append((pos[n + mx + i], pos[int(q)], 1))
    return (n, CX.shape[0], CZ.shape[0], tuple(sorted(edges)))


def dedup(codes, exact_cap=24, verbose=True):
    """codes: list of (label, CX, CZ, n).  Returns (classes, stats).

    A class is a list of labels PROVEN mutually permutation-equivalent."""
    buckets = defaultdict(list)
    kinds = defaultdict(int)
    for (label, CX, CZ, n) in codes:
        k = n - CX.shape[0] - CZ.shape[0]
        kind, inv = stab_weight_enumerator(CX, CZ, n, exact_cap)
        kinds[kind] += 1
        buckets[(n, k, kind, inv)].append((label, CX, CZ, n))
    classes, certified, collided, split = [], 0, 0, 0
    for key, group in buckets.items():
        if len(group) == 1:
            classes.append([group[0][0]])
            continue
        collided += len(group)
        by_cert = defaultdict(list)
        for (label, CX, CZ, n) in group:
            try:
                cert = canonical_certificate(CX, CZ, n)
            except Exception:
                cert = ("uncertified", label)      # never merge on failure
            by_cert[cert].append(label)
        if len(by_cert) > 1:
            split += 1                 # same invariant, PROVEN inequivalent
        for cert, labels in by_cert.items():
            if len(labels) > 1:
                certified += len(labels) - 1
            classes.append(labels)
    stats = {"codes": len(codes), "buckets": len(buckets),
             "classes": len(classes), "merged_by_certificate": certified,
             "codes_in_colliding_buckets": collided,
             "buckets_split_by_certificate": split,
             "invariant_kinds": dict(kinds)}
    if verbose:
        print(json.dumps(stats, indent=1))
    return classes, stats


# --------------------------------------------------------------- zoo helpers
def _as_arr(M):
    return np.asarray(M, dtype=np.uint8)


def load_json(path):
    """Load codes from a JSON file: either a list of
    {label,n,CX,CZ} or a dict {label: {n,CX,CZ}}."""
    data = json.load(open(path))
    items = data.items() if isinstance(data, dict) else \
        ((e.get("label", str(i)), e) for i, e in enumerate(data))
    out = []
    for label, e in items:
        CX, CZ = _as_arr(e["CX"]), _as_arr(e["CZ"])
        out.append((label, CX, CZ, int(e["n"])))
    return out


def prove_equivalent(A, B):
    """Convenience: A,B each a (CX,CZ,n) triple. Returns True iff certified
    permutation-equivalent. Requires equal invariants AND equal certificates."""
    (CXa, CZa, na), (CXb, CZb, nb) = A, B
    if (na, CXa.shape[0], CZa.shape[0]) != (nb, CXb.shape[0], CZb.shape[0]):
        return False
    if stab_weight_enumerator(CXa, CZa, na) != stab_weight_enumerator(CXb, CZb, nb):
        return False
    return canonical_certificate(CXa, CZa, na) == canonical_certificate(CXb, CZb, nb)


# ------------------------------------------------------------------- selftest
def _steane():
    H = np.array([[0, 0, 0, 1, 1, 1, 1],
                  [0, 1, 1, 0, 0, 1, 1],
                  [1, 0, 1, 0, 1, 0, 1]], dtype=np.uint8)
    return H.copy(), H.copy(), 7                       # CSS Steane [[7,1,3]]


def _shor():
    CZ = np.array([[1, 1, 0, 0, 0, 0, 0, 0, 0],
                   [0, 1, 1, 0, 0, 0, 0, 0, 0],
                   [0, 0, 0, 1, 1, 0, 0, 0, 0],
                   [0, 0, 0, 0, 1, 1, 0, 0, 0],
                   [0, 0, 0, 0, 0, 0, 1, 1, 0],
                   [0, 0, 0, 0, 0, 0, 0, 1, 1]], dtype=np.uint8)
    CX = np.array([[1, 1, 1, 1, 1, 1, 0, 0, 0],
                   [0, 0, 0, 1, 1, 1, 1, 1, 1]], dtype=np.uint8)
    return CX, CZ, 9                                    # Shor [[9,1,3]]


def _422():
    CX = np.array([[1, 1, 1, 1]], dtype=np.uint8)
    CZ = np.array([[1, 1, 1, 1]], dtype=np.uint8)
    return CX, CZ, 4                                    # [[4,2,2]]


def _permute(triple, perm):
    CX, CZ, n = triple
    perm = np.asarray(perm)
    return CX[:, perm].copy(), CZ[:, perm].copy(), n


def selftest():
    rng = np.random.default_rng(0)
    ok = True

    def check(name, cond):
        nonlocal ok
        ok = ok and cond
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    # 1. reflexive: every code certifies equivalent to itself
    for nm, t in [("Steane", _steane()), ("Shor", _shor()), ("[[4,2,2]]", _422())]:
        check(f"{nm} == itself", prove_equivalent(t, t))

    # 2. invariant under a random qubit permutation (the core soundness claim)
    for nm, t in [("Steane", _steane()), ("Shor", _shor()), ("[[4,2,2]]", _422())]:
        for s in range(3):
            p = rng.permutation(t[2])
            check(f"{nm} == permutation#{s}", prove_equivalent(t, _permute(t, p)))

    # 3. distinct codes must NOT be certified equivalent
    check("Steane != Shor (different n)", not prove_equivalent(_steane(), _shor()))
    # a genuinely different [[4,2,2]]-length CSS code (surface-like, weight-2)
    other4 = (np.array([[1, 1, 0, 0], [0, 0, 1, 1]], dtype=np.uint8),
              np.array([[1, 0, 1, 0], [0, 1, 0, 1]], dtype=np.uint8), 4)
    check("[[4,2,2]] != other n=4 CSS code",
          not prove_equivalent(_422(), other4))

    # 4. dedup() groups a mixed pile correctly
    st = _steane()
    codes = [("steane", *st),
             ("steane_perm", *_permute(st, rng.permutation(7))),
             ("shor", *_shor()),
             ("shor_perm", *_permute(_shor(), rng.permutation(9))),
             ("c422", *_422())]
    classes, stats = dedup(codes, verbose=False)
    cls = sorted(sorted(c) for c in classes)
    check("dedup merges the two Steane presentations",
          ["steane", "steane_perm"] in cls)
    check("dedup merges the two Shor presentations",
          ["shor", "shor_perm"] in cls)
    check("dedup keeps [[4,2,2]] separate", ["c422"] in cls)
    check("dedup yields exactly 3 classes", len(classes) == 3)

    print("\nSELFTEST:", "ALL PASS" if ok else "FAILURES PRESENT")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true",
                    help="run built-in equivalence assertions")
    ap.add_argument("--json", metavar="FILE",
                    help="dedup a JSON list/dict of {label,n,CX,CZ} codes")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(selftest())
    if args.json:
        codes = load_json(args.json)
        print(f"{len(codes)} codes loaded from {args.json}", flush=True)
        classes, stats = dedup(codes)
        multi = [c for c in classes if len(c) > 1]
        print(f"{len(multi)} certified-equivalent classes with >1 member")
        for c in multi[:20]:
            print("   ", c[:6], "..." if len(c) > 6 else "")
        sys.exit(0)
    ap.print_help()
    sys.exit(2)
