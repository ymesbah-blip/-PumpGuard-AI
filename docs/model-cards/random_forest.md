# Model card: `random_forest`

> **Status:** evaluated on synthetic data only (pipeline dry run). No result on real
> measurements exists yet. Nothing here is validated for operational or safety decisions.

## Overview
- **Task:** detection (healthy vs damaged) and diagnosis (healthy / outer race / inner race) of
  rolling-element bearings from vibration features.
- **Model type and key hyperparameters:** scikit-learn `RandomForestClassifier`, 300 trees,
  `min_samples_leaf=3`, `max_features="sqrt"`, `class_weight="balanced"`,
  `random_state=seed`, single-threaded for reproducibility. Fixed by
  [protocol amendment 1](../benchmark-protocol.md#amendment-1-learned-models-v04-2026-11-21-before-any-real-result);
  not tuned.
- **Input features:** `rms`, `kurtosis`, `crest_factor`, `impulse_factor`,
  `spectral_centroid_hz`, `hf_energy_ratio`, `env_bpfo_ratio`, `env_bpfi_ratio`.
- **Code / package version:** `pumpguard.models.RandomForestModel`, PumpGuard 0.3.0+
  (v0.4 work), optional extra `[ml]`.

## Training data
- **Datasets:** synthetic dry run (`pumpguard benchmark --synthetic --learned`). Planned: Paderborn
  KAt `real3` and `artificial_to_real` ([dataset card](../datasets/paderborn-kat.md)).
- **Synthetic, real, or both?** Synthetic only so far.
- **Preprocessing:** rows with non-finite features are dropped and counted. No scaling (trees do
  not need it).

## Evaluation
- **Split strategy:** stratified group k-fold by `group_id`, k = 5, seed 0; 95 % group-bootstrap
  intervals, 1000 replicates.
- **Synthetic dry run** (5 machines per class, 4 segments each):

  | Task | Balanced accuracy [95 % CI] | Best baseline | Beats all baselines? |
  |---|---|---|---|
  | detection | 0.913 [0.78, 1.00] | `envelope_rule` 1.000 | no |
  | diagnosis | 0.933 [0.82, 1.00] | `envelope_rule` 1.000 | no |

- **Leakage check (synthetic):** a random segment split raises balanced accuracy by +0.04
  (detection) and +0.05 (diagnosis) when faults are clear. With subtle faults the gap grows to
  +0.32 to +0.39, the largest of the three models tested
  ([leakage experiment](../leakage-experiment.md)).
- **Results under shift:** not yet measured.

## Explainability
- `importances()` gives mean impurity decrease. In the synthetic diagnosis run the top features
  are `env_bpfi_ratio` (0.21), `env_bpfo_ratio` (0.20) and `kurtosis` (0.17), consistent with
  the physics. For detection the impulsiveness features (`impulse_factor`, `kurtosis`,
  `crest_factor`) lead.
- Impurity importance is computed on training data and favours continuous, high-cardinality
  features. Treat it as a hint. Permutation importance on held-out groups is the stronger check
  (planned for v0.5).

## Limitations and intended use
- **Not validated for operational or safety decisions.**
- The most flexible model here, and the one that profits most from group-level shortcuts. Its
  random-split scores are the least trustworthy; only group-split results count.
- On synthetic data the one-parameter envelope rule is at least as good.
- Bearing test-rig data say nothing about centrifugal pumps in the field.
