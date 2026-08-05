from __future__ import annotations

import binascii
import numpy as np
from .models import PulseTrain

# A fixed high-transition preamble for simulation only. The detector does not receive
# this sequence and searches for repeated frame structure blind.
PREAMBLE = np.array(
    [1, 1, 1, 0, 1, 0, 0, 1, 0, 1, 1, 0, 0, 0, 1, 1,
     0, 1, 0, 0, 1, 1, 1, 0, 0, 1, 0, 1, 0, 1, 1, 1],
    dtype=np.uint8,
)


def bytes_to_bits(payload: bytes) -> np.ndarray:
    return np.unpackbits(np.frombuffer(payload, dtype=np.uint8))


def manchester_encode(bits: np.ndarray) -> np.ndarray:
    bits = bits.astype(np.uint8)
    out = np.empty(bits.size * 2, dtype=np.uint8)
    out[0::2] = 1 - bits
    out[1::2] = bits
    return out


def build_frame(payload: bytes) -> np.ndarray:
    """Build a self-checking synthetic frame: preamble + length + payload + CRC32."""
    if len(payload) > 65535:
        raise ValueError("payload too large")
    length = len(payload).to_bytes(2, "big")
    crc = binascii.crc32(payload).to_bytes(4, "big")
    body = bytes_to_bits(length + payload + crc)
    return np.concatenate([PREAMBLE, manchester_encode(body)])


def inject_repeated_frame(
    train: PulseTrain,
    frame: np.ndarray,
    start: int = 1000,
    repeats: int = 7,
    gap_pulses: int = 97,
    amplitude_one: float = 1.25,
    amplitude_zero: float = 0.025,
    polarization_strength: float = 0.42,
    bit_flip_rate: float = 0.018,
    seed: int = 99,
) -> PulseTrain:
    """Inject an artificial pulse-null/amplitude/polarization modulation.

    The same bit is redundantly represented in amplitude and polarization, allowing
    the detector to test multi-channel consistency.
    """
    rng = np.random.default_rng(seed)
    out = train.copy()
    frame = frame.astype(np.uint8)
    cursor = start

    for _ in range(repeats):
        if cursor + frame.size > out.n_pulses:
            break
        noisy = frame.copy()
        flips = rng.random(frame.size) < bit_flip_rate
        noisy[flips] ^= 1
        idx = np.arange(cursor, cursor + frame.size)

        # 0 -> deliberate null; 1 -> controlled bright pulse.
        out.amplitude[idx] = np.where(
            noisy == 1,
            amplitude_one + rng.normal(0.0, 0.08, frame.size),
            amplitude_zero + np.abs(rng.normal(0.0, 0.015, frame.size)),
        )
        # Independent redundant channel with occasional natural noise.
        out.polarization[idx] = np.where(
            noisy == 1,
            polarization_strength + rng.normal(0.0, 0.035, frame.size),
            -polarization_strength + rng.normal(0.0, 0.035, frame.size),
        )
        cursor += frame.size + gap_pulses

    return out
