# Dataset card: `<dataset name>`

Copy this file for each dataset you use or add a loader for. Leave no field blank; write
"unknown" when the source does not say.

## Source
- **Name / version:**
- **URL / DOI:**
- **License and terms of use:**
- **Required citation:**
- **Date accessed / checksum (SHA-256):**

## Acquisition
- **Machine:** (type, model, rated power, impeller vane count)
- **Bearings:** (designation, geometry, where installed)
- **Sensor:** (type, sensitivity, mounting, location, direction)
- **Sampling rate (Hz) and anti-aliasing filter:**
- **Operating conditions:** (speeds, loads, flow/head if pump)
- **Recording length and segmentation:**

## Labels
- **Classes and how many recordings per class:**
- **How faults were created:** (seeded / natural / accelerated life)
- **Fault sizes / severities:**
- **Labelling method and known label noise:**

## Grouping and leakage
- **Natural group unit:** (machine, test run, bearing, recording file)
- **Group column used in this project:**
- **Known leakage risks:** (e.g. segments of one recording, same bearing across loads)

## Known issues and limitations
- Class imbalance, missing metadata, sensor problems, anything unusual.

## Use in this project
- **Loader:** `pumpguard.datasets.<name>` (if any)
- **Preprocessing:** (resampling, filtering, segmentation)
- **Who reviewed this card and when:**
