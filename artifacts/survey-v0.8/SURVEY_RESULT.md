# Vela multibeam cross-check (v0.8) — 4 Parkes pointings, 2 nights

Date: 2026-08-05 · pulsarnet v0.8.0 · Manifest: `manifest-vela-multibeam.yaml` (frozen before scanning) · 2048 surrogates · seed 20260808 · runtime 5m45s · log: `run/run.log`

## Design note (declared in the frozen manifest)

B7 and B13 were acquired as candidate **off-source** beams, but fold-lock verification showed Vela detected in every beam (B7 z = 24.7, B13 z = 158 — Vela is bright enough to dominate the entire multibeam receiver through sidelobes). The manifest therefore declares them additional **on-source pointings**, honestly: no true off-source control is obtainable from this session. A future Level-2 candidate still requires genuine off-source data from another archive.

This is itself a documented methods lesson: for the brightest pulsars, "another beam of the same receiver" is not an off-source control.

## Result: NULL — 4/4 consistent_with_fitted_natural_model

| observation | rotations | verdict | disposition |
|---|---|---|---|
| 58347-B1 | 669 | natural | null |
| 58348-B3 | 671 | natural | null |
| 58347-B7 | 669 | natural | null |
| 58347-B13 | 669 | natural | null |

All 32 registered controls clean. Four independent receiver pointings across two nights agree: no protocol-like structure in 2,678 Vela rotations at 292.6 µs with all four feature channels live.

## Cumulative project state after v0.8

- 5 frozen experiments · 2 observatories · 4 pulsars · 6 sky pointings · 148 registered analyses · 15,913 real rotations
- 2 instrumental artifact classes identified and attributed · **0 follow-up candidates**

## Remaining continuations

1. Deep archives (FAST / CSIRO DAP) for 10⁴–10⁵-rotation sensitivity.
2. True off-source pointings (blank-sky scans from the same sessions, different target names in the BL archive).
3. Amendment 2 (slow-drift whitening) if the GBT lag-400+ residual recurs.
