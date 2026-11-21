# Roadmap

Each milestone ends with something reproducible: code, tests, and a short write-up of what
was learned **and what was not shown**.

## ✅ v0.2: Solid foundation
Installable package, CLI, frequency-domain and envelope features, bearing kinematics, richer
synthetic conditions, leakage-aware dataset builder, CI, community files.

## ✅ v0.3: Local data integration code (not experimentally validated)
- Paderborn KAt loader for local files (no redistribution), dataset card, provenance validation.
- Leakage-safe benchmark of transparent baselines with group-bootstrap intervals and a
  pre-registered protocol.
- Pump/ESP hydraulics: operating point as pump ∩ system curve, orders vs sensor observability,
  typed SCADA loader with time-block splits, lab rig plan.
- **Still open:** first run on the real files (confirm units, channel names, durations), then
  publish `report.md` for `real3` and `artificial_to_real`. Notebook comparing synthetic and
  measured feature behaviour. Fit a `PumpCurve` from real catalog points and validate
  `solve_operating_point` against a measured well test.

## ✅ v0.4: Learned models and honest evaluation (research preview)
- ✅ Optional `[ml]` extra (scikit-learn).
- ✅ Learned models (logistic regression, random forest) on the same transparent features, judged
  against the v0.3 baselines under the unchanged protocol (amendment 1: fixed hyperparameters,
  decision rule against every baseline).
- ✅ Experiment: the same model evaluated with a random split vs a group split
  (`pumpguard leakage`, [write-up](docs/leakage-experiment.md), synthetic result).
- ✅ Run both on the real Paderborn `real3` table and publish the reports
  ([results](docs/results/paderborn-real3/README.md)). Still open: `artificial_to_real`.
- Nested group cross-validation, if tuning is ever needed (inside training folds only).
- Second dataset with a different rig, to test whether conclusions transfer.

## v0.5: Robustness and explainability
- Sensitivity to noise, speed variation and severity (severity sweeps are already
  supported by the generator).
- Kurtogram / spectral-kurtosis band selection for envelope analysis.
- Compare model attributions with physically expected features (e.g. BPFI ratio for an
  inner-race fault).
- Model card for every published baseline.

## v0.6: Digital-twin prototype
- State model: operating point (speed, flow, head) → expected vibration signature.
- Degradation trajectories (severity over time) and remaining-useful-life experiments,
  clearly labelled synthetic.
- Uncertainty-aware comparison of measured vs expected signatures.

## v1.0: Stable API
- Documented, versioned public API with deprecation policy.
- Documentation site (MkDocs) with tutorials.
- Engineering validation report against measured data, including limitations.

## Good first issues

- Add a bearing preset with a cited source (e.g. a 6203 or 6305 bearing).
- Add `--waveform-seconds` to `pumpguard demo`.
- Add a `misalignment` example figure to the docs.
- Add an `rms_velocity` feature (integrate acceleration to velocity in the frequency domain,
  10–1000 Hz band) with an analytic test.
- Translate the README quick start into Arabic or French (`docs/i18n/`).
