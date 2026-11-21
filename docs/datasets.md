# Dataset provenance and licensing

The bundled generator outputs only **synthetic, uncalibrated, arbitrary-unit signals**. Its three labels are illustrative classes rather than field-verified pump faults.

## Candidate experimental dataset

**Paderborn University, KAt Bearing DataCenter**: https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter

Vibration and motor-current measurements from a bearing test rig, **not a centrifugal-pump field dataset**. It is listed as **CC BY-NC 4.0**; the university says non-commercial academic use is permitted with attribution to Christian Lessmeier et al. Commercial use requires contacting the author. Keep this dataset out of the MIT-licensed code repository unless rights are established; download it from the original site and cite its publication.

## Expected record metadata (not yet automated)

For every trace document `dataset_id`, source URL, source licence and citation, `machine_type`, sensor location/orientation, sensor calibration and physical units (e.g., m/s²), `fs_hz`, measurement duration, `rpm` measured rather than assumed, load/flow/pressure, operating point, labeling method and collection date. Capture the same machine identifier for grouped cross-validation. Never split adjacent windows from the same acquisition across train and test.

## CSV import contract

Columns `time_s` and `vibration`, numeric, finite, strictly increasing, sampling interval within 1% of median. No automatic resampling, integration, acceleration-unit conversion, filtering or calibration occurs. Use `--input-csv path/to/trace.csv --rpm <measured-speed>`; `--rpm` is a user-supplied value, not estimated from the signal. Outputs remain unverified until dataset provenance is documented.
