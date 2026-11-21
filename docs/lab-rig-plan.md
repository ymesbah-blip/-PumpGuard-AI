# Lab rig plan: from a pump test loop to a citable dataset

Purpose: produce measured, labelled, provenance-complete vibration and hydraulic data for
centrifugal pumps (including short ESP stage stacks), so that PumpGuard methods can be
validated beyond synthetic data and bearing rigs.

> This plan covers **laboratory experiments only**. It contains no recommendation for operating
> field equipment, and no result from the rig should be turned into one without a separate
> engineering review by the asset owner.

## 1. Rig configuration

- **Loop:** closed water loop with a tank of sufficient volume to limit temperature rise,
  a throttle valve on the discharge (flow control), a valve or vacuum system on the suction side
  (NPSH control, used only in supervised NPSH tests), and a bypass for minimum-flow protection.
- **Pump under test:** a single-stage end-suction pump, or a short horizontal stack of ESP stages
  in a test housing. Record model, impeller and diffuser vane counts, stage count and assembly ID.
- **Drive:** induction motor on a VSD. Log drive output frequency and motor electrical power.

## 2. Instrumentation

| Quantity | Sensor (example class) | Location | Sampling | Notes |
|---|---|---|---|---|
| Vibration | IEPE accelerometer, ~100 mV/g, flat to ≥ 10 kHz | stud-mounted on bearing housings: radial horizontal, radial vertical, axial | ≥ 25.6 kHz, anti-alias ≤ 0.4 fs | calibration certificate; back-to-back check before each campaign |
| Speed reference | once-per-revolution optical/laser probe | shaft with reflective mark | record the raw pulse train at the DAQ rate | needed for order tracking and accurate 1x |
| Suction pressure | **absolute** pressure transducer | suction measurement section | ≥ 1 kHz if pulsations are studied, otherwise ≥ 10 Hz | absolute value needed for NPSHa |
| Discharge pressure | gauge/absolute transducer | discharge measurement section | as above | head = Δp/(ρg) + velocity/elevation terms |
| Flow | electromagnetic flowmeter | straight run per manufacturer | ≥ 10 Hz | verify zero before each run |
| Fluid temperature | RTD (Pt100) | tank / suction | 1 Hz | density and vapour pressure |
| Motor power | power analyser | motor terminals | ≥ 1 Hz (RMS values) | shaft power needs motor efficiency, or use a torque meter |

All channels go through one DAQ clock (or are hardware-synchronised). Before each campaign,
check every channel with `pumpguard.sensors.sampling_report` against the frequencies you intend
to study (`pumpguard.orders.characteristic_frequencies`).

## 3. Acquisition and identifiers

- **acquisition_id**: `<rig>-<assembly>-<run>-<YYYYMMDDThhmmss>`, one per recording.
- **group_id**: the physical **assembly** (pump build). All runs of one build share its
  imbalance, alignment and wear, so splits must be by assembly (or at least by day), never by
  segment.
- Raw files are immutable. Store a SHA-256 for each, and keep derived data in a separate folder.
- Each recording gets a provenance record validated by
  `pumpguard.datasets.validate_provenance` (units, calibration, fs, rpm source, operating point,
  label method).

## 4. Test matrix (healthy baseline first)

1. Healthy baseline: at least 3 speeds × at least 5 flows within the pump's allowable operating
   region (e.g. 60–120 % of BEP flow), each repeated on at least 3 different days, in randomised
   order. Never run at shut-off longer than the manufacturer allows.
2. Seeded mechanical conditions, one at a time, each with a documented magnitude and a return to
   baseline afterwards: added unbalance mass (record g·mm and angle), coupling misalignment
   (shim thickness, measured offset), bearing with a documented artificial defect.
3. Hydraulic regime only under supervision: NPSH tests by controlled suction-pressure reduction
   following a recognised pump-test standard procedure (e.g. a 3 % head-drop criterion), with the
   stop criteria fixed in advance.

## 5. Rig → dataset path

raw files → provenance records (validated) → dataset card
(`docs/dataset-card-template.md`) → segmentation and features
(`pumpguard.features.extract_all_features`) → split by `group_id` → benchmark with the fixed
protocol (`docs/benchmark-protocol.md`). Publish the dataset card and code; publish raw data only
with the owner's and institution's agreement.

## 6. Safety boundaries (non-negotiable)

- Operate within the pump's, motor's and loop's rated speed, pressure and temperature. A
  pressure-relief device and an emergency stop are tested before every campaign.
- Guard all rotating parts, and apply lockout/tagout before any mechanical intervention
  (adding unbalance mass, changing shims, mounting sensors).
- Respect the manufacturer's minimum continuous flow. Do not run against a closed valve beyond
  the allowed time.
- Hydraulic-regime experiments (low NPSH, two-phase) only with a written procedure, a
  supervisor present, hearing protection, and predefined stop criteria (vibration level,
  temperature, head drop).
- No unattended operation, and no remote control of the rig from analysis code.

## 7. What may be claimed

- Cavitation or gas-related conditions may be **labelled** only from controlled experiments with
  the reference criterion recorded (e.g. measured head drop at a known NPSHa). Until such data
  exist, PumpGuard's `cavitation_like` signal stays a synthetic teaching example and no
  cavitation classifier is reported.
- Results from the rig describe that rig. Transfer to field ESPs (different housings, gas, long
  cables, downhole sensors) must be shown, not assumed.
