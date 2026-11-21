# Data provenance, licences and measured-signal integration

The repository contains no real bearing or pump measurements. Its illustrative data have arbitrary amplitude units.

## Scientific candidate dataset

Paderborn University KAt Bearing DataCenter:
https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter

The university provides vibration and motor-current signals acquired on a **bearing / electromechanical drivetrain rig**, not a centrifugal-pump field rig. It states that the dataset uses **CC BY-NC 4.0** and requires attribution (Christian Lessmeier et al.); commercial use requires contacting the author. Do not assume the data inherits this repository's MIT code licence, and do not redistribute it inside this repository without confirming the applicable rights.

## Metadata requirements

Record dataset source, original URL, citation, licence, machine type, acquisition ID, sensor location and orientation, amplitude units, accelerometer calibration, fs, RPM, load, hydraulic conditions where measured, acquisition duration and fault-label provenance.

For local CSV imports, require monotonic timestamps, numeric finite values and approximately uniform sampling before Fourier/PSD analysis. If RPM is entered manually, label it as **supplied** rather than estimated or measured.

Never upload proprietary field recordings, site names, sensor identifiers or sensitive industrial logs without authorization.
