# Whitened three-pulsar survey (v0.6) — B0329+54, B2021+51, B0531+21

Date: 2026-08-05 · pulsarnet v0.6.0 · Manifest: `manifest-survey-whitened.yaml` (frozen with Registered Amendment 1 before the run) · 2048 surrogates · seed 20260806 · runtime 64 min · log: `run/run.log`

## Result: NULL — zero follow-up candidates (again, now with a cleaner detector)

| observation | rotations | v0.5 verdict | v0.6 verdict (whitened) | disposition |
|---|---|---|---|---|
| B0329+54-0016 | 251 | interesting_but_inconclusive | **consistent_with_natural_model** | null |
| B0329+54-0059 | 419 | interesting_but_inconclusive | interesting_but_inconclusive (p=0.059) | null |
| B2021+51-2020 | 566 | interesting_but_inconclusive (freq lag 32!) | **consistent_with_natural_model** | null |
| Crab-0035 | 1,770 | interesting_but_inconclusive | candidate → **rejected_by_negative_controls** | null |
| Crab-0036 | 8,889 | candidate → rejected by 7 controls | **consistent_with_natural_model** (p=1, gain 0) | null |

## What whitening accomplished

1. **The v0.5 lag-32/36 artifact is eliminated at the source.** Crab-0036, which previously hit Level-1 with 336-bit gain, is now maximally unremarkable (adjusted p = 1.0, gain 0, no channel below p = 1). B2021+51's lag-32 frequency structure (score 0.71) is gone (best remaining: lag 176, score 0.13, p = 1).
2. **The detector still catches residual instrument behavior — and rejects it correctly.** Crab-0035 (the shorter, noisier scan) now shows a *different*, longer-timescale frequency structure at lag 472 (≈16 s, slower than the 33-rotation whitening window). It reached Level-1 (gain 160), and the registered controls killed it immediately: the same structure fires in two off-pulse windows and a wrong-period fold, and its split halves are incompatible. Disposition: `rejected_by_negative_controls`. The remaining slow gain wander (>10 s) is below the whitening cutoff — a known, documented residual, still fully covered by the control battery.
3. B0329+54-0059 retains its mild amplitude quasi-periodicity at lag 34 (p = 0.015 single-channel, p = 0.059 adjusted) — consistent with this pulsar's known sub-pulse drifting/mode-switching; far below Level-1, not batch-significant.

## Scientific position after v0.6

- Two frozen surveys, 90 registered analyses, 11,895 real rotations, three sky-separated pulsars, two epochs each for two of them: **no protocol-like modulation survives the registered gates.**
- The pipeline has now demonstrated, on real data, both failure-mode classes it was designed for: a fast instrumental artifact (caught by whitening after control-based attribution) and a slow one (still caught live by off-pulse controls).
- Null-result scope: constrains only the tested modulation families, cadences 0.03–0.7 s, bands 1.0–2.7 GHz, these epochs and this sensitivity.

## Next decisive step (unchanged from docs/NEXT_REAL_SCAN.md)

Longer observations (10⁴–10⁵ rotations) and independent-observatory epochs (FAST / Parkes / CHIME archives) for the slow pulsars, and a registered slow-drift extension of the whitening window if the lag-400+ residual persists in future GBT data.
