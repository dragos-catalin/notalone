# Next milestone: first frozen archival scan

> **STATUS (2026-08-05): COMPLETED and exceeded.** The pilot ran as v0.4; the
> full campaign (v0.5–v1.0, seven frozen experiments, 63,005 folds, two
> observatories, zero candidates) is summarized in `docs/CAMPAIGN_REPORT.md`.
> This document is retained for the original design rationale. Future-work
> items live in the campaign report, section 6.

The software experiment is ready for a real-data pilot. The next run must not tune thresholds after looking at candidate results.

## Pilot design

- Select 5–10 bright, well-characterized pulsars before downloading or inspecting pulse-level anomalies.
- Prefer search-mode data with individual rotations, broad frequency coverage and polarization.
- Include repeated observations and, where available, independent observatories.
- Use at least 4,000 surrogate realizations for a 10-target batch if a single candidate must be able to reach batch q < 0.01 under the current four-channel correction.
- Run the target, off-pulse, wrong-period, wrong-DM and block-permutation controls from the frozen manifest.
- Keep a held-out observation for recurrence testing.

## Escalation rule

A software anomaly is not announced as a technosignature. Escalation requires raw-data inspection, observatory/instrument review, off-source exclusion, predicted recurrence and independent telescope confirmation.
