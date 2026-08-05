from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import hashlib
import json
import sys
import time

import numpy as np
import yaml

from .detector import benjamini_hochberg, scan_pulse_train
from .models import DetectionReport, PulseTrain
from .observations import (
    DynamicSpectrum,
    extract_pulse_train,
    load_hdf5_dynamic_spectrum,
    load_psrfits_search,
    load_sigproc_filterbank,
)


@dataclass(slots=True)
class ControlResult:
    control_id: str
    control_type: str
    parameters: dict[str, Any]
    pulse_train_path: str
    report: dict[str, Any]


@dataclass(slots=True)
class ObservationResult:
    observation_id: str
    source_id: str
    input_path: str
    input_sha256: str
    input_format: str
    target_pulse_train_path: str
    target_report: dict[str, Any]
    controls: list[dict[str, Any]]
    split_half: dict[str, Any]
    batch_fdr_q_value: float | None = None
    disposition: str = "pending_batch_correction"
    disposition_reasons: list[str] | None = None


@dataclass(slots=True)
class ExperimentResult:
    experiment_id: str
    manifest_path: str
    manifest_sha256: str
    seed: int
    surrogate_count: int
    observations: list[dict[str, Any]]
    summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def sha256_file(path: str | Path, chunk_bytes: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_bytes):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        payload = yaml.safe_load(text)
    else:
        payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("experiment manifest must be a mapping")
    if not isinstance(payload.get("observations"), list) or not payload["observations"]:
        raise ValueError("manifest requires a non-empty observations list")
    return payload


def _load_dynamic(entry: dict[str, Any]) -> DynamicSpectrum:
    fmt = str(entry["format"]).lower()
    path = entry["path"]
    if fmt == "hdf5":
        return load_hdf5_dynamic_spectrum(
            path,
            start_sample=int(entry.get("start_sample", 0)),
            max_samples=entry.get("max_samples"),
        )
    if fmt == "filterbank":
        return load_sigproc_filterbank(
            path,
            start_sample=int(entry.get("start_sample", 0)),
            max_samples=entry.get("max_samples"),
        )
    if fmt == "psrfits":
        return load_psrfits_search(
            path,
            start_subint=int(entry.get("start_subint", 0)),
            max_subints=entry.get("max_subints"),
        )
    raise ValueError(f"{fmt!r} is not a dynamic-spectrum format")


def _extract(
    spectrum: DynamicSpectrum,
    entry: dict[str, Any],
    *,
    period_s: float | None = None,
    dm_pc_cm3: float | None = None,
    window_phase_offset_fraction: float = 0.0,
    label: str = "target",
    dedispersion_cache: dict | None = None,
) -> PulseTrain:
    train = extract_pulse_train(
        spectrum,
        period_s=float(period_s if period_s is not None else entry["period_s"]),
        dm_pc_cm3=float(dm_pc_cm3 if dm_pc_cm3 is not None else entry.get("dm_pc_cm3", 0.0)),
        on_window_fraction=float(entry.get("on_window_fraction", 0.08)),
        rfi_z_threshold=float(entry.get("rfi_z_threshold", 6.0)),
        time_rfi_z_threshold=(
            float(entry["time_rfi_z_threshold"]) if entry.get("time_rfi_z_threshold") is not None else None
        ),
        # Period refinement applies to the TARGET fold only. Controls that
        # deliberately mis-fold (wrong-period) pass an explicit period_s and must
        # not be refined back toward the true rotation.
        refine_period_fraction=(
            float(entry["refine_period_fraction"])
            if entry.get("refine_period_fraction") is not None and period_s is None
            else None
        ),
        whiten_frequency=bool(entry.get("whiten_frequency", False)),
        window_phase_offset_fraction=window_phase_offset_fraction,
        _dedispersion_cache=dedispersion_cache,
    )
    train.source_id = f"{spectrum.source_id}:{label}"
    train.metadata["analysis_label"] = label
    return train


def _slice_train(train: PulseTrain, start: int, stop: int, label: str) -> PulseTrain:
    return PulseTrain(
        period_s=train.period_s,
        amplitude=train.amplitude[start:stop],
        arrival_residual_s=train.arrival_residual_s[start:stop],
        polarization=train.polarization[start:stop],
        frequency_centroid_hz=train.frequency_centroid_hz[start:stop],
        source_id=f"{train.source_id}:{label}",
        metadata={**train.metadata, "slice": [start, stop], "analysis_label": label},
    )


def _block_permutation_control(train: PulseTrain, seed: int, block_size: int = 64) -> PulseTrain:
    """Permute aligned pulse blocks while preserving within-block natural texture."""
    rng = np.random.default_rng(seed)
    n = train.n_pulses
    blocks = [np.arange(start, min(start + block_size, n)) for start in range(0, n, block_size)]
    rng.shuffle(blocks)
    order = np.concatenate(blocks)
    out = PulseTrain(
        period_s=train.period_s,
        amplitude=train.amplitude[order],
        arrival_residual_s=train.arrival_residual_s[order],
        polarization=train.polarization[order],
        frequency_centroid_hz=train.frequency_centroid_hz[order],
        source_id=f"{train.source_id}:block-permutation",
        metadata={**train.metadata, "control_type": "block_permutation", "block_size": block_size},
    )
    return out


def _scan_and_save(
    train: PulseTrain,
    path: Path,
    surrogate_count: int,
    seed: int,
) -> DetectionReport:
    path.parent.mkdir(parents=True, exist_ok=True)
    train.save_npz(str(path))
    report = scan_pulse_train(train, surrogate_count=surrogate_count, seed=seed)
    path.with_suffix(".report.json").write_text(report.to_json(), encoding="utf-8")
    return report


def _is_level1(report: dict[str, Any]) -> bool:
    return bool(report["adjusted_p_value"] < 0.05 and report["compression_gain_bits"] > 128)


def _split_half_check(train: PulseTrain, surrogate_count: int, seed: int) -> dict[str, Any]:
    midpoint = train.n_pulses // 2
    if midpoint < 128 or train.n_pulses - midpoint < 128:
        return {"available": False, "reason": "fewer than 128 pulses per half"}
    first = scan_pulse_train(_slice_train(train, 0, midpoint, "first-half"), surrogate_count, seed)
    second = scan_pulse_train(_slice_train(train, midpoint, train.n_pulses, "second-half"), surrogate_count, seed + 1)
    lag_a, lag_b = first.strongest_lag, second.strongest_lag
    compatible = False
    if lag_a is not None and lag_b is not None:
        tolerance = max(3, int(max(lag_a, lag_b) * 0.03))
        compatible = abs(lag_a - lag_b) <= tolerance
    return {
        "available": True,
        "compatible_lag": compatible,
        "first": first.to_dict(),
        "second": second.to_dict(),
    }


class _Progress:
    """Console progress/ETA reporter for manifest runs.

    Steps are weighted because a step is dominated by its surrogate scan: the
    target, each control and both split-half scans cost roughly one scan unit,
    while extraction cost is folded into its owning step. ETA uses the mean
    cost of completed units, which stabilizes after the first observation.

    Every line carries a wall-clock UTC timestamp and is mirrored to
    ``run.log`` inside the output directory so a crashed or killed run leaves a
    complete forensic trail.
    """

    def __init__(self, total_units: float, enabled: bool = True, log_path: Path | None = None) -> None:
        self.total = max(total_units, 1e-9)
        self.done = 0.0
        self.started = time.monotonic()
        self.enabled = enabled
        self._last_time = self.started
        self._ewma_rate: float | None = None  # seconds per unit, recency-weighted
        self.log_path = log_path
        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)

    def _emit(self, level: str, label: str) -> None:
        elapsed = time.monotonic() - self.started
        pct = 100.0 * self.done / self.total
        if self._ewma_rate is not None and self.done > 0:
            eta = self._ewma_rate * (self.total - self.done)
            eta_text = f"ETA {int(eta // 60):d}m{int(eta % 60):02d}s"
        else:
            eta_text = "ETA --"
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        line = f"{stamp} [{elapsed:7.1f}s] {pct:5.1f}% | {eta_text:>10} | {level:<5} | {label}"
        if self.enabled:
            print(line, file=sys.stderr, flush=True)
        if self.log_path is not None:
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")

    def step(self, label: str, units: float = 1.0) -> None:
        self._emit("INFO", label)

    def finish(self, label: str, units: float = 1.0) -> None:
        now = time.monotonic()
        if units > 0:
            rate = (now - self._last_time) / units
            # Recency-weighted seconds/unit: adapts within ~4 completed units
            # when moving between small and large observations.
            self._ewma_rate = rate if self._ewma_rate is None else 0.7 * self._ewma_rate + 0.3 * rate
        self._last_time = now
        self.done += units
        self._emit("INFO", label)

    def warn(self, label: str) -> None:
        self._emit("WARN", label)

    def error(self, label: str) -> None:
        self._emit("ERROR", label)


def run_manifest(
    manifest_path: str | Path,
    *,
    output_dir: str | Path,
    progress: bool = True,
) -> ExperimentResult:
    manifest_path = Path(manifest_path).resolve()
    manifest = load_manifest(manifest_path)
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    experiment_id = str(manifest.get("experiment_id", manifest_path.stem))
    seed = int(manifest.get("seed", 20260804))
    surrogate_count = int(manifest.get("surrogate_count", 192))
    if surrogate_count < 24:
        raise ValueError("surrogate_count must be at least 24")

    # Pre-compute the work plan for progress/ETA: per observation we run the
    # target scan, one block-permutation control, the declared dynamic controls
    # and two split-half scans (weighted 0.5 each for their half-length data).
    def _entry_units(entry: dict[str, Any]) -> float:
        units = 2.0  # target + block permutation
        if str(entry["format"]).lower() != "npz":
            units += len(entry.get("offpulse_phase_offsets", [0.25, 0.50, 0.75]))
            units += len(entry.get("wrong_period_fractions", [-0.005, 0.005]))
            if float(entry.get("dm_pc_cm3", 0.0)) > 0:
                units += len(entry.get("wrong_dm_fractions", [-0.25, 0.25]))
        units += 1.0  # split-half pair
        return units

    tracker = _Progress(
        sum(_entry_units(dict(e)) for e in manifest["observations"]),
        enabled=progress,
        log_path=output_dir / "run.log",
    )
    from . import __version__ as _pkg_version
    tracker.step(
        f"experiment {experiment_id}: {len(manifest['observations'])} observations, "
        f"{surrogate_count} surrogates | pulsarnet v{_pkg_version} | seed {seed} | "
        f"manifest sha256 {sha256_file(manifest_path)[:16]}…"
    )

    raw_results: list[ObservationResult] = []
    failures: list[dict[str, Any]] = []
    for index, raw_entry in enumerate(manifest["observations"]):
        entry = dict(raw_entry)
        observation_id = str(entry.get("id", f"observation-{index:04d}"))
        input_path = Path(entry["path"])
        if not input_path.is_absolute():
            input_path = (manifest_path.parent / input_path).resolve()
        if not input_path.exists():
            raise FileNotFoundError(input_path)
        entry["path"] = str(input_path)
        fmt = str(entry["format"]).lower()
        obs_dir = output_dir / observation_id
        obs_dir.mkdir(parents=True, exist_ok=True)
        case_seed = seed + index * 10_000

        # ---- Checkpoint: a completed observation writes checkpoint.json with
        # the input hash + analysis parameters. On resume, matching checkpoints
        # are loaded instead of recomputed; stale ones are discarded loudly.
        checkpoint_path = obs_dir / "checkpoint.json"
        checkpoint_key = {
            "input_sha256": sha256_file(input_path),
            "surrogate_count": surrogate_count,
            "case_seed": case_seed,
            "entry": {k: v for k, v in sorted(entry.items()) if k != "path"},
        }
        if checkpoint_path.exists():
            try:
                saved = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                saved = None
                tracker.warn(f"{observation_id}: corrupt checkpoint.json ignored")
            if saved and saved.get("key") == checkpoint_key:
                raw_results.append(ObservationResult(**saved["result"]))
                tracker.finish(
                    f"{observation_id}: RESUMED from checkpoint ({saved['result']['target_report']['n_pulses']} pulses)",
                    units=_entry_units(entry),
                )
                continue
            if saved:
                tracker.warn(
                    f"{observation_id}: checkpoint stale (input/seed/params changed) — recomputing"
                )

        try:
            result = _run_observation(
                entry, observation_id, input_path, fmt, obs_dir, case_seed,
                surrogate_count, tracker,
            )
        except Exception as exc:  # noqa: BLE001 — isolate per-observation failures
            tracker.error(f"{observation_id}: FAILED — {type(exc).__name__}: {exc}")
            failures.append({
                "observation_id": observation_id,
                "error_type": type(exc).__name__,
                "error": str(exc),
            })
            (obs_dir / "failure.json").write_text(
                json.dumps({
                    "observation_id": observation_id,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "entry": checkpoint_key["entry"],
                }, indent=2),
                encoding="utf-8",
            )
            continue

        checkpoint_path.write_text(
            json.dumps({"key": checkpoint_key, "result": asdict(result)}, indent=2),
            encoding="utf-8",
        )
        raw_results.append(result)

    if not raw_results:
        raise RuntimeError(f"All {len(failures)} observations failed; see run.log and failure.json files")

    q_values = benjamini_hochberg([item.target_report["adjusted_p_value"] for item in raw_results])
    candidate_count = 0
    for item, q_value in zip(raw_results, q_values):
        item.batch_fdr_q_value = float(q_value)
        reasons: list[str] = []
        target_l1 = _is_level1(item.target_report)
        contaminating = [
            control for control in item.controls
            if _is_level1(control["report"])
            or control["report"]["adjusted_p_value"] <= item.target_report["adjusted_p_value"]
        ]
        if not target_l1:
            item.disposition = "no_registered_level1_anomaly"
            reasons.append("Target does not meet adjusted-p and compression thresholds.")
        elif q_value >= 0.01:
            item.disposition = "level1_only_not_batch_significant"
            reasons.append("Target does not survive registered batch FDR q < 0.01.")
        elif contaminating:
            item.disposition = "rejected_by_negative_controls"
            reasons.append("One or more negative controls are at least as anomalous as the target.")
            reasons.extend(f"Control: {control['control_id']}" for control in contaminating)
        elif item.split_half.get("available") and not item.split_half.get("compatible_lag"):
            item.disposition = "not_replicated_across_split_halves"
            reasons.append("Strongest candidate lag is not compatible across held-out halves.")
        else:
            item.disposition = "follow_up_candidate"
            reasons.append("Survives registered software, batch and negative-control gates.")
            candidate_count += 1
        item.disposition_reasons = reasons

    minimum_adjusted_p = min(1.0, 4.0 / (surrogate_count + 1))
    single_candidate_q_floor = min(1.0, minimum_adjusted_p * len(raw_results))
    summary = {
        "observation_count": len(raw_results),
        "failed_observation_count": len(failures),
        "failures": failures,
        "minimum_possible_channel_adjusted_p": minimum_adjusted_p,
        "single_candidate_batch_q_floor": single_candidate_q_floor,
        "registered_level1_p_threshold_resolvable": minimum_adjusted_p < 0.05,
        "registered_single_candidate_q_threshold_resolvable": single_candidate_q_floor < 0.01,
        "minimum_surrogates_for_single_candidate_q_below_0_01": max(1, 400 * len(raw_results)),
        "registered_level1_count": sum(_is_level1(item.target_report) for item in raw_results),
        "follow_up_candidate_count": candidate_count,
        "disposition_counts": {
            disposition: sum(item.disposition == disposition for item in raw_results)
            for disposition in sorted({item.disposition for item in raw_results})
        },
        "scientific_boundary": "A follow-up candidate is an anomaly requiring independent observatory and astrophysical validation, not evidence of extraterrestrial intelligence.",
    }
    result = ExperimentResult(
        experiment_id=experiment_id,
        manifest_path=str(manifest_path),
        manifest_sha256=sha256_file(manifest_path),
        seed=seed,
        surrogate_count=surrogate_count,
        observations=[asdict(item) for item in raw_results],
        summary=summary,
    )
    (output_dir / "experiment-report.json").write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    tracker.finish(
        f"experiment complete: {len(raw_results)} ok, {len(failures)} failed, "
        f"{candidate_count} follow-up candidate(s)", units=0.0,
    )
    return result


def _run_observation(
    entry: dict[str, Any],
    observation_id: str,
    input_path: Path,
    fmt: str,
    obs_dir: Path,
    case_seed: int,
    surrogate_count: int,
    tracker: _Progress,
) -> ObservationResult:
    """Analyze one observation: target, all registered controls, split-half."""
    tracker.step(f"{observation_id}: loading + extracting target")
    if fmt == "npz":
        target = PulseTrain.load_npz(str(input_path))
        target.source_id = f"{target.source_id}:target"
        dynamic = None
        dedispersion_cache: dict = {}
    else:
        dynamic = _load_dynamic(entry)
        dedispersion_cache = {}
        target = _extract(dynamic, entry, label="target", dedispersion_cache=dedispersion_cache)

    target_path = obs_dir / "target.npz"
    target_report = _scan_and_save(target, target_path, surrogate_count, case_seed)
    tracker.finish(f"{observation_id}: target scanned ({target.n_pulses} pulses, verdict={target_report.verdict})")
    controls: list[ControlResult] = []

    # A block-order control is available for every format and preserves local texture.
    block_size = int(entry.get("control_block_size", 64))
    shuffled = _block_permutation_control(target, case_seed + 100, block_size=block_size)
    control_path = obs_dir / "control-block-permutation.npz"
    report = _scan_and_save(shuffled, control_path, surrogate_count, case_seed + 101)
    controls.append(ControlResult(
        "block-permutation", "block_permutation", {"block_size": block_size}, str(control_path), report.to_dict()
    ))
    tracker.finish(f"{observation_id}: control block-permutation done")

    if dynamic is not None:
        # Off-pulse controls are the SAME fold as the target with a shifted
        # analysis window — reuse the target's refined period instead of
        # re-running the 400-fold refinement grid per control. Wrong-period
        # controls remain deliberately mis-folded and unrefined.
        period = float(target.metadata.get("period_s", entry["period_s"]))
        dm = float(entry.get("dm_pc_cm3", 0.0))
        for cindex, offset in enumerate(entry.get("offpulse_phase_offsets", [0.25, 0.50, 0.75])):
            label = f"offpulse-{float(offset):+.3f}"
            control = _extract(dynamic, entry, period_s=period, window_phase_offset_fraction=float(offset), label=label, dedispersion_cache=dedispersion_cache)
            control_path = obs_dir / f"control-{label}.npz"
            report = _scan_and_save(control, control_path, surrogate_count, case_seed + 200 + cindex)
            controls.append(ControlResult(label, "offpulse", {"phase_offset_fraction": float(offset)}, str(control_path), report.to_dict()))
            tracker.finish(f"{observation_id}: control {label} done")

        for cindex, fraction in enumerate(entry.get("wrong_period_fractions", [-0.005, 0.005])):
            control_period = period * (1.0 + float(fraction))
            label = f"wrong-period-{float(fraction):+.5f}"
            control = _extract(dynamic, entry, period_s=control_period, label=label, dedispersion_cache=dedispersion_cache)
            control_path = obs_dir / f"control-{label}.npz"
            report = _scan_and_save(control, control_path, surrogate_count, case_seed + 300 + cindex)
            controls.append(ControlResult(label, "wrong_period", {"period_s": control_period}, str(control_path), report.to_dict()))
            tracker.finish(f"{observation_id}: control {label} done")

        if dm > 0:
            for cindex, fraction in enumerate(entry.get("wrong_dm_fractions", [-0.25, 0.25])):
                control_dm = max(0.0, dm * (1.0 + float(fraction)))
                label = f"wrong-dm-{float(fraction):+.3f}"
                control = _extract(dynamic, entry, period_s=period, dm_pc_cm3=control_dm, label=label, dedispersion_cache=dedispersion_cache)
                control_path = obs_dir / f"control-{label}.npz"
                report = _scan_and_save(control, control_path, surrogate_count, case_seed + 400 + cindex)
                controls.append(ControlResult(label, "wrong_dm", {"dm_pc_cm3": control_dm}, str(control_path), report.to_dict()))
                tracker.finish(f"{observation_id}: control {label} done")

    split_half = _split_half_check(target, max(24, surrogate_count // 2), case_seed + 500)
    tracker.finish(f"{observation_id}: split-half recurrence checked")
    return ObservationResult(
        observation_id=observation_id,
        source_id=target.source_id,
        input_path=str(input_path),
        input_sha256=sha256_file(input_path),
        input_format=fmt,
        target_pulse_train_path=str(target_path),
        target_report=target_report.to_dict(),
        controls=[asdict(item) for item in controls],
        split_half=split_half,
    )
