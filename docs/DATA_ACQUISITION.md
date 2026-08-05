# Data acquisition protocol for the first real archival scan

## Target product

Prefer public search-mode or single-pulse observations that preserve individual rotations, frequency channels and polarization products. Folded profiles and timing-arrival tables are insufficient for pulse-by-pulse modulation searches.

## Selection order

1. Stable, bright pulsars with long observations and known ephemerides.
2. Millisecond pulsars with high timing precision, provided individual pulses remain measurable.
3. Pulsars observed independently by more than one observatory.
4. Observations with nearby off-source pointings or calibrator scans.

Do not select targets because their preliminary data look unusual. Freeze the target list before scanning.

## Required metadata

- source name and sky coordinates;
- telescope, backend and project identifier;
- observation start time and duration;
- sampling interval, channel frequencies and polarization order;
- rotation period and dispersion measure appropriate to the observing epoch;
- calibration and RFI-processing history;
- original download URL, archive identifier, file size and SHA-256 digest.

## Minimum controls

Every target receives the registered block-permutation control. Dynamic-spectrum inputs additionally receive three off-pulse windows, two wrong-period folds and two wrong-DM reductions when DM is positive. A surviving candidate still requires off-source and independent-observatory validation.

## Data preservation

Keep the original archive file read-only. Write all derived products to a separate directory. Never overwrite calibration weights or headers. Publish the frozen manifest, hashes, software version, full reports and excluded-file log with any result.
