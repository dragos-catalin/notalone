from __future__ import annotations

import math
import os
import zlib
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from scipy.signal import find_peaks, fftconvolve
from .models import PulseTrain, DetectionReport


def robust_binary(values: np.ndarray) -> np.ndarray:
    """Convert a one-dimensional channel to robust two-cluster bits."""
    x = np.asarray(values, dtype=float)
    finite = np.isfinite(x)
    if not np.all(finite):
        replacement = float(np.nanmedian(x)) if np.any(finite) else 0.0
        x = np.where(finite, x, replacement)
    q20, q80 = np.quantile(x, [0.20, 0.80])
    low, high = float(q20), float(q80)
    if abs(high - low) < 1e-15:
        return np.zeros(len(x), dtype=np.uint8)
    for _ in range(40):
        threshold = (low + high) / 2.0
        left = x[x <= threshold]
        right = x[x > threshold]
        if left.size == 0 or right.size == 0:
            break
        new_low, new_high = float(left.mean()), float(right.mean())
        if abs(new_low - low) + abs(new_high - high) < 1e-10:
            break
        low, high = new_low, new_high
    return (x > (low + high) / 2.0).astype(np.uint8)


def transition_matrix(bits: np.ndarray) -> np.ndarray:
    counts = np.ones((2, 2), dtype=float)
    if len(bits) >= 2:
        pairs = bits[:-1].astype(np.int64) * 2 + bits[1:].astype(np.int64)
        counts += np.bincount(pairs, minlength=4).reshape(2, 2)
    return counts / counts.sum(axis=1, keepdims=True)


def _normalized_autocorrelation(bits: np.ndarray, max_lag: int) -> np.ndarray:
    x = bits.astype(float)
    x -= x.mean()
    denom = float(np.dot(x, x))
    if denom <= 1e-12:
        return np.zeros(max_lag + 1)
    full = fftconvolve(x, x[::-1], mode="full")
    ac = full[len(x) - 1 : len(x) + max_lag]
    overlap = np.arange(len(x), len(x) - max_lag - 1, -1)
    return (ac / denom) * (len(x) / overlap)


def _markov_surrogate(n: int, tm: np.ndarray, rng: np.random.Generator, start: int) -> np.ndarray:
    """Vectorized two-state Markov surrogate via alternating geometric run lengths.

    A binary Markov chain is exactly a sequence of alternating runs whose lengths
    are geometric with the state's self-transition probability. Sampling runs in
    bulk avoids a Python-level per-pulse loop.
    """
    if n <= 0:
        return np.empty(0, dtype=np.uint8)
    state = int(start)
    # Switch probability out of each state; clamp to keep geometric sampling finite.
    p_switch = np.clip([1.0 - tm[0, 0], 1.0 - tm[1, 1]], 1e-9, 1.0)
    pieces: list[np.ndarray] = []
    total = 0
    while total < n:
        remaining = n - total
        # Expected runs needed, with margin; at least 16 per draw.
        expect = max(16, int(remaining * max(p_switch) * 1.5) + 16)
        states = (np.arange(expect) + state) % 2
        lengths = rng.geometric(p_switch[states])
        pieces.append(np.repeat(states.astype(np.uint8), lengths))
        total += int(lengths.sum())
        state = int((states[-1] + 1) % 2)
    return np.concatenate(pieces)[:n]


def _run_lengths(bits: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    changes = np.flatnonzero(np.diff(bits) != 0) + 1
    bounds = np.concatenate([[0], changes, [len(bits)]])
    lengths = np.diff(bounds)
    states = bits[bounds[:-1]]
    return states.astype(np.uint8), lengths.astype(int)


def _run_permutation_surrogate(bits: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    states, lengths = _run_lengths(bits)
    on_lengths = lengths[states == 1].copy()
    off_lengths = lengths[states == 0].copy()
    rng.shuffle(on_lengths)
    rng.shuffle(off_lengths)
    n = len(bits)
    start = int(states[0])
    # Upper bound on runs needed: alternate the two shuffled length pools
    # (cycled) until the cumulative length covers n, all without Python loops.
    n_on, n_off = len(on_lengths), len(off_lengths)
    est_runs = len(lengths) + 4
    while True:
        run_states = ((np.arange(est_runs) + start) % 2).astype(np.uint8)
        run_lengths = np.empty(est_runs, dtype=np.int64)
        on_slots = run_states == 1
        off_slots = ~on_slots
        counts_on = int(on_slots.sum())
        counts_off = est_runs - counts_on
        run_lengths[on_slots] = (
            on_lengths[np.arange(counts_on) % n_on] if n_on else 1
        )
        run_lengths[off_slots] = (
            off_lengths[np.arange(counts_off) % n_off] if n_off else 1
        )
        if int(run_lengths.sum()) >= n:
            break
        est_runs *= 2
    return np.repeat(run_states, run_lengths)[:n]




def _block_bootstrap_surrogate(
    bits: np.ndarray,
    rng: np.random.Generator,
    mean_block: int | None = None,
) -> np.ndarray:
    """Circular fixed-block bootstrap preserving local pulsar texture.

    The vectorized implementation samples contiguous circular blocks. It retains
    local mode persistence and short quasi-periodic patterns while breaking
    long-range frame alignment.
    """
    n = len(bits)
    if n == 0:
        return bits.copy()
    block_size = int(mean_block or max(16, min(256, round(math.sqrt(n)))))
    block_count = int(math.ceil(n / block_size))
    starts = rng.integers(0, n, size=block_count)
    indices = (starts[:, None] + np.arange(block_size)[None, :]) % n
    return bits[indices.reshape(-1)[:n]].astype(np.uint8, copy=False)

def _compression_bits(bits: np.ndarray) -> int:
    symbols = bits.astype(np.uint8).tobytes()
    return len(zlib.compress(symbols, level=9)) * 8


def _prime_gap_enrichment(bits: np.ndarray) -> float:
    null_idx = np.flatnonzero(bits == 0)
    if null_idx.size < 4:
        return 0.0
    gaps = np.diff(null_idx)
    max_gap = int(gaps.max(initial=2))
    sieve = np.ones(max_gap + 1, dtype=bool)
    sieve[:2] = False
    for p in range(2, int(math.sqrt(max_gap)) + 1):
        if sieve[p]:
            sieve[p * p :: p] = False
    observed = float(np.mean(sieve[gaps]))
    expected = float(np.mean(sieve[2:])) if max_gap >= 2 else 0.0
    return observed / expected if expected > 0 else 0.0


def _candidate_lags(bits: np.ndarray, min_lag: int = 32, max_lag: int = 4096) -> tuple[list[int], float, int | None]:
    max_lag = min(max_lag, len(bits) // 3)
    if max_lag <= min_lag:
        return [], 0.0, None
    ac = _normalized_autocorrelation(bits, max_lag)
    region = ac[min_lag:]
    med = float(np.median(region))
    mad = float(np.median(np.abs(region - med))) + 1e-9
    peaks, _props = find_peaks(region, prominence=max(0.02, 5.0 * mad), distance=8)
    if peaks.size == 0:
        idx = int(np.argmax(region)) + min_lag
        return [idx], float(ac[idx]), idx
    lags = (peaks + min_lag).astype(int)
    scores = ac[lags]
    order = np.argsort(scores)[::-1]
    ranked = [int(lags[i]) for i in order[:8]]
    best = ranked[0]
    return ranked, float(ac[best]), best


def _observed_channel(bits: np.ndarray) -> dict:
    candidates, best_score, best_lag = _candidate_lags(bits)
    compressed = _compression_bits(bits)
    # One byte per bit is intentional; lower ratios indicate repeated symbolic structure.
    compression_ratio = compressed / max(8.0, len(bits) * 8.0)
    return {
        "strongest_lag": best_lag,
        "strongest_lag_score": best_score,
        "candidate_frame_lengths": candidates,
        "observed_compression_bits": compressed,
        "compression_ratio": compression_ratio,
        "transition_matrix": transition_matrix(bits).tolist(),
        "one_fraction": float(np.mean(bits == 1)),
    }


def _surrogate_batch(
    bits: np.ndarray,
    tm: np.ndarray,
    indices: list[int],
    seed: int,
) -> tuple[list[float], list[int]]:
    """Score one batch of surrogates. Deterministic per surrogate index.

    Each surrogate gets its own child seed derived from (seed, index) so results
    are identical no matter how indices are distributed across workers.
    """
    scores: list[float] = []
    compression: list[int] = []
    for index in indices:
        rng = np.random.default_rng(np.random.SeedSequence(entropy=seed, spawn_key=(index,)))
        family = index % 3
        if family == 0:
            surrogate = _markov_surrogate(len(bits), tm, rng, int(bits[0]))
        elif family == 1:
            surrogate = _run_permutation_surrogate(bits, rng)
        else:
            surrogate = _block_bootstrap_surrogate(bits, rng)
        _, score, _ = _candidate_lags(surrogate)
        scores.append(score)
        compression.append(_compression_bits(surrogate))
    return scores, compression


def _channel_scan(
    bits: np.ndarray,
    surrogate_count: int,
    rng: np.random.Generator,
    observed: dict | None = None,
    *,
    seed: int | None = None,
    workers: int | None = None,
) -> dict:
    tm = transition_matrix(bits)
    observed = dict(observed or _observed_channel(bits))
    best_score = float(observed["strongest_lag_score"])
    if seed is None:
        seed = int(rng.integers(0, 2**31 - 1))
    if workers is None:
        workers = _default_workers(surrogate_count, len(bits))

    all_indices = list(range(surrogate_count))
    if workers <= 1:
        surrogate_scores, surrogate_compression = _surrogate_batch(bits, tm, all_indices, seed)
    else:
        chunks = [all_indices[i::workers] for i in range(workers)]
        surrogate_scores, surrogate_compression = [], []
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for scores, compression in pool.map(
                _surrogate_batch, [bits] * workers, [tm] * workers, chunks, [seed] * workers
            ):
                surrogate_scores.extend(scores)
                surrogate_compression.extend(compression)

    scores = np.asarray(surrogate_scores)
    p_value = float((1 + np.sum(scores >= best_score)) / (surrogate_count + 1))
    compression_gain = float(np.median(surrogate_compression) - int(observed["observed_compression_bits"]))
    observed.update({
        "surrogate_p_value": p_value,
        "compression_gain_bits": compression_gain,
        "transition_matrix": tm.tolist(),
    })
    return observed


def _default_workers(surrogate_count: int, n_bits: int) -> int:
    """Choose a worker count where process spawn overhead is actually paid back."""
    env = os.environ.get("PULSARNET_WORKERS")
    if env is not None:
        return max(1, int(env))
    # Windows spawn + pickling costs ~1-2 s total; short trains scan thousands
    # of surrogates per second serially, so only parallelize real bit volume.
    if surrogate_count * max(n_bits, 1) < 4_000_000:
        return 1
    return min(max(os.cpu_count() or 1, 1), 16)

def _channel_bitstreams(train: PulseTrain) -> dict[str, np.ndarray]:
    return {
        "amplitude": robust_binary(train.amplitude),
        "polarization": robust_binary(train.polarization),
        "timing": robust_binary(train.arrival_residual_s),
        "frequency": robust_binary(train.frequency_centroid_hz),
    }


def scan_pulse_train(
    train: PulseTrain,
    surrogate_count: int = 128,
    seed: int = 1234,
) -> DetectionReport:
    """Score protocol-like structure across amplitude, polarisation, timing and frequency."""
    if train.n_pulses < 128:
        raise ValueError("at least 128 pulses are required")
    rng = np.random.default_rng(seed)
    channels = _channel_bitstreams(train)
    observed = {name: _observed_channel(bits) for name, bits in channels.items()}
    # Pre-select one feature channel, then apply a four-channel look-elsewhere correction.
    # This is much faster than running a full surrogate ensemble four times while
    # remaining conservative about the data-driven channel selection.
    def pre_score(name: str) -> float:
        metric = observed[name]
        return float(metric["strongest_lag_score"]) + 0.35 * (1.0 - float(metric["compression_ratio"]))

    best_channel = max(observed, key=pre_score)
    best = _channel_scan(
        channels[best_channel],
        surrogate_count=surrogate_count,
        rng=rng,
        observed=observed[best_channel],
        seed=seed,
    )
    metrics = observed
    metrics[best_channel] = best
    for name, metric in metrics.items():
        metric.setdefault("surrogate_p_value", 1.0)
        metric.setdefault("compression_gain_bits", 0.0)
    adjusted_p = min(1.0, float(best["surrogate_p_value"]) * len(metrics))
    best_lag = best["strongest_lag"]

    support = 1
    if best_lag is not None:
        tolerance = max(2, int(best_lag) // 50)
        support = sum(
            1
            for metric in metrics.values()
            if metric["strongest_lag"] is not None
            and abs(int(metric["strongest_lag"]) - int(best_lag)) <= tolerance
            and float(metric["strongest_lag_score"]) >= 0.08
        )

    amplitude_bits = channels["amplitude"]
    prime_enrichment = _prime_gap_enrichment(amplitude_bits)
    compression_gain = float(best["compression_gain_bits"])
    notes: list[str] = []
    if adjusted_p < 0.05:
        notes.append(f"{best_channel} structure exceeds the mixed Markov/run-length/block-bootstrap surrogate ensemble.")
    if compression_gain > 128:
        notes.append(f"The {best_channel} bitstream is substantially more compressible than surrogates.")
    if support >= 2:
        notes.append(f"A compatible frame lag is supported by {support} independent feature channels.")
    if prime_enrichment > 1.8:
        notes.append("Amplitude null gaps are enriched at prime intervals; verify against selection effects.")

    if adjusted_p < 0.05 and compression_gain > 128:
        verdict = "candidate_structured_modulation"
    elif adjusted_p < 0.10 or compression_gain > 96 or support >= 2:
        verdict = "interesting_but_inconclusive"
    else:
        verdict = "consistent_with_fitted_natural_model"

    return DetectionReport(
        source_id=train.source_id,
        n_pulses=train.n_pulses,
        null_fraction=float(np.mean(amplitude_bits == 0)),
        transition_matrix=metrics["amplitude"]["transition_matrix"],
        strongest_lag=best_lag,
        strongest_lag_score=float(best["strongest_lag_score"]),
        surrogate_p_value=float(best["surrogate_p_value"]),
        adjusted_p_value=adjusted_p,
        compression_gain_bits=compression_gain,
        prime_gap_enrichment=float(prime_enrichment),
        candidate_frame_lengths=list(best["candidate_frame_lengths"]),
        verdict=verdict,
        notes=notes,
        best_channel=best_channel,
        cross_channel_support=support,
        channel_metrics=metrics,
    )


def cross_node_correlation(a: PulseTrain, b: PulseTrain, max_lag: int = 4096) -> dict[str, float | int | str]:
    """Find the strongest shared feature-channel structure between two pulse streams."""
    best: dict[str, float | int | str] = {"lag_pulses": 0, "normalized_correlation": -1.0, "channel": "amplitude"}
    a_channels = _channel_bitstreams(a)
    b_channels = _channel_bitstreams(b)
    for channel in a_channels:
        x = a_channels[channel].astype(float)
        y = b_channels[channel].astype(float)
        n = min(len(x), len(y))
        x, y = x[:n], y[:n]
        x -= x.mean()
        y -= y.mean()
        corr = fftconvolve(x, y[::-1], mode="full")
        lags = np.arange(-n + 1, n)
        mask = np.abs(lags) <= min(max_lag, n - 1)
        corr = corr[mask]
        lags = lags[mask]
        denom = np.linalg.norm(x) * np.linalg.norm(y)
        corr = corr / denom if denom > 0 else np.zeros_like(corr)
        idx = int(np.argmax(corr))
        score = float(corr[idx])
        if score > float(best["normalized_correlation"]):
            best = {"lag_pulses": int(lags[idx]), "normalized_correlation": score, "channel": channel}
    return best


def benjamini_hochberg(p_values: list[float]) -> list[float]:
    """Return Benjamini-Hochberg false-discovery-rate adjusted q-values."""
    p = np.asarray(p_values, dtype=float)
    if p.size == 0:
        return []
    order = np.argsort(p)
    ranked = p[order]
    q = ranked * len(p) / np.arange(1, len(p) + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    q = np.clip(q, 0.0, 1.0)
    out = np.empty_like(q)
    out[order] = q
    return out.tolist()
