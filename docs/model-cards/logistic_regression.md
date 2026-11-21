# Model card: `logistic_regression`

> **Status:** evaluated on synthetic data only (pipeline dry run). No result on real
> measurements exists yet. Nothing here is validated for operational or safety decisions.

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
- **Synthetic, real, or both?** Synthetic only so far.
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
- **Results under shift:** not yet measured. See the
  [leakage experiment](../leakage-experiment.md) for behaviour as fault severity decreases.

## Explainability
- Coefficients are on z-scored features (`coefficients()`). In the synthetic diagnosis run the
  largest weights are `env_bpfo_ratio` for outer race and `env_bpfi_ratio` for inner race, which
  matches the physics. For detection, `kurtosis` and `impulse_factor` also weigh heavily, as
  expected for impulsive faults.
- Correlated features (crest, impulse and kurtosis) share weight, so a single coefficient's size
  is not a measure of that feature's importance.

## Limitations and intended use
- **Not validated for operational or safety decisions.**
- Linear decision boundary in the eight features: interactions (e.g. speed-dependent thresholds)
  are not modelled.
- On synthetic data the one-parameter envelope rule is at least as good, so the extra parameters
  are not justified there. The protocol decides on real data.
- Bearing test-rig data say nothing about centrifugal pumps in the field.
