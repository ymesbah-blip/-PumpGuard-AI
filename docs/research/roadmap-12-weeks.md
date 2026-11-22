# PumpGuard-AI research roadmap: 12 weeks from 2026-11-23

Status on 2026-11-22: v0.4.0 released; PR #12 (real3 evidence) open, CI green; amendment 2
(v0.5 band selection) at Draft 5, not frozen. Decisions are tracked in
[`decision-register.md`](decision-register.md).

Roles:

- **Owner**: project owner. Makes scientific decisions, merges PRs, approves real-data runs,
  releases and anything public.
- **Engineer**: Claude as research engineer. Drafts, implements, tests, runs synthetic gates,
  writes reports. Never merges, freezes or runs real data without the owner's approval.
- **Reviewer**: an independent reviewer (a person, or a separate agent that has not seen the
  work) for the freeze and the results report.

Rule for every week: a failed gate, an unresolved scientific decision or a missing approval
stops the plan at that point. No threshold, band or rule is tuned after seeing held-out results.

---

## Week 1 (Nov 23–29): close PR #12 and freeze amendment 2

- **Objective:** evidence on `main`; amendment 2 frozen with hashes recorded.
- **Tasks:** owner reviews `docs/protocol/review/pr12-evidence-review.md` and merges PR #12;
  publish branch `docs/amendment-2-v0.5` and open a PR; owner decides D-perm (1 000 or 9 999)
  and approves Markdown, config, decision rules and freeze; engineer applies the freeze
  procedure (section 16) on a branch; reviewer checks the frozen files; owner merges.
- **Role:** Owner (decisions, merges), Engineer (freeze edits, checker), Reviewer (freeze check).
- **Inputs:** Draft 5, config, freeze-readiness report, PR #12 review.
- **Deliverables:** PR #12 merged; amendment and config FROZEN; SHA-256 of both in
  `CHANGELOG.md`; freeze PR merged.
- **Acceptance:** `check_amendment2.py` passes on `main` with status FROZEN; hashes in
  `CHANGELOG.md` equal `sha256sum` of the files on `main`.
- **Risks:** owner time; a late design change. Mitigation: any change after the freeze becomes
  amendment 3.
- **Dependencies:** none.

## Week 2 (Nov 30–Dec 6): `pumpguard.bandselect` core

- **Objective:** band features and nested selection, reading only the frozen config.
- **Tasks:** config loader that checks the config hash against the `CHANGELOG.md` freeze record
  (L8); `candidate_bands()` with no data argument (L12); vectorised envelope features per band;
  nested selection for V1, V1-45 and VG with the δ rule and tie-break; V2 kurtosis selection;
  C0 and R0.
- **Role:** Engineer.
- **Inputs:** frozen amendment and config; v0.4 `EnvelopeRule`, `stratified_group_kfold`.
- **Deliverables:** module, unit tests L1, L2, L4, L6, L7, L12.
- **Acceptance:** tests pass; `mypy --strict`; ruff clean; no outer-test row reaches selection
  (canary test L1).
- **Risks:** compute cost of 45 bands × 1 196 segments. Mitigation: measured 6.7 ms per
  segment-band, about 6 min for the real cube.
- **Dependencies:** week 1 freeze.

## Week 3 (Dec 7–13): statistics, decision rules, report

- **Objective:** S1, S2, S3, P1/P3/P2, R1 and the report writer, all from the frozen config.
- **Tasks:** S1 bearing bootstrap (as v0.4); S2 class-stratified paired bootstrap; S3 permutation
  with fold regeneration and Clopper–Pearson interval; decision table wording exactly as section
  10.3; results JSON with seeds, config hash, commit and environment; `pumpguard bandselect` CLI.
- **Role:** Engineer.
- **Inputs:** week 2 module.
- **Deliverables:** tests L3, L5, L8–L11, L13 and a determinism test.
- **Acceptance:** all L1–L13 tests pass; two runs on synthetic data give identical output.
- **Risks:** permutation runtime with 9 999 (owner decision). Mitigation: vectorise threshold
  fitting; measured 0.69 ms per fit.
- **Dependencies:** week 2.

## Week 4 (Dec 14–20): gate G1 review and synthetic positive controls

- **Objective:** implementation merged; G4a and G4b decided on synthetic data.
- **Tasks:** PR for weeks 2–3 (owner merges = G1); run G4a (3 kHz resonance) and G4b (8 kHz) with
  data seed 2026; write `docs/results/paderborn-real3-v0.5/synthetic/`.
- **Role:** Engineer (run, report), Owner (merge G1).
- **Inputs:** merged module; frozen synthetic set-up.
- **Deliverables:** G4a and G4b results with selected band per fold, ΔBA and S2 interval.
- **Acceptance:** each gate passes or fails by its frozen criterion. A failure stops the plan;
  no parameter is adjusted.
- **Risks:** G4a fails because the generator's resonance is too weak at 3 kHz. Mitigation: none
  allowed after freezing except a new amendment; report the failure.
- **Dependencies:** week 3, owner merge.

## Week 5 (Dec 21–27): negative control and pre-run checks

- **Objective:** G5 decided; real-data pre-run checks ready for approval.
- **Tasks:** run G5 (20 data sets × 200 permutations, about 64 min); prepare G2 (file counts,
  sample ratio, short files) and G3 (R0 and folds) scripts; ask the owner to approve running
  G2 and G3 on the real files (they compute no V1 outcome).
- **Role:** Engineer; Owner (approval for G2/G3).
- **Inputs:** synthetic gates; local Paderborn copy (outside Git).
- **Deliverables:** G5 report; G2/G3 scripts; approval request.
- **Acceptance:** G5 ≤ 3 of 20 at p ≤ 0.05. After approval: G2 counts equal 300 files and
  1 196 segments; G3 R0 within 1e-9 and folds equal.
- **Risks:** holiday availability. Mitigation: week 6 is a buffer.
- **Dependencies:** week 4 pass.

## Week 6 (Dec 28–Jan 3): buffer, then the confirmatory run if approved

- **Objective:** the single real-data run (G6), only with the owner's explicit approval.
- **Tasks:** request approval with the exact command, commit, config hash and expected runtime
  (about 83 min for the 9 999 permutations, plus about 6 min for the feature cube);
  run once; write the report whatever the outcome; commit results next to v0.4's.
- **Role:** Owner (approval), Engineer (run).
- **Inputs:** G1–G5 passed; G2/G3 passed.
- **Deliverables:** `docs/results/paderborn-real3-v0.5/` (JSON, Markdown report, figure, feature-cube
  hash, run log), as section 14 of the amendment specifies.
- **Acceptance:** one run; outputs list every item of section 12; conclusion uses the exact
  wording of section 10.3.
- **Risks:** a crash mid-run. Mitigation: the run log records it; a rerun is reported as a rerun.
- **Dependencies:** weeks 4–5; approval.

## Week 7 (Jan 4–10): results report and independent review

- **Objective:** a v0.5 report that a sceptical reader can check.
- **Tasks:** write the report (primary, secondary, exploratory clearly separated); reviewer
  checks numbers against the results JSON and the claims against the decision table; update
  dataset and protocol docs.
- **Role:** Engineer (report), Reviewer (check), Owner (approve).
- **Inputs:** G6 outputs.
- **Deliverables:** reviewed report; doc updates; draft v0.5.0 release notes.
- **Acceptance:** every number traces to the JSON; no claim exceeds the pre-registered wording.
- **Risks:** pressure to explain a null result away. Mitigation: the decision table fixes the
  wording in advance.
- **Dependencies:** week 6.

## Week 8 (Jan 11–17): release v0.5.0

- **Objective:** reproducible public release (owner approval required).
- **Tasks:** version bump, CHANGELOG, tag and GitHub release prepared on a branch; owner approves
  and publishes; reproduction instructions for the v0.5 run.
- **Role:** Engineer (prepare), Owner (publish).
- **Inputs:** week 7 report.
- **Deliverables:** v0.5.0 release; reproduction guide.
- **Acceptance:** CI green on the tag; wheel smoke test passes; results hashes listed in the
  release notes.
- **Risks:** packaging issues. Mitigation: the CI build job already tests the wheel.
- **Dependencies:** week 7 approval.

## Week 9 (Jan 18–24): draft amendment 3 (harmonic proximity, U7)

- **Objective:** a draft protocol for separating BPFO/BPFI peaks from 3× and 5× shaft harmonics.
- **Tasks:** draft using full 4 s records (0.25 Hz resolution) and narrower peak windows; state
  which v0.5 outputs the drafter has seen (the section 9.4 diagnostic) and keep v0.5 held-out
  results out of the design.
- **Role:** Engineer (draft), Reviewer, Owner (review).
- **Inputs:** v0.5 report; amendment 2 section 9.4 diagnostic.
- **Deliverables:** amendment 3 Draft 1 and its config, with the checker extended.
- **Acceptance:** reviewer finds no design choice tuned on held-out results.
- **Risks:** hindsight bias. Mitigation: disclosure section and an independent reviewer.
- **Dependencies:** week 7.

## Week 10 (Jan 25–31): open-source quality

- **Objective:** make the toolkit easier to trust and to contribute to.
- **Tasks:** NOTICE for third-party data licences; follow-ups F1–F4 from the PR #12 review;
  generalise the checker into `pumpguard protocol check`; CONTRIBUTING section on protocol
  amendments; close coverage gaps.
- **Role:** Engineer; Owner (merge).
- **Inputs:** PR #12 review; current test coverage.
- **Deliverables:** PRs for each item.
- **Acceptance:** CI green; coverage does not drop; licence notice reviewed by the owner.
- **Risks:** scope creep. Mitigation: one PR per item.
- **Dependencies:** none (can move earlier).

## Week 11 (Feb 1–7): external validation plan

- **Objective:** choose a second data set to test whether findings transfer beyond one rig.
- **Tasks:** shortlist public bearing or pump vibration data sets; check each licence from the
  original source; check sampling rate, labels and grouping unit; draft amendment 4 (external
  validation) without touching the data.
- **Role:** Engineer (research), Owner (choice).
- **Inputs:** v0.5 results; data-set documentation.
- **Deliverables:** comparison table with licence, grouping unit and fit to the protocol;
  amendment 4 Draft 1.
- **Acceptance:** owner picks one data set; licence allows the intended use.
- **Risks:** no data set with a clean grouping unit. Mitigation: report it and keep scope to
  Paderborn.
- **Dependencies:** week 8.

## Week 12 (Feb 8–14): consolidation

- **Objective:** a clear state of the project and the next quarter's plan.
- **Tasks:** retrospective; technical-report outline (methods, v0.4 and v0.5 results, null
  results included); update this roadmap and the decision register; freeze readiness for
  amendment 3 or 4.
- **Role:** Engineer, Owner.
- **Inputs:** weeks 1–11.
- **Deliverables:** updated roadmap; report outline; freeze-readiness report for the next
  amendment.
- **Acceptance:** owner approves the next-quarter plan.
- **Risks:** none specific.
- **Dependencies:** weeks 9–11.
