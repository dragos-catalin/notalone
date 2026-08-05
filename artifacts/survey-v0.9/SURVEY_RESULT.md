# Off-source (blank-sky) validation — v0.9

Date: 2026-08-05 · pulsarnet v0.9.0 · Manifest: `manifest-offsource.yaml` (frozen with registered expectation before scanning) · 2048 surrogates · seed 20260809 · runtime 27m30s

## Design

Two HIP star-field scans (HIP20369, HIP20482) from the **same GBT session, night and backend** as the Crab observations (AGBT17A_999_02, MJD 57792) — no pulsar in the beam — folded **as if they were the Crab** (P = 0.0337204 s, DM = 56.77), whitening ON. Registered expectation, declared in the frozen manifest: any structure found is instrument-only.

## Result: exactly as registered — instrument artifacts, fully rejected

| scan | verdict | freq gain | lag | split-half | disposition |
|---|---|---|---|---|---|
| HIP20369 | candidate_structured_modulation | 3,408 bits | 379 | incompatible | rejected_by_negative_controls |
| HIP20482 | candidate_structured_modulation | 2,424 bits | 86 | incompatible | rejected_by_negative_controls |

**0 follow-up candidates.** All 7–8 controls fire at Level-1 in both scans — on blank sky, every "control" is just another window on the same backend, so uniform firing is the expected signature of a pure instrument effect.

## What this completes

1. **Attribution closed.** The slow frequency-channel gain wander appears at full strength with NO astrophysical source in the beam — it is conclusively a GBT/BL backend property, not anything on the sky. Combined with v0.5 (artifact in pulsar data), v0.6 (fast component removed by whitening) and now v0.9 (slow component present on blank sky), the artifact chain is fully documented.
2. **The disposition logic is validated end-to-end on true negatives.** Blank sky produced the *loudest* raw anomalies of the entire project (3,408-bit gain — 10× the Crab's) and the registered gates rejected 100% of them, without any manual intervention.
3. **Lesson for the preregistration**: incompatible split halves + uniform control firing is the canonical instrument signature; a real sky-borne candidate must show the inverse pattern (target ≫ controls, split-half compatible).

## Cumulative after v0.9

6 frozen experiments · 2 observatories · 4 pulsars + 2 blank-sky fields · 168 registered analyses · 33,699 real rotations/folds · 3 artifact validations · **0 follow-up candidates**

## Remaining depth milestone

FAST/CSIRO deep archives (10⁴–10⁵ rotations of slow pulsars) remain the path to preregistered sensitivity; the detection instrument is now fully validated at both ends (injected positives in the red-team benchmark, real-world true negatives here).
