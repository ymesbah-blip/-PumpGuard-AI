# Scientific validity and verification plan

This page states what each computed quantity means, how it is tested, and what has **not** been
validated. It describes the code as implemented in v0.3.

## Quantities

| Quantity | Definition (implementation) | Unit |
|---|---|---|
| Shaft frequency | f_r = rpm / 60 | Hz |
| RMS | sqrt(mean(x[n]²)) | unit of x |
| Crest factor | max\|x\| / RMS; `nan` for an all-zero signal | – |
| Kurtosis | Pearson (normal = 3, sine = 1.5), SciPy `fisher=False, bias=False`; `nan` for constant signals | – |
| Amplitude spectrum | mean removed, Hann window, single-sided, corrected for coherent gain (a bin-centred sine of amplitude A reads A) | unit of x |
| Order amplitude (`amp_1x`, ...) | largest spectrum value within ±max(3 bins, 2 %) of order × f_r | unit of x |
| Spectral centroid, `hf_energy_ratio` | from a Hann-windowed periodogram (not Welch averaging); power above 1 kHz / total non-DC power | Hz, – |
| Envelope ratio (`env_bpfo_ratio`, `env_bpfi_ratio`) | 4th-order zero-phase Butterworth band-pass (default 0.1–0.4 fs), Hilbert magnitude, amplitude spectrum; peak within ±max(3 bins, 2 %) of the defect frequency divided by the median envelope-spectrum level over (0, 5 × f_defect] | – |
| Bearing defect frequencies | kinematic formulas without slip (`bearings.py`) | Hz |
| Head from pressure | H = Δp / (ρ g), g = 9.80665 m/s² unless given | m |
| Hydraulic power | P = ρ g Q H | W |
| Multistage pump head | n · (N/N0)² · h_stage(Q·N0/N), catalog range only | m |
| Operating point | Q where pump head = system required head (Brent) | m³/s |
| Shaft / vane-pass frequency | rpm/60; n_vanes · rpm/60; rpm = 120 f/p · (1 − slip) | Hz |

The **toy health score** uses RMS only and has **no calibration**. It is not remaining useful
life, a fault probability or an alarm criterion. It is deliberately blind to early bearing
defects.

## Test levels

1. **Unit tests (automated, CI):** analytic values (sine RMS, crest factor, kurtosis),
   recovered tone amplitudes, AM envelope recovery, kinematic identities (BPFO + BPFI = n·f_r),
   alias rejection, determinism under fixed seeds, CSV timestamp checks, provenance validation,
   group-split invariants, metrics computed by hand, bootstrap reproducibility.
2. **Loader integration (automated with invented fixtures; manual with real files):** channel
   lookup by name, documented sampling rates, duration check, speed plausibility, corrupt-file
   handling. **Pending:** a first run on real Paderborn files to confirm channel names, units
   and durations (`pumpguard paderborn inspect`).
3. **Algorithm studies:** [benchmark protocol](benchmark-protocol.md): bearing-grouped
   cross-validation, transparent baselines first, group-bootstrap intervals, leakage check,
   artificial → real transfer.
4. **Prototype rig (not started):** calibrated sensors, known excitation, speed and load
   variation, repeated trials.
5. **Site deployment (out of scope):** engineering acceptance, cybersecurity, alarm management
   and safety certification are **not** provided by PumpGuard AI.

## Failure cases to document

- Variable speed (envelope peaks smear; order tracking not implemented).
- Defect frequencies vary 1–2 % between bearing manufacturers; slip adds 1–2 %. The 2 % search
  tolerance may pick a neighbouring peak at low frequency resolution.
- The envelope band is fixed. A band without the structural resonance hides bearing impacts.
- Electrical interference (inverter switching) inside the demodulation band can mimic
  modulation.
- A strong 1x component is not proof of imbalance: looseness, bent shafts, resonance or
  electrical effects can produce it too.
- Bearing test-rig results do not transfer automatically to pumps: different transfer paths,
  hydraulic excitation (vane pass, cavitation) and mounting.

## Further reading

- Paderborn KAt-DataCenter and terms: <https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter>
- Dataset publication: Lessmeier et al., PHM Society European Conference, 2016.
- SciPy signal processing reference: <https://docs.scipy.org/doc/scipy/reference/signal.html>
