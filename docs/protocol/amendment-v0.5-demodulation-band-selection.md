# Protocol amendment 2 (v0.5): training-only demodulation band selection at 900 rpm

| | |
|---|---|
| Amends | [`docs/benchmark-protocol.md`](../benchmark-protocol.md) (fixed protocol + amendment 1) |
| Amendment dates | Draft 1: 2026-11-21. Drafts 2–4: 2026-11-22. **Draft 5: 2026-11-22** (pre-freeze audit corrections, section 17) |
| Status | **DRAFT** (Draft 5). Design approved in review 2; pre-freeze audit corrections applied; PR #12 merge, permutation-count decision and owner sign-off pending. Not executed |
| Machine-readable configuration | [`amendment-v0.5-config.json`](amendment-v0.5-config.json), checked against this text by `scripts/protocol/check_amendment2.py` (section 18) |
| Based on | v0.4 results in [`docs/results/paderborn-real3/`](../results/paderborn-real3/README.md), identified by content hash (section 2.1) |
| Scope | Paderborn KAt `real3` task, envelope physics rule only |

**This amendment precedes the v0.5 experiment.** No demodulation band other than the v0.4
default (6.4–25.6 kHz) has been applied to Paderborn data. No v0.5 code exists. The authors of
this draft know the v0.4 results, including the per-condition scores and the per-bearing
envelope medians at the default band; those results motivate the study and are listed in
section 2. Nothing else about candidate bands has been observed. Between Draft 1 and Draft 5,
only primary sources (the 2016 publication, the KAt rig page), v0.4 file metadata (sample
counts), the stored v0.4 result files and the remote repository state were consulted.

---

## 1. Purpose

v0.4 found that the envelope physics rule detects damage at chance level at 900 rpm. This
amendment fixes, before any experiment, one way to test whether a demodulation band chosen on
**training bearings only** improves detection at 900 rpm on **bearings never used in
selection or fitting**, and how to decide the answer.

The goal is a defensible yes or no. A higher score obtained any other way does not count.

## 2. Evidence from v0.4 (frozen, not re-analysed here)

Source: `benchmark_results.json`, stratified group 5-fold by bearing, seed 0.

| Model (v0.4) | Detection BA, all conditions | Detection BA at `N09_M07_F10` (900 rpm) | Detection BA at the three 1 500 rpm conditions |
|---|---|---|---|
| `envelope_rule` | 0.691 [0.56, 0.79] | **0.469** | 0.762–0.771 |
| `single_feature_threshold` | 0.766 [0.60, 0.92] | 0.671 | 0.786–0.810 |
| `logistic_regression` | 0.739 [0.50, 0.90] | 0.753 | 0.721–0.751 |
| `random_forest` | 0.699 [0.48, 0.90] | 0.616 | 0.690–0.758 |

BA = balanced accuracy. Per-condition values in v0.4 have no interval of their own.

Three facts follow and constrain the design:

1. **Information exists at 900 rpm.** Logistic regression on the same segments reaches 0.753
   there, so the failure is specific to the envelope rule, not to the data.
2. **v0.4 fitted one envelope threshold across all four conditions.** If envelope ratios run
   lower at 900 rpm, a threshold set mostly by 1 500 rpm data misclassifies 900 rpm segments
   regardless of band. Control arm C0 (section 7) separates this from any band effect.
3. **Leakage is large on this data.** Random segment splits inflated the random forest from
   0.512 to 0.994 (diagnosis). Band selection is a fitted choice and must sit inside the same
   bearing-wise separation as every other fitted quantity.

### 2.1 Identity of the v0.4 evidence

**Commit history.**

- The v0.4 results were produced on 2026-11-21 and committed locally as `7b9ca46` (full hash
  `7b9ca464ec4a15a623d112183940d1cd3aa79b6a`), on top of `1d8d1ab`.
- The code of `1d8d1ab` was later merged to `main` as PR #11 and released as `v0.4.0` (tag at
  `90e2282`). That release does **not** contain the real3 results.
- On 2026-11-22 the results commit was replayed on top of the current `main` (`68848a5`) as
  **`d203b5eed799f6bea33f0ea8c965ac1fc7639e98`** on branch `feat/paderborn-real3-evidence`. The
  only change from `7b9ca46` is that its `CHANGELOG.md` entries moved from the released
  `[0.4.0]` section to `[Unreleased]`.
- **Published 2026-11-22:** the project owner pushed the branch from the bundle, preserving
  `d203b5e`, and opened [PR #12](https://github.com/ymesbah-blip/-PumpGuard-AI/pull/12)
  against `main`. The four hashes below were then recomputed from the files served by GitHub,
  independently by the reviewer and by this drafting session. All four match. PR #12 has
  25 changed files, no raw data, and is not merged.

**Content hashes.** Because commit hashes change when history is replayed, this amendment
identifies the evidence by the content of the files. The hashes below were computed on the
original commit and found **byte-identical** on `d203b5e`:

| File in `docs/results/paderborn-real3/` | SHA-256 |
|---|---|
| `benchmark_results.json` | `8a5049e42cc412904240c0768a34e090d65128ebcf288274c3d810bb76f4bf01` |
| `leakage_results.json` | `dbd31fce4e6ab4fedf95694a60678805749d10defd7210fe0f6f054ac598a250` |
| `feature_table_provenance.json` | `0bd2d22d270f5a4da06456cd5d18b02f96d276b83ece4345426da10aa90d2f20` |
| `paderborn_verification.json` | `77ad58199cd0789a78cc28c57b6853bb3d784049977aebac63440d2a17e797aa` |

**Version label in the evidence files.**

- `feature_table_provenance.json` and the benchmark and leakage results record
  `pumpguard_version: "0.3.0"`, although the public release is v0.4.0.
- The run used commit `1d8d1ab` plus the source changes of the evidence commit. Between
  `1d8d1ab` and the v0.4.0 release (`90e2282`), `src/` and `tests/` differ in one line only:
  `_version.py`, `"0.3.0"` → `"0.4.0"`, set by the release commit `7d5ca74` after the code was
  written.
- The code that produced the four evidence files is the v0.4.0 code under its earlier version
  label, plus two parts of the evidence commit that existed when the run started: the
  empty-`Unit` reader fix and the archive-verification module (with its `paderborn verify` CLI).
- Three parts of the evidence commit came **after** the run and did not affect any hashed file:
  - the report-header wording fix in `benchmark.py`, after which `benchmark_report.md` was
    regenerated from the unchanged `benchmark_results.json`;
  - the KI04/KI14 description strings in the bearing table, edited while feature extraction
    was running, after the process had loaded the module; these strings enter no result file;
  - the figure script and the documentation.
- The results files record a package version but no commit hash. The code state is therefore
  reconstructed, not recorded. Gate G3 (exact reproduction of R0 and of the outer folds) is the
  empirical check of this reconstruction.
- The evidence files stay as recorded. Rewriting the label would break their hashes.

**Origin of `paderborn_verification.json`.** It was written on 2026-11-21 by
`pumpguard.datasets.paderborn_archives.write_verification()`. Its inputs were:

- **Archive MD5s, computed twice on the project owner's computer** (Windows `Get-FileHash` in
  `scripts/paderborn/fetch_real3.ps1`, and an independent Python `hashlib` pass). Both were
  compared with the Zenodo files API values built into `ZENODO_MANIFEST`. 15 of 15 matched.
- **`check_inventory()` on the extracted files.** It found 15 bearings × 4 conditions × 20
  measurements, with none missing.

Gate G0(a) requires the evidence branch on GitHub, and a reviewer to confirm these four hashes
against the files as served by GitHub, before freezing.

## 3. Consistency with the existing protocol

The fixed protocol states: "Envelope demodulation band: default 0.1–0.4 fs (6.4–25.6 kHz).
Tuning the band is **not** part of this protocol. A later protocol may select it on training
folds only." This amendment is that later protocol.

It changes nothing retroactively:

- v0.4 tasks, folds, features, baselines, metrics, intervals, decision rules and reported
  results stay as published.
- The existing decision rule stays in force for H1 as criterion P1: "a difference counts as
  meaningful only if the better method's lower 95 % bound exceeds the other's point estimate".
- Amendment 1 (learned models) is unaffected.

Two extensions are proposed and justified in section 10. Both add conditions; neither relaxes
the existing rule.

- **P3:** a paired test of the difference ΔBA = BA(V1) − BA(C0), as the direct inferential
  test of H1.
- **P2:** a permutation test, used only to show that V1 performs above its empirical null
  distribution under exchangeability of bearing labels. It is not evidence that V1 beats C0.

No contradiction with existing documentation was found.

## 4. Hypotheses and research questions

**H1 (primary, confirmatory).** At 900 rpm (`N09_M07_F10`), the envelope rule with a
demodulation band selected by nested, bearing-wise cross-validation on training bearings only
(arm V1) detects damage on unseen bearings better than the same rule with the v0.4 default band
and the same condition-specific threshold fitting (arm C0).

**H0.** ΔBA = BA(V1) − BA(C0) ≤ 0 at 900 rpm.

Secondary questions (descriptive, no confirmatory claim):

- **RQ2, threshold effect.** Does fitting the threshold on 900 rpm training data alone (C0)
  already recover detection, compared with the frozen v0.4 rule (R0 = 0.469, exact value in G3)?
- **RQ3, label-free selection.** Does a band chosen without labels (maximum spectral kurtosis on
  training segments, arm V2) perform like V1?
- **RQ4, global band.** Does one band selected on all four conditions (arm VG) change detection
  at 1 500 rpm, for better or worse?
- **RQ5, diagnosis.** With V1's band, how does the envelope rule's outer vs inner diagnosis at
  900 rpm compare with C0?
- **RQ6, stability.** Do different outer folds select the same band, and does it match a
  physically plausible resonance region?
- **RQ7, exclusion sensitivity.** Does searching all 45 bands, including those that contain the
  inverter switching frequency (arm V1-45), change the selection or the result?

## 5. Physical justification

**Mechanism.** A localised defect produces a short impact each time a rolling element passes it.
Each impact excites structural resonances of the bearing housing, adapter and sensor at
frequencies far above the defect frequency. Band-pass filtering around such a resonance and
taking the envelope (Hilbert magnitude) recovers the impact repetition rate: BPFO for the outer
race, BPFI for the inner race. An inner-race defect rotates with the shaft through the load
zone, which adds ±1× shaft sidebands around BPFI.

**Why the band matters.** The v0.4 default band (6.4–25.6 kHz) is 19.2 kHz wide. If the
impact-excited resonance occupies only part of it, the rest adds broadband noise and lowers the
peak-to-median ratio the rule thresholds. Impact energy rises with rolling speed, so at 900 rpm
the impulses are weaker relative to background, and a band concentrated on the resonance region
could restore prominence. That is the mechanism H1 tests.

**Electrical interference at 16 kHz.**

- The motor is driven by a KEB Combivert 07F5E 1D-2B0A inverter with a **16 kHz switching
  frequency**. The motor is a 425 W PMSM with **p = 4 pole pairs** (Lessmeier et al. 2016, p. 7),
  so its electrical frequency is f_el = p · f_r = 60 Hz at 900 rpm and 100 Hz at 1 500 rpm.
- Switching produces components at k · 16 kHz with sidebands at multiples of f_el. The sampling
  rate is 64 kHz = 4 × 16 kHz, so **every switching harmonic aliases onto 0, 16 or 32 kHz**: for
  example, 48 kHz → 16 kHz and 80 kHz → 16 kHz.
- The only documented analogue filter is the charge amplifier's 30 kHz low-pass, 2nd order. On
  its own it would attenuate these harmonics only weakly: if it were a Butterworth filter, which
  the source does not state, it would give about −8.8 dB at 48 kHz.
- **Anti-alias filtering in the acquisition system is not documented.** The publication states
  only that the signal is digitised at 64 kHz. If the acquisition hardware filters before
  sampling, harmonics above 32 kHz are suppressed and only the 16 kHz fundamental and its
  in-band sidebands remain relevant. Whether components above 32 kHz reach the samples is
  therefore unknown.
- If switching noise couples into the vibration channel, it therefore concentrates around
  16 kHz. Its amplitude can vary with motor current, and so with load and speed, which would put
  an electrical modulation into the envelope.
- None of this proves that the vibration channel is contaminated. It does make 16 kHz a known
  candidate for non-mechanical content. The primary search therefore excludes bands that contain
  16 kHz (section 8), and a selected band near 16 kHz is never read automatically as a
  mechanical resonance.

**Competing explanations the experiment cannot remove** (they bound what H1 can achieve):

1. **Threshold shared across speeds** (fact 2 above). Arm C0 isolates it.
2. **Shaft harmonics inside the peak window.** For the 6203 geometry, BPFO = 3.0543 × f_r and
   BPFI = 4.9457 × f_r, so both lie 0.054 × f_r from the 3rd and 5th shaft harmonics. At 900 rpm
   the gap is **0.81 Hz**, below the 1 Hz resolution of a 1 s segment, and well inside the
   ±3 Hz peak-search window (`peak_near`: max(3 bins, 2 % of f₀)). Any shaft-synchronous
   modulation at 3× or 5× therefore counts as a "defect peak" in every class. At 1 500 rpm the
   gap is 1.36 Hz, still inside the window. Band selection cannot fix this; it lives in the
   envelope-spectrum stage. Section 9.4 adds a non-confirmatory diagnostic. Amendment 3 will
   address it (decision U7).
3. **Lower impact energy at low speed** may push some defects (KA15, KA22 and KA30 are already
   weak at 1 500 rpm) below the noise floor in every band.

## 6. Signal facts used (no value is assumed)

| Quantity | Value | Source |
|---|---|---|
| Vibration channel | `vibration_1`, accelerometer PCB 336C04 at the top of the bearing module | Lessmeier et al. (2016), p. 7; dataset card |
| Sampling rate | 64 kHz (Nyquist 32 kHz) | Publication; files: vibration samples ÷ 4 kHz-channel samples ≈ 16 in every used file (256 004 / 16 001 = 15.999) |
| Signal-conditioning low-pass | Kistler 5015A charge amplifier, **30 kHz low-pass, 2nd order** (filter type not stated) | Cut-off: publication p. 7. Order: KAt rig page ("filter 30 kHz (2nd order)") |
| Acquisition-system anti-alias filter | **Not documented** | Open item U8 (section 15) |
| Accelerometer frequency response | **Not documented** in the publication or rig page; datasheet not obtained | Open item U5 (section 15) |
| Drive | KEB Combivert 07F5E 1D-2B0A inverter, **16 kHz switching**; 425 W PMSM, p = 4 | Publication p. 7 |
| Recording length | Nominal 4 s. Observed in files: 256 004 vibration samples typical. 4 files at 900 rpm hold 255 997–255 999 samples (just under 4 s; 3 whole 1 s segments). 4 files at 1 500 rpm were rejected in v0.4 for inconsistent vibration length; none at 900 rpm | v0.4 feature table and file metadata |
| Segmentation | Non-overlapping 1 s (64 000 samples), as v0.4 | Protocol |
| 900 rpm data | 300 files, **1 196 segments** (healthy 399, outer 398, inner 399), 15 bearings | v0.4 feature table |
| Shaft speed | Measured `speed` channel, 899.3–900.2 rpm at `N09_M07_F10` | v0.4 provenance |
| Defect frequencies, 6203 (8 balls, 6.75 mm, pitch 28.55 mm), 900 rpm | f_r 15.00 Hz, BPFO 45.81 Hz, BPFI 74.19 Hz, FTF 5.73 Hz, BSF 29.95 Hz | `pumpguard bearing --rpm 900 --bearing 6203`; geometry confirmed by fact sheets |
| Same at 1 500 rpm | f_r 25.00 Hz, BPFO 76.36 Hz, BPFI 123.64 Hz | same |
| Envelope implementation | 4th-order Butterworth band-pass applied forward and backward (`sosfiltfilt`, zero phase; effective response \|H\|², −6 dB at the nominal edges), Hilbert magnitude, mean removed, Hann window, single-sided amplitude spectrum | `pumpguard.spectral.envelope`, `amplitude_spectrum` |
| Feature | `env_bpfo_ratio`, `env_bpfi_ratio` = peak within ±max(3 bins, 2 % f₀) divided by the median envelope-spectrum level over (0, 5 f₀] | `pumpguard.spectral.peak_to_median_ratio` |
| Envelope rule | detection: damaged if max(BPFO ratio, BPFI ratio) > threshold; threshold maximises training balanced accuracy, inverted rules refused | `pumpguard.baselines.EnvelopeRule` |

Gate G2 checks the counts and ratios above on the files before any v0.5 computation.

## 7. Arms

All arms use identical segments, measured speeds, geometry, peak definition and outer folds.
Only the band set and the data used to fit the threshold differ.

| Arm | Band | Threshold fitted on | Role |
|---|---|---|---|
| **V1** | Selected per outer fold by nested inner CV from the **35 eligible bands**, with D0 as fallback (section 9.2) | 900 rpm segments of the 12 outer-training bearings | Primary experimental |
| **C0** | D0 = v0.4 default, 6 400–25 600 Hz | 900 rpm segments of the 12 outer-training bearings | Primary control (isolates the band) |
| **R0** | D0 | All four conditions of the outer-training bearings (exactly v0.4) | Frozen reference, must reproduce 0.4685836297141851 within 1e-9 (gate G3) |
| V1-45 | As V1, but from all 45 candidates, including the 9 that contain 16 kHz | as V1 | Secondary, pre-specified sensitivity analysis (RQ7) |
| V2 | Per outer fold: the eligible band (of 35) with the largest median spectral kurtosis over the 900 rpm segments of the 12 outer-training bearings. Spectral kurtosis of one segment in band b: K = mean(\|a\|⁴) / mean(\|a\|²)² − 2, with a the analytic signal of the band-passed segment (Antoni's definition). No labels, no δ rule, no D0 fallback; ties broken as in V1 (wider bandwidth, then lower f_lo) | as V1 | Secondary (RQ3) |
| VG | Per outer fold: nested inner CV on all four conditions pooled, 35 eligible bands, D0 fallback | All conditions (as v0.4) | Secondary (RQ4) |

## 8. Candidate search space

### 8.1 Definition

Dyadic bandwidths with 50 % overlap, the same bandwidths as levels 1 to 4 of Antoni's fast
kurtogram at 64 kHz (fs/2^(k+1) = 16, 8, 4, 2 kHz):

- Bandwidth B ∈ {2, 4, 8, 16} kHz.
- Lower edges f_lo = 1 000 Hz + m · B/2, m = 0, 1, 2, …, keeping f_hi = f_lo + B ≤ 27 000 Hz.
- This gives **44 grid bands**: 25 at 2 kHz, 12 at 4 kHz, 5 at 8 kHz, 2 at 16 kHz.

**Switching exclusion.** A band is excluded from the primary search if
f_lo ≤ 16 000 Hz ≤ f_hi. That removes **9 bands** (kHz): (14, 16), (15, 17), (16, 18),
(13, 17), (15, 19), (9, 17), (13, 21), (1, 17) and (9, 25). Bands with 16 kHz exactly at an
edge are excluded too, because the filter passes −6 dB there.

The sets are:

| Set | Content | Use |
|---|---|---|
| **Eligible (35)** | Grid bands that do not contain 16 kHz | Selection in V1, V2, VG |
| **D0** | (6 400, 25 600) Hz, contains 16 kHz | Control C0, reference R0, fallback for V1/VG under the δ rule; never chosen as "best" |
| **Full (45)** | 44 grid bands + D0 | Sensitivity arm V1-45 only |

All sets are fixed and do not depend on any data. The implementation stores them in the frozen
config JSON.

### 8.2 Justification of each constraint

| Constraint | Value | Reason |
|---|---|---|
| Upper edge | ≤ 27 kHz | Limited by the charge-amplifier low-pass: 2nd order at 30 kHz, filter type not stated. If it were Butterworth, the response would be about −1.8 dB at 25.6 kHz (D0's edge) and −2.2 dB at 27 kHz: non-flat but usable, because the feature is a ratio within one band. Below Nyquist (32 kHz) with a 5 kHz guard against content aliased onto 32 kHz. **27 kHz is not a calibrated sensor range**: the accelerometer's response there is unknown (U5). |
| Lower edge | ≥ 1 kHz | Keeps direct low-order components out of the band: the 8th harmonic of BPFI at 1 500 rpm is 989 Hz. Envelope peaks must come from demodulation, not from defect or shaft harmonics passing the filter directly. Also keeps content aliased near 0 Hz out. Matches the project's existing 1 kHz definition of "high frequency" (`hf_energy_ratio`). |
| Minimum bandwidth | 2 kHz | Approximate rationale, not a spectral guarantee. The feature's reference level is the median over (0, 5 f₀]. For BPFI at 1 500 rpm that window reaches 618 Hz, so modulation sidebands up to ±618 Hz should pass. B = 2 kHz gives a 1 kHz half-width, but the zero-phase filter is already −6 dB at the edges and attenuates progressively before them. A resonance off the band centre loses more of one sideband. A 1 kHz band would cut part of the reference window at 1 500 rpm and inflate ratios artificially. At 900 rpm the window reaches 371 Hz. |
| Maximum bandwidth | 16 kHz plus D0 (19.2 kHz) | Wider bands converge to D0. |
| Switching exclusion | f_lo ≤ 16 kHz ≤ f_hi | Section 5. Sidebands at multiples of f_el (60 / 100 Hz) mostly stay within ±1 kHz of 16 kHz at low order. Bands with an edge at 15 or 17 kHz may still catch higher-order sidebands, which is a residual risk; V1-45 and cautious interpretation address it. |
| Grid resolution | 50 % overlap | Each frequency lies in two candidates of each bandwidth, so a resonance near an edge is not missed. The grid stays small, which limits selection optimism. |

## 9. Nested bearing-wise validation

### 9.1 Outer loop (evaluation)

- Data: the 1 196 segments of `N09_M07_F10` (V1, V1-45, V2, C0); all conditions for R0 and VG.
- Folds: `stratified_group_kfold(groups=bearing, labels=3-class label, n_splits=5, seed=0)`, the
  v0.4 assignment. The function depends only on the bearing list and bearing labels, so the
  partition equals v0.4's. Implementation asserts this against `benchmark_results.json`
  (gate G3).
- Each outer fold tests 3 bearings (one per class) and trains on 12 (4 per class).

### 9.2 Inner loop (band selection, training bearings only)

For outer fold k, with training bearings T_k:

```
inner_folds = stratified_group_kfold(groups=T_k bearings, labels=3-class, n_splits=4,
                                     seed=1000 + k)    # 9 train / 3 validation (one per class)
for each band b in ELIGIBLE (35) plus D0:
    pooled_pred = {}
    for (inner_train, inner_val) in inner_folds:
        rule = EnvelopeRule("detection").fit(features[b][inner_train], y_det[inner_train])
        pooled_pred[inner_val] = rule.predict(features[b][inner_val])
    S[b] = balanced_accuracy(y_det[T_k], pooled_pred)       # inner score, training bearings only
b_best = argmax over ELIGIBLE of S[b]; ties broken by (wider bandwidth, then lower f_lo)
b_star = b_best if S[b_best] >= S[D0] + 0.05 else D0       # default preferred unless clearly beaten
rule_k = EnvelopeRule("detection").fit(features[b_star][T_k], y_det[T_k])
outer_pred[test_k] = rule_k.predict(features[b_star][test_k])
```

`features[b]` is the pair (`env_bpfo_ratio`, `env_bpfi_ratio`) computed for band b. The
function that implements this loop receives only the rows of T_k for selection and fitting; the
outer-test rows are passed only to `predict` with the frozen band and threshold. V1-45 runs the
same code with FULL (45) in place of ELIGIBLE.

**Why δ = 0.05** (decision U1). With 12 training bearings the inner score moves in coarse steps,
and the maximum over 35 candidates is biased upward. Requiring a 0.05 margin over the default
before leaving it limits selection on noise. δ = 0 is reported as a sensitivity analysis and
cannot change the primary conclusion.

### 9.3 Why computing features for all segments first is not leakage

`features[b]` for a segment is a fixed function of that segment alone (filter, Hilbert, FFT,
peak ratio) with no fitted parameter. Computing it for every segment once, before any split,
uses no label and no other segment. Selection and threshold fitting read only training rows.
This precomputation is allowed; reading test rows during selection is not, and section 11 tests
for it.

### 9.4 Non-confirmatory diagnostic (cannot change any decision)

For 900 rpm segments, report the envelope-spectrum amplitude at exact 3× and 5× f_r next to the
BPFO and BPFI peak values, by class, for D0 and for each selected band. Also report envelope
spectra of full 4 s records (0.25 Hz resolution), where BPFO and 3× f_r are about 3 bins apart.
This only describes the size of competing explanation 2. Amendment 3 will treat it as its own
confirmatory question.

## 10. Endpoints, statistics and decision criteria

### 10.1 Endpoints

- **Primary endpoint:** detection balanced accuracy (healthy vs damaged) at `N09_M07_F10` on
  outer-test bearings, predictions pooled over the 5 outer folds, for V1 and C0. The primary
  estimand is their paired difference, ΔBA = BA(V1) − BA(C0).
- **Secondary:**
  - macro-F1, per-class recall and the confusion matrix;
  - per-bearing accuracy;
  - R0, V1-45, V2 and VG results (VG per condition and overall);
  - diagnosis BA at 900 rpm for V1's band vs C0 (decision U2: descriptive only);
  - selected band per outer fold and arm;
  - inner-to-outer optimism (mean inner S[b*] minus outer BA);
  - δ = 0 sensitivity.
- **Exploratory:** the section 9.4 diagnostic.

### 10.2 Statistics

**S1. Marginal intervals (as v0.4).** For every reported BA: 95 % percentile bootstrap over
bearings, 1 000 replicates, seed 0, not stratified. This is the v0.4 procedure, kept so that P1
is computed exactly as the existing rule defines it.

**S2. Paired difference (direct test of H1).** For ΔBA = BA(V1) − BA(C0):

- Use a **class-stratified paired bearing bootstrap** with 10 000 replicates, seed 0.
- Each replicate draws 5 bearings with replacement within each class (healthy, outer, inner).
  That keeps every class represented, so balanced accuracy is always defined.
- It then evaluates **both arms on the same drawn bearings**, using their fixed outer
  predictions, and computes ΔBA. The 95 % percentile interval comes from the replicates.
- Pairing removes the bearing-to-bearing variation that both arms share. This is the correct
  test of "V1 better than C0".

**S3. Permutation test (empirical null for V1; not a test of H1).**

- Permute the 3-class labels among the 15 bearings, preserving class counts. Derive detection
  labels and regenerate the outer folds with seed 0.
- Rerun the complete nested V1 procedure and record the pooled outer BA.
- Do this for 9 999 permutations (owner decision D-perm, 2026-11-22), seed 12345.
- p = (1 + k) / (1 + N), with k = #{null BA ≥ observed BA} and N = 9 999, so p = (1 + k) / 10 000.
  The smallest attainable p is 0.0001.
- **Monte Carlo uncertainty is reported with p:** the permutation seed, the number of completed
  permutations (must equal N = 9 999), k, and the 95 % Clopper–Pearson interval for the
  exceedance probability k / N. Near the threshold the standard error is about
  √(0.05 · 0.95 / N) ≈ 0.002. The decision uses the point value p ≤ 0.05 as registered. No
  permutations are added after the result is seen. If the interval contains 0.05, the report
  says that P2 is close to the threshold.

**What S3 tests.**

- It tests H₀′: bearing labels are exchangeable with respect to V1's complete procedure. In
  other words, V1's features carry no class information that transfers to unseen bearings.
- It does **not** test whether V1 beats C0.

**Why an empirical null rather than a fixed value.**

- For binary balanced accuracy, predictions made independently of the true labels have an
  expected score of 0.5.
- The finite-sample distribution of the complete grouped procedure can still differ from a
  distribution centred at 0.5 with simple binomial spread. That procedure covers bearing-level
  label exchange, fold regeneration, nested selection and threshold fitting. Two things cause
  the difference:
  - the 1 196 segments are clustered in 15 bearings;
  - the fitted threshold depends on which bearings share a fold. The v0.4 leakage experiment
    and the synthetic study produced group-split scores below 0.5 for this reason.
- S3 compares V1 with its empirical null under exchangeability of bearing labels. It does not
  assume a different universal chance level.
- Nested CV already keeps band selection out of the outer estimate. S3 adds only the reference
  distribution.

### 10.3 Decision rules (fixed now)

**H1 is supported** only if all three hold:

| Criterion | Statistic | Condition | Role |
|---|---|---|---|
| **P1** | S1 | lower 95 % bound of BA(V1) > point estimate of BA(C0) | Existing project rule |
| **P3** | S2 | lower 95 % bound of ΔBA > 0 | Direct inferential test of H1 |
| **P2** | S3 | permutation p ≤ 0.05 | Precondition: V1 above its empirical null under bearing-label exchangeability. Not evidence of V1 > C0 |

**Outcomes and the wording that will be used:**

| Condition | Reported conclusion |
|---|---|
| P1, P3, P2 hold | "Training-only band selection improved 900 rpm detection on unseen bearings under the pre-registered criteria." |
| P1 and P3 hold, P2 fails | "Inconclusive: V1 beats the control, but its score is not distinguishable from the empirical permutation null." |
| P3 holds, P1 fails | "H1 not supported under the project's decision rule. The paired difference favours V1 (ΔBA = … [lo, hi]) but is below the pre-registered threshold for a meaningful difference." |
| P1 holds, P3 fails | "H1 not supported: the paired difference is not distinguishable from zero." |
| Neither P1 nor P3, ΔBA ≥ 0 | "H1 not supported: no meaningful improvement at the pre-registered criteria." |
| ΔBA < 0 | "H1 not supported: band selection did not help and may have hurt." |

**A "reproducible band" claim** additionally needs **R1:** in at least 4 of 5 outer folds, the
selected band overlaps the most frequently selected band by ≥ 50 % of the narrower band's width.
Without R1, any improvement is described as fold-dependent, and no band is recommended as a new
default.

**Secondary questions** use the existing rule for descriptive statements only:

- RQ2: C0 vs R0, judged as C0's lower bound > the R0 point estimate (0.4685836297141851).
- RQ3: V2 vs C0.
- RQ4: VG per condition vs the v0.4 per-condition values.
- RQ7: V1-45 vs V1, reporting whether any selected band contains 16 kHz.

They support no confirmatory claim. Adopting any band as a new project default requires a
further amendment.

### 10.4 Comparison against the frozen v0.4 baselines

The v0.5 report lists, next to V1 and C0:

- R0, recomputed (must equal 0.4685836297141851 within 1e-9, gate G3);
- v0.4 `single_feature_threshold` at 900 rpm (0.671);
- v0.4 `logistic_regression` at 900 rpm (0.753, learned; context only).

v0.5 claims nothing about beating learned models. All v0.4 numbers are quoted from the frozen
results file, not re-tuned.

## 11. Leakage-prevention checklist

| # | Risk | Control | Verified by (test, to be written before the real run) |
|---|---|---|---|
| L1 | Band chosen with outer-test bearings | Selection function receives training rows only | Canary: set all outer-test features to NaN or random values; the selected bands must not change |
| L2 | Inner folds contain outer-test bearings | Inner folds built from T_k only | Assert inner bearings ⊂ T_k and ∩ test_k = ∅ for every k |
| L3 | Threshold fitted with test data | `EnvelopeRule.fit` on T_k rows only | Canary as L1, applied to thresholds |
| L4 | Segments of one bearing on both sides | Splits by bearing at both levels | Assert per fold: no bearing in both train and test |
| L5 | Outer folds differ from v0.4 (silent re-split) | v0.4 fold function and seed | Assert fold assignment equals the v0.4 assignment |
| L6 | Fitted preprocessing on all data | Features are per-segment, fit-free; no global scaling | Test that `features[b]` of a segment is identical when computed alone or in a batch |
| L7 | Labels entering features | Speed from the measured channel, condition from file names, geometry fixed | Code review plus test that the feature function has no label argument |
| L8 | Band sets, δ or seeds changed after seeing results | Sets, δ and seeds frozen here; amendment and config hashes recorded at freeze | Implementation reads the frozen config and checks its hash against the freeze record |
| L9 | Looking at outer results before all arms finish | Single scripted run writes all arms, then the report | Run log with timestamps; no intermediate outer metrics printed |
| L10 | Repeated runs with different seeds, best one kept | One run, fixed seeds | Results file stores seeds and config hash; any rerun is reported |
| L11 | Permutation null that skips selection or reuses the observed folds | Null reruns fold generation and the full nested selection for each permutation | Test on a toy cube that each permutation regenerates folds and records its own selected bands, and that they vary across permutations |
| L12 | Exclusion list derived from data | Eligible set is computed from the frequency rule in 8.1 only | Test that `candidate_bands()` returns exactly the 35 / 9 / 45 sets listed here, with no data argument |
| L13 | Paired bootstrap resamples the arms independently | One bearing draw per replicate, applied to both arms | Test: if V1 and C0 predictions are identical, every replicate gives ΔBA = 0 |

## 12. Reproducibility requirements

- **Code:** one commit tagged for the run. The package version and commit hash are stored in the
  results.
- **Data:** the v0.4 `paderborn_verification.json` (hash in 2.1) and the list of files used. The
  900 rpm set must be the 300 files / 1 196 segments of v0.4.
- **Configuration file** (JSON, frozen with this amendment):
  - the eligible (35), excluded (9) and full (45) band lists, and D0;
  - δ = 0.05;
  - inner k = 4 with seeds 1000 + k;
  - outer seed 0;
  - S1 bootstrap seed 0, 1 000 replicates;
  - S2 bootstrap seed 0, 10 000 replicates;
  - S3 permutation seed 12345, 9 999 permutations;
  - the tie-break order;
  - the SHA-256 values of section 2.1.
- **Feature cube:** all 45 bands × 1 196 segments (and all conditions for VG), saved with
  SHA-256.
- **Outputs:**
  - inner score table (all bands × all outer folds × arms);
  - selected band per fold and arm;
  - outer predictions per segment;
  - all metrics with intervals;
  - S2 replicate distribution;
  - permutation null distribution;
  - Markdown report and JSON.
- **Environment:** Python, NumPy, SciPy and pandas versions recorded in the results JSON.
- **Determinism:** two runs on the same machine must produce identical selections and metrics
  (tested on synthetic data).

## 13. Execution gates (in order; any failure stops the run)

| Gate | Requirement |
|---|---|
| G0 | In this order: (a) the evidence branch `feat/paderborn-real3-evidence` is on GitHub and the four hashes of section 2.1 are confirmed against the files served by GitHub; (a′) PR #12 is merged into `main` on the project owner's authorization; (b) all content edits are complete and `scripts/protocol/check_amendment2.py` passes; (c) the project owner's decisions (permutation count, approval) are recorded in section 16; (d) the status is changed to FROZEN with the date, in this file and in the config's `protocol_status`; (e) **only then** SHA-256 of this file and of the config JSON are computed and recorded in `CHANGELOG.md` and `amendment-v0.5-freeze-record.json`. |
| G1 | Implementation and tests merged: L1–L13, band sets, tie-break, δ rule, S2 pairing, determinism |
| G2 | Measured on the files, not assumed: 300 files and 1 196 segments at 900 rpm. Every used file has a vibration ÷ 4 kHz-channel sample ratio of 16 (± 0.1 %) and a vibration length within ±10 % of 4 s. At 900 rpm, the 4 known short files (255 997–255 999 samples, 3 segments) are the only ones below 256 000. Any deviation stops the run and requires an amendment. |
| G3 | R0 recomputed equals the stored v0.4 value **0.4685836297141851** within an absolute tolerance of 1e-9, and the outer fold assignment equals v0.4's: fold 0 = {K003, KA04, KI21}, fold 1 = {K005, KA16, KI14}, fold 2 = {K004, KA22, KI16}, fold 3 = {K001, KA30, KI04}, fold 4 = {K002, KA15, KI18} |
| G4 | **Synthetic positive control** (section 13.1): V1 must find a known resonance that D0 cannot see, and must beat C0 |
| G5 | **Synthetic negative control** (section 13.1): smoke test against gross false-positive inflation |
| G6 | Single real-data run; report written regardless of outcome; results committed next to v0.4's |

### 13.1 Synthetic controls (validate the implementation; not the v0.5 experiment)

**Common set-up:**

- `pumpguard.signals` generator at fs = 64 kHz, 1 s segments, 6203 geometry.
- 900 rpm for every machine (no machine-specific speed). Each segment keeps the generator's
  speed drift: rpm × (1 + 0.005 · N(0, 1)).
- 5 virtual machines per class (healthy, outer, inner), 20 segments per machine.
- Noise and severity drawn per machine from the `make_synthetic_dataset` defaults:
  noise_std 0.03–0.10, severity 0.5–1.5.
- Data seed 2026.
- The same code path, band sets, δ and seeds as the real run.

**G4a, resonance outside D0 (power check).** `resonance_hz = 3 000`: inside the eligible grid,
far below D0's 6.4 kHz edge. Pass requires both:

- (i) in ≥ 4 of 5 outer folds V1 selects a **non-D0** band with f_lo < 3 kHz < f_hi;
- (ii) ΔBA (V1 − C0) ≥ 0.20, with the S2 lower bound > 0.

D0 is not expected to see these impacts, so this tests the selection itself. It addresses the
review finding that a resonance inside D0 could pass even if selection never worked.

**G4b, resonance inside D0 (harm check).** `resonance_hz = 8 000`. Pass requires both:

- in ≥ 4 of 5 outer folds, V1 either keeps D0 or selects a band with f_lo < 8 kHz < f_hi;
- ΔBA ≥ −0.05.

Selection must not damage a case the default already handles.

**G5, no class information (false-positive smoke test).**

- 20 independent synthetic data sets in which every signal is generated healthy and the 3
  class labels are assigned to machines at random (5 / 5 / 5).
- Each runs the complete V1 procedure and S3 with 200 permutations (to bound compute).
- Pass: at most 3 of 20 reach p ≤ 0.05 (α = 0.05). A calibrated test expects 1; a calibrated
  test fails this gate with probability 0.016.
- **This is not a calibration proof.** Twenty data sets only detect gross inflation: a true
  false-positive rate of 0.25 would be caught with probability 0.77.

## 14. Required documentation and test updates (after approval, before the run)

**Code (new module `pumpguard.bandselect`):**

- `candidate_bands()` returning the eligible, excluded and full sets;
- `band_feature_cube(segments, bands)`;
- `select_band_nested(...)`;
- `run_band_selection(...)` for arms V1, V1-45, V2, C0, R0 and VG;
- `paired_bootstrap_delta(...)`;
- `permutation_test(...)`;
- a report writer.

**CLI:** `pumpguard bandselect FEATURES_DIR --config docs/protocol/amendment-v0.5-config.json --out DIR`.

**Tests (`tests/test_bandselect.py`):**

- band sets: 44 grid, 9 excluded, 35 eligible, 45 full, D0 present; edges in [1, 27] kHz;
  bandwidths ≥ 2 kHz;
- leakage tests L1–L13;
- v0.4 fold reproduction;
- tie-break and δ rule;
- S2 pairing and stratification;
- permutation p formula;
- determinism;
- synthetic controls G4a, G4b and G5 (G5 marked `slow`).

**Docs:**

- a pointer from `docs/benchmark-protocol.md` to this amendment;
- the frozen config JSON next to this file;
- `CHANGELOG.md` (amendment and config hashes, later results);
- `ROADMAP.md` v0.5 item;
- the dataset card: inverter, pole pairs and filter order;
- after the run: `docs/results/paderborn-real3-v0.5/` with report, JSON, figure, and a README in
  the format of the v0.4 write-up.

**Unchanged:** v0.4 results, model cards, existing tests.

## 15. Risks, limitations and open items

**Risks and limitations**

1. **Low power.** 15 bearings, one condition. v0.4 intervals spanned ±0.12 to ±0.20 for the full
   data set; per-condition intervals will be at least that wide. P1 can only pass for large
   effects (on the order of 0.15–0.20 BA). P3 is more sensitive because it is paired, but H1
   needs both. A real but small improvement will likely end as "not supported".
2. **Shaft harmonics inside the peak window** (section 5) may cap 900 rpm performance in every
   band. Amendment 3 addresses this.
3. **Selection instability.** Four training bearings per class per outer fold may select
   different bands in different folds; R1 reports this rather than hiding it.
4. **Electrical interference.** Switching content concentrates at 16 kHz (section 5). Excluding
   the 9 bands that contain it reduces but does not rule out interference, because sidebands can
   extend further. V1-45 shows whether the exclusion matters.
5. **Sensor response unknown** (U5). Selected bands above ~10 kHz may reflect sensor or adapter
   resonance. That is acceptable for envelope analysis but limits physical interpretation.
6. **Label structure.** KI04 and KI14 carry a secondary outer-ring indentation. This does not
   affect detection (both are damaged) and affects diagnosis only (RQ5).
7. **One rig, one bearing type, mirror source.** Results do not transfer to pumps or to other
   machines without new data. Files come from the Zenodo mirror (MD5-verified against the
   mirror, not against the university's originals).
8. **Multiplicity.** Only H1 is confirmatory; everything else is descriptive and is labelled so.
9. **What S2 does not capture.** The paired bootstrap resamples test bearings while holding the
   fitted bands and thresholds fixed. Its interval reflects which bearings were tested, not how
   the selection and thresholds would vary with other training bearings. Selection instability
   is reported separately (R1, selected band per fold) and is not folded into the interval.

**Decisions taken in review (2026-11-22)**

| Item | Decision |
|---|---|
| U1, δ = 0.05 | Accepted; not to be changed after results |
| U2, detection only as primary endpoint | Accepted; diagnosis descriptive |
| U3, 2 kHz minimum bandwidth | Accepted, worded as an approximate rationale (section 8.2) |
| U4, switching frequency | Resolved: 16 kHz (publication p. 7). 9 bands excluded; D0 kept as control and fallback; full-grid search is the pre-specified sensitivity analysis |
| U5, accelerometer datasheet | **Open.** Does not block freezing. Consequence: no selected band above ~10 kHz is attributed to a specific mechanical resonance, and 27 kHz is not treated as a calibrated sensor range |
| U6, permutation count | Review 2 accepted 1 000; replaced by owner decision D-perm (9 999). S3 reframed as an empirical null under bearing-label exchangeability (section 10.2, review 2) |
| U7, harmonic proximity | Accepted as a separate amendment 3, after v0.5, with longer records and narrower peak windows |
| U8, acquisition anti-alias filter | **Open** (pre-freeze audit). Does not block freezing. Consequence: the aliasing argument in section 5 is conditional |
| D-perm, permutation count | **Decided by the project owner on 2026-11-22: 9 999 permutations.** p denominator 10 000; Monte Carlo SE ≈ 0.002 near p = 0.05; estimated compute ≈ 83 min (≈ 8 min for the 1 000 registered in review 2). Sections 10.2, 12 and 18 and the config state the same value |

## 16. Change control and sign-off

- Edits before freezing are recorded as drafts in section 17.
- Freeze procedure, in this order:
  1. Complete all content edits.
  2. Record the project owner's decision in the sign-off table below.
  3. Change the status in the header and at the end of this file, and the `protocol_status` field
     of the config JSON, to FROZEN with the date. Run
     `scripts/protocol/check_amendment2.py --no-freeze-record` (the hashes do not exist yet).
  4. Compute SHA-256 of this file **as it now stands** and of the config JSON.
  5. Record both hashes in `CHANGELOG.md` and in `amendment-v0.5-freeze-record.json`, next to
     this file.
  6. Run `scripts/protocol/check_amendment2.py` without the flag. Every check, including the
     comparison of the recorded hashes with the files, must pass.
- The hash lives outside this file. Writing it into the file would change the file and break
  the hash.
- Any byte changed after step 4 voids the freeze and requires a new hash and a recorded reason.
  The checker detects such a change, because the recorded hashes no longer match the files.
- After the v0.5 run starts, this file does not change. Any later change becomes a new
  amendment, states its reason, and leaves the v0.5 results reported next to the new ones.
- Results are published whatever the outcome.

| Role | Name | Decision | Date |
|---|---|---|---|
| Project owner / reviewer, review 1 | | Revision required | 2026-11-22 |
| Project owner / reviewer, review 2 | | Design approved with minor corrections; freeze pending G0 | 2026-11-22 |
| Project owner, final sign-off | | Approve / revise / reject | |

## 17. Revision history and responses to reviews

**Draft 1, 2026-11-21:** initial draft.

**Draft 2, 2026-11-22:** responds to review 1 ("revision required"). Each finding was checked
against primary sources before acceptance.

| # | Review finding | Verified | Change in Draft 2 |
|---|---|---|---|
| 1 | Inverter switching at 16 kHz (KEB Combivert 07F5E 1D-2B0A) | Yes, publication p. 7; also p = 4 pole pairs | Sections 5, 6, 8: switching analysis, including the aliasing of k · 16 kHz onto 16 kHz at fs = 64 kHz (not in the review); 9 bands excluded; V1-45 sensitivity arm |
| 2 | 30 kHz amplifier filter is 2nd order | Yes, KAt rig page (the publication gives only the cut-off) | Sections 6, 8.2: order stated, type marked unknown |
| 3 | 9 of 44 grid bands contain 16 kHz | Yes, with edges counted as inside | Section 8.1: listed explicitly; 35 eligible |
| 4 | Permutation test does not test H1 | Agreed | Section 10: paired ΔBA with class-stratified paired bootstrap (P3) is the direct test; the permutation test (P2) is an above-chance precondition only |
| 5 | G4 can pass without working selection (8 kHz lies inside D0) | Agreed | G4a: resonance at 3 kHz outside D0, non-D0 band and ΔBA ≥ 0.20 required; G4b: 8 kHz harm check |
| 6 | G5 with 20 data sets is not a calibration proof | Agreed | G5 reworded as a smoke test; its detection power stated |
| 7 | Commit `7b9ca46` not on GitHub | Correct: it is local, delivered as patch and bundle | Section 2.1: full hash, content hashes of the result files, origin of `paderborn_verification.json`; G0(a) requires the commits on GitHub |
| 8 | G2 should check actual counts and rates, not assume 4 s | Agreed | G2 checks file and segment counts, the 16:1 sample ratio and the 4 known short files |
| 9 | B/2 ≥ 618 Hz is approximate | Agreed | Section 8.2 reworded |
| 10 | 27 kHz must not be read as a calibrated sensor range | Agreed | Section 8.2 and U5 |

**Draft 3, 2026-11-22:** responds to review 2 ("experimental design approved; freeze pending
corrections and evidence"). The candidate grid, thresholds, statistics and hypotheses are
unchanged.

| # | Review 2 finding | Change in Draft 3 |
|---|---|---|
| 1 | "Chance is not 0.5" was too categorical | Section 10.2: S3 described as an empirical null under bearing-label exchangeability; the 0.5 expectation for label-independent predictions stated; reasons the finite-sample grouped distribution can differ given |
| 2 | Freeze order: hashing before the status change breaks the hash | Section 16 and G0: edits, owner decision, status FROZEN, then SHA-256, then `CHANGELOG.md`; hash kept outside the file |
| 3 | Results commit and `docs/results/paderborn-real3/` not on GitHub | Section 2.1: v0.4.0 release history stated; results replayed on current `main` as `d203b5e` on branch `feat/paderborn-real3-evidence`, with the four file hashes confirmed byte-identical; G0(a) requires publication and reviewer confirmation on GitHub |

**Draft 4, 2026-11-22:** documentation only; no experimental choice changed.

- Section 2.1 records that the evidence branch is published as PR #12, with `d203b5e` preserved
  and the four hashes recomputed from GitHub by the reviewer and by this session.
- Section 2.1 also explains the `pumpguard_version: "0.3.0"` label raised in PR #12: the code
  equals v0.4.0 apart from the version string.

**Draft 5, 2026-11-22:** responds to the pre-freeze audit (verdict "conditionally ready"). No
hypothesis, arm, candidate band, threshold, seed, replicate count or decision rule changed.

| # | Audit finding | Change in Draft 5 |
|---|---|---|
| A1 | Section 2.1 said the run used "three changes" from the evidence commit, including the report-header wording, which came after the run | Section 2.1 separates the two parts present at run time (reader fix, archive verification) from the three later parts (report header, KI04/KI14 strings, figure script and docs); states that the code state is reconstructed and that G3 checks it |
| A2 | "Anti-alias filter" used for the charge amplifier's 30 kHz low-pass | Sections 5 and 6 call it the signal-conditioning low-pass; the acquisition-system anti-alias filter is recorded as not documented (open item U8); the aliasing argument is marked conditional |
| A3 | G3 compared R0 with the rounded value 0.469 and no tolerance | G3, sections 7, 10.3 and 10.4 and the config use 0.4685836297141851 with absolute tolerance 1e-9, plus the explicit outer-fold assignment |
| A4 | V2 tie-break, fallback and statistic not specified | Section 7: spectral kurtosis defined; no δ rule, no D0 fallback; tie-break as V1 |
| A5 | Permutation p reported without Monte Carlo uncertainty | Section 10.2: k, N and a Clopper–Pearson interval reported; no sequential extension. Permutation count recorded as owner decision D-perm (section 15) |
| A6 | S2's fixed-model limitation not stated | Section 15, limitation 9 |
| A7 | "= 16 in every used file" is not exact | Section 6: ≈ 16 (256 004 / 16 001 = 15.999) |
| A8 | Config incomplete: status field, G4a S2 condition and strict containment, G4b band condition, G5 α, synthetic set-up, V2 rule, secondary analyses | Config rewritten with these fields; section 18 lists every registered value with its config path |
| A9 | Markdown and config can drift apart | `scripts/protocol/check_amendment2.py` recomputes the band sets from the rule and compares section 18, the prose values, the evidence hashes and the status fields with the config; run in the test suite |
| A10 | G0 did not require the PR #12 merge or the config status | G0 (a′) and (d); section 16 step 3 |

**Draft 5 with the owner's decisions, 2026-11-22 (before freezing).** The project owner approved
the Draft 5 text, the config, the decision rules P1, P3, P2 and R1, and the freeze after the
PR #12 merge, and chose the permutation count. Changes:

| Change | Sections |
|---|---|
| S3 uses 9 999 permutations (p = (1 + k) / 10 000); the report states the seed and the number of completed permutations | 10.2, 12, 15 (U6, D-perm), 18; config |
| Disclosure of what was consulted extended to Drafts 4 and 5 (the stored v0.4 result files) | Opening paragraph |
| CLI example names the real config path | 14 |
| G0 (a′) says "on the project owner's authorization"; the freeze record file is named next to `CHANGELOG.md`; freeze steps 3 and 6 say how to run the checker | 13, 16 |
| G2 tolerances and the short-file threshold added to section 18 and the config (values unchanged) | 18; config |

No hypothesis, arm, candidate band, δ, fold, seed, replicate count other than the permutation
count, threshold or decision rule changed.

## 18. Registered parameters (machine-checked)

Each row below is compared with the config JSON by `scripts/protocol/check_amendment2.py`. The
value column is JSON. A path written `len(x)` compares the length of the list at `x`. The
checker also recomputes the 44 / 9 / 35 / 45 band sets from the rule in section 8.1, checks
that the prose of sections 10.2, 12 and 13 states the same permutation count, δ and G3 value,
checks the four evidence hashes against the files in `docs/results/paderborn-real3/`, checks
that the header, the final status line and `protocol_status` agree, and, once the amendment is
frozen, checks the hashes recorded in `CHANGELOG.md` and `amendment-v0.5-freeze-record.json`
against the files.

<!-- registered-parameters:start -->
| Parameter | Value | Config path |
|---|---|---|
| Task | `"real3"` | `task` |
| Primary condition | `"N09_M07_F10"` | `primary_condition` |
| Channel | `"vibration_1"` | `channel` |
| Sampling rate (Hz) | `64000` | `fs_hz` |
| Segment length (s) | `1.0` | `segment_seconds` |
| Bearing geometry | `"6203"` | `bearing_geometry` |
| Envelope filter order | `4` | `envelope_filter.order` |
| Bandwidths (Hz) | `[2000, 4000, 8000, 16000]` | `bands.rule.bandwidths_hz` |
| Lowest f_lo (Hz) | `1000` | `bands.rule.f_lo_min_hz` |
| Highest f_hi (Hz) | `27000` | `bands.rule.f_hi_max_hz` |
| Switching frequency (Hz) | `16000` | `bands.rule.switching_frequency_hz` |
| Default band D0 (Hz) | `[6400, 25600]` | `bands.default_D0` |
| Grid bands | `44` | `len(bands.grid_44)` |
| Excluded bands | `9` | `len(bands.excluded_9)` |
| Eligible bands | `35` | `len(bands.eligible_35)` |
| Full set | `45` | `len(bands.full_45)` |
| δ | `0.05` | `selection.delta` |
| Inner k | `4` | `selection.inner_k` |
| Inner seed base (seed = base + outer fold index) | `1000` | `selection.inner_seed_base` |
| Outer k | `5` | `outer.k` |
| Outer seed | `0` | `outer.seed` |
| S1 replicates | `1000` | `statistics.S1_marginal_bootstrap.replicates` |
| S1 seed | `0` | `statistics.S1_marginal_bootstrap.seed` |
| S2 replicates | `10000` | `statistics.S2_paired_bootstrap.replicates` |
| S2 seed | `0` | `statistics.S2_paired_bootstrap.seed` |
| S2 draws per class | `5` | `statistics.S2_paired_bootstrap.per_class_draws` |
| S3 permutations | `9999` | `statistics.S3_permutation.permutations` |
| S3 seed | `12345` | `statistics.S3_permutation.seed` |
| P2 threshold | `0.05` | `decision.P2_alpha` |
| G2 files at 900 rpm | `300` | `gates.G2.files_N09` |
| G2 segments at 900 rpm | `1196` | `gates.G2.segments_N09` |
| G2 sample-ratio tolerance | `0.001` | `gates.G2.ratio_tolerance` |
| G2 vibration-length tolerance | `0.1` | `gates.G2.vibration_length_tolerance` |
| G2 short-file threshold (samples) | `256000` | `gates.G2.short_file_threshold_samples` |
| G3 expected R0 | `0.4685836297141851` | `gates.G3.R0_detection_ba_N09_expected` |
| G3 tolerance | `1e-09` | `gates.G3.abs_tolerance` |
| G4a resonance (Hz) | `3000` | `gates.G4a.resonance_hz` |
| G4a minimum ΔBA | `0.2` | `gates.G4a.min_delta_ba` |
| G4a minimum folds | `4` | `gates.G4a.min_folds` |
| G4b resonance (Hz) | `8000` | `gates.G4b.resonance_hz` |
| G4b minimum ΔBA | `-0.05` | `gates.G4b.min_delta_ba` |
| G4b minimum folds | `4` | `gates.G4b.min_folds` |
| G5 data sets | `20` | `gates.G5.datasets` |
| G5 permutations each | `200` | `gates.G5.permutations_each` |
| G5 maximum significant | `3` | `gates.G5.max_significant` |
| G5 α | `0.05` | `gates.G5.alpha` |
| Synthetic data seed | `2026` | `synthetic.data_seed` |
| Synthetic machines per class | `5` | `synthetic.machines_per_class` |
| Synthetic segments per machine | `20` | `synthetic.segments_per_machine` |
| Synthetic speed (rpm) | `900` | `synthetic.rpm` |
| Evidence commit | `"d203b5eed799f6bea33f0ea8c965ac1fc7639e98"` | `evidence_commit` |
<!-- registered-parameters:end -->

---

Draft 5: pre-freeze audit corrections applied; experimental design unchanged since review 2.
Freeze is pending the rest of gate G0: PR #12 merged, the permutation-count decision, and owner
sign-off. Implementation and the real-data experiment are not authorised until the amendment is
frozen.

**PROTOCOL STATUS: DRAFTED — NOT YET EXPERIMENTALLY EXECUTED.**
