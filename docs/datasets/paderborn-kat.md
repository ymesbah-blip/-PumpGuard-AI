# Dataset card: Paderborn University KAt bearing dataset

Filled from [`docs/dataset-card-template.md`](../dataset-card-template.md). Facts are taken from
the dataset publication (Lessmeier et al., 2016) and the KAt-DataCenter web pages. Items marked
*verify locally* depend on the files themselves; check them with
`pumpguard paderborn inspect <file>.mat`.

> **Not a centrifugal-pump dataset.** These are measurements from an electromechanical
> bearing test rig. Results on it say something about bearing-damage signatures under
> controlled conditions, not about diagnosing pumps in the field.

## Source
- **Name:** KAt-DataCenter, bearing data, Chair of Design and Drive Technology (KAt),
  Paderborn University
- **URL:** <https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter>
- **License:** Creative Commons Attribution-NonCommercial 4.0 (CC BY-NC 4.0). Non-commercial
  academic use is allowed with citation; for commercial use, contact the authors.
- **Required citation:** Lessmeier, C.; Kimotho, J. K.; Zimmer, D.; Sextro, W.: *Condition
  Monitoring of Bearing Damage in Electromechanical Drive Systems by Using Motor Current Signals
  of Electric Motors: A Benchmark Data Set for Data-Driven Classification.* European Conference
  of the PHM Society, Bilbao, 2016. Also name the author, institute and link to the
  KAt-DataCenter.
- **Redistribution in this repository:** none. PumpGuard AI only reads files the user downloaded.
- **Checksum:** compute per file with `read_measurement(..., compute_sha256=True)`.

### Mirror: Zenodo (used while the university server was offline, 2026-11-21)
- **Record:** "Paderborn Bearing Dataset", DOI
  [10.5281/zenodo.15845309](https://zenodo.org/records/15845309), uploaded 2025-07-09 by
  J. van den Hoogen (Osnabrück University). 31 RAR archives, 5.2 GB, with size and MD5 per file.
- **Licence label:** the mirror says CC BY 4.0 and has no description or citation. A copy cannot
  relax the original licence: treat the files as **CC BY-NC 4.0** and cite Lessmeier et al.
- **Coverage:** all bearings except **KA08** (artificial outer-race damage). `real3` is complete;
  `artificial_to_real` and `all_single` lack KA08 when built from the mirror.
- **Integrity:** sizes and MD5s are built into `pumpguard.datasets.paderborn_archives`
  (`ZENODO_MANIFEST`, read from the Zenodo files API). They prove a download matches the mirror,
  not that the mirror matches the university's originals. When the original server is
  reachable, compare a few `.mat` files' SHA-256 between both sources.
- **Windows helper:** `scripts/paderborn/fetch_real3.ps1` downloads the 15 `real3` archives with
  `curl.exe`, checks size and MD5, extracts them with Windows `tar` (7-Zip as fallback) and logs
  the result.

## Acquisition
- **Machine:** modular test rig: electric motor, torque-measuring shaft, bearing test
  module, flywheel and load motor. Bearings run in the test module.
- **Bearings:** deep-groove ball bearing type 6203, 8 balls. Geometry used here: ball diameter
  6.75 mm, pitch diameter 28.55 mm, contact angle 0°. Bearings came from several manufacturers
  (FAG, MTK, IBU); the publication reports 1–2 % variation of characteristic frequencies.
  At 1500 rpm: BPFO ≈ 76.4 Hz, BPFI ≈ 123.6 Hz (`pumpguard bearing --rpm 1500 --bearing 6203`).
- **Vibration sensor:** PCB 336C04 piezoelectric accelerometer on an adapter at the top of the
  bearing module housing, main load direction. Kistler 5015A charge amplifier with 30 kHz
  low-pass filter.
- **Channels and rates:** `vibration_1`, `phase_current_1` and `phase_current_2` at 64 kHz;
  `force`, `torque` and `speed` at 4 kHz; `temp_2_bearing_module` at 1 Hz.
- **Units in the files:** not given. The `Unit` field is an empty MATLAB array for every
  channel (checked on real files); the loader records "unspecified in source" and applies no
  conversion. Ratio features (kurtosis, crest factor, envelope ratios) do not depend on the unit;
  `rms` is in the file's raw unit.
- **Operating conditions:**

  | Code | Speed (rpm) | Load torque (Nm) | Radial force (N) |
  |---|---|---|---|
  | N15_M07_F10 | 1500 | 0.7 | 1000 |
  | N09_M07_F10 | 900 | 0.7 | 1000 |
  | N15_M01_F10 | 1500 | 0.1 | 1000 |
  | N15_M07_F04 | 1500 | 0.7 | 400 |

- **Recordings:** 20 measurements of 4 s per bearing and operating condition, one `.mat` file
  each, named `<condition>_<bearing>_<n>.mat` (e.g. `N15_M07_F10_KA01_1.mat`).

## Labels
- **32 bearings:** 6 healthy (K001–K006), 12 with artificial damage, 14 with real damage from
  accelerated lifetime tests.
- **Artificial damage:** outer ring KA01 (EDM), KA03/KA05/KA06 (electric engraver),
  KA07/KA08/KA09 (drilling); inner ring KI01 (EDM), KI03/KI05/KI07/KI08 (electric engraver).
- **Real damage:** outer ring KA04, KA15, KA16, KA22, KA30; inner ring KI04, KI14, KI16, KI17,
  KI18, KI21; combined outer + inner KB23, KB24, KB27 (fatigue pitting or plastic indentations).
- **Labelling method:** by construction (artificial) or by inspection after lifetime tests
  (real), as documented in the publication's fact sheets. PumpGuard maps code prefixes `K0`,
  `KA`, `KI` and `KB` to `healthy`, `outer`, `inner` and `outer+inner`.

## Grouping and leakage
- **Natural group unit:** the **physical bearing** (four-character code). All files of one
  bearing share its individual damage geometry and mounting.
- **Group column:** `group_id` = bearing code.
- **Leakage risks:**
  - Segments of one recording, and recordings of one bearing under different operating
    conditions, must never be split across train and test.
  - Healthy bearings differ in run-in history. With only 5–6 healthy units, a model can learn
    individual bearings, so evaluate by bearing.
  - Artificial and real damage differ systematically. Training on one and testing on the other
    is a deliberate domain-shift test (`artificial_to_real` task), not a standard split.

## Fact-sheet check (2026-11-21, files from the Zenodo mirror)
Each archive contains the bearing's fact sheet (`<code>.pdf`) and measuring log. For the 10
damaged `real3` bearings, mode, ring, extent and method in the fact sheets match the bearing
table in `pumpguard.datasets.paderborn`, with one addition: **KI04 and KI14 have two damages**,
inner-ring fatigue pitting (extent 1) **and** plastic deformation on the outer ring
("damage combination: M", multiple). They keep the label `inner`, as in the publication, but an
outer-race envelope signature on them is physically plausible and is reported as a known
failure mode, not as a model error. KA16 and KA30 have repetitive damage ("R").

Observed in the files (KA04, N15_M07_F10): `Unit` is empty for every channel, `vibration_1`
has 256 004 samples (4.0001 s at 64 kHz), the `speed` channel reads 1 499–1 501 rpm, torque
1.04–1.46 Nm (the nominal setting is 0.7 Nm), radial force 812–1 365 N (nominal 1 000 N) and
bearing-module temperature 55.5 °C.

## Known issues and limitations
- Reported as unreadable by `scipy.io.loadmat`: `KA08/N15_M01_F10_KA08_2.mat` (per third-party
  documentation; *verify locally*). The loader records such files under `failures` and
  continues.
- The archives are RAR files; extract them with any RAR-capable tool before use (Windows 10/11
  `tar -xf X.rar`, 7-Zip, `unrar`). Then run `pumpguard paderborn verify <folder> --archives
  <rar folder>`: it checks every MD5 and that each bearing has 20 measurements in each of the 4
  operating conditions, and stores the result in `paderborn_verification.json`, which the
  feature-table report copies.
- One rig, one bearing type, steady operating points: no variable speed, no transfer path
  through a pump casing, no process noise.

## Use in this project
- **Loader:** `pumpguard.datasets.paderborn` (`scan`, `read_measurement`,
  `build_feature_table`) and `pumpguard.datasets.paderborn_archives` (`verify_archives`,
  `check_inventory`), CLI `pumpguard paderborn index | verify | inspect | features`.
- **Preprocessing:** non-overlapping segments (default 1 s), no resampling, no filtering except
  the envelope band-pass inside the envelope features. Speed comes from the `speed` channel
  when it lies within ±20 % of the nominal setting, otherwise from the nominal setting (recorded
  as `rpm_source`).
- **Benchmark protocol:** [`docs/benchmark-protocol.md`](../benchmark-protocol.md).
- **Reviewed:** v0.3.0, against the 2016 publication. Re-verify units, channel names and
  durations on the first real files.
