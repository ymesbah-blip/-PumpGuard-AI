# Datasets: provenance and licensing

## What is bundled

Only the **synthetic generator** (`pumpguard.signals`). Its outputs are uncalibrated,
arbitrary-unit signals with six illustrative conditions (healthy, imbalance, misalignment,
outer-race and inner-race bearing defects, a cavitation-like pattern; see
[synthetic-model.md](synthetic-model.md)). Every synthetic file carries `"synthetic": true`.

No third-party measurements are bundled, mirrored or downloaded automatically.

## Supported external dataset

| Dataset | Loader | Licence | What it is | Card |
|---|---|---|---|---|
| Paderborn University KAt bearing data | `pumpguard.datasets.paderborn` | CC BY-NC 4.0 | 6203 bearings in an electromechanical test rig; **not** a pump dataset | [paderborn-kat.md](datasets/paderborn-kat.md) |

### Using the Paderborn data

1. Read the licence on the
   [KAt-DataCenter page](https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter): it
   permits non-commercial use with attribution.
2. Download the bearing archives you need (at least the 15 bearings of the `real3` task) and
   extract them into one folder, e.g. `data/paderborn/K001/N15_M07_F10_K001_1.mat`. The folder
   layout does not matter; files are found recursively by name.
3. Check that the files are complete and that the structure matches:
   ```bash
   pumpguard paderborn index data/paderborn
   pumpguard paderborn inspect data/paderborn/K001/N15_M07_F10_K001_1.mat
   ```
4. Extract features and run the benchmark ([protocol](benchmark-protocol.md)):
   ```bash
   pumpguard paderborn features data/paderborn --task real3 --out outputs/pu_real3.csv
   pumpguard benchmark outputs/pu_real3.csv --out outputs/bench_real3
   ```

`data/` is in `.gitignore`. Never commit the data, and do not publish derived feature tables
without checking that the licence allows it.

## Provenance record (enforced)

Every measured recording that enters an analysis gets a record validated by
`pumpguard.datasets.validate_provenance`. Missing or inconsistent fields raise
`ProvenanceError`, which lists **all** problems at once. Required fields:

`dataset_id`, `source_url`, `license`, `citation`, `synthetic`, `source_file`,
`acquisition_id`, `group_id`, `machine_type`, `sensor`, `sensor_location`, `channel`, `unit`,
`calibration`, `fs_hz`, `duration_s`, `rpm`, `rpm_source`, `operating_condition`, `label`,
`label_method`, `damage_origin`.

Rules beyond presence and type: positive `fs_hz`, `duration_s` and `rpm`; `rpm_source` in
{`measured_speed_channel`, `nominal_setting`, `tachometer`, `user_supplied`, `synthetic`};
synthetic and measured records cannot be mixed up.

`rpm` is never estimated from the vibration signal. It comes from a speed channel or tachometer,
the documented nominal setting, or the user, and `rpm_source` says which.

## Splitting rule

Split by `group_id` (the unit that shares individual properties: machine, bearing, or
recording), never by segment. Use `pumpguard.evaluation.stratified_group_kfold` or a predefined
split by group. `pumpguard benchmark` refuses predefined splits that put one group on both
sides.

## Your own CSV recordings

`pumpguard features recording.csv --rpm <measured rpm>` reads columns `time_s` and
`vibration` (finite, strictly increasing time, sampling interval uniform within 0.1 %). No
resampling, unit conversion, integration, filtering or calibration is applied. Results stay
unverified until the recording's provenance is documented with a dataset card.
