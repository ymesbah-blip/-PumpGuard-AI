# Changelog

All notable changes are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/) (pre-1.0: minor versions may break APIs).

## [Unreleased]

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
