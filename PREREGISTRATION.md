# Pre-registration draft for the first public archival scan

This document must be versioned and frozen before examining the selected real-data results.

## Primary hypothesis

After correcting known propagation, instrument and RFI effects, at least one pulsar observation contains repeatable protocol-like structure not adequately reproduced by the registered natural surrogate ensemble.

## Null hypothesis

All detected structure is compatible with natural pulsar variability, interstellar propagation, terrestrial interference, instrumental effects, selection effects or the registered statistical models.

## Inclusion criteria

- Public search-mode or single-pulse data.
- Known source position, rotation period and dispersion measure.
- At least 10,000 usable rotations where practical.
- Time and frequency resolution sufficient to preserve individual pulses.
- Rawest available calibrated product retained.

## Exclusion criteria fixed before scanning

- Fewer than 16 complete rotations after preprocessing.
- More than 90% of channels rejected by the registered RFI mask.
- Corrupted/incomplete headers or inconsistent sample dimensions.
- Candidate appearing in off-pulse, wrong-period, wrong-DM, off-source or geographically local RFI controls.
- Candidate dependent on one undocumented preprocessing choice.

## Registered channels

1. pulse amplitude;
2. signed polarization proxy;
3. arrival-time residual;
4. frequency centroid.

No additional feature channel may be added after seeing candidate results without labeling the analysis exploratory.

## Registered detector

- Robust two-cluster binarization.
- Autocorrelation frame search from lag 32 to min(4096, N/3).
- Mixed Markov, run-length-permutation and circular block-bootstrap surrogate ensemble.
- Four-channel selection correction.
- Compression gain as a secondary metric.
- Benjamini-Hochberg correction across the target batch.

## Registered preprocessing amendments

### Amendment 1 — 2026-08-05 (v0.6): frequency-centroid whitening

Motivation: the v0.5 three-pulsar survey identified slow per-channel gain wander
of the GBT/Breakthrough Listen backend that imprints a lag ≈ 32–38 rotation
periodicity on the frequency-centroid channel. The artifact was proven
instrumental by the registered controls: it appears identically in off-pulse
windows, wrong-period folds, wrong-DM reductions and across two unrelated
pulsars (B0531+21 and B2021+51).

Amendment: when `whiten_frequency` is enabled in a manifest, each frequency
channel's per-rotation on-window power is detrended by a moving median across
rotations (window: min(33, n_pulses/8) rotations, odd) before computing the
frequency centroid. This removes gain variations slower than ~10 rotations
while preserving pulse-to-pulse spectral modulation. The amendment is declared
BEFORE any v0.6 data run; it applies identically to targets and controls and
does not alter thresholds, channels or surrogate families.

## Analysis thresholds

### Level 1 — software anomaly

- channel-adjusted p < 0.05;
- compression gain > 128 bits;
- survives the registered preprocessing sensitivity checks.

### Level 2 — follow-up candidate

- batch FDR q < 0.01 after an escalated surrogate run;
- compatible candidate lag in held-out split halves;
- recurrence in a held-out observation;
- no corresponding off-source/local RFI event;
- compatible structure in frequency or polarization sub-bands.

### Level 3 — technosignature candidate

- independent observatory confirmation;
- predicted recurrence succeeds;
- raw-data and instrument teams exclude known effects;
- recovered structure contains framing/redundancy or error-detection behavior.

### Level 4 — network evidence

- a statistically corrected, independently replicated shared protocol across at least three sky-separated pulsars;
- timing relationships compatible with a declared propagation/repeater model;
- no plausible common terrestrial or pipeline source.

No single-software detection will be described as proof of extraterrestrial intelligence.

## Negative result policy

A null result constrains only the tested modulation families, cadences, frequencies, datasets and detector sensitivity. It does not show that no extraterrestrial communication network exists.
