from __future__ import annotations

from dataclasses import dataclass, asdict
import binascii
import numpy as np

from .detector import robust_binary
from .encoding import PREAMBLE
from .models import PulseTrain


@dataclass(slots=True)
class FrameRecovery:
    channel: str
    frame_period: int
    start_index: int
    repeats_used: int
    mean_pair_similarity: float
    stable_fraction: float
    consensus_bits: str
    confidence: list[float]
    decoded_payload_utf8: str | None
    crc_valid: bool
    decode_notes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _channel_values(train: PulseTrain, channel: str) -> np.ndarray:
    mapping = {
        "amplitude": train.amplitude,
        "polarization": train.polarization,
        "timing": train.arrival_residual_s,
        "frequency": train.frequency_centroid_hz,
    }
    if channel not in mapping:
        raise ValueError(f"unknown channel {channel!r}")
    return np.asarray(mapping[channel], dtype=float)


def _manchester_decode(encoded: np.ndarray) -> np.ndarray | None:
    if len(encoded) % 2:
        encoded = encoded[:-1]
    pairs = encoded.reshape(-1, 2)
    valid = ((pairs[:, 0] == 1) & (pairs[:, 1] == 0)) | ((pairs[:, 0] == 0) & (pairs[:, 1] == 1))
    if np.mean(valid) < 0.92:
        return None
    # encoding: original 0 -> 10, original 1 -> 01
    return pairs[:, 1].astype(np.uint8)


def _bits_to_bytes(bits: np.ndarray) -> bytes:
    usable = bits[: len(bits) - (len(bits) % 8)]
    return np.packbits(usable).tobytes()


def decode_synthetic_frame(consensus: np.ndarray, confidence: np.ndarray) -> tuple[str | None, bool, list[str]]:
    """Attempt the v0.x synthetic framing protocol; generic detection does not depend on it."""
    notes: list[str] = []
    if len(consensus) < len(PREAMBLE) + 32:
        return None, False, ["Consensus is too short for the synthetic protocol."]

    best_offset = None
    best_distance = len(PREAMBLE) + 1
    cyclic = np.concatenate([consensus, consensus[: len(PREAMBLE) - 1]])
    for offset in range(len(consensus)):
        distance = int(np.sum(cyclic[offset : offset + len(PREAMBLE)] != PREAMBLE))
        if distance < best_distance:
            best_distance = distance
            best_offset = offset
    if best_offset is None or best_distance > max(2, len(PREAMBLE) // 8):
        return None, False, ["No compatible synthetic preamble found."]
    notes.append(f"Synthetic preamble found at offset {best_offset} with Hamming distance {best_distance}.")

    ordered = np.concatenate([consensus[best_offset:], consensus[:best_offset]])
    encoded = ordered[len(PREAMBLE) :]
    # Decode only the fixed-length header first. The consensus period may include a
    # natural inter-frame gap after the encoded frame, which must not be mistaken
    # for malformed Manchester data.
    decoded_header = _manchester_decode(encoded[:32])
    if decoded_header is None or len(decoded_header) < 16:
        return None, False, notes + ["Manchester length header could not be decoded reliably."]
    header_bytes = _bits_to_bytes(decoded_header)
    payload_length = int.from_bytes(header_bytes[:2], "big")
    required = 2 + payload_length + 4
    required_encoded_bits = required * 8 * 2
    if required_encoded_bits > len(encoded):
        return None, False, notes + [f"Frame announces {payload_length} payload bytes but consensus is incomplete."]
    decoded = _manchester_decode(encoded[:required_encoded_bits])
    if decoded is None:
        return None, False, notes + ["Manchester payload layer could not be decoded reliably."]
    body = _bits_to_bytes(decoded)
    payload = body[2 : 2 + payload_length]
    expected_crc = int.from_bytes(body[2 + payload_length : required], "big")
    actual_crc = binascii.crc32(payload)
    crc_valid = expected_crc == actual_crc
    notes.append(f"CRC32 {'matches' if crc_valid else 'does not match'}.")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        text = None
        notes.append("Payload is not valid UTF-8; binary payload retained conceptually.")
    return text, crc_valid, notes


def recover_repeated_frame(
    train: PulseTrain,
    *,
    channel: str,
    frame_period: int,
    min_repeats: int = 4,
    max_repeats: int = 16,
    stable_threshold: float = 0.82,
) -> FrameRecovery:
    """Recover a consensus block from windows repeating every ``frame_period`` pulses.

    The method is protocol-neutral. It finds a contiguous run of highly similar
    windows, aligns them, and reports per-position confidence. A separate optional
    decoder recognizes only the project's synthetic test protocol.
    """
    if frame_period < 8:
        raise ValueError("frame_period must be >= 8")
    bits = robust_binary(_channel_values(train, channel))
    if len(bits) < frame_period * (min_repeats + 1):
        raise ValueError("pulse train is too short for requested repeated-frame recovery")

    similarities = np.empty(len(bits) - 2 * frame_period + 1, dtype=float)
    for start in range(len(similarities)):
        a = bits[start : start + frame_period]
        b = bits[start + frame_period : start + 2 * frame_period]
        similarities[start] = float(np.mean(a == b))

    # Rank pair matches by both similarity and information content. Long constant
    # stretches are highly self-similar but cannot encode a useful frame.
    candidate_quality = np.empty_like(similarities)
    for start in range(len(similarities)):
        block = bits[start : start + frame_period]
        p_one = float(np.mean(block))
        balance = 4.0 * p_one * (1.0 - p_one)
        transitions = float(np.mean(np.diff(block) != 0))
        candidate_quality[start] = similarities[start] * balance + 0.20 * transitions
    candidate_order = np.argsort(candidate_quality)[::-1]
    best: tuple[float, int, int] | None = None
    visited_phases: set[tuple[int, int]] = set()
    for raw_start in candidate_order[: min(2000, len(candidate_order))]:
        phase = int(raw_start % frame_period)
        approx_block = int(raw_start // frame_period)
        key = (phase, approx_block)
        if key in visited_phases:
            continue
        visited_phases.add(key)
        start = int(raw_start)
        blocks = [bits[start : start + frame_period]]
        cursor = start + frame_period
        while cursor + frame_period <= len(bits) and len(blocks) < max_repeats:
            similarity = float(np.mean(blocks[-1] == bits[cursor : cursor + frame_period]))
            if similarity < 0.75:
                break
            blocks.append(bits[cursor : cursor + frame_period])
            cursor += frame_period
        if len(blocks) < min_repeats:
            continue
        stack = np.vstack(blocks)
        confidence = np.maximum(stack.mean(axis=0), 1.0 - stack.mean(axis=0))
        stable_fraction = float(np.mean(confidence >= stable_threshold))
        pair_score = float(np.mean([np.mean(stack[i] == stack[i + 1]) for i in range(len(stack) - 1)]))
        consensus_preview = (stack.mean(axis=0) >= 0.5).astype(np.uint8)
        one_fraction = float(np.mean(consensus_preview))
        balance = 4.0 * one_fraction * (1.0 - one_fraction)
        transition_rate = float(np.mean(np.diff(consensus_preview) != 0))
        # Constant natural stretches can look perfectly repeatable but carry virtually
        # no information. Reward balanced, transitioning consensus blocks.
        objective = (0.50 * stable_fraction + 0.25 * pair_score) * balance + 0.20 * transition_rate + min(len(blocks), 10) * 0.005
        if best is None or objective > best[0]:
            best = (objective, start, len(blocks))

    if best is None:
        # Return the best pair rather than fabricate a multi-repeat recovery.
        start = int(np.argmax(similarities))
        repeats = 2
    else:
        _, start, repeats = best

    blocks = np.vstack([bits[start + i * frame_period : start + (i + 1) * frame_period] for i in range(repeats)])
    ones = blocks.mean(axis=0)
    consensus = (ones >= 0.5).astype(np.uint8)
    confidence = np.maximum(ones, 1.0 - ones)
    mean_pair = float(np.mean([np.mean(blocks[i] == blocks[i + 1]) for i in range(len(blocks) - 1)])) if repeats > 1 else 0.0
    stable_fraction = float(np.mean(confidence >= stable_threshold))
    payload, crc_valid, notes = decode_synthetic_frame(consensus, confidence)
    if repeats < min_repeats:
        notes.insert(0, f"Only {repeats} aligned blocks were recovered; treat as inconclusive.")

    return FrameRecovery(
        channel=channel,
        frame_period=frame_period,
        start_index=start,
        repeats_used=repeats,
        mean_pair_similarity=mean_pair,
        stable_fraction=stable_fraction,
        consensus_bits="".join(str(int(bit)) for bit in consensus),
        confidence=[float(value) for value in confidence],
        decoded_payload_utf8=payload,
        crc_valid=crc_valid,
        decode_notes=notes,
    )
