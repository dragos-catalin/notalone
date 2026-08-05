from __future__ import annotations

import argparse
import json
from pathlib import Path

from .simulator import simulate_natural_pulsar
from .encoding import build_frame, inject_repeated_frame
from .detector import scan_pulse_train, cross_node_correlation, benjamini_hochberg
from .models import PulseTrain
from .plotting import save_diagnostic_plot
from .benchmark import run_benchmark
from .framing import recover_repeated_frame
from .experiment import run_manifest
from .sensitivity import run_sensitivity
from .observations import (
    extract_pulse_train,
    load_hdf5_dynamic_spectrum,
    load_psrfits_search,
    load_sigproc_filterbank,
)


def cmd_demo(args: argparse.Namespace) -> int:
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    natural = simulate_natural_pulsar(n_pulses=args.pulses, seed=args.seed, source_id="SYNTH-NATURAL")
    frame = build_frame(args.message.encode("utf-8"))
    modulated = inject_repeated_frame(
        natural, frame, start=args.start, repeats=args.repeats, gap_pulses=args.gap, seed=args.seed + 1
    )
    modulated.source_id = "SYNTH-MODULATED"
    natural.save_npz(str(out_dir / "natural.npz"))
    modulated.save_npz(str(out_dir / "modulated.npz"))
    save_diagnostic_plot(modulated, str(out_dir / "modulated-diagnostic.png"), start=max(0, args.start - 100))
    reports = {
        "natural": scan_pulse_train(natural, surrogate_count=args.surrogates, seed=args.seed).to_dict(),
        "modulated": scan_pulse_train(modulated, surrogate_count=args.surrogates, seed=args.seed).to_dict(),
    }
    (out_dir / "reports.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
    print(json.dumps(reports, indent=2))
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    train = PulseTrain.load_npz(args.input)
    print(scan_pulse_train(train, surrogate_count=args.surrogates, seed=args.seed).to_json())
    return 0


def cmd_scan_batch(args: argparse.Namespace) -> int:
    paths = sorted(Path(args.input_dir).glob(args.pattern))
    if not paths:
        raise SystemExit(f"No files match {args.pattern!r} in {args.input_dir}")
    reports = [
        scan_pulse_train(PulseTrain.load_npz(str(path)), surrogate_count=args.surrogates, seed=args.seed + i)
        for i, path in enumerate(paths)
    ]
    q_values = benjamini_hochberg([report.adjusted_p_value for report in reports])
    payload = []
    for path, report, q_value in zip(paths, reports, q_values):
        item = report.to_dict()
        item["input"] = str(path)
        item["batch_fdr_q_value"] = q_value
        payload.append(item)
    text = json.dumps(payload, indent=2)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text)
    return 0


def cmd_correlate(args: argparse.Namespace) -> int:
    a = PulseTrain.load_npz(args.input_a)
    b = PulseTrain.load_npz(args.input_b)
    print(json.dumps(cross_node_correlation(a, b, max_lag=args.max_lag), indent=2))
    return 0


def _load_observation(args: argparse.Namespace):
    if args.format == "hdf5":
        return load_hdf5_dynamic_spectrum(args.input, start_sample=args.start_sample, max_samples=args.max_samples)
    if args.format == "filterbank":
        return load_sigproc_filterbank(args.input, start_sample=args.start_sample, max_samples=args.max_samples)
    if args.format == "psrfits":
        return load_psrfits_search(args.input, start_subint=args.start_subint, max_subints=args.max_subints)
    raise ValueError(args.format)


def cmd_extract(args: argparse.Namespace) -> int:
    observation = _load_observation(args)
    train = extract_pulse_train(
        observation,
        period_s=args.period,
        dm_pc_cm3=args.dm,
        on_window_fraction=args.on_window_fraction,
        rfi_z_threshold=args.rfi_z,
        time_rfi_z_threshold=args.time_rfi_z,
        whiten_frequency=args.whiten_frequency,
    )
    train.save_npz(args.output)
    report = scan_pulse_train(train, surrogate_count=args.surrogates, seed=args.seed)
    report_path = Path(args.output).with_suffix(".report.json")
    report_path.write_text(report.to_json(), encoding="utf-8")
    print(json.dumps({"pulse_train": args.output, "report": str(report_path), **report.to_dict()}, indent=2))
    return 0



def cmd_recover(args: argparse.Namespace) -> int:
    train = PulseTrain.load_npz(args.input)
    result = recover_repeated_frame(
        train,
        channel=args.channel,
        frame_period=args.frame_period,
        min_repeats=args.min_repeats,
        max_repeats=args.max_repeats,
    )
    text = json.dumps(result.to_dict(), indent=2)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text)
    return 0

def cmd_benchmark(args: argparse.Namespace) -> int:
    summary = run_benchmark(
        cases=args.cases,
        n_pulses=args.pulses,
        surrogate_count=args.surrogates,
        seed=args.seed,
        output=args.output,
    )
    print(json.dumps(summary.to_dict(), indent=2))
    return 0



def cmd_run_manifest(args: argparse.Namespace) -> int:
    if args.fetch:
        from .experiment import load_manifest
        from .acquisition import fetch_manifest_inputs
        manifest = load_manifest(args.manifest)
        records = fetch_manifest_inputs(manifest, args.data_dir)
        fetched_manifest = Path(args.output) / "manifest-fetched.json"
        fetched_manifest.parent.mkdir(parents=True, exist_ok=True)
        fetched_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        (Path(args.output) / "download-provenance.json").write_text(
            json.dumps(records, indent=2), encoding="utf-8"
        )
        result = run_manifest(str(fetched_manifest), output_dir=args.output, progress=not args.no_progress)
        print(json.dumps(result.to_dict(), indent=2))
        return 0
    result = run_manifest(args.manifest, output_dir=args.output, progress=not args.no_progress)
    print(json.dumps(result.to_dict(), indent=2))
    return 0


def cmd_fetch_bl(args: argparse.Namespace) -> int:
    from .acquisition import query_breakthrough_listen, download_with_provenance
    files = query_breakthrough_listen(args.target, limit=args.limit)
    if args.pattern:
        files = [f for f in files if args.pattern in f.url]
    listing = [f.to_dict() for f in files]
    print(json.dumps(listing, indent=2))
    if args.list_only:
        return 0
    if not files:
        raise SystemExit(f"No Breakthrough Listen files matched target={args.target!r} pattern={args.pattern!r}")
    budget = args.max_bytes
    records = []
    for f in sorted(files, key=lambda item: item.size_bytes):
        if budget is not None and f.size_bytes > budget:
            continue
        record = download_with_provenance(f.url, Path(args.output) / Path(f.url).name)
        records.append(record)
        if budget is not None:
            budget -= f.size_bytes
        if args.max_files and len(records) >= args.max_files:
            break
    provenance = Path(args.output) / "download-provenance.json"
    provenance.write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(json.dumps(records, indent=2))
    return 0


def cmd_sensitivity(args: argparse.Namespace) -> int:
    train = PulseTrain.load_npz(args.input)
    strengths = [float(value) for value in args.strengths.split(",") if value.strip()]
    result = run_sensitivity(
        train,
        channel=args.channel,
        strengths_sigma=strengths,
        trials_per_strength=args.trials,
        surrogate_count=args.surrogates,
        seed=args.seed,
        output=args.output,
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pulsarnet")
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo", help="Run a natural-vs-injected detection demo")
    demo.add_argument("--output", default="artifacts/demo")
    demo.add_argument("--pulses", type=int, default=16384)
    demo.add_argument("--seed", type=int, default=7)
    demo.add_argument("--message", default="MATHEMATICS IS A SHARED REFERENCE")
    demo.add_argument("--start", type=int, default=900)
    demo.add_argument("--repeats", type=int, default=8)
    demo.add_argument("--gap", type=int, default=97)
    demo.add_argument("--surrogates", type=int, default=128)
    demo.set_defaults(func=cmd_demo)

    scan = sub.add_parser("scan", help="Scan an NPZ pulse train")
    scan.add_argument("input")
    scan.add_argument("--surrogates", type=int, default=128)
    scan.add_argument("--seed", type=int, default=1234)
    scan.set_defaults(func=cmd_scan)

    batch = sub.add_parser("scan-batch", help="Scan NPZ files and apply batch FDR correction")
    batch.add_argument("input_dir")
    batch.add_argument("--pattern", default="*.npz")
    batch.add_argument("--output")
    batch.add_argument("--surrogates", type=int, default=128)
    batch.add_argument("--seed", type=int, default=1234)
    batch.set_defaults(func=cmd_scan_batch)

    corr = sub.add_parser("correlate", help="Cross-correlate two NPZ pulse trains")
    corr.add_argument("input_a")
    corr.add_argument("input_b")
    corr.add_argument("--max-lag", type=int, default=4096)
    corr.set_defaults(func=cmd_correlate)

    recover = sub.add_parser("recover", help="Recover a consensus frame from a detected periodic channel")
    recover.add_argument("input")
    recover.add_argument("--channel", choices=["amplitude", "polarization", "timing", "frequency"], required=True)
    recover.add_argument("--frame-period", type=int, required=True)
    recover.add_argument("--min-repeats", type=int, default=4)
    recover.add_argument("--max-repeats", type=int, default=16)
    recover.add_argument("--output")
    recover.set_defaults(func=cmd_recover)

    extract = sub.add_parser("extract", help="Extract and scan pulses from a real dynamic-spectrum file")
    extract.add_argument("input")
    extract.add_argument("--format", choices=["hdf5", "filterbank", "psrfits"], required=True)
    extract.add_argument("--period", type=float, required=True, help="Known pulsar rotation period in seconds")
    extract.add_argument("--dm", type=float, default=0.0, help="Dispersion measure in pc cm^-3")
    extract.add_argument("--output", required=True)
    extract.add_argument("--start-sample", type=int, default=0)
    extract.add_argument("--max-samples", type=int)
    extract.add_argument("--start-subint", type=int, default=0)
    extract.add_argument("--max-subints", type=int)
    extract.add_argument("--on-window-fraction", type=float, default=0.08)
    extract.add_argument("--rfi-z", type=float, default=6.0)
    extract.add_argument("--time-rfi-z", type=float, default=None,
                         help="Optional zero-DM broadband RFI threshold; off by default")
    extract.add_argument("--whiten-frequency", action="store_true",
                         help="Detrend per-channel gain before the frequency centroid")
    extract.add_argument("--surrogates", type=int, default=128)
    extract.add_argument("--seed", type=int, default=1234)
    extract.set_defaults(func=cmd_extract)

    benchmark = sub.add_parser("benchmark", help="Run a seeded natural-vs-injected red-team benchmark")
    benchmark.add_argument("--output", default="artifacts/benchmark.json")
    benchmark.add_argument("--cases", type=int, default=24)
    benchmark.add_argument("--pulses", type=int, default=12000)
    benchmark.add_argument("--surrogates", type=int, default=96)
    benchmark.add_argument("--seed", type=int, default=20260804)
    benchmark.set_defaults(func=cmd_benchmark)

    manifest = sub.add_parser("run-manifest", help="Run a preregistered target-and-controls archival experiment")
    manifest.add_argument("manifest")
    manifest.add_argument("--output", default="artifacts/manifest-run")
    manifest.add_argument("--no-progress", action="store_true", help="Silence stderr progress/ETA log")
    manifest.add_argument("--fetch", action="store_true", help="Download url-declared inputs before running")
    manifest.add_argument("--data-dir", default="data", help="Directory for downloaded observation files")
    manifest.set_defaults(func=cmd_run_manifest)

    fetch_bl = sub.add_parser("fetch-bl", help="Query/download public Breakthrough Listen data with SHA-256 provenance")
    fetch_bl.add_argument("target", help="Archive target name, e.g. B0329+54")
    fetch_bl.add_argument("--pattern", default=None, help="Substring the file URL must contain, e.g. .0002.h5")
    fetch_bl.add_argument("--limit", type=int, default=100)
    fetch_bl.add_argument("--list-only", action="store_true")
    fetch_bl.add_argument("--output", default="data")
    fetch_bl.add_argument("--max-files", type=int, default=None)
    fetch_bl.add_argument("--max-bytes", type=int, default=None, help="Total download budget in bytes")
    fetch_bl.set_defaults(func=cmd_fetch_bl)

    sensitivity = sub.add_parser("sensitivity", help="Estimate injection-recovery sensitivity on an extracted pulse train")
    sensitivity.add_argument("input")
    sensitivity.add_argument("--channel", choices=["amplitude", "polarization", "timing", "frequency"], default="amplitude")
    sensitivity.add_argument("--strengths", default="0,0.25,0.5,0.75,1,1.5,2")
    sensitivity.add_argument("--trials", type=int, default=8)
    sensitivity.add_argument("--surrogates", type=int, default=48)
    sensitivity.add_argument("--seed", type=int, default=20260804)
    sensitivity.add_argument("--output", default="artifacts/sensitivity.json")
    sensitivity.set_defaults(func=cmd_sensitivity)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
