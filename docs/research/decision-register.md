# Scientific decision register

One row per decision that shapes what PumpGuard-AI claims. Status values: **Decided** (in force),
**Pending** (needs the owner), **Open** (known unknown, does not block), **Proposed** (engineer's
recommendation, not yet accepted). Last update: 2026-11-22.

| ID | Decision | Status | Owner of the decision | Evidence or reason | Where recorded |
|---|---|---|---|---|---|
| D-01 | Primary evaluation is stratified group k-fold by bearing; a random segment split is never the primary result | Decided | Owner | v0.4 leakage experiment shows random splits inflate scores | `docs/benchmark-protocol.md`, `leakage_results.json` |
| D-02 | Paderborn data from the Zenodo mirror, treated as CC BY-NC 4.0; raw files stay outside Git | Decided | Owner | Mirror cannot relax the original licence; KA08 missing from the mirror | `docs/datasets/paderborn-kat.md`, PR #12 |
| D-03 | Historical result JSON files are never edited, including the `"0.3.0"` version label | Decided | Owner | Editing breaks the four evidence hashes | Amendment 2, section 2.1 |
| D-04 | v0.5 candidate set: 44 grid bands, 9 containing 16 kHz excluded, 35 eligible, D0 as control and fallback | Decided (review 2) | Owner | Inverter switching at 16 kHz, aliasing at fs = 64 kHz | Amendment 2, section 8 |
| D-05 | δ = 0.05 margin before leaving D0; δ = 0 reported as sensitivity only | Decided (U1) | Owner | Coarse inner scores with 12 training bearings | Amendment 2, section 9.2 |
| D-06 | Direct test of H1 is the class-stratified paired bearing bootstrap (S2, 10 000 replicates) | Decided (review 2) | Owner | Review 1 finding 4 | Amendment 2, section 10.2 |
| D-07 | S3 permutation count: 1 000 or 9 999 | **Pending** | Owner | Trade-off: Monte Carlo SE ≈ 0.007 vs ≈ 0.002 near p = 0.05; ≈ 8 vs ≈ 83 min | Amendment 2, section 15 (D-perm); freeze-readiness report |
| D-08 | H1 supported only if P1, P3 and P2 hold; R1 needed for a reproducible-band claim | Approved in review 2; **final sign-off pending** | Owner | Section 10.3 | Amendment 2, section 10.3 |
| D-09 | G3 reference is 0.4685836297141851 within 1e-9, plus the five v0.4 outer folds | Proposed in Draft 5; **approval pending** | Owner | Value read from `benchmark_results.json`; folds recomputed from stored labels | Amendment 2, section 13; config `gates.G3` |
| D-10 | Freeze only after PR #12 is merged (G0 a′) | Proposed in Draft 5; **approval pending** | Owner | Frozen protocol must point at evidence on `main` | Amendment 2, section 13 |
| D-11 | Acquisition-system anti-alias filter is not documented (U8) | Open | — | Only the 30 kHz charge-amplifier low-pass is documented | Amendment 2, sections 5, 6, 15 |
| D-12 | Harmonic proximity (BPFO/BPFI near 3× and 5× f_r at 900 rpm) handled by a separate amendment 3 | Decided (U7) | Owner | 0.81 Hz separation at 1 s segments | Amendment 2, section 15 |
| D-13 | Running G2 and G3 on the real files (no V1 outcome) needs explicit approval | Proposed | Owner | Real-data access rule | Roadmap week 5 |
| D-14 | The confirmatory real-data run (G6) needs explicit approval and runs once | Decided (master instructions) | Owner | Pre-registration | Amendment 2, section 13; roadmap week 6 |
| D-15 | Add a NOTICE stating that derived results and figures come from CC BY-NC 4.0 data | Proposed | Owner | MIT covers code only | PR #12 review |
| D-16 | Publish branch `docs/amendment-2-v0.5` and open a PR for Draft 5 | **Pending** | Owner | Public upload needs approval | This session |
