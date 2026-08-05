from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import numpy as np

from .detector import scan_pulse_train
from .encoding import build_frame, inject_repeated_frame
from .models import PulseTrain
from .simulator import simulate_natural_pulsar


@dataclass(slots=True)
class BenchmarkCase:
    case_id: str
    label: str
    natural_variant: str
    injection_family: str | None
    report: dict


@dataclass(slots=True)
class BenchmarkSummary:
    seed: int
    cases: int
    natural_cases: int
    injected_cases: int
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    precision: float
    recall: float
    false_positive_rate: float
    cases_detail: list[dict]

    def to_dict(self) -> dict:
        return asdict(self)


def _natural_variant(n_pulses: int, seed: int, variant: str, source_id: str) -> PulseTrain:
    if variant == "markov":
        return simulate_natural_pulsar(n_pulses=n_pulses, seed=seed, source_id=source_id)
    if variant == "bursty":
        return simulate_natural_pulsar(
            n_pulses=n_pulses,
            p_on_to_null=0.008,
            p_null_to_on=0.10,
            seed=seed,
            source_id=source_id,
        )
    if variant == "rapid_nulling":
        return simulate_natural_pulsar(
            n_pulses=n_pulses,
            p_on_to_null=0.06,
            p_null_to_on=0.55,
            seed=seed,
            source_id=source_id,
        )
    if variant == "quasi_periodic":
        train = simulate_natural_pulsar(n_pulses=n_pulses, seed=seed, source_id=source_id)
        rng = np.random.default_rng(seed + 991)
        spacing = int(rng.integers(90, 180))
        cursor = int(rng.integers(20, spacing))
        while cursor < n_pulses:
            run = int(rng.integers(2, 8))
            train.amplitude[cursor : cursor + run] *= rng.uniform(0.02, 0.18)
            cursor += spacing + int(rng.integers(-8, 9))
        return train
    raise ValueError(f"unknown natural variant {variant}")


def _inject_family(train: PulseTrain, family: str, seed: int) -> PulseTrain:
    rng = np.random.default_rng(seed)
    payload = rng.bytes(int(rng.integers(5, 18)))
    frame = build_frame(payload)
    start = int(rng.integers(400, 900))
    gap = int(rng.integers(43, 131))
    repeats = int(rng.integers(7, 11))

    if family == "amplitude":
        return inject_repeated_frame(train, frame, start=start, repeats=repeats, gap_pulses=gap, seed=seed)

    out = train.copy()
    cursor = start
    for _ in range(repeats):
        if cursor + len(frame) > out.n_pulses:
            break
        noisy = frame.copy()
        noisy[rng.random(len(frame)) < 0.02] ^= 1
        idx = np.arange(cursor, cursor + len(frame))
        signs = np.where(noisy == 1, 1.0, -1.0)
        if family == "polarization":
            out.polarization[idx] = 0.62 * signs + rng.normal(0.0, 0.06, len(frame))
        elif family == "timing":
            shift = out.period_s * 4.0e-4
            out.arrival_residual_s[idx] = signs * shift + rng.normal(0.0, shift * 0.12, len(frame))
        elif family == "frequency":
            out.frequency_centroid_hz[idx] = 1.4e9 + signs * 8.0e6 + rng.normal(0.0, 0.6e6, len(frame))
        else:
            raise ValueError(f"unknown injection family {family}")
        cursor += len(frame) + gap
    return out


def run_benchmark(
    *,
    cases: int = 24,
    n_pulses: int = 12000,
    surrogate_count: int = 96,
    seed: int = 20260804,
    output: str | Path | None = None,
) -> BenchmarkSummary:
    """Run a seeded red-team benchmark over natural and injected pulse streams."""

    rng = np.random.default_rng(seed)
    variants = ["markov", "bursty", "rapid_nulling", "quasi_periodic"]
    families = ["amplitude", "polarization", "timing", "frequency"]
    details: list[dict] = []
    tp = fp = tn = fn = 0

    for index in range(cases):
        case_seed = int(rng.integers(0, 2**31 - 1))
        variant = variants[index % len(variants)]
        injected = bool(index % 2)
        family = families[(index // 2) % len(families)] if injected else None
        source_id = f"BENCH-{index:04d}"
        train = _natural_variant(n_pulses, case_seed, variant, source_id)
        if family is not None:
            train = _inject_family(train, family, case_seed + 1)
        report = scan_pulse_train(train, surrogate_count=surrogate_count, seed=case_seed + 2)
        # Benchmark operating point: strong inconclusive detections count as recovered
        # injections, but this is not the evidentiary threshold for a real discovery.
        positive = report.verdict == "candidate_structured_modulation" or (
            report.verdict == "interesting_but_inconclusive"
            and report.adjusted_p_value <= 0.10
            and report.compression_gain_bits > 512
        )
        if injected and positive:
            tp += 1
        elif injected and not positive:
            fn += 1
        elif (not injected) and positive:
            fp += 1
        else:
            tn += 1
        details.append(
            asdict(
                BenchmarkCase(
                    case_id=source_id,
                    label="injected" if injected else "natural",
                    natural_variant=variant,
                    injection_family=family,
                    report=report.to_dict(),
                )
            )
        )

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    summary = BenchmarkSummary(
        seed=seed,
        cases=cases,
        natural_cases=tn + fp,
        injected_cases=tp + fn,
        true_positives=tp,
        false_positives=fp,
        true_negatives=tn,
        false_negatives=fn,
        precision=precision,
        recall=recall,
        false_positive_rate=fpr,
        cases_detail=details,
    )
    if output is not None:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary.to_dict(), indent=2), encoding="utf-8")
    return summary
