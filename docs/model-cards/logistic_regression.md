# Model card: `logistic_regression`

> **Status:** evaluated on synthetic data and on the real Paderborn `real3` bearings (test rig,
> not a pump). It does not beat the transparent baselines. Nothing here is validated for
> operational or safety decisions.

## Overview
- **Task:** detection (healthy vs damaged) and diagnosis (healthy / outer race / inner race) of
  rolling-element bearings from vibration features.
- **Model type and key hyperparameters:** scikit-learn `LogisticRegression` after z-scoring with
  training-fold statistics; L2 penalty, C = 1, `class_weight="balanced"`, `max_iter=5000`,
  multinomial for three classes. Fixed by
  [protocol amendment 1](../benchmark-protocol.md#amendment-1-learned-models-v04-2026-11-21-before-any-real-result);
  not tuned.
- **Input features:** `rms`, `kurtosis`, `crest_factor`, `impulse_factor`,
  `spectral_centroid_hz`, `hf_energy_ratio`, `env_bpfo_ratio`, `env_bpfi_ratio`
  (definitions: [synthetic-model.md](../synthetic-model.md), `pumpguard.features`).
- **Code / package version:** `pumpguard.models.LogisticRegressionModel`, PumpGuard 0.3.0+
  (v0.4 work), optional extra `[ml]`.

## Training data
- **Datasets:** synthetic dry run (`pumpguard benchmark --synthetic --learned`). Planned: Paderborn
  KAt `real3` and `artificial_to_real` ([dataset card](../datasets/paderborn-kat.md)).
- **Synthetic, real, or both?** Both: synthetic dry run and Paderborn `real3` (Zenodo mirror, MD5-verified).
- **Preprocessing:** rows with non-finite features are dropped and counted; z-scoring inside
  each training fold.

## Evaluation
- **Split strategy:** stratified group k-fold by `group_id` (virtual machine; physical bearing
  for Paderborn), k = 5, seed 0. Intervals: 95 % percentile bootstrap over groups, 1000
  replicates.
- **Synthetic dry run** (5 machines per class, 4 segments each):

  | Task | Balanced accuracy [95 % CI] | Best baseline | Beats all baselines? |
  |---|---|---|---|
  | detection | 0.925 [0.80, 1.00] | `envelope_rule` 1.000 | no |
  | diagnosis | 0.933 [0.78, 1.00] | `envelope_rule` 1.000 | no |

- **Leakage check (synthetic):** a random segment split raises balanced accuracy by +0.05
  (detection) and +0.07 (diagnosis).
- **Real data, Paderborn `real3`** (15 bearings, 4 765 segments,
  [full results](../results/paderborn-real3/README.md)):

  | Task | Balanced accuracy [95 % CI] | Best baseline | Beats all baselines? | Random-split score |
  |---|---|---|---|---|
  | detection | 0.739 [0.50, 0.90] | `single_feature_threshold` 0.766 | no | 0.919 (+0.18) |
  | diagnosis | 0.572 [0.39, 0.74] | `envelope_rule` 0.583 | no | 0.796 (+0.22) |
- **Results under shift:** not yet measured. See the
  [leakage experiment](../leakage-experiment.md) for behaviour as fault severity decreases.

## Explainability
- Coefficients are on z-scored features (`coefficients()`). In the synthetic diagnosis run the
  largest weights are `env_bpfo_ratio` for outer race and `env_bpfi_ratio` for inner race, which
  matches the physics. For detection, `kurtosis` and `impulse_factor` also weigh heavily, as
  expected for impulsive faults.
- Correlated features (crest, impulse and kurtosis) share weight, so a single coefficient's size
  is not a measure of that feature's importance.

## Real-data flag

- **Real data flag (amendment 1):** on `real3` the largest weight goes to `hf_energy_ratio`
  (healthy direction), ahead of `env_bpfo_ratio` and `impulse_factor`. A broadband level feature
  that differs between individual bearings carries the model, which explains its +0.22 gain under
  a random split.

## Limitations and intended use
- **Not validated for operational or safety decisions.**
- Linear decision boundary in the eight features: interactions (e.g. speed-dependent thresholds)
  are not modelled.
- On synthetic data the one-parameter envelope rule is at least as good, so the extra parameters
  are not justified there. The protocol decides on real data.
- Bearing test-rig data say nothing about centrifugal pumps in the field.
