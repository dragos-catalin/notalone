# First real-data pilot — PSR B0329+54 (Breakthrough Listen / GBT)

Date: 2026-08-04 · Pipeline: pulsar-network-experiment v0.4.0 · Manifest: `manifest-real-pilot.yaml` (frozen before pulse-level inspection) · Surrogates: 2048 · Seed: 20260804

## Data

Two independent GBT L/S-band epochs of PSR B0329+54 (P = 0.714520 s, DM = 26.7641 pc cm⁻³), Breakthrough Listen Open Data high-time-resolution products (tsamp = 349.5 µs, ≈2044 samples/rotation), downloaded with pinned SHA-256:

| id | epoch | file | sha256 | rotations |
|---|---|---|---|---|
| B0329+54-AGBT17A-0016 | 2017-02-07 | …0016.gpuspec.8.0001.h5 | `eea28c0c…59f8b62` | 251 |
| B0329+54-AGBT18A-0059 | 2018-03-25 | …0059.gpuspec.8.0001.h5 | `79b08ee0…1edbea` | 419 |

## Result: NULL — no registered Level-1 anomaly

| observation | verdict | adj. p | compression gain | disposition |
|---|---|---|---|---|
| AGBT17A-0016 | consistent_with_fitted_natural_model | 0.187 | 32 bits | no_registered_level1_anomaly |
| AGBT18A-0059 | interesting_but_inconclusive | 0.0039 | 32 bits | no_registered_level1_anomaly |

All 16 registered controls (block-permutation, 3× off-pulse, 2× wrong-period, 2× wrong-DM per observation) were clean.

## Interpretation

- AGBT18A-0059 shows a timing-channel periodicity near lag 35 pulses with a small surrogate p-value, but only 32 bits of compression gain — far below the preregistered 128-bit Level-1 threshold. PSR B0329+54 is a canonical drifting-subpulse / mode-switching pulsar; low-compressibility quasi-periodicity in single-pulse arrival jitter is the expected natural signature of exactly that behavior. The pipeline classified it correctly as not protocol-like.
- This is the intended operation of the falsifiable design: a real astrophysical quasi-periodicity was noticed, quantified, and rejected by the registered thresholds instead of being promoted to a "signal".

## Pilot limitations (declared in the frozen manifest)

- Stokes-I only; polarization channel inert.
- 251/419 rotations per epoch — well below the preregistered 10,000-rotation preference; sensitivity to short repeated frames is limited.
- Single telescope (GBT); the two epochs serve as mutual recurrence context only.

## Per the preregistered negative-result policy

This null constrains only the tested modulation families, this cadence (~0.7 s rotations over ~1–5 min), this frequency band (1.8–2.3 GHz), these two epochs and this detector's sensitivity. It says nothing about the existence of extraterrestrial communication networks in general.

## Next step

Scale to the full pilot design in `docs/NEXT_REAL_SCAN.md`: 5–10 pulsars, longer observations (10⁴+ rotations, e.g. the 0000.h5 fine-frequency products or FAST/CSIRO search-mode archives), independent observatories, and a held-out recurrence epoch per target.
