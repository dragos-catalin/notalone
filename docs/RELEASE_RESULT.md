# Pulsar Network Experiment v0.3 — release result

## What was demonstrated

- 10 automated tests passed.
- Red-team benchmark: 12/12 injected cases recovered and 0/12 synthetic natural cases falsely flagged.
- Blind synthetic manifest run: candidate period 207 pulses; block-permutation control period 1427 pulses.
- Candidate period replicated across held-out halves: True.
- Batch FDR q-value: 0.007797.
- Recovered payload: `NETWORK BEACON V03`; CRC valid: True.
- Demonstrative sensitivity: zero-strength control detected 0/2; 1σ and 2σ injections detected 2/2 each.

## Scientific boundary

These are synthetic validation results. They show that the software can recover a hidden repeated protocol and reject registered controls. They do not show that pulsars are engineered, that a network exists, or that extraterrestrial intelligence has been detected.

## Next decisive step

Freeze a real-data target manifest, download public search-mode/single-pulse observations, preserve archive hashes, and run the same target/control pipeline without changing thresholds after viewing results.
