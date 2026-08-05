from __future__ import annotations

import numpy as np
from .models import PulseTrain


def _red_noise(n: int, rng: np.random.Generator, scale: float = 0.06) -> np.ndarray:
    white = rng.normal(0.0, 1.0, n)
    kernel = np.exp(-np.arange(80) / 18.0)
    kernel /= kernel.sum()
    return scale * np.convolve(white, kernel, mode="same")


def simulate_natural_pulsar(
    n_pulses: int = 16_384,
    period_s: float = 0.71452,
    p_on_to_null: float = 0.018,
    p_null_to_on: float = 0.35,
    seed: int = 7,
    source_id: str = "SYNTH-J0000+0000",
) -> PulseTrain:
    """Generate a natural-looking pulse train with Markov nulling and noise.

    This is not a full magnetosphere simulation. It is a controlled null hypothesis
    for validating detection logic before touching real data.
    """
    if n_pulses < 128:
        raise ValueError("n_pulses must be >= 128")
    rng = np.random.default_rng(seed)

    on = np.ones(n_pulses, dtype=bool)
    state = True
    for i in range(1, n_pulses):
        if state and rng.random() < p_on_to_null:
            state = False
        elif (not state) and rng.random() < p_null_to_on:
            state = True
        on[i] = state

    intrinsic = rng.lognormal(mean=0.0, sigma=0.38, size=n_pulses)
    mode_switch = np.ones(n_pulses)
    # Natural mode changes: long, irregular amplitude regimes.
    for _ in range(max(1, n_pulses // 5000)):
        start = int(rng.integers(0, max(1, n_pulses - 300)))
        length = int(rng.integers(80, 420))
        mode_switch[start : start + length] *= rng.uniform(0.45, 1.45)

    baseline = 0.08 + _red_noise(n_pulses, rng)
    amplitude = baseline + on * intrinsic * mode_switch + rng.normal(0.0, 0.055, n_pulses)
    amplitude = np.clip(amplitude, 0.0, None)

    # Pulse arrival jitter plus slow timing wander.
    jitter = rng.normal(0.0, period_s * 1.8e-4, n_pulses)
    timing_wander = np.cumsum(rng.normal(0.0, period_s * 1.2e-7, n_pulses))
    arrival_residual_s = jitter + timing_wander

    polarization = np.clip(rng.normal(0.22, 0.12, n_pulses) + 0.08 * on, -1.0, 1.0)
    frequency_centroid_hz = 1.4e9 + rng.normal(0.0, 1.8e6, n_pulses)

    # Sparse RFI-like contamination, deliberately not synchronized to pulse phase.
    rfi_count = max(1, n_pulses // 2500)
    rfi_idx = rng.choice(n_pulses, size=rfi_count, replace=False)
    amplitude[rfi_idx] += rng.uniform(3.0, 8.0, rfi_count)
    frequency_centroid_hz[rfi_idx] += rng.uniform(-40e6, 40e6, rfi_count)

    return PulseTrain(
        period_s=period_s,
        amplitude=amplitude,
        arrival_residual_s=arrival_residual_s,
        polarization=polarization,
        frequency_centroid_hz=frequency_centroid_hz,
        source_id=source_id,
    )
