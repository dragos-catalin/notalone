# Three-pulsar survey — PSR B0329+54, B2021+51, B0531+21 (Crab)

Date: 2026-08-05 · pulsarnet v0.5.0 · Manifest: `manifest-survey.yaml` (frozen 2026-08-04, SHA-256 pinned inputs) · 2048 surrogates · seed 20260805 · runtime 65 min · full log: `run/run.log`

## Data

Five GBT observations of three sky-separated pulsars from the Breakthrough Listen public archive (high-time-resolution products, 349.5 µs):

| observation | pulsar | epoch | rotations | refined fold peak z |
|---|---|---|---|---|
| AGBT17A-0016 | B0329+54 | 2017-02-07 | 251 | — |
| AGBT18A-0059 | B0329+54 | 2018-03-25 | 419 | 99.4 |
| GBT-2020 | B2021+51 | 2020-09-11 | 566 | — |
| AGBT17A-0035 | B0531+21 | 2017-02-08 | 1,770 | 55.3 |
| AGBT17A-0036 | B0531+21 | 2017-02-08 | 8,889 | — |

## Result: NULL — zero follow-up candidates

Dispositions: 4× `no_registered_level1_anomaly`, 1× `rejected_by_negative_controls`.

The scientifically interesting event is **B0531+21-AGBT17A-0036** (the 8,889-rotation Crab scan): the target reached the registered Level-1 software-anomaly thresholds (adjusted p = 0.00195 — the resolution floor of 2048 surrogates — with 336-bit compression gain in the frequency channel, split-half replicated, batch q = 0.0049). It was then **rejected by all seven registered dynamic controls**: the identical frequency-centroid periodicity (lag ≈ 32–38 pulses) fires just as strongly in

- all three **off-pulse** windows (no pulsar signal present),
- both **wrong-period** folds, and
- both **wrong-DM** reductions.

A real on-pulse modulation cannot survive in windows where the pulse is absent. This lag-≈32–38 frequency-channel structure also appears in B2021+51 (score 0.71–0.73, identical in off-pulse controls) and weakly in the other Crab scan. The pattern across sources, windows and folds identifies it as **instrumental band structure / frequency-dependent gain wander of the GBT/BL backend leaking into the frequency-centroid feature**, not pulsar modulation — precisely the failure class the off-pulse control was registered to catch.

## What this run demonstrated

1. The registered control battery caught a Level-1 statistical anomaly that would look impressive in isolation (p at floor, 336-bit gain, replicated across halves) and correctly attributed it to the instrument.
2. The batch-FDR machinery, split-half checks, checkpointed runner and ETA-logged forensic trail all operated on real telescope data end to end.
3. Negative-result policy: this null constrains only the tested modulation families, cadences (0.03–0.7 s rotations, 1–5 min scans), bands (1.0–2.7 GHz), epochs and sensitivity. It is not a statement that no communication networks exist.

## Follow-up actions for a future survey

- Add a registered **frequency-centroid whitening** step (per-channel bandpass detrending) so the inert artifact stops consuming the frequency channel's statistical power.
- Longer observations (10⁴+ rotations) of the slow pulsars; independent-observatory epochs (FAST/Parkes archives) for any future Level-1 event.
- The cross-target shared-protocol check (Level-4 criterion) is moot for this batch: zero observations survived Level 2.
