# Amendment 2: Draft 4 → Draft 5 change report

Date: 2026-11-22. Scope: the pre-freeze audit corrections. Status of the amendment after this
change: **DRAFT**, not frozen, not executed.

## Summary

- Draft 5 changes wording, precision and machine-readability. It changes no hypothesis, arm,
  candidate band, δ, seed, replicate count, permutation count, threshold or decision rule.
- The only numeric value that changed is the G3 reference: the rounded 0.469 became the stored
  value 0.4685836297141851 with an absolute tolerance of 1e-9. The rounded number in Draft 4
  could not be tested with equality.
- Every value the config registers is now listed in section 18 of the amendment, and
  `scripts/protocol/check_amendment2.py` compares the two files on every test run.

## How Draft 4 was obtained for this diff

Draft 4 was never committed; Draft 5 was written over it in the working tree. Draft 4 was
rebuilt by applying the recorded Draft 5 edit operations in reverse. Two checks support the
rebuild:

1. The seven Draft 4 line numbers cited by the audit (L91–93, L179, L209, L210, L236, L371,
   L498) hold the cited text in the rebuilt file.
2. A diff of the saved Draft 3 copy (SHA-256 `cb6ce5f69bdf0895…`) against the rebuilt Draft 4
   shows exactly the change set recorded for Draft 4 in section 17: header, status, section 2.1
   publication note and version-label note, revision entry and footer.

The trailing newline of Draft 4 is assumed. File hashes (informational, not freeze hashes):

| File | SHA-256 |
|---|---|
| Draft 4, rebuilt | `d1929beed4b7ee3259ebd986fc2f6e0a91fd66f6c9e190a60ff81b4381a2c883` |
| Draft 5 Markdown | recorded at freeze, not here (the file is still a draft) |

The full line diff is in [`amendment-2-draft4-to-draft5.diff`](amendment-2-draft4-to-draft5.diff).

## Markdown changes by audit finding

| # | Finding | Draft 4 | Draft 5 | Sections |
|---|---|---|---|---|
| A1 | Provenance overstated | The run used "three changes" from the evidence commit, including the report-header wording | Two parts existed at run time (reader fix, archive verification). Three came later and touched no hashed file (report header, KI04/KI14 strings, figure and docs). Code state is reconstructed; G3 checks it | 2.1 |
| A2 | Filter terminology | "The 30 kHz anti-alias filter is 2nd order"; table row "Anti-alias / conditioning" | Signal-conditioning low-pass (documented). Acquisition anti-alias filter: not documented, open item U8. Aliasing argument marked conditional | 5, 6, 8.2, 15 |
| A3 | G3 not testable | "R0 recomputed equals the v0.4 value 0.469" | 0.4685836297141851 within 1e-9, plus the five-fold bearing assignment | 4, 7, 10.3, 10.4, 13 |
| A4 | V2 under-specified | "maximum median spectral kurtosis … no labels" | Kurtosis formula stated; no δ rule; no D0 fallback; V1 tie-break | 7 |
| A5 | p without Monte Carlo error | p = (1 + k) / 1 001 | Same p, plus k, N and a Clopper–Pearson interval; no sequential extension; permutation count recorded as owner decision D-perm | 10.2, 15 |
| A6 | S2 limitation missing | none | Limitation 9: the paired bootstrap holds fitted bands and thresholds fixed | 15 |
| A7 | Sample ratio wording | "= 16 in every used file" | "≈ 16 (256 004 / 16 001 = 15.999)" | 6 |
| A8 | Synthetic set-up vague | "900 rpm … default noise and severity ranges" | Fixed 900 rpm with the generator's 0.5 % per-segment drift; noise 0.03–0.10 and severity 0.5–1.5 per machine; G4b uses strict containment; G5 states α | 13.1 |
| A10 | G0 incomplete | G0 did not require the PR #12 merge or the config status | G0 (a′) PR #12 merged; (b) checker passes; (d) status FROZEN in both files | 13, 16 |
| — | Traceability | none | Header links the config; section 17 Draft 5 entry; section 18 registered-parameter table; file ends with the required status line | header, 17, 18 |

## Config changes (key level)

No registered design value changed. Keys were added so that the config holds every value the
Markdown fixes, and three keys were renamed for clarity.

| Change | Keys |
|---|---|
| Status | `status` (free text) → `protocol_status` = `"DRAFT"`, plus `status_rule`, `draft`, `draft_date` |
| G3 | `gates.G3_R0_expected_detection_ba_N09` = 0.469 → `gates.G3.R0_detection_ba_N09_expected` = 0.4685836297141851, `abs_tolerance` = 1e-9, `outer_folds_v04`, `source` |
| G4a | `min_folds_non_D0_containing` → `min_folds` (4) + `fold_condition` (non-D0, strict containment) + `require_S2_lower_bound_gt_0` |
| G4b | added `min_folds` (4) and `fold_condition` (D0, or strict containment) |
| G5 | added `alpha` (0.05), `signals`, `labels` |
| Synthetic set-up | `gates.synthetic_data_seed` → `synthetic.data_seed` (2026); added generator, fs, segment length, rpm 900, drift, classes, 5 machines per class, 20 segments, noise and severity ranges |
| Selection | `inner_seed` (text) → `inner_seed_base` (1000) + `inner_seed_rule`; added `inner_folds`, `fallback` |
| Bands | added `switching_frequency_hz` (16000); exclusion text refers to it |
| Arms | added `arm_rules` for V1, C0, R0, V1-45, V2, VG (V2: kurtosis formula, no δ rule, no fallback, tie-break) |
| Statistics | S2 `limitation`; S3 `p_formula`, `monte_carlo_report`, `sequential_extension` = false, `permutations_owner_decision` (PENDING, options 1000 / 9999, registered 1000) |
| Decision | added `P2_alpha` (0.05) |
| Secondary | added `secondary` (δ = 0 sensitivity, RQ2, RQ3, RQ4, RQ7, diagnosis BA, optimism; descriptive only) |

## Owner decisions applied after this report (2026-11-22, before freezing)

| Change | Where |
|---|---|
| S3 permutation count 1 000 → **9 999** (owner decision D1); p = (1 + k) / 10 000; Monte Carlo SE ≈ 0.002; the report states seed and completed permutations | Sections 10.2, 12, 15, 18; config `statistics.S3_permutation` |
| `permutations_owner_decision` set to DECIDED (2026-11-22) | Config |
| G2 tolerances and short-file threshold registered (values from the existing text) | Section 18; config `gates.G2` |
| Disclosure extended to Drafts 4 and 5; real config path in the CLI example; G0 (a′) wording; freeze-record file and checker steps in section 16 | Opening paragraph, sections 13, 14, 16 |

The test `test_config_matches_the_approved_design` pins every design value listed in the
approved protocol, so a later unapproved change fails CI.

## Verification run on Draft 5

- `python scripts/protocol/check_amendment2.py`: 86 checks passed, 0 failed.
- `pytest`: 288 passed, including 8 new tests in `tests/test_protocol_amendment2.py`. Five of
  them inject a fault (δ drift, permutation count, status, stale wording, changed evidence file)
  and confirm that the checker reports it.
- `ruff check .`, `ruff format --check .`, `mypy`: clean.
