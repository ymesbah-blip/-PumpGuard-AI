# Benchmark report: paderborn-kat real3

> **Read this first.** Transparent baselines and learned models (scikit-learn, hyperparameters fixed in advance) evaluated on the same leakage-safe folds. Intervals come from a bootstrap over groups.
> Data come from an electromechanical bearing test rig (not a centrifugal pump). They do **not** validate diagnosis of centrifugal pumps in the field.

## Data

| Class | Groups | Segments |
|---|---|---|
| healthy | 5 | 1594 |
| inner | 5 | 1582 |
| outer | 5 | 1589 |

Rows dropped for non-finite features: 0.

## Protocol

- Split: `stratified_group_kfold` {"n_splits": 5, "groups_per_class": {"healthy": 5, "inner": 5, "outer": 5}}
- Features: `rms`, `kurtosis`, `crest_factor`, `impulse_factor`, `spectral_centroid_hz`, `hf_energy_ratio`, `env_bpfo_ratio`, `env_bpfi_ratio`
- Seed 0, 1000 group-bootstrap replicates, 95 % percentile intervals

## Results: detection

| Model | Balanced accuracy [95 % CI] | Macro-F1 [95 % CI] | Fitted (first fold) |
|---|---|---|---|
| majority_class | 0.500 [0.50, 0.50] | 0.400 [0.29, 0.46] | always predicts 'damaged' |
| single_feature_threshold | 0.766 [0.60, 0.92] | 0.759 [0.60, 0.89] | 'damaged' if spectral_centroid_hz < 8100 |
| envelope_rule | 0.691 [0.56, 0.79] | 0.684 [0.53, 0.78] | damaged if max(BPFO, BPFI envelope ratio) > 3.26 |
| logistic_regression | 0.739 [0.50, 0.90] | 0.728 [0.50, 0.88] | logistic regression (C=1); largest z-score weights: hf_energy_ratio (+14.29 for healthy), env_bpfo_ratio (-4.67 for healthy), impulse_factor (+3.79 for healthy) |
| random_forest | 0.699 [0.48, 0.90] | 0.701 [0.47, 0.85] | random forest (300 trees, min leaf 3); top impurity importances: hf_energy_ratio (0.26), spectral_centroid_hz (0.25), rms (0.15) |

<details><summary>majority_class: confusion matrix and failure modes</summary>

| true \ predicted | healthy | damaged |
|---|---|---|
| healthy | 0 | 1594 |
| damaged | 0 | 3171 |

Groups with accuracy < 0.5: 5 of 15
- `K001` (healthy): 0.00
- `K002` (healthy): 0.00
- `K003` (healthy): 0.00
- `K004` (healthy): 0.00
- `K005` (healthy): 0.00

Balanced accuracy per operating condition:
- `N09_M07_F10`: 0.500
- `N15_M01_F10`: 0.500
- `N15_M07_F04`: 0.500
- `N15_M07_F10`: 0.500

</details>

<details><summary>single_feature_threshold: confusion matrix and failure modes</summary>

| true \ predicted | healthy | damaged |
|---|---|---|
| healthy | 1157 | 437 |
| damaged | 612 | 2559 |

Groups with accuracy < 0.5: 2 of 15
- `K004` (healthy): 0.24
- `K005` (healthy): 0.39

Balanced accuracy per operating condition:
- `N09_M07_F10`: 0.671
- `N15_M01_F10`: 0.799
- `N15_M07_F04`: 0.810
- `N15_M07_F10`: 0.786

</details>

<details><summary>envelope_rule: confusion matrix and failure modes</summary>

| true \ predicted | healthy | damaged |
|---|---|---|
| healthy | 1010 | 584 |
| damaged | 796 | 2375 |

Groups with accuracy < 0.5: 3 of 15
- `K002` (healthy): 0.26
- `KA22` (damaged): 0.28
- `KA30` (damaged): 0.40

Balanced accuracy per operating condition:
- `N09_M07_F10`: 0.469
- `N15_M01_F10`: 0.771
- `N15_M07_F04`: 0.762
- `N15_M07_F10`: 0.764

</details>

<details><summary>logistic_regression: confusion matrix and failure modes</summary>

| true \ predicted | healthy | damaged |
|---|---|---|
| healthy | 1134 | 460 |
| damaged | 738 | 2433 |

Groups with accuracy < 0.5: 3 of 15
- `K002` (healthy): 0.00
- `KA30` (damaged): 0.09
- `KI04` (damaged): 0.48

Balanced accuracy per operating condition:
- `N09_M07_F10`: 0.753
- `N15_M01_F10`: 0.733
- `N15_M07_F04`: 0.751
- `N15_M07_F10`: 0.721

</details>

<details><summary>random_forest: confusion matrix and failure modes</summary>

| true \ predicted | healthy | damaged |
|---|---|---|
| healthy | 932 | 662 |
| damaged | 591 | 2580 |

Groups with accuracy < 0.5: 3 of 15
- `K002` (healthy): 0.07
- `K005` (healthy): 0.14
- `KA22` (damaged): 0.32

Balanced accuracy per operating condition:
- `N09_M07_F10`: 0.616
- `N15_M01_F10`: 0.758
- `N15_M07_F04`: 0.690
- `N15_M07_F10`: 0.733

</details>

## Results: diagnosis

| Model | Balanced accuracy [95 % CI] | Macro-F1 [95 % CI] | Fitted (first fold) |
|---|---|---|---|
| majority_class | 0.331 [0.17, 0.50] | 0.238 [0.08, 0.43] | always predicts 'healthy' |
| envelope_rule | 0.583 [0.44, 0.73] | 0.589 [0.44, 0.71] | damaged if max(BPFO, BPFI envelope ratio) > 3.26; outer if BPFO ratio >= BPFI ratio |
| nearest_centroid | 0.554 [0.36, 0.75] | 0.550 [0.33, 0.72] | nearest of 3 class means; most separating: env_bpfi_ratio, spectral_centroid_hz, impulse_factor |
| logistic_regression | 0.572 [0.39, 0.74] | 0.571 [0.38, 0.71] | logistic regression (C=1); largest z-score weights: hf_energy_ratio (+11.17 for healthy), env_bpfo_ratio (-3.11 for healthy), impulse_factor (+2.59 for healthy) |
| random_forest | 0.512 [0.32, 0.70] | 0.513 [0.32, 0.67] | random forest (300 trees, min leaf 3); top impurity importances: hf_energy_ratio (0.28), spectral_centroid_hz (0.19), rms (0.16) |

<details><summary>majority_class: confusion matrix and failure modes</summary>

| true \ predicted | healthy | outer | inner |
|---|---|---|---|
| healthy | 1274 | 0 | 320 |
| outer | 1274 | 0 | 315 |
| inner | 1275 | 0 | 307 |

Groups with accuracy < 0.5: 10 of 15
- `K004` (healthy): 0.00
- `KA04` (outer): 0.00
- `KA15` (outer): 0.00
- `KA16` (outer): 0.00
- `KA22` (outer): 0.00
- `KA30` (outer): 0.00
- `KI04` (inner): 0.00
- `KI14` (inner): 0.00
- `KI18` (inner): 0.00
- `KI21` (inner): 0.00

Balanced accuracy per operating condition:
- `N09_M07_F10`: 0.333
- `N15_M01_F10`: 0.330
- `N15_M07_F04`: 0.327
- `N15_M07_F10`: 0.334

</details>

<details><summary>envelope_rule: confusion matrix and failure modes</summary>

| true \ predicted | healthy | outer | inner |
|---|---|---|---|
| healthy | 1010 | 530 | 54 |
| outer | 542 | 958 | 89 |
| inner | 254 | 517 | 811 |

Groups with accuracy < 0.5: 6 of 15
- `K002` (healthy): 0.26
- `KA15` (outer): 0.42
- `KA22` (outer): 0.26
- `KA30` (outer): 0.34
- `KI14` (inner): 0.33
- `KI16` (inner): 0.21

Balanced accuracy per operating condition:
- `N09_M07_F10`: 0.418
- `N15_M01_F10`: 0.669
- `N15_M07_F04`: 0.603
- `N15_M07_F10`: 0.643

</details>

<details><summary>nearest_centroid: confusion matrix and failure modes</summary>

| true \ predicted | healthy | outer | inner |
|---|---|---|---|
| healthy | 1117 | 230 | 247 |
| outer | 271 | 606 | 712 |
| inner | 212 | 452 | 918 |

Groups with accuracy < 0.5: 8 of 15
- `K004` (healthy): 0.26
- `K005` (healthy): 0.25
- `KA15` (outer): 0.00
- `KA22` (outer): 0.00
- `KA30` (outer): 0.00
- `KI14` (inner): 0.27
- `KI16` (inner): 0.40
- `KI21` (inner): 0.48

Balanced accuracy per operating condition:
- `N09_M07_F10`: 0.599
- `N15_M01_F10`: 0.563
- `N15_M07_F04`: 0.502
- `N15_M07_F10`: 0.552

</details>

<details><summary>logistic_regression: confusion matrix and failure modes</summary>

| true \ predicted | healthy | outer | inner |
|---|---|---|---|
| healthy | 1070 | 354 | 170 |
| outer | 453 | 769 | 367 |
| inner | 200 | 497 | 885 |

Groups with accuracy < 0.5: 6 of 15
- `K002` (healthy): 0.00
- `KA15` (outer): 0.19
- `KA22` (outer): 0.46
- `KA30` (outer): 0.05
- `KI14` (inner): 0.43
- `KI16` (inner): 0.24

Balanced accuracy per operating condition:
- `N09_M07_F10`: 0.600
- `N15_M01_F10`: 0.619
- `N15_M07_F04`: 0.508
- `N15_M07_F10`: 0.559

</details>

<details><summary>random_forest: confusion matrix and failure modes</summary>

| true \ predicted | healthy | outer | inner |
|---|---|---|---|
| healthy | 945 | 360 | 289 |
| outer | 449 | 739 | 401 |
| inner | 191 | 634 | 757 |

Groups with accuracy < 0.5: 7 of 15
- `K002` (healthy): 0.04
- `K005` (healthy): 0.30
- `KA15` (outer): 0.11
- `KA22` (outer): 0.27
- `KA30` (outer): 0.21
- `KI14` (inner): 0.11
- `KI21` (inner): 0.00

Balanced accuracy per operating condition:
- `N09_M07_F10`: 0.574
- `N15_M01_F10`: 0.502
- `N15_M07_F04`: 0.420
- `N15_M07_F10`: 0.552

</details>

## Decision: learned models vs baselines

Protocol rule: a learned model is meaningfully better than a baseline only if its lower 95 % bound exceeds the baseline's point estimate, and is worth reporting as an improvement only if that holds against **every** baseline.

| Task / model | Lower 95 % bound | Beats all baselines | Baselines not beaten |
|---|---|---|---|
| detection/logistic_regression | 0.504 | no | single_feature_threshold, envelope_rule |
| detection/random_forest | 0.475 | no | majority_class, single_feature_threshold, envelope_rule |
| diagnosis/logistic_regression | 0.392 | no | envelope_rule, nearest_centroid |
| diagnosis/random_forest | 0.318 | no | majority_class, envelope_rule, nearest_centroid |

## Leakage check

The same baselines with a random segment split that ignores groups. The gap shows how much a leaky protocol would overstate performance.

| Task / baseline | Group k-fold | Random segments | Inflation |
|---|---|---|---|
| detection/single_feature_threshold | 0.766 | 0.830 | +0.064 |
| detection/envelope_rule | 0.691 | 0.716 | +0.025 |
| detection/logistic_regression | 0.739 | 0.919 | +0.179 |
| detection/random_forest | 0.699 | 0.994 | +0.295 |
| diagnosis/envelope_rule | 0.583 | 0.603 | +0.020 |
| diagnosis/nearest_centroid | 0.554 | 0.620 | +0.065 |
| diagnosis/logistic_regression | 0.572 | 0.796 | +0.224 |
| diagnosis/random_forest | 0.512 | 0.994 | +0.482 |

## Limitations

- Few independent groups: intervals are wide; small differences between baselines are not meaningful.
- Thresholds and centroids are fitted per training fold; the rules shown are from the first fold only (all folds are in `results.json`).
- Learned models use fixed hyperparameters (see `results.json`); none were tuned. Random-forest importances are impurity-based, computed on training data, and biased toward continuous features: they are hints, not evidence.
- Envelope features use a fixed demodulation band and nominal bearing geometry (1-2 % manufacturer variation); no band optimisation was performed.

## Data source and licence

- Source: https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter
- Licence: CC BY-NC 4.0
- Cite: Lessmeier, C.; Kimotho, J. K.; Zimmer, D.; Sextro, W. (2016): Condition Monitoring of Bearing Damage in Electromechanical Drive Systems by Using Motor Current Signals of Electric Motors: A Benchmark Data Set for Data-Driven Classification. European Conference of the Prognostics and Health Management Society, Bilbao (Spain). Data: Christian Lessmeier et al., KAt-DataCenter, Chair of Design and Drive Technology, Paderborn University.
- Files used: 1196, failed: 4, missing bearings: []

_Generated by pumpguard 0.3.0._
