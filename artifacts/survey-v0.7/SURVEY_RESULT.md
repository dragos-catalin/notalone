# Cross-observatory survey (v0.7) — PSR J0835-4510 (Vela) at Parkes

Date: 2026-08-05 · pulsarnet v0.7.0 · Manifest: `manifest-vela-parkes.yaml` (frozen before scanning) · 2048 surrogates · seed 20260807 · runtime 2m 40s · log: `run/run.log`

## Why this run matters

First data from a **second, independent observatory**: Parkes 64 m (Murriyang, Australia), Breakthrough Listen multibeam session, two consecutive-night epochs (2018-08-17/18) of the Vela pulsar. Also the first observations with **live polarization** (4 IF products, 292.6 µs, 305 samples/rotation) — all four registered feature channels carried real data for the first time.

## Result: NULL — cleanest batch yet

| observation | rotations | verdict | adj. p | gain | disposition |
|---|---|---|---|---|---|
| VELA-PKS-58347-B1 | 669 | consistent_with_natural_model | 0.52 | 16 | null |
| VELA-PKS-58348-B3 | 671 | consistent_with_natural_model | 0.49 | 20 | null |

- No channel in either epoch shows structure above noise (all lag scores ≤ 0.14; the two epochs don't even agree on a best lag: 135 vs 148 in different channels — exactly what noise looks like).
- All 16 registered controls clean; whitening (Amendment 1) active throughout.
- Fold quality verified: refined P = 0.0894008 s (catalog 0.0893), profile peak z = 13.1.

## Cumulative project state after v0.7

| | |
|---|---|
| Frozen experiments run | 4 (pilot, v0.5, v0.6, v0.7) |
| Observatories | 2 (GBT, Parkes) — independent instruments, hemispheres, backends |
| Pulsars | 4 (B0329+54, B2021+51, B0531+21, J0835-4510) |
| Registered analyses | 108 |
| Real rotations scanned | 13,235 |
| Instrumental artifacts identified & attributed | 2 (fast bandpass wander → fixed by Amendment 1; slow gain wander → caught live by controls) |
| Follow-up candidates | **0** |

## Interpretation

Across two telescopes, four pulsars, five epochs and both hemispheres, no protocol-like modulation survives the preregistered gates. The registered negative-result policy applies: this constrains the tested modulation families at 0.03–0.7 s cadences, 1.0–3.4 GHz, minutes-long scans, at current sensitivity — nothing more, nothing less. The instrument-artifact discoveries demonstrate the control battery works as designed on real data.

## Natural continuations

1. **Depth**: 10⁴–10⁵-rotation datasets (FAST open archives; CSIRO DAP Parkes ultra-wideband) for the sensitivity the preregistration prefers.
2. **A held-out recurrence epoch** per target, reserved before scanning, for any future Level-2 event.
3. **Slow-drift whitening extension** (would-be Amendment 2) if the lag-400+ GBT residual reappears.
