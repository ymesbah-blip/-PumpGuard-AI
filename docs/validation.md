# Scientific validity and reproducibility

## Current status
This repository generates **synthetic** single-channel waveforms and a demonstration health score. It is not calibrated to actual pumps or industrial standards.

## Equations and interpretation

- Shaft frequency: f_rot [Hz] = RPM / 60.
- RMS = sqrt(mean(x[n]^2)), in signal amplitude units.
- Crest factor = max(abs(x[n])) / RMS (dimensionless).
- Pearson kurtosis is dimensionless; document the small-sample convention.
- Welch PSD: windowed overlapping segment periodograms, averaged; units of amplitude squared per Hz. See https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html
- Shaft-order band energy: numerical integral of PSD near f = order × RPM/60, with units amplitude squared. Not a standardized fault threshold.

## Evaluation plan

1. Validate code on deterministic simulated tones, zero signals, invalid sampling rates and time jitter.
2. Require metadata for any external measurement: sensor position and orientation, calibration, amplitude units, sampling frequency, RPM, pump operating state, label and acquisition ID.
3. Prevent data leakage by grouping windows by acquisition/machine, not by individual sample, across train and test.
4. Compare simple non-ML baselines to advanced methods under variable RPM/load and out-of-domain machines.
5. Report precision, recall, false positive rate, uncertainty and repeated independent experiments only when true labels exist.
6. Validate on instrumented pumps before even suggesting operational use; industrial safety and cyber-security requirements need independent assessment.

## Caveats

Cavitation, misalignment, imbalance, bearing problems and sensor mounting can produce overlapping spectral effects. Simulated signals establish software reproducibility, **not** fault-detection sensitivity or specificity. An order peak is evidence of spectral energy only.
