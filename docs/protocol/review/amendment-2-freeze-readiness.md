# Amendment 2 (v0.5): freeze-readiness report

Date: 2026-11-22. Amendment state: **Draft 5, DRAFT**. Nothing has been frozen, implemented or
run on real data.

## Verdict

**Ready to freeze once the owner gives five approvals and PR #12 is merged.** Every audit
correction is applied, the Markdown and the config agree (86 automated checks), and the design
is unchanged since review 2.

## Gate G0 status

| Step | Requirement | Status |
|---|---|---|
| (a) | Evidence branch on GitHub; four hashes confirmed against GitHub | Done (PR #12, `d203b5e`) |
| (a′) | PR #12 merged into `main` by the owner | **Waiting for owner** |
| (b) | Content edits complete; `check_amendment2.py` passes | Done for Draft 5 (86 / 86) |
| (c) | Owner decisions recorded in section 16 | **Waiting for owner** |
| (d) | Status FROZEN with date in the Markdown and in `protocol_status` | Not started (after c) |
| (e) | SHA-256 of both files computed and recorded in `CHANGELOG.md` | Not started (after d) |

## Audit items

| # | Item | Status |
|---|---|---|
| A1 | Provenance precision (section 2.1) | Fixed |
| A2 | Filter terminology; acquisition anti-alias filter unknown (U8) | Fixed; U8 open, does not block |
| A3 | G3 exact value, tolerance and folds | Fixed; value matches `benchmark_results.json`; folds recomputed |
| A4 | V2 statistic, tie-break, no fallback | Fixed |
| A5 | Monte Carlo uncertainty of p | Fixed; count needs decision D-perm |
| A6 | S2 fixed-model limitation | Fixed |
| A7 | Sample-ratio wording | Fixed |
| A8 | Config completeness (status, G4a, G4b, G5, synthetic set-up, V2, secondary) | Fixed |
| A9 | Automated Markdown/config consistency | Done: checker and 8 tests |
| A10 | G0 ordering includes PR #12 merge and config status | Fixed |

## Decisions the owner must make

### 1. Permutation count for S3 (decision D-perm)

| Option | p resolution | Monte Carlo SE near p = 0.05 | Compute (estimate) | Effect on G5 |
|---|---|---|---|---|
| **1 000** (registered in review 2) | 1 / 1 001 | ≈ 0.007 | ≈ 8 min | none (G5 uses 200 per data set) |
| **9 999** (reviewer's preference if compute allows) | 1 / 10 000 | ≈ 0.002 | ≈ 83 min | none |

- The estimates come from the measured cost of one threshold fit (0.69 ms) and the nested
  procedure; the real run may differ by a small factor.
- Either value is valid. 9 999 narrows the Monte Carlo interval around p and costs about
  75 extra minutes once. P2 is a precondition, not the test of H1, so the choice does not change
  what H1 means.
- If you choose 9 999, these places change together, and the checker enforces it:
  sections 10.2 and 12 (prose), section 15 (D-perm row), section 18, and
  `statistics.S3_permutation` in the config.

### 2. Approval of the Markdown protocol (Draft 5)

File: `docs/protocol/amendment-v0.5-demodulation-band-selection.md`. Changes since Draft 4:
`docs/protocol/review/amendment-2-draft4-to-draft5.md`.

### 3. Approval of the config JSON

File: `docs/protocol/amendment-v0.5-config.json`. Every registered value is listed in section 18
of the Markdown.

### 4. Approval of the decision rules

H1 supported only if P1, P3 and P2 all hold (section 10.3):

- P1: S1 lower 95 % bound of BA(V1) > point estimate of BA(C0);
- P3: S2 lower 95 % bound of ΔBA > 0;
- P2: S3 permutation p ≤ 0.05 (precondition only).

A reproducible-band claim also needs R1 (≥ 4 of 5 folds overlap the modal band by ≥ 50 %).

### 5. Readiness to freeze

Approve the freeze procedure of section 16 once PR #12 is merged and decisions 1 to 4 are
recorded.

## What happens after approval

1. Record decisions 1 to 4 and the date in section 16 (and section 15, D-perm).
2. Set the status to FROZEN with the date in the Markdown header, the final line and
   `protocol_status`; set `permutations_owner_decision.status` to the decision.
3. Run `check_amendment2.py` (it requires a sign-off date and a recorded decision once FROZEN).
4. Compute SHA-256 of both files and record them in `CHANGELOG.md` only.
5. Commit on a review branch, open a PR, and wait for the owner's approval before merging.
6. Only after that merge: implement `pumpguard.bandselect` (gate G1), then the synthetic gates
   G4 and G5. The real-data run (G6) needs a separate explicit approval.
