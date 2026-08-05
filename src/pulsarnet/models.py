from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any
import json
import numpy as np


@dataclass(slots=True)
class PulseTrain:
    """A simplified single-pulse observation indexed by pulse number."""

    period_s: float
    amplitude: np.ndarray
    arrival_residual_s: np.ndarray
    polarization: np.ndarray
    frequency_centroid_hz: np.ndarray
    source_id: str = "synthetic"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        n = len(self.amplitude)
        for name in ("arrival_residual_s", "polarization", "frequency_centroid_hz"):
            value = getattr(self, name)
            if len(value) != n:
                raise ValueError(f"{name} length {len(value)} != amplitude length {n}")
        if self.period_s <= 0:
            raise ValueError("period_s must be positive")
        self.amplitude = np.asarray(self.amplitude, dtype=float)
        self.arrival_residual_s = np.asarray(self.arrival_residual_s, dtype=float)
        self.polarization = np.asarray(self.polarization, dtype=float)
        self.frequency_centroid_hz = np.asarray(self.frequency_centroid_hz, dtype=float)

    @property
    def n_pulses(self) -> int:
        return int(len(self.amplitude))

    def copy(self) -> "PulseTrain":
        return PulseTrain(
            period_s=self.period_s,
            amplitude=self.amplitude.copy(),
            arrival_residual_s=self.arrival_residual_s.copy(),
            polarization=self.polarization.copy(),
            frequency_centroid_hz=self.frequency_centroid_hz.copy(),
            source_id=self.source_id,
            metadata=dict(self.metadata),
        )

    def save_npz(self, path: str) -> None:
        np.savez_compressed(
            path,
            period_s=np.array([self.period_s]),
            amplitude=self.amplitude,
            arrival_residual_s=self.arrival_residual_s,
            polarization=self.polarization,
            frequency_centroid_hz=self.frequency_centroid_hz,
            source_id=np.array([self.source_id]),
            metadata_json=np.array([json.dumps(self.metadata, sort_keys=True)]),
        )

    @classmethod
    def load_npz(cls, path: str) -> "PulseTrain":
        data = np.load(path, allow_pickle=False)
        return cls(
            period_s=float(data["period_s"][0]),
            amplitude=data["amplitude"].astype(float),
            arrival_residual_s=data["arrival_residual_s"].astype(float),
            polarization=data["polarization"].astype(float),
            frequency_centroid_hz=data["frequency_centroid_hz"].astype(float),
            source_id=str(data["source_id"][0]),
            metadata=(json.loads(str(data["metadata_json"][0])) if "metadata_json" in data.files else {}),
        )


@dataclass(slots=True)
class DetectionReport:
    source_id: str
    n_pulses: int
    null_fraction: float
    transition_matrix: list[list[float]]
    strongest_lag: int | None
    strongest_lag_score: float
    surrogate_p_value: float
    compression_gain_bits: float
    prime_gap_enrichment: float
    candidate_frame_lengths: list[int]
    verdict: str
    notes: list[str]
    best_channel: str = "amplitude"
    adjusted_p_value: float = 1.0
    cross_channel_support: int = 1
    channel_metrics: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)
