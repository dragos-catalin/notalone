# notalone — Pulsar Network Experiment v1.0

A hypothesis-neutral, falsifiable software experiment for detecting protocol-like modulation in pulsar single-pulse data.

*Are we alone? This project doesn't answer that. It builds the discipline needed to trust any answer: preregistered thresholds, negative controls that catch the instrument lying, and honest, bounded nulls.*

**Quick links:** [Campaign report](docs/CAMPAIGN_REPORT.md) · [Preregistration](PREREGISTRATION.md) · [Methods paper draft](paper/pulsarnet-methods-note.tex) · [Changelog](CHANGELOG.md)

## v1.0 campaign result (2026-08-05)

Seven frozen experiments on public Breakthrough Listen data: **2 observatories** (GBT, Parkes), **4 pulsars** (B0329+54, B2021+51, B0531+21/Crab, J0835-4510/Vela) **+ 2 blank-sky fields**, **45 observations**, **63,005 pulse folds**, **~400 registered analyses**.

**Result: NULL — zero follow-up candidates.** All four Level-1 statistical anomalies that arose were attributed to instrumental gain wander by the preregistered control battery (one fixed by registered whitening, one caught live, two confirmed on blank sky with nothing in the beam). One recurrence epoch remains reserved and unscanned. Full narrative: `docs/CAMPAIGN_REPORT.md`; per-experiment reports in `artifacts/*/SURVEY_RESULT.md`.

## Scientific boundary

This project does **not** assume that pulsars form an artificial network. It tests a narrower question:

> Can observed pulse features be explained by fitted natural/statistical models, or do they contain repeated, self-consistent structure that warrants independent follow-up?

A positive software result is an anomaly, not evidence of extraterrestrial intelligence by itself. A credible technosignature would require raw-data inspection, instrument and RFI exclusion, independent observatories, recurrence, and expert astrophysical review.

## Reproduce the campaign

```bash
python -m venv .venv && .venv/Scripts/activate   # or source .venv/bin/activate
pip install setuptools wheel
pip install -e ".[dev]" --no-build-isolation
pytest tests -q                                   # 20 tests

# Re-download any experiment's pinned inputs and run it, e.g.:
pulsarnet run-manifest artifacts/survey-v1.0/manifest-vela-deep.yaml \
  --fetch --data-dir data --output artifacts/survey-v1.0/rerun
```

Raw observation files (~34 GB) are not in the repo; every manifest pins the
public Breakthrough Listen URL and SHA-256 of each input, and
`data/*provenance*.json` records what was originally analyzed. The held-out
recurrence epoch (`guppi_58348_19002_456667_J0835-4510_B13_0001.0001.fil`)
must remain unscanned unless validating a Level-2 candidate.

## What changed in v0.3

- Preregistered manifest runner for target observations and negative controls.
- SHA-256 provenance for every manifest and input file.
- Automatic off-pulse, wrong-period, wrong-DM and block-permutation controls.
- Split-half recurrence checks before a candidate can advance.
- Stronger mixed null ensemble: Markov, run-length permutation and circular block bootstrap.
- Injection-recovery sensitivity curves on any extracted pulse train.
- Batch FDR gating and explicit candidate dispositions.
- Pulse-train metadata retained through NPZ round trips.

The v0.2 multi-channel detector, frame recovery, CRC validation and HDF5/SIGPROC/PSRFITS ingestion remain available.

## What changed in v0.5–v0.6

- Frozen three-pulsar survey (B0329+54 ×2, B2021+51, Crab ×2; 90 analyses; 11,895 real rotations) run twice: v0.5 identified an instrumental frequency-channel artifact via the registered control battery; v0.6 added preregistered frequency-centroid whitening (Amendment 1) and re-ran clean. Both surveys: NULL — zero follow-up candidates. Full reports in `artifacts/survey-v0.5/` and `artifacts/survey-v0.6/`.
- Process-parallel surrogate ensemble (deterministic per-index seeding), checkpoint/resume, per-observation failure isolation, timestamped `run.log` forensics, EWMA ETA progress in the terminal.

## What changed in v0.4

- Real-data acquisition: `pulsarnet fetch-bl B0329+54 --pattern .8.0001.h5` queries and downloads public Breakthrough Listen files with pinned SHA-256 provenance; `run-manifest --fetch` downloads url-declared manifest inputs.
- Fractional-period phase folding: the extractor now folds at the exact floating-point period, fixing pulse smearing on real observations where the rotation is not an integer number of samples.
- First frozen real-data pilot completed on two GBT epochs of PSR B0329+54: null result, all 16 registered controls clean (`artifacts/pilot-v0.4/PILOT_RESULT.md`).

## What changed in v0.3.1

- Vectorized Markov surrogates: long-observation scans (100k+ rotations) are now practical at pilot surrogate counts.
- Optional zero-DM broadband RFI mitigation via `--time-rfi-z` on `extract` or `time_rfi_z_threshold` in a manifest entry. Off by default; the flagged fraction is preserved in metadata for audit.

## Install

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e . --no-build-isolation
```

PSRFITS support:

```bash
pip install -e '.[psrfits]' --no-build-isolation
```

## Synthetic detection demo

```bash
pulsarnet demo --output artifacts/demo-v0.2 --surrogates 128
```

## Recover a repeated frame

First read `strongest_lag` and `best_channel` from the detection report, then:

```bash
pulsarnet recover artifacts/demo-v0.2/modulated.npz \
  --channel polarization \
  --frame-period 371 \
  --output artifacts/demo-v0.2/recovery.json
```

The generic recovery stage returns:

- aligned start index;
- number of repeats used;
- consensus bit block;
- confidence per bit;
- stable-position fraction;
- optional synthetic payload and CRC result.

## Ingest a real observation

HDF5:

```bash
pulsarnet extract observation.h5 \
  --format hdf5 \
  --period 0.71452 \
  --dm 15.35 \
  --output artifacts/JXXXX+XXXX.npz
```

SIGPROC filterbank:

```bash
pulsarnet extract observation.fil \
  --format filterbank \
  --period 0.71452 \
  --dm 15.35 \
  --output artifacts/JXXXX+XXXX.npz
```

PSRFITS:

```bash
pulsarnet extract observation.fits \
  --format psrfits \
  --period 0.71452 \
  --dm 15.35 \
  --output artifacts/JXXXX+XXXX.npz
```

The extractor is an auditable baseline, not a replacement for observatory-calibrated PSRCHIVE/PRESTO processing. Precision candidate work should preserve raw/search-mode data and compare both pipelines.

## Red-team benchmark

```bash
pulsarnet benchmark \
  --cases 24 \
  --pulses 10000 \
  --surrogates 48 \
  --output artifacts/benchmark-v0.2.json
```

The included seeded run recovered 12/12 synthetic injections with 0/12 false positives at the benchmark operating point. This small synthetic result validates the pipeline mechanics only; it is not an estimated real-sky sensitivity or false-alarm rate.

## Batch archival scan

```bash
pulsarnet scan-batch artifacts/pulse-trains \
  --pattern '*.npz' \
  --surrogates 1024 \
  --output artifacts/batch-report.json
```

For a serious archival scan, freeze targets, metrics, thresholds and exclusion rules before viewing results. See `PREREGISTRATION.md`.

## Current detector logic

1. Derive robust binary streams from four pulse-level feature channels.
2. Search each channel for repeated frame periods.
3. Preselect the strongest channel.
4. Compare it against a mixed natural surrogate ensemble.
5. Correct for selecting among four channels.
6. Measure compressibility and cross-channel lag support.
7. Recover a consensus frame only after a periodic candidate exists.

## Prior work

The broad idea of artificial pulsar modulation is not new. Relevant starting points include:

- Chennamangalam et al., *Jumping the energetics queue: Modulation of pulsar signals by extraterrestrial civilizations*.
- Vidal, *Pulsar Positioning System: A quest for evidence of extraterrestrial engineering*.
- Hippke, *Interstellar communication network. I. Overview and assumptions*.

The implementation contribution here is a reusable, falsifiable, multi-channel detector and protocol-recovery pipeline rather than the original pulsar-modulation concept.

## Preregistered target-and-controls run

```bash
pulsarnet run-manifest examples/archive-manifest.example.yaml \
  --output artifacts/first-archival-run
```

The manifest runner writes immutable input hashes, extracted pulse trains, reports for every control, split-half results, batch q-values and one final disposition per observation. A target is rejected if a negative control is at least as anomalous.

## Injection-recovery sensitivity

```bash
pulsarnet sensitivity artifacts/JXXXX+XXXX.npz \
  --channel amplitude \
  --strengths 0,0.5,1,1.5,2 \
  --trials 8 \
  --surrogates 128 \
  --output artifacts/JXXXX+XXXX-sensitivity.json
```

The zero-strength point is the empirical false-alarm control. Sensitivity results apply only to the selected observation, channel, protocol family and preprocessing configuration.
