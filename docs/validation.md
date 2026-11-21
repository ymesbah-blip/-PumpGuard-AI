# Scientific validity and verification plan

## Signals and measurements

- Shaft frequency: f_r = RPM / 60 Hz.
- Discrete RMS: sqrt(mean(x[n]^2)); amplitude has the same units as x.
- Crest factor: max(|x|) / RMS (dimensionless), defined as 0 for all-zero signal.
- Pearson kurtosis: unbiased SciPy calculation with fisher=False (dimensionless); returns NaN for constant signals.
- Welch PSD: Hann-windowed, overlapping periodograms averaged. PSD has amplitude²/Hz; the integrated PSD approximates variance when mean is removed.
- Order band power: sum(PSD(f) * df) around `order * RPM/60`; it is a descriptive energy proxy, **not** a standard fault threshold.

The toy health score has **no calibration** and is intentionally labeled as such. Never interpret it as remaining useful life, a fault probability or industrial alarm criterion.

## Test levels

1. Unit tests: finite inputs, zero signals, sample count, alias rejection, deterministic seeded generation, exact tone peak, energy consistency and CSV timestamp QA.
2. Dataset integration: verify units, speed, sensor position, labels, licensing and independently measured operating conditions before loading experimental data.
3. Algorithm studies: stratify/group by machine and acquisition; use a held-out machine/operating-point test if available. Compare to simple RMS and shaft-harmonic baselines, and include uncertainty intervals.
4. Prototype rig: verify sensor calibration, excitation spectrum, speed and load variation, repeated trials and safe instrument handling before any claims about diagnostic sensitivity.
5. Site deployment: separate external engineering acceptance, cyber-security, alarms and safety certification is required. **Not provided** by PumpGuard-AI.

## Failure cases to document

Variable speed or sampling, cavitation, bearing defects, impeller imbalance, misalignment, seal wear and sensor mounting are all distinct physical mechanisms. A strong synthetic 1x vibration signal is **not** proof of imbalance; similar peaks can occur with other excitation paths. The 4.2x impulse sequence is a pedagogical stand-in, not a bearing fault-frequency model, and cannot establish bearing condition without actual geometry.

## Further reading

- SciPy Welch PSD: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html
- Paderborn University original dataset and terms: https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter
