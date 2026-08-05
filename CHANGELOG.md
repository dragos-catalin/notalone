# Changelog

## 1.0.0 — 2026-08-05

- Deep Vela batch: all 26 public BL Parkes multibeam epochs downloaded (22 new, ~24 GB, 0 failures); 25 analyzed with one held-out recurrence epoch reserved before scanning (58348_19002_B13, pinned in `held-out-epoch.json`) — the last previously unexercised preregistration requirement.
- Result: 25/25 null, 0 Level-1 events, 200/200 controls clean, no cross-epoch lag agreement (min adj. p 0.055 ≈ expectation for 25 draws under the null). 225 registered analyses over 16,741 rotations in 33 minutes. See `artifacts/survey-v1.0/SURVEY_RESULT.md`.
- v1.x campaign closed: 7 frozen experiments, 2 observatories, 4 pulsars + 2 blank fields, 393 registered analyses, 50,440 pulse folds, 2 artifact classes fully attributed, 1 held-out epoch reserved, 0 follow-up candidates.

## 0.9.0 — 2026-08-05

- True off-source validation: two same-session GBT blank-sky scans (HIP20369/HIP20482, no pulsar in beam) folded at the Crab ephemeris with a registered NULL expectation. Both produced the loudest raw anomalies of the project (frequency gains 3,408/2,424 bits, adjusted p at floor) and BOTH were rejected by the full control battery with incompatible split halves — 0 follow-up candidates, artifact attribution conclusively closed (slow gain wander is backend-only, present with nothing on the sky).
- Canonical instrument signature documented: uniform Level-1 firing across all controls + split-half incompatibility. A genuine sky candidate must show the inverse.
- Cumulative after v0.9: 6 frozen experiments, 168 registered analyses, 33,699 rotations/folds, 0 follow-up candidates.

## 0.8.0 — 2026-08-05

- Vela multibeam cross-check: 4 Parkes pointings across 2 nights (B1, B3, B7, B13), 2,678 rotations, 36 analyses in 5m45s. NULL — 4/4 consistent_with_fitted_natural_model, 32/32 controls clean.
- Methods finding, declared in the frozen manifest: Vela is detected in ALL beams of the Parkes multibeam receiver (sidelobe domination; B13 fold z=158), so same-receiver beams are NOT valid off-source controls for the brightest pulsars — true off-source data must come from separate blank-sky scans.
- Cumulative after v0.8: 5 frozen experiments, 2 observatories, 4 pulsars, 148 registered analyses, 15,913 real rotations, 0 follow-up candidates.

## 0.7.0 — 2026-08-05

- First cross-observatory run: two consecutive-night Parkes (Murriyang) epochs of PSR J0835-4510 (Vela) from the Breakthrough Listen multibeam session — the first non-GBT data and the first with live polarization (4 IF filterbanks, 292.6 µs, all four registered channels active).
- Result: NULL — both epochs consistent_with_fitted_natural_model (adj. p 0.52 / 0.49, gains 16/20 bits, no cross-epoch lag agreement), 16/16 controls clean, 2m40s total runtime. See `artifacts/survey-v0.7/SURVEY_RESULT.md`.
- Cumulative after v0.7: 4 frozen experiments, 2 observatories, 4 pulsars, 108 registered analyses, 13,235 real rotations, 2 instrumental artifacts identified and attributed, 0 follow-up candidates.

## 0.6.0 — 2026-08-05

- Registered frequency-centroid whitening (PREREGISTRATION.md Amendment 1): optional per-channel moving-median detrend across rotations before the centroid, controlled by `whiten_frequency` (manifest) / `--whiten-frequency` (CLI). Applies identically to targets and controls.
- Verified on the v0.5 Level-1 artifact (Crab AGBT17A-0036): whiten=False reproduces lag-36 frequency structure (verdict candidate_structured_modulation, gain 336 bits, adjusted p 0.0078); whiten=True removes it entirely (verdict consistent_with_fitted_natural_model, gain 0, adjusted p 1.0).
- Re-ran the three-pulsar survey with whitening enabled (v0.6, 64 min, 5/5 ok): NULL — zero follow-up candidates. Crab-0036 dropped from Level-1-with-artifact to fully unremarkable (p=1, gain 0); B2021+51's lag-32 structure eliminated; Crab-0035 exposed a slower residual gain wander (lag 472 ≈ 16 s, beyond the whitening window) that the off-pulse and wrong-period controls rejected in-flight. See `artifacts/survey-v0.6/SURVEY_RESULT.md`.

## 0.5.0 — 2026-08-05

- Completed the frozen three-pulsar survey (B0329+54 ×2, B2021+51, Crab ×2; 11,895 total rotations; 2048 surrogates; 45 analyses) in 65 minutes. Result: NULL — zero follow-up candidates. See `artifacts/survey-v0.5/SURVEY_RESULT.md`.
- The 8,889-rotation Crab scan reached registered Level-1 thresholds (adjusted p at the 2048-surrogate floor, 336-bit frequency-channel compression gain, split-half replicated) and was then rejected by ALL seven dynamic controls — the same lag≈32–38 frequency structure fires in off-pulse windows, wrong-period folds and wrong-DM reductions across two different pulsars, identifying instrumental band structure, not sky modulation.
- ETA now uses a recency-weighted (EWMA) seconds-per-unit estimate instead of the cumulative mean, fixing systematic underestimation when observation sizes vary widely.
- Off-pulse and wrong-DM controls reuse the target's refined period instead of re-running the refinement grid (≈40% faster per control; scientifically identical fold).
- Registered two-stage period refinement (`refine_period`, `refine_period_fraction` manifest key) — profile-sharpness metric only; wrong-period controls are never refined.

## 0.4.3 — 2026-08-05

- Checkpoint/resume for manifest runs: each completed observation writes `checkpoint.json` keyed on input SHA-256 + surrogate count + case seed + analysis parameters. Re-running the same manifest resumes instantly from checkpoints; stale checkpoints (changed input/seed/params) are detected and recomputed with a WARN.
- Per-observation failure isolation: an observation that throws writes `failure.json` (error type, message, UTC timestamp, parameters) and the run continues; failures are listed in the report summary. The run only aborts if every observation fails.
- Forensic run log: every progress line now carries a UTC timestamp and INFO/WARN/ERROR level, and is mirrored to `run.log` in the output directory — a killed or crashed run leaves a complete trail.
- Run header logs pulsarnet version, seed and manifest SHA-256 for audit.
- Added `__version__` to the package; checkpoint/resume/invalidation covered by a new test (20 total).

## 0.4.2 — 2026-08-05

- Surrogate ensemble now runs across CPU processes (`ProcessPoolExecutor`), auto-sized to core count for jobs where spawn overhead pays back; override with `PULSARNET_WORKERS`. 512 surrogates on a 120k-pulse train: 40.8 s → 5.6 s (7.3× on 32 logical cores).
- Parallel results are bit-identical to serial: each surrogate index derives its own `SeedSequence(seed, spawn_key=(index,))`, so the p-value and compression gain do not depend on worker count or scheduling.
- GPU (CUDA) evaluated and intentionally NOT adopted: per-surrogate work is dominated by FFT autocorrelation on ~1e5-bit arrays plus zlib compression — transfer overhead and a CuPy/zlib port would outweigh gains at current data sizes; CPU parallelism already saturates the pipeline.

## 0.4.1 — 2026-08-05

- Performance pass on the real-data path, measured on the Crab 335 MB file (171k samples × 2464 channels): extraction 110 s → 33 s.
  - Robust channel/time statistics (median/MAD) now estimated on a deterministic ≤16k-row stride subsample instead of full float64 partitions over the whole cube.
  - `refine_period` decimates the folded time series to ≤4M points (block means) while computing candidate phases analytically — the returned period is exact.
  - Dedispersion groups channels by identical integer shift (one contiguous copy per shift) and no longer copies the cube at DM=0.
  - Run-length-permutation surrogate fully vectorized (`np.repeat` over alternating shuffled run pools); an 8.9k-pulse scan with 256 surrogates now takes 0.6 s.
  - `run_manifest` reuses one dedispersed cube per (observation, DM) across the target and all same-DM controls via an internal cache.

## 0.4.0 — 2026-08-04

- Added `pulsarnet.acquisition`: Breakthrough Listen Open Data queries, resumable HTTPS downloads with SHA-256 provenance records, and manifest input fetching (`fetch-bl` command, `run-manifest --fetch`).
- Replaced integer-sample folding with fractional-period phase folding in `extract_pulse_train`. Integer folding drifted ~0.26 samples/rotation on real B0329+54 data and completely smeared the pulse; phase folding locks it (peak z ≈ 5.3).
- HDF5 loader now auto-registers `hdf5plugin` codecs (bitshuffle/LZ4) required by Breakthrough Listen products; `hdf5plugin` is a core dependency.
- Arrival-time residuals are now intensity-weighted phase offsets in seconds of pulse period; metadata records fractional period samples and fold bin count.
- Ran the first frozen real-data pilot: two GBT epochs of PSR B0329+54 (251 + 419 rotations, 2048 surrogates, 16 controls). Result: NULL — no registered Level-1 anomaly; all controls clean. See `artifacts/pilot-v0.4/PILOT_RESULT.md`.

## 0.3.1 — 2026-08-04

- Vectorized the Markov surrogate generator (geometric run-length sampling) and transition-matrix estimation; a 120,000-pulse scan with 256 surrogates now completes in ~25 s.
- Added opt-in zero-DM broadband time-sample RFI mitigation (`time_sample_rfi_mask`, `--time-rfi-z`, manifest key `time_rfi_z_threshold`); flagged samples are median-replaced, flagged fraction is recorded in pulse-train metadata, and extraction refuses observations where more than half the samples are flagged.
- Added nine hardening tests covering surrogate statistics, degenerate Markov chains, NaN/constant channels, broadband-burst flagging and majority-flag rejection (19 tests total).

## 0.3.0 — 2026-08-04

- Added manifest-driven archival experiments with SHA-256 provenance.
- Added off-pulse, wrong-period, wrong-DM and block-permutation negative controls.
- Added split-half recurrence checks and explicit candidate dispositions.
- Added circular block-bootstrap surrogates to preserve local natural texture.
- Added injection-recovery sensitivity analysis.
- Added persistent pulse-train metadata and three automated tests.
- Fixed cyclic frame recovery when a recovered packet wraps across the candidate period boundary.

## 0.2.0 — 2026-08-04

- Added multi-channel anomaly detection across amplitude, polarization, timing and frequency-centroid streams.
- Added mixed Markov/run-length natural surrogate ensemble and four-channel selection correction.
- Added generic repeated-frame consensus recovery and synthetic Manchester/CRC verification.
- Added HDF5, SIGPROC filterbank and optional PSRFITS ingestion adapters.
- Added incoherent dedispersion, robust RFI-channel masking and pulse-feature extraction.
- Added red-team benchmark families, batch FDR correction and a pre-registration draft.
- Added seven automated tests and release artifacts.
