# Architecture

## Module map

```text
src/pumpguard/
├── signals.py     SignalConfig → simulate() → SyntheticSignal (+ metadata)
├── bearings.py    BearingGeometry → DefectFrequencies (BPFO, BPFI, FTF, BSF)
├── features.py    extract_features (time domain), extract_all_features (time + spectral)
├── spectral.py    amplitude/envelope spectra, order amplitudes, band energy, centroid
├── health.py      demo_health_score (toy, RMS only)
├── dataset.py     make_synthetic_dataset, group_train_test_split
├── io.py          save_signal / load_signal (CSV + JSON sidecar)
├── plotting.py    plot_signal_overview (Matplotlib OO API, headless-safe)
├── units.py       SI conversions (BPD, ft, bar, psi, temperature)
├── hydraulics.py  OperatingPoint, PumpCurve, WellSystem, solve_operating_point (mechanism)
├── orders.py      shaft / vane-pass frequencies, rpm from VSD frequency (mechanism)
├── sensors.py     SensorSpec, observability checks, measure() (sensor)
├── regime.py      synthetic speed sweeps, naive-projection error
├── datasets/      provenance.py (schema), paderborn.py (bearing files), scada.py (trend logs)
├── baselines.py   transparent non-ML baselines (threshold, envelope rule, nearest centroid)
├── models.py      learned models, optional [ml] extra (logistic regression, random forest)
├── evaluation.py  group k-fold, metrics, group-bootstrap intervals
├── benchmark.py   leakage-safe benchmark + decision rule + Markdown/JSON report
├── leakage.py     same model under random vs group split, repeated over fold seeds
├── cli.py         `pumpguard` command (demo, features, dataset, bearing, paderborn,
│                  benchmark, leakage)
├── demo.py        legacy `python -m pumpguard.demo` entry point
└── _validation.py shared input checks
```

## Data flow

```text
            ┌──────────────┐     ┌─────────────┐
 config ──► │  simulate()  │ ──► │  t, x, meta │──┐
            └──────────────┘     └─────────────┘  │
 real CSV ─────────────────► load_signal() ───────┤
                                                  ▼
                                    extract_all_features(x, fs, rpm, bearing)
                                                  │
                         ┌────────────────────────┼─────────────────────────┐
                         ▼                        ▼                         ▼
                  feature table          plot_signal_overview      dataset + group split
                                                                      (→ models, v0.4)
```

The feature pipeline does not care whether a signal is synthetic or measured. That keeps the
path from synthetic experiments to real data short.

## Design principles

1. **Transparent before clever.** Every feature has a physical meaning and an analytic test.
   Models (v0.4+) consume these features before any black-box representation is considered.
2. **Synthetic is always labelled.** `SyntheticSignal.metadata()` sets `"synthetic": true`;
   the CLI and figures say "synthetic" explicitly.
3. **Reproducible by default.** Every random draw comes from a seeded `numpy.random.Generator`;
   identical config gives identical output (tested).
4. **Fail loudly.** Invalid or physically meaningless inputs (aliasing, NaNs, impossible
   geometry) raise `ValueError` with an explanation.
5. **Leakage-aware data structures.** Datasets carry `group_id`; the split utility never puts
   one group on both sides.
6. **Light core.** Runtime dependencies: NumPy, SciPy, pandas, Matplotlib. Heavier tools (ML,
   docs) go into optional extras. `pumpguard.models` imports scikit-learn only when a model is
   created, and a test checks that importing the core never loads it.
7. **Headless-safe.** Plotting uses `matplotlib.figure.Figure`, never `pyplot` global state.

## Public API and stability

Names exported from `pumpguard/__init__.py` are the public API. Before 1.0, minor releases may
change them, but every change is listed in `CHANGELOG.md`, and renamed items keep a deprecated
alias for at least one minor release (as `bearing_like` → `bearing_outer` does).
