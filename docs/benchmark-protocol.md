# Benchmark protocol (fixed before results)

This protocol is written down **before** any result on real data is produced. Changing it after
seeing results must be recorded in `CHANGELOG.md` with the reason, and earlier results must stay
reported next to the new ones.

## Questions

1. **Detection:** can transparent features separate healthy from damaged bearings when tested
   on bearings never seen in training?
2. **Diagnosis:** can they separate outer-race from inner-race damage under the same condition?
3. **Leakage:** how much would a random segment split overstate the result?
4. **Transfer:** do rules fitted on artificial damage hold on real damage?

## Data and tasks

Data: Paderborn KAt bearing dataset, vibration channel `vibration_1`, all four operating
conditions, all 20 measurements per setting unless stated. See the
[dataset card](datasets/paderborn-kat.md).

| Task | Bearings | Split |
|---|---|---|
| `real3` (primary) | healthy K001–K005; real outer KA04, KA15, KA16, KA22, KA30; real inner KI04, KI14, KI16, KI18, KI21 | stratified group k-fold by bearing, k = 5, seed 0 |
| `artificial_to_real` | train: K001–K003 + 12 artificial; test: K004–K006 + the 10 real damaged bearings of `real3` | predefined, by bearing |
| `all_single` (secondary) | all bearings except combined damage (KB23, KB24, KB27) | stratified group k-fold by bearing |

The `real3` bearing set follows the real-damage experiment of the dataset publication. The
`artificial_to_real` split is this project's definition, not the paper's.

## Features (fixed)

Segments: non-overlapping, 1.0 s (64 000 samples). Features from `extract_all_features` with
measured speed (or nominal, see the dataset card) and 6203 geometry:

`rms`, `kurtosis`, `crest_factor`, `impulse_factor`, `spectral_centroid_hz`, `hf_energy_ratio`,
`env_bpfo_ratio`, `env_bpfi_ratio`.

Envelope demodulation band: default 0.1–0.4 fs (6.4–25.6 kHz). Tuning the band is **not** part
of this protocol. A later protocol may select it on training folds only.

## Baselines (in this order)

1. `majority_class`: lower bound.
2. `single_feature_threshold` (detection only): best single feature and threshold, chosen on
   the training fold by balanced accuracy.
3. `envelope_rule`: one threshold on max(BPFO ratio, BPFI ratio), chosen on the training fold;
   outer vs inner by the larger ratio.
4. `nearest_centroid` (diagnosis only): standardised with training-fold statistics.

A learned classifier (roadmap v0.4) is only worth reporting if it beats **all** of these under
this exact protocol.

## Metrics and uncertainty

- Primary: **balanced accuracy**. Secondary: macro-F1, per-class precision/recall, confusion
  matrix.
- 95 % intervals: percentile bootstrap over **bearings** (1000 replicates, seed 0), not over
  segments.
- Failure modes: per-bearing accuracy (bearings below 0.5 are listed) and balanced accuracy
  per operating condition.
- Leakage check: the same baselines with random segment k-fold. Report the difference; never
  report random-split numbers as the result.

## Decision rules

- A difference between two methods counts as meaningful only if the better method's lower
  95 % bound exceeds the other's point estimate.
- If `envelope_rule` matches or beats `nearest_centroid` on `real3`, the conclusion is that the
  physics rule suffices on this rig; extra complexity needs a new justification.
- No statement about pumps follows from these results. Any summary must say that the data come
  from a bearing test rig.

## Amendment 1: learned models (v0.4, 2026-11-21, before any real result)

Added before the first run on real files, so no earlier result exists to keep next to it.
Everything above stays unchanged: same tasks, folds, features, metrics, intervals and decision
rules.

Models (optional `[ml]` extra, scikit-learn), evaluated with `pumpguard benchmark --learned`:

| Model | Fixed hyperparameters |
|---|---|
| `logistic_regression` | z-score with training-fold statistics; L2 penalty, C = 1; `class_weight="balanced"`; multinomial for diagnosis |
| `random_forest` | 300 trees; `min_samples_leaf = 3`; `max_features = "sqrt"`; `class_weight="balanced"`; `random_state = seed` |

- **No tuning.** Hyperparameters are not chosen on the evaluation folds, or on any fold of the
  reported task. A later amendment may add nested group cross-validation (tuning inside each
  training fold only). Until then the values above are the protocol.
- **Same features** as the baselines (the eight listed above). Nothing derived from the label,
  the group or the file name enters the model.
- **Always reported.** Learned models are reported whether they win or lose, with the same
  intervals, failure modes and leakage check as the baselines. This replaces "only worth
  reporting if it beats all baselines" above, so that a losing model is never quietly dropped.
- **Decision rule.** A learned model counts as an improvement only if its lower 95 % bound of
  balanced accuracy exceeds the point estimate of **every** baseline on that task
  (`results["decision"]`). Otherwise the conclusion is that the transparent baselines suffice
  on this data.
- **Explanations are hints.** Logistic-regression weights are on z-scored features. Random-forest
  importances are impurity-based, come from training data and favour continuous features. A
  model whose top features contradict the physics (e.g. separates outer from inner race mainly
  with `rms` while the envelope ratios carry little weight) is flagged in its model card, not
  hidden.

Model cards: [logistic regression](model-cards/logistic_regression.md),
[random forest](model-cards/random_forest.md).

## Reproduction

```bash
pumpguard paderborn index  /path/to/paderborn
pumpguard paderborn features /path/to/paderborn --task real3 --out outputs/pu_real3.csv
pumpguard benchmark outputs/pu_real3.csv --out outputs/bench_real3 --learned
pumpguard leakage   outputs/pu_real3.csv --out outputs/leak_real3
pumpguard paderborn features /path/to/paderborn --task artificial_to_real --out outputs/pu_a2r.csv
pumpguard benchmark outputs/pu_a2r.csv --out outputs/bench_a2r --learned
```

Run the benchmark once without `--learned` as well. The baseline rows must be identical in both
runs (same folds), which `tests/test_models.py` checks on synthetic data.

Each `report.md` lists the package version, data files used and failed, the licence and the
citation.
