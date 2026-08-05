from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json

import numpy as np

from .detector import scan_pulse_train
from .encoding import build_frame
from .models import PulseTrain


@dataclass(slots=True)
class SensitivityPoint:
    strength_sigma: float
    trials: int
    detected: int
    detection_rate: float
    median_adjusted_p: float
    median_compression_gain_bits: float


@dataclass(slots=True)
class SensitivityResult:
    source_id: str
    channel: str
    strengths_sigma: list[float]
    trials_per_strength: int
    surrogate_count: int
    seed: int
    minimum_possible_adjusted_p: float
    registered_threshold_resolvable: bool
    points: list[dict]

    def to_dict(self) -> dict:
        return asdict(self)


def _channel_array(train: PulseTrain, channel: str) -> np.ndarray:
    mapping = {
        "amplitude": train.amplitude,
        "polarization": train.polarization,
        "timing": train.arrival_residual_s,
        "frequency": train.frequency_centroid_hz,
    }
    try:
        return mapping[channel]
    except KeyError as exc:
        raise ValueError(f"unknown channel {channel}") from exc


def inject_strength(
    train: PulseTrain,
    *,
    channel: str,
    strength_sigma: float,
    seed: int,
    repeats: int = 8,
    gap_pulses: int = 73,
) -> PulseTrain:
    """Inject a repeated framed protocol at a registered signal-strength scale."""
    rng = np.random.default_rng(seed)
    out = train.copy()
    values = _channel_array(out, channel)
    payload = rng.bytes(int(rng.integers(6, 18)))
    frame = build_frame(payload)
    required = repeats * len(frame) + max(0, repeats - 1) * gap_pulses
    if required + 64 > out.n_pulses:
        repeats = max(3, (out.n_pulses - 64 + gap_pulses) // (len(frame) + gap_pulses))
    if repeats < 3:
        raise ValueError("pulse train is too short for sensitivity injection")
    total = repeats * len(frame) + (repeats - 1) * gap_pulses
    start = int(rng.integers(16, max(17, out.n_pulses - total)))

    median = float(np.median(values))
    sigma = float(1.4826 * np.median(np.abs(values - median)))
    if sigma <= 1e-12:
        sigma = float(np.std(values)) or 1.0
    low = median - strength_sigma * sigma
    high = median + strength_sigma * sigma
    cursor = start
    for _ in range(repeats):
        end = cursor + len(frame)
        bits = frame.copy()
        bits[rng.random(len(bits)) < 0.015] ^= 1
        values[cursor:end] = np.where(bits == 1, high, low) + rng.normal(0.0, sigma * 0.08, len(bits))
        cursor = end + gap_pulses
    out.source_id = f"{train.source_id}:sensitivity-{channel}-{strength_sigma:.3f}"
    out.metadata.update({
        "injection": {
            "channel": channel,
            "strength_sigma": strength_sigma,
            "start": start,
            "repeats": repeats,
            "gap_pulses": gap_pulses,
            "frame_length": len(frame),
        }
    })
    return out


def run_sensitivity(
    train: PulseTrain,
    *,
    channel: str = "amplitude",
    strengths_sigma: list[float] | None = None,
    trials_per_strength: int = 8,
    surrogate_count: int = 48,
    seed: int = 20260804,
    output: str | Path | None = None,
) -> SensitivityResult:
    strengths = strengths_sigma or [0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0]
    points: list[dict] = []
    for sindex, strength in enumerate(strengths):
        detected = 0
        p_values: list[float] = []
        gains: list[float] = []
        for trial in range(trials_per_strength):
            trial_seed = seed + sindex * 10_000 + trial * 17
            candidate = train if strength == 0 else inject_strength(
                train, channel=channel, strength_sigma=float(strength), seed=trial_seed
            )
            report = scan_pulse_train(candidate, surrogate_count=surrogate_count, seed=trial_seed + 1)
            positive = report.adjusted_p_value < 0.05 and report.compression_gain_bits > 128
            detected += int(positive)
            p_values.append(report.adjusted_p_value)
            gains.append(report.compression_gain_bits)
        points.append(asdict(SensitivityPoint(
            strength_sigma=float(strength),
            trials=trials_per_strength,
            detected=detected,
            detection_rate=detected / trials_per_strength,
            median_adjusted_p=float(np.median(p_values)),
            median_compression_gain_bits=float(np.median(gains)),
        )))
    result = SensitivityResult(
        source_id=train.source_id,
        channel=channel,
        strengths_sigma=[float(value) for value in strengths],
        trials_per_strength=trials_per_strength,
        surrogate_count=surrogate_count,
        seed=seed,
        minimum_possible_adjusted_p=min(1.0, 4.0 / (surrogate_count + 1)),
        registered_threshold_resolvable=(4.0 / (surrogate_count + 1) < 0.05),
        points=points,
    )
    if output is not None:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    return result
