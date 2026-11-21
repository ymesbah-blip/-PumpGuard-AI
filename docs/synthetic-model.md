# The synthetic signal model

> **Everything described here is synthetic.** The model is built to make signal-processing
> concepts visible and testable. It is not calibrated to any pump, standard or failure
> mode, and its outputs must never be presented as measurements.

Implementation: [`src/pumpguard/signals.py`](../src/pumpguard/signals.py). All amplitudes are
in arbitrary units (a.u.).

## Baseline (every condition)

```
x(t) = 0.10 · sin(2π·fr·t + φ1)          residual unbalance at 1x
     + 0.06 · sin(2π·Nv·fr·t + φ2)       vane-pass tone
     + σ · n(t)                          white Gaussian noise, σ = noise_std (default 0.05)
     + severity · fault(t)               condition-specific term (below)
```

- `fr = rpm / 60` is the shaft frequency in Hz.
- `Nv` is the impeller vane count (default 5), so the vane-pass frequency is `Nv · fr`.
  Every centrifugal pump has a vane-pass component; its growth is a classic indicator of
  hydraulic problems.
- Phases `φ` are random but seeded. Baseline random draws happen **before** any fault
  draws, so `severity = 0` reproduces the healthy signal exactly for the same seed.

## Fault terms (at `severity = 1`)

| Condition | Term | Physical idea | Feature that reveals it |
|---|---|---|---|
| `healthy` | none | — | — |
| `imbalance` | `0.60 · sin(2π·fr·t + φ)` | Mass unbalance → once-per-rev force | `amp_1x`, `rms` |
| `misalignment` | `0.10·sin(1x) + 0.35·sin(2x) + 0.10·sin(3x)` | Coupling misalignment → strong 2x | `amp_2x` > `amp_1x` |
| `bearing_outer` | impacts at **BPFO**, constant amplitude 0.5 | Stationary outer-race defect inside the load zone | `env_bpfo_ratio`, kurtosis |
| `bearing_inner` | impacts at **BPFI**, amplitude modulated at `fr` (0.4 → 0.16) | Inner-race defect rotates through the load zone → ±1x sidebands | `env_bpfi_ratio` |
| `cavitation_like` | band-limited noise (≈2–5 kHz) × slow random envelope, std ≈ 0.12–0.15 | Vapour-bubble collapse → broadband high-frequency, bursty | `hf_energy_ratio` |

### Bearing impacts

Each impact excites a single-degree-of-freedom structural resonance:

```
h(τ) = exp(-ζ·ωn·τ) · sin(ωd·τ),   ωn = 2π·f_n,   ωd = ωn·√(1-ζ²),   τ ≥ 0
```

- `f_n` = `resonance_hz` (default `min(3000 Hz, 0.3·fs)`), `ζ` = `damping_ratio` (default
  0.05). Each response is truncated once it has decayed by a factor of 1000.
- Impacts are placed at their **exact** (sub-sample) times, so the repetition rate is not
  quantised to the sampling grid. v0.1 rounded the spacing to whole samples, which moved a
  126 Hz defect to 133 Hz.
- Spacing is jittered by `slip` (default 1 %, clipped to ±50 %) to mimic rolling-element
  slip. Real bearings show roughly 1–2 % slip, which smears higher envelope harmonics.

Defect frequencies come from kinematics (see [`bearings.py`](../src/pumpguard/bearings.py)).
For the default 6205 geometry (9 balls, d = 7.94 mm, D = 39.04 mm, 0° contact angle):

| Frequency | × shaft | at 1800 rpm |
|---|---|---|
| FTF (cage) | 0.3983 | 11.95 Hz |
| BSF (ball spin) | 2.3567 | 70.70 Hz |
| BPFO (outer race) | 3.5848 | 107.54 Hz |
| BPFI (inner race) | 5.4152 | 162.46 Hz |

### Cavitation-like pattern

Gaussian noise is band-pass filtered (4th-order Butterworth, zero-phase) to
`[min(2000, 0.15·fs), min(5000, 0.4·fs)]` Hz and multiplied by a slowly varying envelope
`0.5 + |z(t)|`. Here `z` is a cubic spline through random knots every 50 ms, normalised to
unit mean. (A very low-cutoff IIR filter was avoided because its edge transients produced
unrealistic spikes.) Real cavitation also changes flow, head and vane-pass behaviour; none of
that is modelled.

## Guards against invalid physics

`SignalConfig` raises `ValueError` when:

- any deterministic component (3x or vane pass) would be at or above Nyquist;
- an explicit `resonance_hz` is ≥ 0.45·fs;
- fewer than 128 samples would be generated, or parameters are non-finite / out of range.

## What this model does **not** capture

Non-stationary speed, load-dependent amplitudes, transfer-path effects between source and
sensor, sensor noise spectra, multiple resonances, ball defects, looseness, rubs, electrical
faults, temperature and process effects, or any calibration to a real machine. Treat
results on synthetic data as a check that the code works, not as evidence about real
machines.
