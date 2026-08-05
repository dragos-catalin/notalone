# Deep Vela batch (v1.0) — 25 Parkes epochs, 16,741 rotations

Date: 2026-08-05 · pulsarnet v1.0.0 · Manifest: `manifest-vela-deep.yaml` (frozen with held-out recurrence epoch) · 2048 surrogates · seed 20260810 · runtime 33m · 225 registered analyses · log: `run/run.log`

## Design

Every public BL Parkes multibeam epoch of PSR J0835-4510 (26 total, 2018-08-17/18, 292.6 µs, full-Stokes) except **one held-out recurrence epoch reserved before scanning** (`58348_19002_B13`, recorded in `held-out-epoch.json`) — fulfilling the last preregistration requirement not yet exercised. Whitening ON, thresholds unchanged, all inputs SHA-256-pinned.

## Result: NULL — the cleanest large batch possible

- **25/25 `no_registered_level1_anomaly`** — zero Level-1 events, zero candidates.
- Minimum adjusted p = 0.055 (VELA-58348-B2) — precisely the expected minimum among 25 independent draws under the null hypothesis; its split halves are incompatible and its q-value is 0.65.
- **No cross-epoch structure**: 25 best-lags are scattered (only one lag/channel pair repeats even twice, at chance level). Independent epochs disagree about everything — the signature of noise, and the exact opposite of the Level-4 shared-protocol criterion.
- 200/200 controls clean. 0 failures, checkpoint files written for all 25 observations.

## The held-out epoch policy is now active

`58348_19002_B13` remains unscanned. Should any future Vela analysis produce a Level-2 event, its predicted structure must replicate in this epoch before escalation — the file and its SHA-256 are pinned but the data has never been examined by the detector.

## Final cumulative scorecard (7 frozen experiments)

| | |
|---|---|
| Observatories | 2 (GBT, Parkes) |
| Pulsars | 4 (+2 blank-sky fields) |
| Sky pointings/epochs | 32 |
| Registered analyses | 393 |
| Real rotations/folds scanned | 50,440 |
| Instrumental artifact classes attributed | 2 (both ends: preprocessing fix + live control rejection + blank-sky confirmation) |
| Held-out recurrence epochs reserved | 1 |
| **Follow-up candidates** | **0** |

## Scientific conclusion of the v1.x campaign

Across two independent observatories, four pulsars, 32 pointings and >50,000 pulse folds, **no protocol-like modulation survives the preregistered detection ladder**. The registered negative-result policy defines the scope precisely: this constrains the tested modulation families (repeated frames in amplitude/polarization/timing/frequency at 32–4096-rotation periodicities), cadences 0.03–0.7 s, bands 1.0–3.4 GHz, minute-scale scans, at the sensitivity established by injection-recovery. It says nothing beyond that scope — and the pipeline that produced it can now be pointed at any new archive with a one-file manifest.
