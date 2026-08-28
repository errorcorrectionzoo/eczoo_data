#!/usr/bin/env python3
"""Certified stabilizer / CSS-code equivalence and database dedup.

Equivalence of quantum codes comes in a HIERARCHY, and this module implements it
as a ladder of ever-more-expensive tests.  Cheap tests can only ever PROVE
*inequivalence* (unequal invariant => different codes); the actual merge is made
by an exact graph-isomorphism certificate.  The ladder, cheapest first:

  A. INVARIANTS (prove inequivalence; equal value proves nothing)
     A1. genus-1 stabilizer weight enumerator  -- `stab_weight_enumerator`
     A2. genus-2 support weight enumerator      -- `stab_weight_enumerator_genus2`
         (joint support distribution over PAIRS of stabilizer elements).
     A3. genus-3 support weight enumerator      -- `stab_weight_enumerator_genus3`
         (the eight-region Venn composition over TRIPLES; the `|g&h&f|` term is not
          a function of the pairwise overlaps, so A3 is strictly finer than A2).
     A4. genus-4 support weight enumerator      -- `stab_weight_enumerator_genus4`
         (the sixteen-region Venn composition over 4-tuples; finer still).
     Each genus sees one more order of joint structure -- A2 the X-Z *alignment* A1
     is blind to, A3 the triple-wise alignment A2 misses, A4 the four-way one.  All
     are invariant under local Clifford AND qubit permutation (a single-qubit
     Clifford maps every Pauli to a Pauli of the SAME support; a permutation just
     relabels coordinates).  They are computed over DISTINCT supports weighted by
     multiplicity, since a structured code has far fewer distinct supports than group
     elements; still, cost grows as `distinct^g`, so treat higher genus as an
     escalating LAST-RESORT tie-breaker (A1 is a routine screen, A4 is not -- run it
     only on a stubborn pair and expect to parallelise `_genus4_partial`).  And it
     may STILL tie: an equal invariant at any genus never proves equivalence.

  B. NECESSARY CONDITIONS (prove inequivalence; informative near-misses)
     B1. the classical component codes must match: `C_X(A)` permutation-equivalent
         to `C_X(B)` and `C_Z(A)` to `C_Z(B)` (or the X<->Z swap).  See
         `classical_perm_certificate`.  NOTE this is necessary but NOT sufficient
         for CSS equivalence: two CSS codes can have permutation-equivalent
         classical parts yet be inequivalent, because no *single* permutation
         aligns C_X and C_Z simultaneously (their mutual position differs).

  C. PERMUTATION EQUIVALENCE.  Certificates, with DIFFERENT soundness:
     C1. `css_codeword_certificate` (CSS) -- BASIS-INDEPENDENT, SOUND IN BOTH
         DIRECTIONS:  cert(A)==cert(B)  <=>  A,B are permutation-equivalent.  Its
         graph's non-qubit nodes are the CODEWORDS (the whole rowspaces of C_X and
         C_Z, coloured X vs Z and by weight), not the generators, so it depends only
         on the code.  This is the one to trust.  It enumerates 2^rank codewords per
         block, so it returns None (declines) once a block rank exceeds `cap_k`.
     C1'. `stab_perm_certificate` (ANY stabilizer code, CSS *or* NON-CSS) -- also
         basis-independent and sound both directions.  Nodes are the whole stabilizer
         GROUP (2^m - 1 non-identity elements), each joined to a per-qubit slot
         coloured by the Pauli TYPE (X/Z/Y) it carries -- a permutation preserves
         type.  Use for non-CSS codes; for CSS it agrees with C1 but is dearer
         (2^m vs 2^rank_X + 2^rank_Z nodes).  `stab_perm_equivalent` wraps it with a
         genus-1 screen; both decline (None / raise) when m > `cap_m`.
     C2. `canonical_certificate` (CSS) -- nauty canonical form of the coloured Tanner
         graph over GENERATOR ROWS.  MERGE-SOUND ONLY: equal certificate still PROVES
         permutation-equivalence, but an UNEQUAL certificate proves NOTHING, because
         the graph is a property of the generator PRESENTATION, not the rowspace --
         two different bases of the same code (e.g. the rref of two column-permuted
         copies) give non-isomorphic Tanner graphs and hence different certs.  Use it
         only as a cheap positive test or when C1 declines (large codes).
     Compare both X/Z orientations -- also `..._certificate(CZ, CX, n)` -- to allow
     the global X<->Z swap.  `_perm_equivalent` wraps the CSS path: C1 when it applies
     (decisive), else the C2 fallback (merge-sound, may under-merge).

  D. CSS LOCAL-CLIFFORD + PERMUTATION EQUIVALENCE (the full physical equivalence)
     `css_lc_perm_equivalent` -- the coarsest equivalence physicists usually mean
     (single-qubit Cliffords are "free").  For CSS codes this is DECIDABLE cheaply:
     a single-qubit Clifford sends a CSS code to a CSS code iff, on each qubit, it
     keeps {X,Z} within {X,Z} -- i.e. it is I or H (a phase gate would create a Y
     on any qubit carrying an X- *and* a Z-check).  So the CSS->CSS local Cliffords
     are exactly the "Hadamard subsets", and we enumerate them by backtracking over
     the 6 single-qubit Cliffords per qubit, pruning the instant a generator
     becomes mixed.  Each surviving frame is applied and its permutation-certificate
     compared to the target.  With the C1 certificate (small codes) this is SOUND
     and COMPLETE -- True proves equivalence, False proves inequivalence; on codes
     too large for C1 it falls back to C2 and only True stays sound (see the
     function's `decisive` flag).

CRITICAL FOOTGUN -- the merge certificate C2 is PER-PRESENTATION.  `rref` first
(every routine does, `reduce=True`) so a redundant generating set -- e.g. all 2L
plaquettes of a toric code, with their linear dependency -- does not spuriously
mismatch its own 2L-1 reduced generators.  But rref only canonicalises for a FIXED
column order: two permutation-equivalent codes still rref to different bases, so C2
can report a spurious "inequivalent".  That is exactly why C2 is merge-only and why
the basis-independent C1 exists; never read an unequal C2 (or an unequal
`canonical_certificate`) as a proof of inequivalence.

Soundness of the merge direction is preserved throughout: an equal certificate
proves equivalence; when in doubt we keep codes SEPARATE.  A missed merge costs
time; a wrong merge would transplant a verdict onto a code that lacks it.

Two cautions worth internalising before trusting rung A:
  * The support enumerators DO see the X-Z (and higher-order) alignment, not just
    the classical `C_X`, `C_Z` marginals -- a relative permutation of `C_Z` against
    `C_X` changes them.  So they are genuine quantum-code invariants, not classical
    ones.  But they are still COARSE: inequivalent codes (even with inequivalent
    alignment) can agree at genus 1, 2, 3 and beyond.  An equal invariant at ANY
    genus is never a proof of equivalence -- only the certificate (C/D) is.
  * The certificate is per-presentation; run rref first (see the FOOTGUN note).  A
    redundant generating set can even fail to match a code to itself.

Non-CSS codes: every rung A function takes an optional `stab=` (an `m x 2n`
symplectic generator matrix, e.g. from `pauli_to_symplectic`) and then works for
ANY stabilizer code -- support is `supp(x) | supp(z)`, an LC+permutation invariant
regardless of CSS structure.  Rungs C/D as written are CSS-specific.

Usage:
  dedup_codes.py --selftest              # built-in equivalence assertions
  dedup_codes.py --json codes.json       # dedup a list of codes
      where codes.json is [{"label","n","CX":[[..]],"CZ":[[..]]}, ...]
      or {"label": {"n","CX","CZ"}, ...}
  dedup_codes.py --json codes.json --lc  # merge up to local Clifford, not just perm
"""
import json, re, sys, argparse
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent


# ----------------------------------------------------------- F2 linear algebra
def rref(M):
    """reduced row-echelon form over F2 (drops zero rows).  Deterministic, so it
    is a stable canonical *presentation* of a rowspace for a FIXED column order --
    which is exactly what the graph certificate needs to be presentation-robust."""
    A = (np.asarray(M, dtype=np.uint8) % 2).copy()
    if A.size == 0:
        return A.reshape(0, A.shape[1] if A.ndim == 2 else 0)
    rows, cols = A.shape
    r = 0
    for c in range(cols):
        piv = None
        for i in range(r, rows):
            if A[i, c]:
                piv = i
                break
        if piv is None:
            continue
        A[[r, piv]] = A[[piv, r]]
        for i in range(rows):
            if i != r and A[i, c]:
                A[i] ^= A[r]
        r += 1
        if r == rows:
            break
    return A[:r]


def reduce_code(CX, CZ):
    """rref both check blocks -- the presentation the certificate should see."""
    return rref(CX), rref(CZ)


# ------------------------------------------------------------------ invariants
def stab_weight_enumerator(CX, CZ, n, exact_cap=18, chunk_bits=16):
    """genus-1: multiset of support weights of all 2^{n-k} stabilizer elements.

    Returns (kind, tuple).  `kind` is "exact" or "skipped".  Codes above the
    direct-enumeration cap are enumerated through distinct supports when their
    stabilizer rank is at most 22; larger codes are skipped rather than screened
    with a presentation-dependent bounded-depth search.

    The exact path is CHUNKED: materialising all `2^m` vectors at once is
    `2^m x 2n` bytes -- 800 MB at m=24 -- which is a memory bomb, not a hash."""
    CX = rref(np.asarray(CX, np.uint8) % 2)
    CZ = rref(np.asarray(CZ, np.uint8) % 2)
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
    # Exact support-compressed path.  A former bounded-depth search counted only
    # combinations of up to three RREF rows.  That count changed under a qubit
    # permutation because RREF is not permutation-covariant, so it was not a valid
    # invariant and could falsely separate equivalent codes.
    distinct = _distinct_supports(CX, CZ, n, enum_bits=22)
    if distinct is None:
        return "skipped", ()
    masks, multiplicities = distinct
    counts = {}
    for weight, count in zip(_popcount64(masks).tolist(), multiplicities.tolist()):
        counts[weight] = counts.get(weight, 0) + count
    return "exact", tuple(sorted(counts.items()))


def _popcount64(a):
    """vectorised SWAR popcount of a uint64 numpy array (wrap-around multiply is
    intended -- that is the point of the mask trick)."""
    a = a.astype(np.uint64)
    a = a - ((a >> np.uint64(1)) & np.uint64(0x5555555555555555))
    a = (a & np.uint64(0x3333333333333333)) + \
        ((a >> np.uint64(2)) & np.uint64(0x3333333333333333))
    a = (a + (a >> np.uint64(4))) & np.uint64(0x0f0f0f0f0f0f0f0f)
    return ((a * np.uint64(0x0101010101010101)) >> np.uint64(56)).astype(np.int64)


def pauli_to_symplectic(strings, n):
    """parse Pauli-string stabilizer generators (e.g. 'X0Z1Y2', or a full-length
    'XZZXI') into a symplectic generator matrix `S` (m x 2n; low n columns = X
    part, high n = Z part).  Accepts either indexed tokens (`X0Z3...`) or dense
    per-qubit strings of length n."""
    S = []
    for s in strings:
        x = np.zeros(n, np.uint8); z = np.zeros(n, np.uint8)
        toks = re.findall(r'([IXYZ])(\d+)', s)
        if toks:                                   # indexed form
            for p, q in toks:
                q = int(q)
                if p in 'XY': x[q] ^= 1
                if p in 'ZY': z[q] ^= 1
        else:                                      # dense length-n form
            for q, p in enumerate(s.strip()):
                if p in 'XY': x[q] ^= 1
                if p in 'ZY': z[q] ^= 1
        S.append(np.concatenate([x, z]))
    return np.array(S, np.uint8)


def _distinct_supports(CX, CZ, n, enum_bits=22, dcap=None, stab=None):
    """(distinct support bitmasks, multiplicities) over the 2^{n-k} stabilizer
    elements -- the key compression for the higher-genus enumerators.  Many group
    elements share a support (a structured code can collapse tens of thousands of
    elements to a few thousand distinct supports), and a genus-g enumerator over the
    GROUP equals the same enumerator over distinct supports weighted by the product
    of multiplicities.

    Works for ANY stabilizer code, CSS or not: support is `supp(x) | supp(z)`, so a
    single-qubit Clifford (which permutes {X,Y,Z} per qubit) leaves it invariant.
    Pass `stab` (an m x 2n symplectic generator matrix) for a general/non-CSS code;
    otherwise the CSS blocks `C_X`, `C_Z` are used.  Returns None when out of budget
    (`n > 64`, `#generators > enum_bits`, or more than `dcap` distinct supports)."""
    if n > 64:
        return None

    def tomask(v):
        out = np.uint64(0)
        for i in np.flatnonzero(v):
            out |= np.uint64(1) << np.uint64(int(i))
        return out
    if stab is not None:                           # general stabilizer code
        S = rref(np.asarray(stab, np.uint8) % 2)   # independent symplectic rows
        rows = [(tomask(r[:n]), tomask(r[n:])) for r in S]
    else:                                          # CSS: block-diagonal
        rows = [(tomask(r), np.uint64(0)) for r in rref(CX)] + \
               [(np.uint64(0), tomask(r)) for r in rref(CZ)]
    if len(rows) > enum_bits:
        return None
    xs = np.zeros(1, dtype=np.uint64)
    zs = np.zeros(1, dtype=np.uint64)
    for (xm, zm) in rows:                          # enumerate the group, XOR-doubling
        xs = np.concatenate([xs, xs ^ xm])
        zs = np.concatenate([zs, zs ^ zm])
    masks, cnts = np.unique(xs | zs, return_counts=True)   # support = X-supp | Z-supp
    if dcap is not None and len(masks) > dcap:
        return None
    return masks, cnts.astype(np.int64)


def stab_weight_enumerator_genus2(CX, CZ, n, enum_bits=22, dcap=20000, stab=None):
    """genus-2 support weight enumerator: the multiset over all ORDERED pairs
    (g,h) of stabilizer elements of (|g|, |h|, |supp(g) & supp(h)|).

    An LC+permutation invariant STRICTLY FINER than genus-1: it resolves the joint
    support / mutual position of pairs, which is exactly what genus-1 collapses.
    Computed over DISTINCT supports weighted by multiplicity (see
    `_distinct_supports`), which is exact and turns the naive `|group|^2` into
    `distinct^2`.  Returns ("genus2", tuple) or ("skipped", ()) when out of budget."""
    ds = _distinct_supports(CX, CZ, n, enum_bits, dcap, stab=stab)
    if ds is None:
        return "skipped", ()
    masks, cnts = ds
    w = _popcount64(masks)
    base = n + 1
    hist = defaultdict(int)
    D = len(masks)
    for i in range(D):
        ov = _popcount64(masks[i] & masks)                     # (D,)  |g_i & h|
        key = (int(w[i]) * base + w) * base + ov               # encode (wi,wh,ov)
        wt = int(cnts[i]) * cnts                               # multiplicity product
        for kk, cc in zip(key.tolist(), wt.tolist()):
            hist[kk] += cc
    out = tuple(sorted(((k // base // base, (k // base) % base, k % base), c)
                       for k, c in hist.items()))
    return "genus2", out


def stab_weight_enumerator_genus3(CX, CZ, n, enum_bits=22, dcap=1500, chunk=256, stab=None):
    """genus-3 support weight enumerator: the multiset over ORDERED TRIPLES
    (g,h,f) of the seven joint statistics
        (|g|, |h|, |f|, |g&h|, |g&f|, |h&f|, |g&h&f|),
    equivalently the eight-region Venn composition of the three supports.

    An LC+permutation invariant STRICTLY FINER than genus-2: it sees the
    TRIPLE-wise alignment (the `|g&h&f|` term is not a function of the pairwise
    overlaps), so it can separate codes that agree at genus 1 and 2.  Computed over
    DISTINCT supports weighted by multiplicity, so the cost is `distinct^3`
    (feasible for the structured codes where distinct << |group|); returns
    ("skipped", ()) above `dcap` distinct supports."""
    ds = _distinct_supports(CX, CZ, n, enum_bits, dcap, stab=stab)
    if ds is None:
        return "skipped", ()
    masks, cnts = ds
    D = len(masks)
    w = _popcount64(masks)
    HF = np.zeros((D, D), dtype=np.int64)                      # |h & f|, once
    for j in range(0, D, chunk):
        HF[j:j + chunk] = _popcount64(masks[j:j + chunk, None] & masks[None, :])
    base = n + 1
    hist = defaultdict(int)
    cn = cnts
    for i in range(D):                                         # outer: element g_i
        mij = masks[i] & masks                                # (D,)  g_i & h
        wgh = _popcount64(mij)                                 # |g_i & h| == |g_i & f|
        ci = int(cn[i]); wgi = int(w[i])
        for j0 in range(0, D, chunk):
            mb = mij[j0:j0 + chunk]                            # (c,)
            ghf = _popcount64(mb[:, None] & masks[None, :])    # (c, D)  |g_i & h & f|
            wj = w[j0:j0 + chunk][:, None]                     # (c,1)  |h|
            ghj = wgh[j0:j0 + chunk][:, None]                  # (c,1)  |g_i & h|
            key = ((((((wgi * base + wj) * base + w[None, :]) * base
                      + ghj) * base + wgh[None, :]) * base + HF[j0:j0 + chunk])
                   * base + ghf)                               # (c, D)
            wt = ci * cn[j0:j0 + chunk][:, None] * cn[None, :]  # (c, D)
            uk, inv = np.unique(key.ravel(), return_inverse=True)
            sums = np.bincount(inv, weights=wt.ravel(), minlength=len(uk))
            for kk, ss in zip(uk.tolist(), sums.tolist()):
                hist[kk] += int(ss)
    def dec(k):
        f = []
        for _ in range(7):
            f.append(k % base); k //= base
        return tuple(reversed(f))                              # (wg,wh,wf,gh,gf,hf,ghf)
    return "genus3", tuple(sorted((dec(k), c) for k, c in hist.items()))


def _genus4_partial(masks, cnts, n, i_indices):
    """partial genus-4 histogram (a raw `{encoded_key: count}` dict) over the
    outer index `i in i_indices`.  Split `i_indices` across processes and merge the
    dicts to parallelise -- the whole thing is `O(distinct^4)`.

    A 4-tuple's 16-region Venn composition is the 4x4 overlap of pair1=(i,j)'s four
    regions with pair2=(k,l)'s four regions; we encode the 15 non-empty regions
    (region 0000 is determined) in base n+1."""
    D = len(masks)
    full = np.uint64((1 << n) - 1)
    base = n + 1
    Mc = full ^ masks
    K = np.repeat(masks, D); L = np.tile(masks, D)             # all ordered (k,l)
    Kc = np.repeat(Mc, D); Lc = np.tile(Mc, D)
    Q = [Kc & Lc, Kc & L, K & Lc, K & L]                       # pair2 regions, (P,)
    PM = (np.repeat(cnts, D) * np.tile(cnts, D)).astype(np.int64)
    hist = defaultdict(int)
    b = np.uint64(base)
    for i in i_indices:
        Mi, Mic, ci = masks[i], Mc[i], int(cnts[i])
        for j in range(D):
            R = [Mic & Mc[j], Mic & masks[j], Mi & Mc[j], Mi & masks[j]]
            key = np.zeros(D * D, dtype=np.uint64)
            for ab in range(4):
                for cd in range(4):
                    if (ab << 2) | cd == 0:                    # skip region 0000
                        continue
                    key = key * b + _popcount64(R[ab] & Q[cd]).astype(np.uint64)
            wt = ci * int(cnts[j]) * PM
            uk, inv = np.unique(key, return_inverse=True)
            s = np.bincount(inv, weights=wt, minlength=len(uk))
            for kk, ss in zip(uk.tolist(), s.tolist()):
                hist[kk] += int(ss)
    return dict(hist)


def stab_weight_enumerator_genus4(CX, CZ, n, enum_bits=22, dcap=120, stab=None):
    """genus-4 support weight enumerator: the multiset over ORDERED 4-tuples of the
    sixteen-region Venn composition of the four supports -- strictly finer than
    genus-3 (it resolves the four-way intersection).

    WARNING: cost is `O(distinct^4)`, so this is a last-resort tie-breaker, not a
    routine screen; `dcap` (default 120 distinct supports) keeps the serial call
    bounded.  For a hard case with many distinct supports, split `_genus4_partial`
    over processes (see the module docstring) rather than raising `dcap` here.
    Returns ("genus4", tuple) or ("skipped", ())."""
    ds = _distinct_supports(CX, CZ, n, enum_bits, dcap, stab=stab)
    if ds is None:
        return "skipped", ()
    masks, cnts = ds
    hist = _genus4_partial(masks, cnts, n, range(len(masks)))
    base = n + 1

    def dec(k):
        f = []
        for _ in range(15):
            f.append(k % base); k //= base
        return tuple(reversed(f))
    return "genus4", tuple(sorted((dec(k), c) for k, c in hist.items()))


# --------------------------------------------- classical component-code check
def _classical_graph(C, n):
    """coloured bipartite graph of a classical F2 code: coordinate nodes vs.
    codeword nodes, codewords coloured by weight.  Permutation-covariant and
    presentation-INDEPENDENT (it uses the whole codeword set, not a generating
    matrix), so isomorphism of these graphs == classical permutation equivalence."""
    import pynauty
    R = rref(C)
    k = R.shape[0]
    words = []
    for b in range(1 << k):
        v = np.zeros(n, dtype=np.uint8)
        for i in range(k):
            if (b >> i) & 1:
                v ^= R[i]
        if v.any():
            words.append(v)
    adj = defaultdict(list)
    wt_of = {}
    for wi, v in enumerate(words):
        node = n + wi
        wt_of[node] = int(v.sum())
        for q in np.flatnonzero(v):
            adj[node].append(int(q))
    # colour classes: coordinates, then codewords grouped by weight
    colours = [set(range(n))]
    for wt in sorted(set(wt_of.values())):
        colours.append({node for node, wv in wt_of.items() if wv == wt})
    return pynauty.Graph(n + len(words), directed=False,
                         adjacency_dict=dict(adj), vertex_coloring=colours), words


def classical_perm_certificate(C, n, cap_k=16):
    """nauty canonical form of the classical code's codeword graph, or None when
    2^k exceeds the enumeration budget.  Equal certs == permutation-equivalent
    classical codes (a COMPLETE test, unlike a raw generator-matrix hash)."""
    import pynauty
    if rref(C).shape[0] > cap_k:
        return None
    g, words = _classical_graph(C, n)
    lab = pynauty.canon_label(g)
    pos = {int(v): i for i, v in enumerate(lab)}
    edges = []
    for wi, v in enumerate(words):
        for q in np.flatnonzero(v):
            edges.append((pos[n + wi], pos[int(q)]))
    return (n, len(words), tuple(sorted(edges)))


def classical_parts_compatible(CX_a, CZ_a, CX_b, CZ_b, n):
    """necessary condition for CSS equivalence: the classical parts match, either
    directly (C_X~C_X, C_Z~C_Z) or under the global X<->Z swap.  Returns
    True / False / None (None = could not decide, e.g. k too large)."""
    cx_a, cz_a = classical_perm_certificate(CX_a, n), classical_perm_certificate(CZ_a, n)
    cx_b, cz_b = classical_perm_certificate(CX_b, n), classical_perm_certificate(CZ_b, n)
    if None in (cx_a, cz_a, cx_b, cz_b):
        return None
    direct = (cx_a == cx_b) and (cz_a == cz_b)
    swapped = (cx_a == cz_b) and (cz_a == cx_b)
    return direct or swapped


# ---------------------------------------------------- CSS permutation certificate
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


def canonical_certificate(CX, CZ, n, reduce=True):
    """nauty canonical form of the GENERATOR Tanner graph.  SOUND FOR MERGING ONLY:

        equal certificate  ==>  the codes ARE permutation-equivalent  (use to MERGE)
        unequal certificate ==>  says NOTHING about the codes.

    The graph's check-nodes are the given generator ROWS, so it is a property of the
    *presentation*, not the rowspace.  `rref` (default `reduce=True`) makes it
    deterministic for a fixed column order, but it does NOT make it a code invariant:
    `rref` of permuted columns is a DIFFERENT basis, so two permutation-equivalent
    codes generally get DIFFERENT certificates.  Do NOT use an unequal certificate to
    conclude inequivalence -- that was a real bug here.  For a basis-independent test
    valid in BOTH directions, use `css_codeword_certificate` (small codes only)."""
    import pynauty
    CX = np.asarray(CX, np.uint8) % 2
    CZ = np.asarray(CZ, np.uint8) % 2
    if reduce:
        CX, CZ = rref(CX), rref(CZ)
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


def css_codeword_certificate(CX, CZ, n, cap_k=15):
    """BASIS-INDEPENDENT CSS permutation certificate -- SOUND IN BOTH DIRECTIONS.

        cert(A) == cert(B)  <==>  A and B are permutation-equivalent CSS codes.

    Unlike `canonical_certificate`, the graph's non-qubit nodes are the CODEWORDS of
    C_X and C_Z (the whole rowspaces, coloured X vs Z and by weight), not the
    generators -- so it depends only on the code, not the presentation.  A binary
    codeword equals its support, so a colour-preserving graph isomorphism is exactly
    a qubit permutation carrying C_X->C_X and C_Z->C_Z simultaneously.

    Enumerates `2^rank` codewords per block, so returns None when either rank exceeds
    `cap_k` (then fall back to keeping codes separate -- the safe direction).  To
    allow the global X<->Z swap, compare `css_codeword_certificate(CZ, CX, n)` too."""
    import pynauty
    RX, RZ = rref(CX), rref(CZ)
    if RX.shape[0] > cap_k or RZ.shape[0] > cap_k:
        return None

    def words(R):
        out = []
        for b in range(1, 1 << R.shape[0]):
            v = np.zeros(n, np.uint8)
            for i in range(R.shape[0]):
                if (b >> i) & 1:
                    v ^= R[i]
            out.append(v)
        return out
    xw, zw = words(RX), words(RZ)
    nx = len(xw)
    adj = defaultdict(list)
    for i, v in enumerate(xw):
        for q in np.flatnonzero(v):
            adj[n + i].append(int(q))
    for i, v in enumerate(zw):
        for q in np.flatnonzero(v):
            adj[n + nx + i].append(int(q))
    # colours: qubits; X-words by weight; Z-words by weight (X and Z kept disjoint)
    groups = defaultdict(set)
    for i, v in enumerate(xw):
        groups[("X", int(v.sum()))].add(n + i)
    for i, v in enumerate(zw):
        groups[("Z", int(v.sum()))].add(n + nx + i)
    colours = [set(range(n))] + [groups[k] for k in sorted(groups)]
    g = pynauty.Graph(n + nx + len(zw), directed=False,
                      adjacency_dict=dict(adj), vertex_coloring=colours)
    lab = pynauty.canon_label(g)
    pos = {int(v): i for i, v in enumerate(lab)}
    edges = []
    for i, v in enumerate(xw):
        for q in np.flatnonzero(v):
            edges.append((pos[n + i], pos[int(q)], 0))
    for i, v in enumerate(zw):
        for q in np.flatnonzero(v):
            edges.append((pos[n + nx + i], pos[int(q)], 1))
    return (n, nx, len(zw), tuple(sorted(edges)))


def stab_perm_certificate(stab, n, cap_m=16):
    """BASIS-INDEPENDENT stabilizer-code PERMUTATION certificate -- CSS *or* NON-CSS,
    SOUND IN BOTH DIRECTIONS:  cert(A) == cert(B)  <==>  A,B permutation-equivalent.

    `stab` is an `m x 2n` symplectic generator matrix `[X-part | Z-part]` (e.g. from
    `pauli_to_symplectic`).  The graph's non-qubit nodes are the `2^m - 1` non-identity
    STABILIZER GROUP ELEMENTS (the whole rowspace, so it is a property of the code, not
    the generating set), each joined to a per-qubit *slot* coloured by the Pauli TYPE it
    carries there -- X, Z or Y.  A qubit permutation preserves Pauli type, so a colour-
    preserving graph isomorphism is exactly a qubit permutation carrying one stabilizer
    group onto the other.  (This is the non-CSS analogue of `css_codeword_certificate`;
    for a CSS code the two give the same equivalence verdicts, but that one is cheaper --
    `2^rank_X + 2^rank_Z` nodes versus `2^m` here.)  This certifies PERMUTATION
    equivalence only; it does NOT quotient by local Cliffords (which would relabel the
    X/Z/Y types).  Returns None when `m > cap_m` (`2^m` elements are enumerated)."""
    import pynauty
    S = rref(np.asarray(stab, np.uint8) % 2)      # independent generators of the group
    m = S.shape[0]
    if m > cap_m:
        return None
    X, Z = S[:, :n], S[:, n:]
    # node layout: qubit hubs [0,n) ; type slots sX/sZ/sY (3 colour classes) ; elements
    sX = lambda i: n + i
    sZ = lambda i: 2 * n + i
    sY = lambda i: 3 * n + i
    base_elem = 4 * n
    adj = defaultdict(list)
    for i in range(n):
        adj[i] += [sX(i), sZ(i), sY(i)]           # tie a qubit's three type-slots together
    profiles, edges_typed = defaultdict(set), []
    e_idx = 0
    for b in range(1, 1 << m):
        x = np.zeros(n, np.uint8); z = np.zeros(n, np.uint8)
        for i in range(m):
            if (b >> i) & 1:
                x ^= X[i]; z ^= Z[i]
        en = base_elem + e_idx; e_idx += 1
        nx = ny = nz = 0
        for i in range(n):
            xi, zi = int(x[i]), int(z[i])
            if xi and not zi:   adj[en].append(sX(i)); nx += 1
            elif zi and not xi: adj[en].append(sZ(i)); nz += 1
            elif xi and zi:     adj[en].append(sY(i)); ny += 1
        profiles[(nx, ny, nz)].add(en)            # type-profile: a permutation invariant
    N = base_elem + e_idx
    groups = ([set(range(n))] +                   # hubs
              [{sX(i) for i in range(n)}, {sZ(i) for i in range(n)},
               {sY(i) for i in range(n)}] +       # the three type-slot classes
              [profiles[k] for k in sorted(profiles)])
    colours = [c for c in groups if c]
    g = pynauty.Graph(N, directed=False, adjacency_dict=dict(adj), vertex_coloring=colours)
    lab = pynauty.canon_label(g)
    pos = {int(v): i for i, v in enumerate(lab)}
    # emit element->slot edges tagged by type (0=X,1=Z,2=Y); the hub structure is
    # fixed by n, so it need not enter the certificate
    for en in range(base_elem, N):
        for s in adj[en]:
            t = 0 if s < 2 * n else (1 if s < 3 * n else 2)
            edges_typed.append((pos[en], pos[s], t))
    return (n, m, e_idx, tuple(sorted(edges_typed)))


def stab_perm_equivalent(stab_a, stab_b, n, cheap_first=True):
    """Decide PERMUTATION-equivalence of two general stabilizer codes (CSS or not),
    sound in BOTH directions via `stab_perm_certificate`.

    `stab_a`, `stab_b` are `m x 2n` symplectic generator matrices.  `cheap_first`
    screens on the genus-1 support weight enumerator (an invariant) before the
    certificate.  Raises `NotImplementedError` if a code exceeds the certificate's
    `cap_m` (there is no sound non-CSS fallback -- unlike the CSS Tanner certificate)."""
    Sa = rref(np.asarray(stab_a, np.uint8) % 2)
    Sb = rref(np.asarray(stab_b, np.uint8) % 2)
    if Sa.shape[0] != Sb.shape[0]:
        return False                                   # different stabilizer dimension
    if cheap_first:
        da = _distinct_supports(None, None, n, stab=Sa)
        db = _distinct_supports(None, None, n, stab=Sb)
        if da is not None and db is not None:
            ha = tuple(sorted(zip(_popcount64(da[0]).tolist(), da[1].tolist())))
            hb = tuple(sorted(zip(_popcount64(db[0]).tolist(), db[1].tolist())))
            if ha != hb:
                return False                           # genus-1 invariant separates them
    ca = stab_perm_certificate(Sa, n)
    cb = stab_perm_certificate(Sb, n)
    if ca is None or cb is None:
        raise NotImplementedError(
            "code exceeds stab_perm_certificate cap_m; no sound non-CSS fallback.")
    return ca == cb


# --------------------------------------- CSS local-Clifford + permutation test
# the six single-qubit Cliffords mod Paulis, as 2x2 F2 matrices acting on the
# symplectic column (x, z)^T.  {I, H} are the two that keep {X,Z} inside {X,Z}
# (they fix the Pauli type-set); the four with an S-component move Y and so can
# only preserve CSS on a qubit that no generator touches on both sides.
_CLIFFORDS = [np.array(m, np.uint8) for m in
              ([[1, 0], [0, 1]], [[0, 1], [1, 0]],       # I, H
               [[1, 0], [1, 1]], [[1, 1], [0, 1]],       # S-family (break CSS...)
               [[0, 1], [1, 1]], [[1, 1], [1, 0]])]      # ...on covered qubits


def _stab_symplectic(CX, CZ, n):
    CX, CZ = rref(CX), rref(CZ)
    top = np.concatenate([CX, np.zeros_like(CX)], axis=1)
    bot = np.concatenate([np.zeros_like(CZ), CZ], axis=1)
    return np.concatenate([top, bot]).astype(np.uint8)


def css_preserving_frames(CX, CZ, n, cap=1 << 20):
    """ALL local-Clifford frames (one single-qubit Clifford per qubit) whose image
    of this CSS code is again CSS, found by backtracking over the 6 Cliffords per
    qubit and pruning the instant a generator carries both an X and a Z part.

    This DERIVES, rather than assumes, that only I/H survive on any qubit lying in
    both an X- and a Z-generator (the usual case), so the list is typically just
    {all-I, all-H} = {identity, global X<->Z swap}.  Returns a list of frames
    (tuples of Clifford indices); raises if more than `cap` are found (a runaway
    guard for pathological low-connectivity codes)."""
    S = _stab_symplectic(CX, CZ, n)
    G = S.shape[0]
    frames, frame = [], [0] * n

    def partial_ok(upto):
        for gi in range(G):
            hasX = hasZ = False
            for i in range(upto):
                M = _CLIFFORDS[frame[i]]
                x, z = int(S[gi, i]), int(S[gi, n + i])
                if (M[0, 0] * x + M[0, 1] * z) & 1:
                    hasX = True
                if (M[1, 0] * x + M[1, 1] * z) & 1:
                    hasZ = True
                if hasX and hasZ:
                    return False
        return True

    def rec(i):
        if len(frames) > cap:
            raise RuntimeError("too many CSS-preserving frames (low connectivity?)")
        if i == n:
            frames.append(tuple(frame))
            return
        for c in range(6):
            frame[i] = c
            if partial_ok(i + 1):
                rec(i + 1)
    rec(0)
    return frames


def _apply_frame(CX, CZ, n, frame):
    """apply a per-qubit Clifford frame; return (CX', CZ') if the image is CSS."""
    S = _stab_symplectic(CX, CZ, n).copy()
    for i in range(n):
        M = _CLIFFORDS[frame[i]]
        x = S[:, i].copy(); z = S[:, n + i].copy()
        S[:, i] = (M[0, 0] * x + M[0, 1] * z) % 2
        S[:, n + i] = (M[1, 0] * x + M[1, 1] * z) % 2
    xp, zp = S[:, :n], S[:, n:]
    pureX = zp.sum(1) == 0
    pureZ = xp.sum(1) == 0
    if not np.all(pureX | pureZ):
        return None
    return xp[pureX], zp[pureZ]


def css_lc_perm_equivalent(CX_a, CZ_a, CX_b, CZ_b, n, cheap_first=True,
                           decisive=True):
    """decide LOCAL-CLIFFORD + PERMUTATION equivalence of two CSS codes.

    Enumerates every local Clifford that keeps the CSS code A CSS (a
    `css_preserving_frame`) and tests each frame's image for permutation-equivalence
    to B; since every CSS-to-CSS local Clifford is such a frame, this exhausts the
    possibilities.  A True result is ALWAYS a sound proof of equivalence.

    The per-frame permutation test uses the BASIS-INDEPENDENT `css_codeword_certificate`
    (sound in both directions) whenever the code is small enough for it; then a False
    result is likewise a sound proof of INequivalence.  For codes too large for that
    certificate (block rank > its `cap_k`) the test falls back to the presentation-
    dependent `canonical_certificate`, which is merge-sound only: a match still proves
    equivalence, but a non-match proves nothing.  In that regime a False cannot be
    trusted, so with `decisive=True` (default) we RAISE rather than return an
    unsound False; pass `decisive=False` (as dedup does) to accept a possibly-
    under-merging False.

    `cheap_first` short-circuits on the genus-1/2 invariants first -- an unequal
    invariant is a certificate of INequivalence at negligible cost."""
    CX_a, CZ_a = rref(CX_a), rref(CZ_a)
    CX_b, CZ_b = rref(CX_b), rref(CZ_b)
    if (CX_a.shape[0], CZ_a.shape[0]) not in {(CX_b.shape[0], CZ_b.shape[0]),
                                              (CZ_b.shape[0], CX_b.shape[0])}:
        return False
    if cheap_first:
        if stab_weight_enumerator(CX_a, CZ_a, n) != stab_weight_enumerator(CX_b, CZ_b, n):
            return False
        g2a = stab_weight_enumerator_genus2(CX_a, CZ_a, n)
        g2b = stab_weight_enumerator_genus2(CX_b, CZ_b, n)
        if g2a[0] == "genus2" and g2a != g2b:
            return False
    # basis-independent codeword certificate if the code is small enough (decisive
    # both directions); else fall back to the merge-only Tanner certificate.  A local
    # Clifford preserves the total rank, so every frame image has the same block
    # ranks as A/B -- one `small` flag governs the whole loop consistently.
    tb = css_codeword_certificate(CX_b, CZ_b, n)
    small = tb is not None
    if small:
        cert = lambda cx, cz: css_codeword_certificate(cx, cz, n)
        target = {tb, css_codeword_certificate(CZ_b, CX_b, n)}
    else:
        cert = lambda cx, cz: canonical_certificate(cx, cz, n)
        target = {cert(CX_b, CZ_b), cert(CZ_b, CX_b)}    # both X/Z orientations
    for frame in css_preserving_frames(CX_a, CZ_a, n):
        img = _apply_frame(CX_a, CZ_a, n, frame)
        if img is None:
            continue
        cxf, czf = img
        if cxf.shape[0] == 0 or czf.shape[0] == 0:
            continue
        if cert(cxf, czf) in target:
            return True                                  # always sound
    if not small and decisive:
        raise NotImplementedError(
            "no CSS-preserving frame matched, but the code exceeds "
            "css_codeword_certificate's cap so a non-match is NOT a proof of "
            "inequivalence; pass decisive=False to accept a non-decisive False.")
    return False


# ---------------------------------------------------------------- top-level dedup
def dedup(codes, exact_cap=24, verbose=True, lc=False):
    """codes: list of (label, CX, CZ, n).  Returns (classes, stats).

    A class is a list of labels PROVEN mutually equivalent.  With `lc=False`
    (default) equivalence means CSS permutation; with `lc=True` it means CSS local
    Clifford + permutation (rung D), which merges strictly more (e.g. a code and
    its global X<->Z swap)."""
    buckets = defaultdict(list)
    kinds = defaultdict(int)
    for (label, CX, CZ, n) in codes:
        CXr, CZr = reduce_code(CX, CZ)
        k = n - CXr.shape[0] - CZr.shape[0]
        kind, inv = stab_weight_enumerator(CXr, CZr, n, exact_cap)
        kinds[kind] += 1
        buckets[(n, k, kind, inv)].append((label, CXr, CZr, n))
    classes, certified, collided, split = [], 0, 0, 0
    for key, group in buckets.items():
        if len(group) == 1:
            classes.append([group[0][0]])
            continue
        collided += len(group)
        merged = []                        # list of (representative_triple, labels)
        for (label, CX, CZ, n) in group:
            placed = False
            for rep in merged:
                (rCX, rCZ, rn), labels = rep
                if lc:
                    eq = css_lc_perm_equivalent(CX, CZ, rCX, rCZ, n, decisive=False)
                else:
                    eq = _perm_equivalent(CX, CZ, rCX, rCZ, n)
                if eq:
                    labels.append(label)
                    placed = True
                    break
            if not placed:
                merged.append(((CX, CZ, n), [label]))
        if len(merged) > 1:
            split += 1                     # same invariant, separated by certificate
                                           # (PROVEN inequivalent under C1; possibly
                                           # only under-merged under the C2 fallback)
        for (_rep, labels) in merged:
            if len(labels) > 1:
                certified += len(labels) - 1
            classes.append(labels)
    stats = {"codes": len(codes), "buckets": len(buckets),
             "classes": len(classes), "merged_by_certificate": certified,
             "codes_in_colliding_buckets": collided,
             "buckets_split_by_certificate": split,
             "equivalence": "lc+perm" if lc else "perm",
             "invariant_kinds": dict(kinds)}
    if verbose:
        print(json.dumps(stats, indent=1))
    return classes, stats


def _perm_equivalent(CXa, CZa, CXb, CZb, n):
    """Decide CSS *permutation*-equivalence (no X<->Z swap).

    Prefers the basis-independent `css_codeword_certificate` -- decisive in BOTH
    directions -- and falls back to the presentation-dependent `canonical_certificate`
    only for codes too large for it.  In the fallback regime a True is still a sound
    merge, but a False merely means 'not proven equivalent' (may under-merge)."""
    ca = css_codeword_certificate(CXa, CZa, n)
    if ca is not None:
        return ca == css_codeword_certificate(CXb, CZb, n)     # decisive both ways
    return canonical_certificate(CXa, CZa, n) == canonical_certificate(CXb, CZb, n)


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


def prove_equivalent(A, B, lc=False):
    """Convenience: A,B each a (CX,CZ,n) triple.  With `lc=False` returns True iff
    certified CSS *permutation*-equivalent; with `lc=True`, iff CSS local-Clifford
    + permutation equivalent.  Cheap invariants gate the expensive test."""
    (CXa, CZa, na), (CXb, CZb, nb) = A, B
    CXa, CZa = rref(CXa), rref(CZa)
    CXb, CZb = rref(CXb), rref(CZb)
    if na != nb:
        return False
    dims_a = {(CXa.shape[0], CZa.shape[0])}
    dims_b = {(CXb.shape[0], CZb.shape[0]), (CZb.shape[0], CXb.shape[0])}
    if not (dims_a & dims_b):
        return False
    if stab_weight_enumerator(CXa, CZa, na) != stab_weight_enumerator(CXb, CZb, nb):
        return False
    if lc:
        return css_lc_perm_equivalent(CXa, CZa, CXb, CZb, na, decisive=False)
    return _perm_equivalent(CXa, CZa, CXb, CZb, na)


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
        ok = ok and bool(cond)
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    # 1. reflexive: every code certifies equivalent to itself (perm and lc)
    for nm, t in [("Steane", _steane()), ("Shor", _shor()), ("[[4,2,2]]", _422())]:
        check(f"{nm} == itself (perm)", prove_equivalent(t, t))
        check(f"{nm} == itself (lc)", prove_equivalent(t, t, lc=True))

    # 2. invariant under a random qubit permutation (the core soundness claim)
    for nm, t in [("Steane", _steane()), ("Shor", _shor()), ("[[4,2,2]]", _422())]:
        for s in range(3):
            p = rng.permutation(t[2])
            check(f"{nm} == permutation#{s}", prove_equivalent(t, _permute(t, p)))

    # 3. FOOTGUN: a redundant generating set still certifies equal to the reduced
    #    one (reduce=True by default makes the certificate presentation-robust).
    cx, cz, n = _steane()
    cx_red = np.concatenate([cx, (cx[0] ^ cx[1])[None, :]])   # add a dependency
    check("redundant generators certify == reduced (rref fix)",
          canonical_certificate(cx_red, cz, n) == canonical_certificate(cx, cz, n))
    check("weight enumerator ignores redundant generators",
          stab_weight_enumerator(cx_red, cz, n) == stab_weight_enumerator(cx, cz, n))
    check("redundant generators would DIFFER without reduce (footgun is real)",
          canonical_certificate(cx_red, cz, n, reduce=False)
          != canonical_certificate(cx, cz, n, reduce=False))

    # 4. genus-2 and genus-3 are permutation invariants (equal codes agree)
    for nm, t in [("Steane", _steane()), ("[[4,2,2]]", _422())]:
        p = rng.permutation(t[2])
        tp = _permute(t, p)
        check(f"{nm} genus-2 permutation-invariant",
              stab_weight_enumerator_genus2(t[0], t[1], t[2])
              == stab_weight_enumerator_genus2(tp[0], tp[1], t[2]))
        check(f"{nm} genus-3 permutation-invariant",
              stab_weight_enumerator_genus3(t[0], t[1], t[2])
              == stab_weight_enumerator_genus3(tp[0], tp[1], t[2]))
        g4 = stab_weight_enumerator_genus4(t[0], t[1], t[2])
        grp = 2 ** (rref(t[0]).shape[0] + rref(t[1]).shape[0])   # |stabilizer group|
        check(f"{nm} genus-4 permutation-invariant",
              g4 == stab_weight_enumerator_genus4(tp[0], tp[1], t[2]))
        check(f"{nm} genus-4 total count == |group|^4",
              sum(c for _, c in g4[1]) == grp ** 4)

    # 5. classical component check: Steane's C_X ~ its C_Z (self-dual)
    cxs, czs, ns = _steane()
    check("Steane classical parts compatible",
          classical_parts_compatible(cxs, czs, cxs, czs, ns) is True)

    # 5a. REGRESSION: the genus-1 screen must remain permutation-invariant above
    #     the direct-enumeration cap.  This rank-20 MCR code exposed the former
    #     bounded-depth search, whose count changed from 280 to 308 under `mcrp`.
    f = np.zeros(11, dtype=np.uint8); f[[0, 1]] = 1
    q = np.zeros(11, dtype=np.uint8); q[[1, 3, 4, 5, 9]] = 1
    qf = np.zeros(11, dtype=np.uint8)
    for i in np.flatnonzero(q):
        for j in np.flatnonzero(f):
            qf[(i + j) % 11] ^= 1
    circ = lambda v: np.vstack([np.roll(v, i) for i in range(11)])
    A, B = circ(f), circ(qf)
    mcr22 = (rref(np.hstack([A, B])), rref(np.hstack([B.T, A.T])), 22)
    mcrp = [1, 11, 20, 15, 7, 12, 21, 17, 16, 2, 10,
            3, 4, 5, 8, 0, 9, 14, 18, 13, 6, 19]
    mcr22p = _permute(mcr22, mcrp)
    mcr_we = stab_weight_enumerator(*mcr22)
    check("rank-20 genus-1 screen is exact and permutation-invariant",
          mcr_we[0] == "exact" and mcr_we == stab_weight_enumerator(*mcr22p))
    check("rank-20 permutation copy passes the default equivalence path",
          prove_equivalent(mcr22, mcr22p))

    # 5b. REGRESSION: support must be supp(x) OR supp(z), never XOR.  A single
    #     Y-bearing stabilizer YY has support {0,1} (weight 2); the XOR bug would
    #     cancel it to weight 0.  This distinguishes the true Pauli support
    #     enumerator from the classical C_X+C_Z one.
    yy = pauli_to_symplectic(["YY"], 2)                 # group {II, YY}
    masks_yy, _ = _distinct_supports(None, None, 2, stab=yy)
    check("Y-bearing support is union not XOR (weights {0,2})",
          sorted(int(bin(int(m)).count('1')) for m in masks_yy) == [0, 2])

    # 5c. NON-CSS support enumerators via stab=: the [[5,1,3]] perfect code
    #     (XZZXI and cyclic shifts).  Genus enumerators must be permutation-invariant
    #     and total to |group|^g even with no CSS structure.
    perf = pauli_to_symplectic(["XZZXI"[-i:] + "XZZXI"[:-i] for i in range(4)], 5)
    pp = rng.permutation(5)
    perf_p = np.concatenate([perf[:, :5][:, pp], perf[:, 5:][:, pp]], axis=1)
    for g, fn in [(2, stab_weight_enumerator_genus2),
                  (3, stab_weight_enumerator_genus3),
                  (4, stab_weight_enumerator_genus4)]:
        a = fn(None, None, 5, stab=perf)
        check(f"perfect code genus-{g} (non-CSS) permutation-invariant",
              a == fn(None, None, 5, stab=perf_p))
        check(f"perfect code genus-{g} total == |group|^{g}",
              sum(c for _, c in a[1]) == 16 ** g)

    # 5d. NON-CSS basis-independent PERMUTATION certificate (`stab_perm_certificate`):
    #     sound both directions, over the whole stabilizer GROUP with type-coloured
    #     edges.  Must be permutation-invariant and must SEPARATE genuinely different
    #     codes (here two [[5,1,*]] non-CSS codes with different distance).
    for s in range(4):
        q = rng.permutation(5)
        perf_q = np.concatenate([perf[:, :5][:, q], perf[:, 5:][:, q]], axis=1)
        check(f"perfect code stab_perm_certificate perm-invariant #{s}",
              stab_perm_certificate(perf, 5) == stab_perm_certificate(perf_q, 5))
        check(f"perfect code stab_perm_equivalent(perm) #{s}",
              stab_perm_equivalent(perf, perf_q, 5))
    other5 = pauli_to_symplectic(["ZZIII", "IZZII", "IIZZI", "XXXXX"], 5)   # a d<3 k=1 code
    check("stab_perm_certificate separates [[5,1,3]] from another 5-qubit code",
          stab_perm_certificate(perf, 5) != stab_perm_certificate(other5, 5))
    check("stab_perm_equivalent says they are NOT equivalent",
          not stab_perm_equivalent(perf, other5, 5))
    # 5e. the non-CSS certificate agrees with the CSS one on a CSS code's verdicts
    _stx = _stab_symplectic(*_steane())
    _p = rng.permutation(7)
    _stxp = np.concatenate([_stx[:, :7][:, _p], _stx[:, 7:][:, _p]], axis=1)
    check("stab_perm_certificate agrees with css_codeword on Steane (perm-equiv)",
          (stab_perm_certificate(_stx, 7) == stab_perm_certificate(_stxp, 7))
          == (css_codeword_certificate(*_steane())
              == css_codeword_certificate(_steane()[0][:, _p], _steane()[1][:, _p], 7)))

    # 6. LOCAL-CLIFFORD merge that PERMUTATION misses: a code vs its global X<->Z
    #    swap.  Not permutation-equivalent in general, but LC-equivalent (global H).
    cxg = np.array([[1, 1, 1, 1, 0, 0], [0, 0, 1, 1, 1, 1]], dtype=np.uint8)
    czg = np.array([[1, 1, 0, 0, 0, 0], [0, 0, 0, 0, 1, 1], [0, 1, 1, 0, 0, 0]],
                   dtype=np.uint8)
    swap = (czg, cxg, 6)
    check("code vs its X<->Z swap: LC-equivalent",
          prove_equivalent((cxg, czg, 6), swap, lc=True))

    # 7. distinct codes must NOT be certified equivalent (both perm and lc)
    check("Steane != Shor (different n)", not prove_equivalent(_steane(), _shor()))
    other4 = (np.array([[1, 1, 0, 0], [0, 0, 1, 1]], dtype=np.uint8),
              np.array([[1, 0, 1, 0], [0, 1, 0, 1]], dtype=np.uint8), 4)
    check("[[4,2,2]] != other n=4 CSS code (perm)",
          not prove_equivalent(_422(), other4))
    check("[[4,2,2]] != other n=4 CSS code (lc)",
          not prove_equivalent(_422(), other4, lc=True))

    # 8. dedup() groups a mixed pile correctly, and does so from REDUNDANT inputs
    st = _steane()
    st_red = (np.concatenate([st[0], (st[0][0] ^ st[0][2])[None, :]]), st[1], st[2])
    codes = [("steane", *st),
             ("steane_redundant", *st_red),
             ("steane_perm", *_permute(st, rng.permutation(7))),
             ("shor", *_shor()),
             ("shor_perm", *_permute(_shor(), rng.permutation(9))),
             ("c422", *_422())]
    classes, stats = dedup(codes, verbose=False)
    cls = sorted(sorted(c) for c in classes)
    check("dedup merges the three Steane presentations (incl. redundant)",
          ["steane", "steane_perm", "steane_redundant"] in cls)
    check("dedup merges the two Shor presentations",
          ["shor", "shor_perm"] in cls)
    check("dedup keeps [[4,2,2]] separate", ["c422"] in cls)
    check("dedup yields exactly 3 classes", len(classes) == 3)

    # 9. THE CERTIFICATE-DIRECTION REGRESSION.  `canonical_certificate` is built
    #    from generator ROWS, so it is presentation-dependent: two permutation-
    #    equivalent codes rref to different bases whose Tanner graphs are NOT
    #    isomorphic, giving different Tanner certs -- a spurious "inequivalent".
    #    This [[10,2]] code + permutation exhibits exactly that.  The basis-
    #    independent `css_codeword_certificate` must nonetheless MATCH, and the
    #    wrappers must report equivalent.  (Guards against ever again reading an
    #    unequal Tanner cert as a proof of inequivalence.)
    rCX = np.array([[1, 0, 0, 1, 0, 0, 0, 0, 0, 1], [0, 1, 0, 1, 0, 0, 1, 0, 0, 1],
                    [0, 0, 1, 1, 0, 0, 1, 1, 1, 0], [0, 0, 0, 0, 1, 0, 1, 0, 1, 0],
                    [0, 0, 0, 0, 0, 1, 0, 0, 1, 0]], dtype=np.uint8)
    rCZ = np.array([[1, 0, 0, 0, 0, 1, 1, 0, 1, 1], [0, 0, 1, 0, 1, 1, 0, 0, 1, 0],
                    [0, 0, 0, 1, 1, 1, 0, 0, 1, 1]], dtype=np.uint8)
    rp = [0, 5, 4, 9, 6, 2, 7, 3, 8, 1]
    rA = (rCX, rCZ, 10)
    rB = _permute(rA, rp)                                 # a genuine permutation copy
    check("regression: Tanner cert MISMATCHES under this permutation (bug is real)",
          canonical_certificate(*rA) != canonical_certificate(*rB))
    check("regression: codeword cert MATCHES (basis-independent, the fix)",
          css_codeword_certificate(*rA) == css_codeword_certificate(*rB))
    check("regression: _perm_equivalent detects the merge Tanner cert misses",
          _perm_equivalent(rCX, rCZ, rB[0], rB[1], 10))
    check("regression: prove_equivalent(perm) True despite Tanner mismatch",
          prove_equivalent(rA, rB))
    check("regression: prove_equivalent(perm) True under lc too",
          prove_equivalent(rA, rB, lc=True))
    # ...and codeword cert is permutation-invariant across many random relabelings
    inv_ok = all(
        css_codeword_certificate(*_permute(t, rng.permutation(t[2])))
        == css_codeword_certificate(*t)
        for t in [_steane(), _shor(), _422(), rA] for _ in range(4))
    check("codeword cert permutation-invariant (sweep)", inv_ok)
    # a distinct code must STILL be separated by the codeword cert (no over-merge)
    check("regression: [[10,2]] code != Shor under codeword cert",
          css_codeword_certificate(*rA) != css_codeword_certificate(*_shor()))

    print("\nSELFTEST:", "ALL PASS" if ok else "FAILURES PRESENT")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true",
                    help="run built-in equivalence assertions")
    ap.add_argument("--json", metavar="FILE",
                    help="dedup a JSON list/dict of {label,n,CX,CZ} codes")
    ap.add_argument("--lc", action="store_true",
                    help="merge up to local Clifford + permutation, not just permutation")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(selftest())
    if args.json:
        codes = load_json(args.json)
        print(f"{len(codes)} codes loaded from {args.json}", flush=True)
        classes, stats = dedup(codes, lc=args.lc)
        multi = [c for c in classes if len(c) > 1]
        print(f"{len(multi)} certified-equivalent classes with >1 member")
        for c in multi[:20]:
            print("   ", c[:6], "..." if len(c) > 6 else "")
        sys.exit(0)
    ap.print_help()
    sys.exit(2)
