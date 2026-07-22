# AGENTS.md — guide for AI agents editing the Error Correction Zoo

This file collects the conventions for adding or editing code entries in this
repository (`eczoo_data`). Follow them exactly. See also `CONTRIBUTING.md`,
the entry template `template.yml` / `blank.yml`, and the `scripts/` folders
(described at the bottom) for tooling.

Every error-correcting code is one YAML file under `codes/`. An entry has a
header (`code_id`, `physical`, `logical`, `name`, `introduced`), then
`description`, `protection`, `features:`, `relations:`, and a `_meta` changelog.

## Entry conventions (rules)

**1. First-paragraph rule.** The FIRST paragraph of `description` must be only a
few sentences giving an umbrella overview of the code and its usefulness, and
must contain NO displayed equations (no `\begin{align}` / `\begin{equation}`;
inline `\(...\)` math is fine). Put detailed constructions, check/boundary
matrices, parameter lists, and examples in LATER paragraphs, or in
`\subsection{...}` blocks. The opening paragraph is the entry's at-a-glance
summary and is shown prominently, so heavy math up front defeats its purpose.
(Lint: `scripts/lint/find_incorrect_description_first_paragraphs.py`.)

**2. One-name rule.** In all prose (`description`, `protection`, `features`,
and relation `detail:` fields), refer to each code by ONLY ONE name — its
primary `name` / `short_name`. Alternative names go in the `alternative_names:`
field and are NOT used as working referents in body text. E.g. write "MM
codes", never "MM (AMC) codes" or "AMC codes". When two names actually denote
two different papers'/authors' *constructions* of the same code, distinguish
them by method (e.g. "Koszul-complex formulation" vs "multi-block-complex
formulation"), not by the code's alternative name.

**3. Unquoted `code_id`.** Every `code_id:` value — in the file header AND in
every `relations:` parent/cousin entry — must be UNQUOTED. Each id is a
connected lowercase string, so quoting is unnecessary. Write
`code_id: hypergraph_product`, never `'hypergraph_product'` or
`"hypergraph_product"`. (Other string fields such as `name:` and `detail:`
remain quoted as usual.)

**4. No redundant `short_name`.** Omit `short_name:` when it differs from
`name:` only by the word "code". E.g. name `'Barbell code'` must NOT carry
short_name `'Barbell'`. `short_name` is only for genuine abbreviations or
acronyms (BB, GB, MM, QDS, 2BGA).

**5. Right `features:` key, not `notes:`.** A `notes:` item that actually
describes gates, decoders, fault tolerance, rate, or thresholds belongs under
the matching `features:` key (`general_gates`, `transversal_gates`,
`decoders`, `fault_tolerance`, `rate`, `threshold`). Reserve `notes:` for
genuinely miscellaneous remarks (databases, software, historical asides).
Check every notes item against the features keys before finalizing.

**6. Run the relation checkers after any hierarchical edit.** Whenever you add,
move, or reparent parents/cousins, run all three from the repo root and fix
what they report:

```
python3 scripts/relations/redundant_primary_parent.py
python3 scripts/relations/redundant_direct_children.py
python3 scripts/relations/check_duplicate_relations.py
```

They catch, respectively: a primary parent already implied via a
secondary-parent chain; a direct child already reachable through an
intermediate code; and duplicate/conflicting relations (both sides declaring
the same cousin, or a pair related as both parent and cousin).
`check_duplicate_relations.py` exits non-zero on violations. See
`scripts/script_list_for_checking.txt` for the fuller routine-check list.

## Relation semantics

- Relations are declared on the CHILD, in its `relations.parents` list; the
  site build auto-generates the reverse (parent → child) link and the reverse
  cousin link. Do not declare both directions by hand.
- **Parent** means IS-A: every code in the family is a special case of the
  parent family. If even one established subfamily falls outside the parent,
  use a **cousin** instead. Cousin = related/overlapping, neither contains the
  other. When in doubt, prefer cousin — an over-broad parent claim distorts the
  hierarchy.
- A relation `detail:` should describe the actual relationship and cite it. If
  a `detail` reads "X is a Y" it is asserting a parent relation, so it should
  not sit under `cousins:`.

## File placement

- Put the `.yml` where its primary-parent chain lives in the `codes/` tree. A
  code that HAS CHILDREN conventionally gets its own directory named after it,
  but this is NOT required: a child may sit as a sibling file next to its
  parent in the same directory (this is common in the repo). Directory nesting
  is organizational only; the hierarchy is defined entirely by `relations`, not
  by the folder tree.

## `_meta` changelog

Add a changelog entry (most-recent-first) with your `user_id` and date
(`'YYYY-MM-DD'`) for each edit. New contributors are added to
`users/users_db.yml` in the "Code Contributors" section (leave out `zooteam:`).

## Scripts (`scripts/`)

Refer to these folders for available tooling; each script has a docstring/header
describing its exact behavior and usage.

- `scripts/relations/` — hierarchy tools. Checkers: `redundant_primary_parent`,
  `redundant_direct_children`, `check_duplicate_relations`,
  `find_property_codes`, `outside_folder_descendants`. Queries: `ancestors`,
  `ancestor_tree`, `children`, `children_tree`, `cousins`. Also
  `dedup_codes.py`, a **ladder of stabilizer/CSS-code equivalence tests** (requires
  `numpy` + `pynauty`; run `--selftest`, or `--json codes.json [--lc]`). Cheapest
  first — each early rung can only PROVE *inequivalence*, the merge is made by an
  exact certificate:
  (A) **weight-enumerator invariants** — genus-1 (`stab_weight_enumerator`) and the
  strictly finer genus-2/3/4 support enumerators (`stab_weight_enumerator_genus2`/
  `_genus3`/`_genus4`: the joint support distribution over pairs / triples /
  4-tuples, each seeing one more order of multi-element *alignment*); all are
  local-Clifford + permutation invariants, computed over distinct supports weighted
  by multiplicity. They see the X–Z alignment (not just the classical `C_X`/`C_Z`
  marginals) and work for **non-CSS** codes too: pass `stab=` (an `m×2n` symplectic
  generator matrix, e.g. from `pauli_to_symplectic`). Cost grows as `distinct^g`:
  genus-1/2 are routine screens, genus-3 is affordable on structured codes, and
  **genus-4 is a last-resort tie-breaker** (`O(distinct^4)`; run it only on a
  stubborn pair, parallelising `_genus4_partial` across processes). A higher genus
  can still tie — an equal invariant never *proves* equivalence, only rungs C/D do;
  (B) **classical component check** (`classical_parts_compatible`) — `C_X`/`C_Z`
  must be individually permutation-equivalent (necessary, NOT sufficient: the
  classical parts can match while no single permutation aligns both);
  (C) **permutation equivalence** — certificates with DIFFERENT soundness.
  `css_codeword_certificate` (CSS) is BASIS-INDEPENDENT and sound in BOTH directions
  (equal ⟺ permutation-equivalent); its graph is built over the *codewords* (the
  whole rowspaces), so use it whenever the block ranks fit under its `cap_k` (it
  returns `None`, i.e. declines, above that). `stab_perm_certificate` is the same idea
  for **any stabilizer code, CSS or NON-CSS** — a graph over the whole stabilizer
  *group* with per-qubit slots coloured by Pauli type (X/Z/Y); also sound both ways,
  declines above `cap_m` (wrapped by `stab_perm_equivalent` with a genus-1 screen).
  `canonical_certificate` (CSS; nauty on the coloured *Tanner* graph over generator
  ROWS) is MERGE-SOUND ONLY: equal cert proves equivalence, but an **unequal cert
  proves nothing** — never read it as inequivalence. `_perm_equivalent` picks the
  right CSS one (codeword cert when it applies, Tanner fallback otherwise). The
  default (no `--lc`) merge uses this;
  (D) **CSS local-Clifford + permutation equivalence** (`css_lc_perm_equivalent`,
  the `--lc` flag) — the full "physical" equivalence, decided by enumerating the
  CSS-preserving single-qubit-Clifford frames (only `I`/`H` per covered qubit) and
  testing each frame's image with the rung-C certificate. On codes small enough for
  the codeword cert this is a true DECISION (True proves equivalence, False proves
  inequivalence); on larger codes it falls back to the Tanner cert where only True
  stays sound, so it takes a `decisive=` flag (raises rather than return an unsound
  False by default; dedup passes `decisive=False` to accept safe under-merging).
  **Footgun: `rref` your generators first** — the Tanner certificate is
  per-*presentation*, so a redundant generating set (e.g. all plaquettes of a toric
  code) gives a spurious mismatch; the routines reduce by default. But note `rref`
  only canonicalises for a *fixed column order* — two permutation-equivalent codes
  still reduce to different bases, which is why the Tanner cert is merge-only and
  why the basis-independent codeword cert exists. All rungs are *sound-toward-
  separation* (a missed merge only costs time; a wrong merge would transplant a
  code's verdict onto a different code). **When you need a definitive
  equivalent/inequivalent verdict (not just a merge), rely on the codeword cert /
  the `decisive` path — an unequal Tanner cert alone is never a proof.**
- `scripts/lint/` — prose/format linters: `find_incorrect_description_first_paragraphs`
  (rule 1), `spellcheck` (+ `spellcheck_wordlist.txt`), `remove_trailing_block_apostrophes`,
  `standardize_citation_locators`, `link`, and `pick_unchecked_yml.sh`.
- `scripts/bib/` — bibliography/citation tooling: extract arXiv IDs, DOIs,
  manual cites and presets; append reference counts.
- `scripts/queries/` — external lookups: `query_qecdb`, `semantic_scholar_recommend`.
- `scripts/codelists/` — code-list tooling: `count_list_codes`.
- `scripts/script_list_for_checking.txt` — the routine set of checks to run
  before submitting changes.
