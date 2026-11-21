# PumpGuard-AI engineering and community roadmap

The repository is an **educational prototype**. Planned capabilities are not operational or safety-ready diagnostics.

## Milestones

- [x] v0.1: Synthetic healthy / imbalance / bearing-like vibration examples and simple time-domain descriptors.
- [ ] v0.2: Installable `src/pumpguard` package, deterministic test suite and Python CI, Welch PSD, shaft-order frequency analysis, validated CSV ingestion, unit-aware reports.
- [ ] v0.3: Documented loaders for experimental bearing data and condition/sampling metadata.
- [ ] v0.4: Robust signal-processing baselines with machine/acquisition-grouped evaluation and confidence intervals.
- [ ] v0.5: Dedicated centrifugal-pump test rig with hydraulic operating data: RPM, head, flow, temperature, pressure, vibration.
- [ ] v0.6: Explainable classifiers validated against simple physics-informed baselines, without data leakage.
- [ ] v1.0: External reproductions, documented releases, field validation plan and sustained community maintenance.

## Engineering constraints

No synthetic vibration should be presented as real plant measurements. A 1x shaft-frequency peak does not prove imbalance. A bearing-like impulse train is not a geometry-derived BPFO/BPFI model. A toy health score is neither a risk probability nor a calibrated diagnostic score.

## Evidence of open-source maintenance

Welcome reproducible issues and outside contributions. Demonstrate meaningful adoption through actual users, cited scientific work, reproducible examples, reviewed contributions and release history rather than manufactured repository metrics. See `docs/validation.md` and `docs/datasets.md`.
