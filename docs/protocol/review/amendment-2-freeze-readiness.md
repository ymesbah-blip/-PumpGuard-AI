# Amendment 2 (v0.5): freeze-readiness report

Date: 2026-11-22. Amendment state: **Draft 5 with the owner's decisions, DRAFT until the
freeze**. Nothing has been implemented or run on real data.

## Verdict

**The owner approved all five decisions on 2026-11-22. The freeze waits only for the PR #12
merge (G0 a′).** Every audit correction is applied, the owner's permutation count (9 999) is in
the Markdown and the config, the two files agree (90 automated checks), and no other design
value changed since review 2.

## Gate G0 status

| Step | Requirement | Status |
|---|---|---|
| (a) | Evidence branch on GitHub; four hashes confirmed against GitHub | Done (PR #12, `d203b5e`; rechecked 2026-11-22) |
| (a′) | PR #12 merged into `main` on the owner's authorization | Authorized (D6); merge pending |
| (b) | Content edits complete; `check_amendment2.py` passes | Done (90 / 90 before freezing) |
| (c) | Owner decisions recorded in section 16 | Approved 2026-11-22; written into section 16 in the freeze commit |
| (d) | Status FROZEN with date in the Markdown and in `protocol_status` | After (a′) |
| (e) | SHA-256 of both files recorded in `CHANGELOG.md` and the freeze record | After (d) |

## Audit items

| # | Item | Status |
|---|---|---|
| A1 | Provenance precision (section 2.1) | Fixed |
| A2 | Filter terminology; acquisition anti-alias filter unknown (U8) | Fixed; U8 open, does not block |
| A3 | G3 exact value, tolerance and folds | Fixed; value matches `benchmark_results.json`; folds recomputed |
| A4 | V2 statistic, tie-break, no fallback | Fixed |
| A5 | Monte Carlo uncertainty of p | Fixed; count decided: 9 999 |
| A6 | S2 fixed-model limitation | Fixed |
| A7 | Sample-ratio wording | Fixed |
| A8 | Config completeness (status, G2, G4a, G4b, G5, synthetic set-up, V2, secondary) | Fixed |
| A9 | Automated Markdown/config consistency | Done: checker and 10 tests |
| A10 | G0 ordering includes PR #12 merge and config status | Fixed |

## Owner decisions (recorded 2026-11-22)

| # | Decision | Effect on the files |
|---|---|---|
| D1 | **9 999 permutations** for S3, p = (1 + k) / 10 000 | Sections 10.2, 12, 15 (U6, D-perm) and 18; `statistics.S3_permutation` (`permutations`, `permutations_owner_decision`, `monte_carlo_report`) |
| D2 | Draft 5 Markdown approved | No change beyond D1 and the pre-freeze accuracy fixes listed in the change report |
| D3 | Config JSON approved | As D1; G2 fields completed from the existing Markdown values |
| D4 | Decision rules P1, P3, P2 approved; R1 required for a reproducible-band claim | None (section 10.3 unchanged) |
| D5 | Freeze authorized after the PR #12 merge and G0 | Freeze procedure of section 16 |

Permutation count, for the record:

| Option | p resolution | Monte Carlo SE near p = 0.05 | Compute (estimate) |
|---|---|---|---|
| 1 000 (review 2) | 1 / 1 001 | ≈ 0.007 | ≈ 8 min |
| **9 999 (chosen)** | 1 / 10 000 | ≈ 0.002 | ≈ 83 min |

The estimates come from the measured cost of one threshold fit (0.69 ms) and the nested
procedure; the real run may differ by a small factor. G5 keeps 200 permutations per synthetic
data set.

## Freeze steps

1. Record the owner's decisions and the date in section 16, and the PR #12 merge in section 2.1.
2. Set the status to FROZEN with the date in the Markdown header, the final line,
   `protocol_status` and `frozen_on`.
3. Run `check_amendment2.py --no-freeze-record` (it requires a sign-off date and a recorded
   decision once FROZEN).
4. Compute SHA-256 of both files and record them in `CHANGELOG.md` and
   `docs/protocol/amendment-v0.5-freeze-record.json`.
5. Run `check_amendment2.py` without the flag: the recorded hashes must equal the files.
6. Commit on `docs/amendment-2-v0.5`, publish the branch, and wait for the owner's approval
   before merging it.
7. Only after that merge: implement `pumpguard.bandselect` (gate G1), then the synthetic gates
   G4 and G5. Real-data gates G2, G3 and G6 each need a separate explicit approval.
