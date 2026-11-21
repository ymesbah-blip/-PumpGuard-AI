# Changelog

All notable changes are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/) (pre-1.0: minor versions may break APIs).

## [Unreleased]

Roadmap v0.4 groundwork: learned models judged against the baselines, and the random-split vs
group-split experiment.

### Added
- Optional extra `[ml]` (`scikit-learn>=1.3`). The core package never imports scikit-learn.
  Without the extra, learned models raise `ImportError` with the install command.
- `pumpguard.models`: `LogisticRegressionModel` (z-score, L2, balanced class weights) and
  `RandomForestModel` (300 trees, min leaf 3, balanced class weights). Both use the baseline
  interface (`fit`, `predict`, `describe`) with fixed hyperparameters. Readable explanations:
  `coefficients()` and `importances()`.
- `run_benchmark(..., learned=True)` and `pumpguard benchmark --learned`. Learned models run on
  the same folds as the baselines and are included in the leakage check.
  `results["decision"]` applies the protocol rule: a model counts as better only if its lower
  95 % bound beats every baseline's point estimate. The report has a matching section.
- `pumpguard.leakage.compare_splits` and `pumpguard leakage`: the same model under group k-fold
  and random k-fold over several fold seeds, with inflation per repeat, a Markdown + JSON report
  and an explanation of below-chance group scores.
- `synthetic_feature_table(severity_range=...)` for subtle-fault synthetic tables.
- `examples/leakage_experiment.py` and figure `docs/images/leakage_vs_severity.png`.
- Docs: `docs/leakage-experiment.md`, model cards for both learned models, and protocol
  amendment 1 (learned models, fixed hyperparameters, written before any real result).
- 25 tests (270 in total). The learned-model tests skip without scikit-learn.

### Changed
- Benchmark report: the results table column is now "Model", and each row has
  `kind: baseline | learned` in `results.json`. Baseline results are unchanged.
- CLI: a missing optional dependency exits with code 2 and a message instead of a traceback.
- CI installs `.[dev,ml]`, runs the learned benchmark and the leakage experiment, and adds a
  core-only job without scikit-learn.

## [0.3.0] - unreleased

First opt-in path to real measurements (scope of issue #3) and a mechanically interpretable
pump/ESP layer (scope of issue #4).

### Added
- `pumpguard.datasets.provenance`: required provenance schema for every recording,
  `validate_provenance()` raising `ProvenanceError` with **all** problems listed.
- `pumpguard.datasets.paderborn`: reader for locally downloaded Paderborn KAt bearing files
  (CC BY-NC 4.0, never bundled). Covers the operating-condition and bearing tables from Lessmeier
  et al. (2016), a filename parser, and a `.mat` reader that finds channels by name instead of
  hard-coded struct indices. Also checks documented sampling rates and the 4 s duration, uses
  the measured speed channel with a ±20 % plausibility check, skips corrupt files and reports
  them, and builds a feature table with `group_id` = physical bearing.
- Predefined tasks `real3`, `artificial_to_real` and `all_single`.
- `pumpguard.baselines`: majority class, single-feature threshold, envelope physics rule,
  nearest centroid. All numpy-only and able to describe the rule they learned.
- `pumpguard.evaluation`: stratified group k-fold, random k-fold (for leakage checks only),
  metrics, group-bootstrap confidence intervals.
- `pumpguard.benchmark` and CLI `pumpguard benchmark`: detection and diagnosis tasks, 95 %
  intervals over groups, per-group and per-condition failure modes, a leakage check, and a
  Markdown + JSON report. `--synthetic` gives a dry run.
- CLI `pumpguard paderborn index | inspect | features`.
- `6203` bearing preset (8 balls, 6.75 mm, pitch 28.55 mm).
- Docs: Paderborn dataset card, benchmark protocol written before any real result.
- Example `examples/benchmark_paderborn.py`; 72 new tests using only invented `.mat` fixtures.

#### Pump operating point, orders and sensors (issue #4)
- `pumpguard.units`: exact SI conversions (BPD, ft, bar, psi, temperature).
- `pumpguard.hydraulics`: typed `OperatingPoint` with derived hydraulic power, efficiency and
  NPSH margin. Inconsistent data (efficiency > 1) is rejected. Also adds `PumpCurve`
  (multistage, affinity-scaled, invertible, no extrapolation), `WellSystem` (linear IPR, static
  lift, friction) and `solve_operating_point`, which finds the pump/system intersection.
- `pumpguard.orders` (mechanism): shaft and vane-pass frequencies, rpm from VSD frequency with
  poles and slip.
- `pumpguard.sensors` (sensor): `SensorSpec`, observability checks (Nyquist, anti-alias,
  2.56× margin), voltage-to-acceleration conversion, `measure()` for simulating acquisition.
- `pumpguard.regime`: synthetic speed sweep (consistent intersections), speed × flow grid, and
  `naive_affinity_projection` to quantify the error of Q ∝ f / Δp ∝ f² projections.
- `pumpguard.datasets.scada`: typed SCADA CSV loader (units, finite values, logging interval,
  gaps) and `time_block_split` (by day, chronological, optional embargo).
- Docs `esp-operating-point.md` and `lab-rig-plan.md` (instrumentation, acquisition IDs,
  rig-to-dataset path, safety boundaries, claim limits). Example
  `examples/esp_operating_regime.py` with figure. 64 exact and property tests.

### Fixed
- README clone instructions: `cd -PumpGuard-AI` fails because `cd` reads the leading `-` as an
  option. The repository is now cloned into `pumpguard-ai`.
- `docs/datasets.md` and `docs/validation.md` described features that do not exist
  (`--input-csv`, Welch PSD, order band power, a "4.2x impulse", three labels, crest factor 0).
  Both now match the implementation.

### Changed
- Dataset policy: loaders read user-downloaded files from a local path; nothing is downloaded
  automatically (licence terms stay with the user).
- `.gitignore` excludes `*.mat` and `*.rar`.

## [0.2.0] - unreleased

### Fixed
- Quick start failed with `ModuleNotFoundError`: the `src/` layout requires installing the
  package. Docs now use `pip install -e .`; tests are collected correctly.
- `LICENSE` was missing the MIT liability paragraph.
- Bearing impacts were rounded to whole samples, shifting the repetition rate (133 Hz instead of
  126 Hz in the v0.1 demo). Impacts are now placed at exact sub-sample times.
- The generator accepted a resonance above Nyquist (aliasing). Configurations that would alias
  now raise `ValueError`.

### Added
- Bearing kinematics: `BearingGeometry`, BPFO/BPFI/FTF/BSF, `6205` preset.
- Synthetic conditions `misalignment`, `bearing_outer`, `bearing_inner`, `cavitation_like`;
  vane-pass tone in every signal; `severity`, `noise_std`, `n_vanes`, slip and resonance
  parameters via `SignalConfig`.
- `simulate()` returning a `SyntheticSignal` with provenance metadata (`"synthetic": true`).
- Frequency-domain features: amplitude spectrum, shaft-order amplitudes, vane-pass amplitude,
  spectral centroid, high-frequency energy ratio, envelope spectrum and envelope peak ratios.
- More time-domain features: skewness, std, peak-to-peak, shape/impulse/clearance factors.
- `make_synthetic_dataset()` with virtual machines (`group_id`) and leakage-safe
  `group_train_test_split()`.
- CSV + JSON-sidecar I/O (`save_signal`, `load_signal`) usable with real recordings.
- `pumpguard` CLI with `demo`, `features`, `dataset`, `bearing` commands.
- Three-panel overview figure (waveform, spectrum, envelope spectrum).
- Test suite (105 tests), CI on Linux/Windows/macOS for Python 3.10–3.13, ruff, strict mypy,
  pre-commit, Dependabot, PyPI trusted-publishing workflow.
- Community files: Code of Conduct, Security policy, issue/PR templates, citation file,
  roadmap, dataset and model card templates.

### Changed
- Default sampling rate is now 12 kHz (was 2 kHz) so bearing resonances fit below Nyquist.
  Pass `fs=2000` to `generate_signal` for the old rate.
- `bearing_like` is deprecated in favour of `bearing_outer` (still accepted, with a warning).
- Undefined ratios (e.g. crest factor of an all-zero signal) are `nan` instead of `0.0`.
- Non-finite input to feature functions raises `ValueError`.
- `demo_health_score` moved to `pumpguard.health` (still importable from `pumpguard.features`).

## [0.1.0] - 2026

### Added
- Initial prototype: synthetic healthy / imbalance / bearing-like signals, RMS, peak, crest
  factor, kurtosis, toy health score, CSV and plot export.
