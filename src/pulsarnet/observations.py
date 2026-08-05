from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import math
import struct

import h5py
import numpy as np

try:  # Registers bitshuffle/LZ4 codecs used by Breakthrough Listen HDF5 products.
    import hdf5plugin  # noqa: F401
except ImportError:  # pragma: no cover - optional, only needed for BL archives
    pass

from .models import PulseTrain


DISPERSION_CONSTANT_S_MHZ2 = 4.148808e3


@dataclass(slots=True)
class DynamicSpectrum:
    """Detected radio-power samples indexed as time × polarisation × frequency.

    The container deliberately stores calibrated/relative power, not raw voltages.
    It is suitable for first-pass single-pulse extraction from SIGPROC filterbank,
    Breakthrough Listen-style HDF5, or search-mode PSRFITS adapters.
    """

    data: np.ndarray
    tsamp_s: float
    frequencies_hz: np.ndarray
    source_id: str = "unknown"
    start_mjd: float | None = None
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        arr = np.asarray(self.data)
        if arr.ndim == 2:
            arr = arr[:, None, :]
        if arr.ndim != 3:
            raise ValueError("data must have shape (time, frequency) or (time, polarisation, frequency)")
        if arr.shape[-1] != len(self.frequencies_hz):
            raise ValueError("frequency axis does not match frequencies_hz")
        if self.tsamp_s <= 0:
            raise ValueError("tsamp_s must be positive")
        self.data = arr.astype(np.float32, copy=False)
        self.frequencies_hz = np.asarray(self.frequencies_hz, dtype=float)
        self.metadata = dict(self.metadata or {})

    @property
    def n_time(self) -> int:
        return int(self.data.shape[0])

    @property
    def n_pol(self) -> int:
        return int(self.data.shape[1])

    @property
    def n_chan(self) -> int:
        return int(self.data.shape[2])

    def save_hdf5(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with h5py.File(path, "w") as handle:
            ds = handle.create_dataset("data", data=self.data, compression="gzip", shuffle=True)
            ds.attrs["tsamp"] = self.tsamp_s
            ds.attrs["source_name"] = self.source_id
            ds.attrs["frequencies_hz"] = self.frequencies_hz
            if self.start_mjd is not None:
                ds.attrs["tstart"] = self.start_mjd
            ds.attrs["pulsarnet_metadata_json"] = json.dumps(self.metadata)


def _attr(container: h5py.AttributeManager, *names: str, default: Any = None) -> Any:
    for name in names:
        if name in container:
            value = container[name]
            if isinstance(value, bytes):
                return value.decode("utf-8", errors="replace")
            if isinstance(value, np.ndarray) and value.size == 1:
                return value.reshape(-1)[0].item()
            return value
    return default


def load_hdf5_dynamic_spectrum(
    path: str | Path,
    *,
    start_sample: int = 0,
    max_samples: int | None = None,
) -> DynamicSpectrum:
    """Load a Breakthrough Listen-style or PulsarNet HDF5 dynamic spectrum.

    Common datasets named ``data`` or ``/data`` are supported. Frequency metadata
    may be explicit or reconstructed from ``fch1`` and ``foff`` in MHz.
    """

    path = Path(path)
    with h5py.File(path, "r") as handle:
        if "data" in handle:
            ds = handle["data"]
        else:
            datasets: list[h5py.Dataset] = []
            handle.visititems(lambda _name, obj: datasets.append(obj) if isinstance(obj, h5py.Dataset) else None)
            if not datasets:
                raise ValueError(f"No dataset found in {path}")
            ds = max(datasets, key=lambda item: item.size)

        stop = ds.shape[0] if max_samples is None else min(ds.shape[0], start_sample + max_samples)
        if start_sample < 0 or start_sample >= stop:
            raise ValueError("invalid sample range")
        data = np.asarray(ds[start_sample:stop])
        if data.ndim == 2:
            data = data[:, None, :]
        elif data.ndim == 3:
            # BL HDF5 normally uses time × IF/pol × frequency.
            pass
        else:
            raise ValueError(f"Unsupported HDF5 data shape {data.shape}")

        attrs = dict(handle.attrs)
        attrs.update(dict(ds.attrs))
        tsamp = float(_attr(attrs, "tsamp", "TBIN", default=0.0))
        if tsamp <= 0:
            raise ValueError("HDF5 file is missing a positive tsamp attribute")

        nchan = data.shape[-1]
        explicit = _attr(attrs, "frequencies_hz", "frequency_hz")
        if explicit is not None:
            freqs = np.asarray(explicit, dtype=float)
        else:
            fch1_mhz = _attr(attrs, "fch1")
            foff_mhz = _attr(attrs, "foff")
            if fch1_mhz is None or foff_mhz is None:
                raise ValueError("HDF5 file needs frequencies_hz or fch1/foff metadata")
            freqs = (float(fch1_mhz) + np.arange(nchan) * float(foff_mhz)) * 1e6

        source = str(_attr(attrs, "source_name", "source_id", "SRC_NAME", default=path.stem))
        start_mjd_raw = _attr(attrs, "tstart", "STT_IMJD")
        start_mjd = float(start_mjd_raw) if start_mjd_raw is not None else None
        metadata_json = _attr(attrs, "pulsarnet_metadata_json")
        metadata: dict[str, Any] = {"format": "hdf5", "path": str(path)}
        if metadata_json:
            try:
                metadata.update(json.loads(str(metadata_json)))
            except json.JSONDecodeError:
                metadata["metadata_parse_error"] = True

    return DynamicSpectrum(
        data=data,
        tsamp_s=tsamp,
        frequencies_hz=freqs,
        source_id=source,
        start_mjd=start_mjd,
        metadata=metadata,
    )


_SIGPROC_STRING_KEYS = {"rawdatafile", "source_name"}
_SIGPROC_INT_KEYS = {
    "machine_id", "telescope_id", "data_type", "barycentric", "pulsarcentric",
    "nbits", "nsamples", "nchans", "nifs", "nbeams", "ibeam", "sumifs", "signed",
}
_SIGPROC_DOUBLE_KEYS = {
    "az_start", "za_start", "src_raj", "src_dej", "tstart", "tsamp", "fch1", "foff",
    "refdm", "period",
}


def _read_sigproc_string(handle) -> str:
    raw = handle.read(4)
    if len(raw) != 4:
        raise EOFError("Unexpected EOF in SIGPROC header")
    length = struct.unpack("<i", raw)[0]
    if length < 0 or length > 1_000_000:
        raise ValueError(f"Invalid SIGPROC string length {length}")
    payload = handle.read(length)
    if len(payload) != length:
        raise EOFError("Unexpected EOF in SIGPROC string")
    return payload.decode("ascii", errors="replace")


def read_sigproc_header(path: str | Path) -> tuple[dict[str, Any], int]:
    path = Path(path)
    header: dict[str, Any] = {}
    with path.open("rb") as handle:
        start = _read_sigproc_string(handle)
        if start != "HEADER_START":
            raise ValueError("Not a SIGPROC filterbank file: HEADER_START missing")
        while True:
            key = _read_sigproc_string(handle)
            if key == "HEADER_END":
                return header, handle.tell()
            if key in _SIGPROC_STRING_KEYS:
                header[key] = _read_sigproc_string(handle)
            elif key in _SIGPROC_INT_KEYS:
                payload = handle.read(4)
                if len(payload) != 4:
                    raise EOFError("Unexpected EOF in SIGPROC integer")
                header[key] = struct.unpack("<i", payload)[0]
            elif key in _SIGPROC_DOUBLE_KEYS:
                payload = handle.read(8)
                if len(payload) != 8:
                    raise EOFError("Unexpected EOF in SIGPROC double")
                header[key] = struct.unpack("<d", payload)[0]
            else:
                raise ValueError(
                    f"Unsupported SIGPROC header key {key!r}; use blimpy/sigpyproc for uncommon extensions"
                )


def load_sigproc_filterbank(
    path: str | Path,
    *,
    start_sample: int = 0,
    max_samples: int | None = None,
) -> DynamicSpectrum:
    """Read a conventional SIGPROC ``.fil`` detected-power stream.

    Supports 8/16-bit integer and 32-bit floating-point samples. Uncommon packed
    1/2/4-bit modes intentionally fail loudly rather than silently misreading data.
    """

    path = Path(path)
    header, data_offset = read_sigproc_header(path)
    nchan = int(header.get("nchans", 0))
    nifs = int(header.get("nifs", 1))
    nbits = int(header.get("nbits", 0))
    if nchan <= 0 or nifs <= 0:
        raise ValueError("SIGPROC header must define positive nchans and nifs")

    signed = bool(header.get("signed", 0))
    dtype_map: dict[tuple[int, bool], np.dtype] = {
        (8, False): np.dtype("u1"),
        (8, True): np.dtype("i1"),
        (16, False): np.dtype("<u2"),
        (16, True): np.dtype("<i2"),
        (32, False): np.dtype("<f4"),
        (32, True): np.dtype("<f4"),
    }
    dtype = dtype_map.get((nbits, signed))
    if dtype is None:
        raise ValueError(f"Unsupported SIGPROC nbits={nbits}, signed={signed}")

    frame_items = nchan * nifs
    file_bytes = path.stat().st_size - data_offset
    n_total = file_bytes // (dtype.itemsize * frame_items)
    if start_sample < 0 or start_sample >= n_total:
        raise ValueError("start_sample outside file")
    n_read = n_total - start_sample if max_samples is None else min(max_samples, n_total - start_sample)
    offset = data_offset + start_sample * frame_items * dtype.itemsize
    flat = np.memmap(path, dtype=dtype, mode="r", offset=offset, shape=(n_read * frame_items,))
    data = np.asarray(flat).reshape(n_read, nifs, nchan).astype(np.float32)

    fch1 = float(header.get("fch1", 0.0))
    foff = float(header.get("foff", 0.0))
    tsamp = float(header.get("tsamp", 0.0))
    if tsamp <= 0 or fch1 == 0.0 or foff == 0.0:
        raise ValueError("SIGPROC header missing tsamp/fch1/foff")
    frequencies_hz = (fch1 + np.arange(nchan) * foff) * 1e6

    return DynamicSpectrum(
        data=data,
        tsamp_s=tsamp,
        frequencies_hz=frequencies_hz,
        source_id=str(header.get("source_name", path.stem)),
        start_mjd=float(header["tstart"]) if "tstart" in header else None,
        metadata={"format": "sigproc", "path": str(path), "header": header},
    )


def write_sigproc_filterbank(path: str | Path, spectrum: DynamicSpectrum, nbits: int = 32) -> None:
    """Write a small standards-compatible filterbank, mainly for tests and fixtures."""

    if nbits != 32:
        raise ValueError("fixture writer currently supports nbits=32 only")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    def write_string(handle, value: str) -> None:
        encoded = value.encode("ascii")
        handle.write(struct.pack("<i", len(encoded)))
        handle.write(encoded)

    freqs_mhz = spectrum.frequencies_hz / 1e6
    foff = float(np.median(np.diff(freqs_mhz))) if spectrum.n_chan > 1 else 1.0
    fields: list[tuple[str, Any, str]] = [
        ("source_name", spectrum.source_id, "s"),
        ("data_type", 1, "i"),
        ("nchans", spectrum.n_chan, "i"),
        ("nifs", spectrum.n_pol, "i"),
        ("nbits", 32, "i"),
        ("signed", 0, "i"),
        ("tsamp", spectrum.tsamp_s, "d"),
        ("fch1", float(freqs_mhz[0]), "d"),
        ("foff", foff, "d"),
    ]
    if spectrum.start_mjd is not None:
        fields.append(("tstart", spectrum.start_mjd, "d"))

    with path.open("wb") as handle:
        write_string(handle, "HEADER_START")
        for key, value, kind in fields:
            write_string(handle, key)
            if kind == "s":
                write_string(handle, str(value))
            elif kind == "i":
                handle.write(struct.pack("<i", int(value)))
            else:
                handle.write(struct.pack("<d", float(value)))
        write_string(handle, "HEADER_END")
        handle.write(np.asarray(spectrum.data, dtype="<f4").tobytes(order="C"))


def load_psrfits_search(
    path: str | Path,
    *,
    start_subint: int = 0,
    max_subints: int | None = None,
) -> DynamicSpectrum:
    """Load conventional search-mode PSRFITS via the optional ``astropy`` package.

    The adapter supports common SUBINT layouts and applies DAT_SCL, DAT_OFFS and
    DAT_WTS. Complex observatory-specific files should be normalized with PRESTO or
    PSRCHIVE first.
    """

    try:
        from astropy.io import fits  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PSRFITS support requires: pip install 'pulsar-network-experiment[psrfits]'") from exc

    path = Path(path)
    with fits.open(path, memmap=True) as hdul:
        primary = hdul[0].header
        subint = hdul["SUBINT"]
        table = subint.data
        header = subint.header
        nchan = int(header["NCHAN"])
        npol = int(header["NPOL"])
        nsblk = int(header.get("NSBLK", 1))
        tbin = float(header["TBIN"])
        end = len(table) if max_subints is None else min(len(table), start_subint + max_subints)
        rows = table[start_subint:end]
        if len(rows) == 0:
            raise ValueError("No PSRFITS SUBINT rows selected")

        blocks: list[np.ndarray] = []
        for row in rows:
            raw = np.asarray(row["DATA"])
            if raw.size != nsblk * npol * nchan:
                raise ValueError(f"Unexpected PSRFITS DATA size {raw.size}")
            cube = raw.reshape(nsblk, npol, nchan).astype(np.float32)
            zero_offs = float(primary.get("ZERO_OFF", primary.get("ZERO_OFFS", 0.0)))
            scales = np.asarray(row["DAT_SCL"], dtype=np.float32).reshape(npol, nchan)
            offsets = np.asarray(row["DAT_OFFS"], dtype=np.float32).reshape(npol, nchan)
            weights = np.asarray(row["DAT_WTS"], dtype=np.float32).reshape(nchan)
            cube = (cube - zero_offs) * scales[None, :, :] + offsets[None, :, :]
            cube *= weights[None, None, :]
            blocks.append(cube)

        data = np.concatenate(blocks, axis=0)
        frequencies_hz = np.asarray(rows[0]["DAT_FREQ"], dtype=float) * 1e6
        source = str(primary.get("SRC_NAME", path.stem)).strip()
        imjd = primary.get("STT_IMJD")
        smjd = primary.get("STT_SMJD", 0.0)
        offs = primary.get("STT_OFFS", 0.0)
        start_mjd = None if imjd is None else float(imjd) + (float(smjd) + float(offs)) / 86400.0

    return DynamicSpectrum(
        data=data,
        tsamp_s=tbin,
        frequencies_hz=frequencies_hz,
        source_id=source,
        start_mjd=start_mjd,
        metadata={"format": "psrfits", "path": str(path)},
    )


def _stat_rows(arr: np.ndarray, max_rows: int = 16384) -> np.ndarray:
    """Deterministic row subsample for robust statistics estimation.

    Channel-level medians/MADs converge long before ~16k rows; estimating them on
    a stride subsample avoids float64 partition passes over multi-GB arrays.
    """
    n = arr.shape[0]
    if n <= max_rows:
        return arr
    stride = n // max_rows
    return arr[:: stride]


def channel_rfi_mask(data: np.ndarray, z_threshold: float = 6.0) -> np.ndarray:
    """Return True for frequency channels with robustly anomalous level or variance."""

    power = np.asarray(data, dtype=float)
    if power.ndim == 3:
        power = power.mean(axis=1)
    power = _stat_rows(power).astype(np.float32, copy=False)
    med_level = np.median(power, axis=0)
    med = np.median(med_level)
    mad = np.median(np.abs(med_level - med)) + 1e-12
    level_z = np.abs(med_level - med) / (1.4826 * mad)

    channel_mad = np.median(np.abs(power - np.median(power, axis=0)), axis=0)
    var_med = np.median(channel_mad)
    var_mad = np.median(np.abs(channel_mad - var_med)) + 1e-12
    variance_z = np.abs(channel_mad - var_med) / (1.4826 * var_mad)
    return (level_z > z_threshold) | (variance_z > z_threshold) | ~np.isfinite(med_level)


def time_sample_rfi_mask(data: np.ndarray, z_threshold: float = 8.0) -> np.ndarray:
    """Return True for time samples with robustly anomalous broadband (zero-DM) power.

    Broadband terrestrial interference is undispersed, so it appears as strong
    excursions in the frequency-averaged time series regardless of the target DM.
    A conservative default threshold avoids clipping genuine giant pulses; callers
    doing candidate work should verify flagged fractions in the report metadata.
    """

    power = np.asarray(data, dtype=float)
    if power.ndim == 3:
        power = power.mean(axis=1)
    zero_dm = power.mean(axis=1)
    sample = _stat_rows(zero_dm[:, None])[:, 0]
    med = np.median(sample)
    mad = np.median(np.abs(sample - med)) + 1e-12
    z = np.abs(zero_dm - med) / (1.4826 * mad)
    return (z > z_threshold) | ~np.isfinite(zero_dm)


def dedisperse_incoherent(
    data: np.ndarray,
    frequencies_hz: np.ndarray,
    tsamp_s: float,
    dm_pc_cm3: float,
) -> np.ndarray:
    """Integer-sample incoherent dedispersion, aligned to the highest frequency."""

    cube = np.asarray(data)
    if cube.ndim == 2:
        cube = cube[:, None, :]
    if dm_pc_cm3 == 0:
        # Zero-DM callers treat the result as read-only until they explicitly
        # copy (time-RFI replacement path); avoid duplicating multi-GB cubes.
        return cube
    freqs_mhz = np.asarray(frequencies_hz, dtype=float) / 1e6
    ref = float(np.max(freqs_mhz))
    delays_s = DISPERSION_CONSTANT_S_MHZ2 * dm_pc_cm3 * (freqs_mhz ** -2 - ref ** -2)
    shifts = np.rint(delays_s / tsamp_s).astype(int)
    max_shift = int(np.max(shifts))
    if max_shift >= cube.shape[0] - 2:
        raise ValueError("Dispersion delay exceeds observation length")
    out_len = cube.shape[0] - max_shift
    out = np.empty((out_len, cube.shape[1], cube.shape[2]), dtype=cube.dtype)
    # Group channels sharing the same integer shift: one contiguous copy per
    # distinct shift instead of one strided copy per channel.
    for shift in np.unique(shifts):
        sel = shifts == shift
        out[:, :, sel] = cube[shift : shift + out_len, :, sel]
    return out


def _robust_standardize_channels(power: np.ndarray, good: np.ndarray) -> np.ndarray:
    selected = power[:, good]
    sample = _stat_rows(selected)
    med = np.median(sample, axis=0)
    mad = np.median(np.abs(sample - med), axis=0)
    scale = 1.4826 * mad
    scale[scale < 1e-8] = 1.0
    return (selected - med) / scale


def refine_period(
    timeseries: np.ndarray,
    tsamp_s: float,
    period_s: float,
    *,
    search_fraction: float = 5e-4,
    steps: int = 201,
    n_bins: int = 256,
) -> tuple[float, float]:
    """Refine a catalog rotation period against the observation itself.

    Two-stage grid fold of the frequency-averaged time series over
    ``period_s * (1 ± search_fraction)`` followed by a 50x finer pass around the
    coarse optimum. Returns ``(best_period_s, peak_z)`` where ``peak_z`` is the
    robust z-score of the sharpest folded-profile peak. This is a registered
    preprocessing step: the metric is profile sharpness only and is blind to any
    modulation hypothesis.
    """

    ts = np.asarray(timeseries, dtype=float)
    ts = ts - np.median(ts)
    idx = np.arange(len(ts), dtype=np.float64)
    tsamp_eff = tsamp_s
    # Decimate so each trial fold works on <= ~4M points while keeping >= 8
    # samples per phase bin per rotation. Profile sharpness at 256 bins does not
    # need more; the fine stage rechecks on the same decimated series, and the
    # chosen period is exact because phases are computed analytically.
    max_points = 4_000_000
    if len(ts) > max_points:
        factor = int(np.ceil(len(ts) / max_points))
        min_per_bin = max(1, int(period_s / tsamp_s / (n_bins * 8)))
        factor = min(factor, max(1, min_per_bin)) if min_per_bin > 1 else 1
        if factor > 1:
            trim = (len(ts) // factor) * factor
            ts = ts[:trim].reshape(-1, factor).mean(axis=1)
            idx = np.arange(len(ts), dtype=np.float64)
            tsamp_eff = tsamp_s * factor

    def _peak_z(trial: float) -> float:
        p_samples = trial / tsamp_eff
        bins = ((idx / p_samples) % 1.0 * n_bins).astype(np.int64)
        counts = np.bincount(bins, minlength=n_bins)
        prof = np.bincount(bins, weights=ts, minlength=n_bins) / np.maximum(counts, 1)
        med = np.median(prof)
        mad = np.median(np.abs(prof - med)) + 1e-12
        return float((prof.max() - med) / (1.4826 * mad))

    best_period, best_z = float(period_s), -np.inf
    for fraction in (search_fraction, search_fraction / 50.0):
        center = best_period
        for trial in np.linspace(center * (1 - fraction), center * (1 + fraction), steps):
            z = _peak_z(float(trial))
            if z > best_z:
                best_period, best_z = float(trial), z
    return best_period, best_z


def extract_pulse_train(
    spectrum: DynamicSpectrum,
    *,
    period_s: float,
    dm_pc_cm3: float = 0.0,
    on_window_fraction: float = 0.08,
    rfi_z_threshold: float = 6.0,
    window_phase_offset_fraction: float = 0.0,
    time_rfi_z_threshold: float | None = None,
    refine_period_fraction: float | None = None,
    whiten_frequency: bool = False,
    _dedispersion_cache: dict | None = None,
) -> PulseTrain:
    """Convert a dynamic spectrum into one feature vector per pulsar rotation.

    This is a deliberately auditable baseline extractor. Precision work should later
    replace integer dedispersion and centroid timing with observatory-calibrated tools.
    """

    if period_s <= spectrum.tsamp_s * 4:
        raise ValueError("period must span at least four time samples")
    cache_key = (id(spectrum), float(dm_pc_cm3))
    if _dedispersion_cache is not None and cache_key in _dedispersion_cache:
        dedispersed = _dedispersion_cache[cache_key]
    else:
        dedispersed = dedisperse_incoherent(
            spectrum.data, spectrum.frequencies_hz, spectrum.tsamp_s, dm_pc_cm3
        )
        if _dedispersion_cache is not None:
            _dedispersion_cache[cache_key] = dedispersed
    rfi = channel_rfi_mask(dedispersed, z_threshold=rfi_z_threshold)
    good = ~rfi
    if np.sum(good) < max(2, spectrum.n_chan // 10):
        raise ValueError("Too many channels rejected as RFI")

    flagged_time_fraction = 0.0
    if time_rfi_z_threshold is not None:
        bad_time = time_sample_rfi_mask(dedispersed[:, :, good], z_threshold=time_rfi_z_threshold)
        flagged_time_fraction = float(np.mean(bad_time))
        if flagged_time_fraction > 0.5:
            raise ValueError("More than half of time samples flagged as broadband RFI")
        if flagged_time_fraction > 0.0:
            # Replace flagged samples with the per-channel median so pulse phase
            # alignment is preserved without injecting artificial structure.
            dedispersed = dedispersed.copy()
            channel_median = np.median(_stat_rows(dedispersed[~bad_time]), axis=0)
            dedispersed[bad_time] = channel_median

    total_power = dedispersed[:, 0, :]
    normalized = _robust_standardize_channels(total_power, good)
    timeseries = np.mean(normalized, axis=1)

    refined_peak_z = None
    if refine_period_fraction:
        period_s, refined_peak_z = refine_period(
            timeseries, spectrum.tsamp_s, period_s, search_fraction=refine_period_fraction
        )

    period_samples_f = period_s / spectrum.tsamp_s
    period_samples = int(round(period_samples_f))
    n_pulses = int(len(timeseries) / period_samples_f)
    if n_pulses < 16:
        raise ValueError("Observation contains fewer than 16 complete rotations")
    # Fractional-period phase folding. Integer-sample folding drifts by
    # (period_samples_f - period_samples) samples per rotation, which smears the
    # on-pulse window across phase for real observations where the period is not
    # an integer number of samples (e.g. B0329+54 at 349.5 us -> 2044.258).
    n_use = int(math.floor(n_pulses * period_samples_f))
    sample_idx = np.arange(n_use)
    rotation = np.floor(sample_idx / period_samples_f).astype(np.int64)
    phase = sample_idx / period_samples_f - rotation

    n_bins = min(1024, period_samples)
    bins = np.minimum((phase * n_bins).astype(np.int64), n_bins - 1)
    ts_used = timeseries[:n_use]
    bin_counts = np.bincount(bins, minlength=n_bins)
    profile = np.bincount(bins, weights=ts_used, minlength=n_bins) / np.maximum(bin_counts, 1)
    detected_peak = int(np.argmax(profile))
    peak_phase = ((detected_peak + 0.5) / n_bins + window_phase_offset_fraction) % 1.0

    half_window = max(on_window_fraction / 2.0, 1.5 / period_samples_f)
    delta = np.abs(phase - peak_phase)
    on_sel = np.minimum(delta, 1.0 - delta) <= half_window
    off_sel = ~on_sel

    def _per_rotation_mean(values: np.ndarray, selector: np.ndarray) -> np.ndarray:
        sums = np.bincount(rotation[selector], weights=values[selector], minlength=n_pulses)
        counts = np.bincount(rotation[selector], minlength=n_pulses)
        return sums / np.maximum(counts, 1)

    on_mean = _per_rotation_mean(ts_used, on_sel)
    baseline = _per_rotation_mean(ts_used, off_sel)
    amplitude = on_mean - baseline

    # Arrival-time residual: intensity-weighted mean phase offset from the peak
    # within the on-window, per rotation.
    signed_offset = phase - peak_phase
    signed_offset -= np.round(signed_offset)
    w = np.maximum(ts_used - baseline[rotation], 0.0)
    w_on = np.where(on_sel, w, 0.0)
    w_sums = np.bincount(rotation, weights=w_on, minlength=n_pulses)
    centroid_sums = np.bincount(rotation, weights=w_on * signed_offset, minlength=n_pulses)
    centroid = np.divide(centroid_sums, w_sums, out=np.zeros(n_pulses), where=w_sums > 1e-12)
    arrival_residual_s = centroid * period_s

    # Boolean per-sample selections reused by the channel/polarisation blocks.
    on_idx_bool = on_sel

    good_freqs = spectrum.frequencies_hz[good]
    on_rot = rotation[on_idx_bool]
    on_counts = np.maximum(np.bincount(on_rot, minlength=n_pulses), 1)
    stream = dedispersed[:n_use, 0, :][:, good]
    channel_power = np.zeros((n_pulses, stream.shape[1]))
    np.add.at(channel_power, on_rot, stream[on_idx_bool])
    channel_power /= on_counts[:, None]
    if whiten_frequency:
        # Registered whitening (v0.6): remove each channel's slow gain trend
        # across rotations (moving-median, window 33 rotations) before the
        # centroid. Instrumental bandpass wander varies over seconds-minutes;
        # genuine pulse-to-pulse spectral modulation survives detrending.
        from scipy.ndimage import median_filter
        window = min(33, max(3, (n_pulses // 8) | 1))
        trend = median_filter(channel_power, size=(window, 1), mode="nearest")
        channel_power = channel_power - trend
    channel_power -= np.median(channel_power, axis=1, keepdims=True)
    positive = np.maximum(channel_power, 0.0)
    freq_denom = positive.sum(axis=1)
    frequency_centroid_hz = np.divide(
        positive @ good_freqs,
        freq_denom,
        out=np.full(n_pulses, float(np.mean(good_freqs))),
        where=freq_denom > 1e-12,
    )

    polarization = np.zeros(n_pulses, dtype=float)

    def _fold_on(pol_index: int) -> np.ndarray:
        s = dedispersed[:n_use, pol_index, :][:, good].mean(axis=1)
        sums = np.bincount(on_rot, weights=s[on_idx_bool], minlength=n_pulses)
        return sums / on_counts

    if dedispersed.shape[1] >= 4:
        # Conventional I,Q,U,V ordering: retain signed circular fraction V/I.
        i_fold = _fold_on(0)
        v_fold = _fold_on(3)
        polarization = np.divide(v_fold, np.abs(i_fold), out=np.zeros_like(v_fold), where=np.abs(i_fold) > 1e-12)
        polarization = np.clip(polarization, -1.0, 1.0)
    elif dedispersed.shape[1] >= 2:
        a = _fold_on(0)
        b = _fold_on(1)
        polarization = np.divide(a - b, np.abs(a) + np.abs(b), out=np.zeros_like(a), where=(np.abs(a) + np.abs(b)) > 1e-12)

    source_id = spectrum.source_id
    return PulseTrain(
        period_s=period_s,
        amplitude=amplitude.astype(float),
        arrival_residual_s=arrival_residual_s.astype(float),
        polarization=polarization.astype(float),
        frequency_centroid_hz=frequency_centroid_hz.astype(float),
        source_id=source_id,
        metadata={
            "observation": dict(spectrum.metadata or {}),
            "start_mjd": spectrum.start_mjd,
            "tsamp_s": spectrum.tsamp_s,
            "n_channels": spectrum.n_chan,
            "n_polarizations": spectrum.n_pol,
            "dm_pc_cm3": dm_pc_cm3,
            "period_s": period_s,
            "period_samples": period_samples,
            "period_samples_fractional": period_samples_f,
            "refine_period_fraction": refine_period_fraction,
            "refined_profile_peak_z": refined_peak_z,
            "whiten_frequency": whiten_frequency,
            "fold_phase_bins": n_bins,
            "rfi_rejected_fraction": float(np.mean(rfi)),
            "time_rfi_flagged_fraction": flagged_time_fraction,
            "time_rfi_z_threshold": time_rfi_z_threshold,
            "detected_peak_phase_bin": detected_peak,
            "analysis_window_peak_phase": peak_phase,
            "window_phase_offset_fraction": window_phase_offset_fraction,
            "on_window_fraction": on_window_fraction,
        },
    )
