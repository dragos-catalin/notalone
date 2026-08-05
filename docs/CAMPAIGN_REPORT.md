# Pulsar Network Experiment — v1.0 Campaign Report

**Period:** 2026-08-04 → 2026-08-05 · **Software:** pulsarnet v0.3.0 → v1.0.0 · **Question:** do pulsar single-pulse streams contain repeated, protocol-like modulation not explained by fitted natural/statistical models?

**Answer for the data examined: no.** Zero follow-up candidates across seven frozen experiments. Every Level-1 statistical anomaly that arose was traced to the instrument by the preregistered control battery.

---

## 1. Verified campaign totals

All numbers below are read directly from the seven `experiment-report.json` files (synthetic v0.3 dry-run excluded).

| experiment | data | obs | folds | Level-1 | candidates |
|---|---|---|---|---|---|
| pilot-v0.4 | GBT · B0329+54 ×2 epochs | 2 | 670 | 0 | 0 |
| survey-v0.5 | GBT · 3 pulsars, 5 obs | 5 | 11,895 | 1 | 0 |
| survey-v0.6 | same, whitened (Amendment 1) | 5 | 11,895 | 1 | 0 |
| survey-v0.7 | **Parkes** · Vela ×2 epochs | 2 | 1,340 | 0 | 0 |
| survey-v0.8 | Parkes · Vela ×4 beams | 4 | 2,678 | 0 | 0 |
| survey-v0.9 | GBT · blank sky ×2 (off-source) | 2 | 17,786 | 2 | 0 |
| survey-v1.0 | Parkes · Vela ×25 epochs | 25 | 16,741 | 0 | 0 |
| **total** | 2 observatories, 4 pulsars + 2 blank fields | **45** | **63,005** | **4** | **0** |

Per-observation battery: target scan + block-permutation + 3 off-pulse + 2 wrong-period + 2 wrong-DM controls + split-half recurrence, 2048 surrogates each (mixed Markov / run-length-permutation / circular block-bootstrap ensemble), Benjamini-Hochberg FDR across each batch. One recurrence epoch (`58348_19002_B13`) remains reserved and unscanned.

## 2. The four Level-1 events — all resolved as instrumental

1. **v0.5, Crab 8,889-rotation scan** — frequency-centroid periodicity, lag ≈ 36, 336-bit compression gain, split-half replicated. Rejected: identical structure in all 7 dynamic controls and in a different pulsar (B2021+51). Attributed to fast per-channel gain wander of the GBT/BL backend.
2. **v0.6, Crab 1,770-rotation scan** — after Amendment 1 whitening removed the fast component, a *slower* wander (lag ≈ 472, ~16 s) reached Level-1. Rejected live: off-pulse + wrong-period controls fire, split halves incompatible.
3. + 4. **v0.9, both blank-sky scans** — the loudest raw anomalies of the campaign (frequency gains 3,408 / 2,424 bits) with *no source in the beam*, folded at the Crab ephemeris. Rejected: uniform Level-1 firing across every control, split halves incompatible. This closed the attribution chain: the artifact is backend-only.

**Canonical instrument signature** (documented for future evaluation): uniform control firing + split-half incompatibility. A genuine sky-borne candidate must show the inverse — target ≫ controls, split-half compatible, and recurrence in the held-out epoch.

## 3. Methods findings with standalone value

- **Integer-sample folding silently destroys real pulses** when the rotation period is a non-integer number of samples (0.26 samples/rotation drift smeared B0329+54 to invisibility). Fractional-phase folding with analytic phase computation fixed it (profile z: 0.0009 → 99.4).
- **Same-receiver beams are not off-source controls for bright pulsars**: Vela is detected in every beam of the Parkes multibeam receiver via sidelobes (fold z up to 158 in "off" beams). True off-source requires separate blank-sky pointings.
- **Amendment discipline works**: the whitening fix was registered (PREREGISTRATION.md Amendment 1) with an A/B verification on the identified artifact before any re-scan, applied identically to targets and controls.
- **Surrogate determinism under parallelism**: per-index `SeedSequence(seed, spawn_key=(index,))` makes p-values a pure function of the seed, independent of worker count/scheduling — verified bit-identical serial vs 16-way parallel.

## 4. Sensitivity and scope of the null

- Red-team benchmark: 12/12 injected protocol families recovered, 0/12 synthetic natural cases falsely flagged at the operating point.
- Injection-recovery on real extracted trains: 1σ and 2σ injections recovered 2/2 each; zero-strength control 0/2.
- The null therefore constrains: repeated-frame modulation in amplitude/polarization/timing/frequency at 32–4096-rotation periodicities, rotation periods 0.03–0.7 s, radio bands 1.0–3.4 GHz, minute-scale scans, two epochs/nights per target (25 for Vela), at the demonstrated sensitivity.
- It does **not** constrain: other modulation families, other cadences/bands, longer integrations, other pulsars, or any channel the detector does not measure. Per the registered negative-result policy, absence of evidence here is a statement about this test only.

## 5. Reproducibility

Every experiment: frozen YAML manifest with SHA-256-pinned inputs → deterministic seeded run → timestamped `run.log` → per-observation `checkpoint.json` → `experiment-report.json` with dispositions and reasons. Re-running any manifest reproduces the reports bit-for-bit (subject only to identical input files, which the hashes enforce). Full provenance for ~30 GB of public archive data in `data/*provenance*.json`.

## 6. If someone wants to continue

1. **New targets, same instrument**: point a one-file manifest at FAST/CHIME/MeerKAT public search-mode data as it becomes available; the ladder, controls and thresholds need no changes.
2. **The reserved epoch**: `data/guppi_58348_19002_456667_J0835-4510_B13_0001.0001.fil` must remain unscanned until a Level-2 event needs a recurrence test.
3. **Would-be Amendment 2**: a slow-drift whitening extension (window > 33 rotations), to be registered only if the lag-400+ GBT residual appears in new data.
4. **Escalation ladder above Level 2** (unchanged): independent observatory confirmation → raw-data and instrument-team review → predicted recurrence → only then the word "technosignature candidate".
