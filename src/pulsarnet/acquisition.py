"""Public-archive data acquisition with provenance for the real-data pilot.

Currently supports the Breakthrough Listen Open Data Archive
(http://seti.berkeley.edu/opendata), which serves GBT/Parkes dynamic spectra as
HDF5/filterbank products over plain HTTPS. High-time-resolution products
(``*.0002.h5``) preserve individual rotations for bright slow pulsars.

Every download records URL, size, SHA-256 and retrieval time so a frozen
manifest can pin the exact bytes analyzed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import json
import time
import urllib.parse
import urllib.request

from .experiment import sha256_file

BL_API = "http://seti.berkeley.edu/opendata/api/query-files"
_USER_AGENT = "pulsar-network-experiment/0.4 (archival research pipeline)"


@dataclass(slots=True)
class ArchiveFile:
    url: str
    target_name: str
    size_bytes: int
    file_type: str
    telescope: str | None = None
    center_freq_mhz: float | None = None
    extra: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def query_breakthrough_listen(target: str, limit: int = 100) -> list[ArchiveFile]:
    """List public Breakthrough Listen files for a named target."""
    params = urllib.parse.urlencode({"target": target, "limit": limit})
    request = urllib.request.Request(f"{BL_API}?{params}", headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.load(response)
    rows = payload.get("data") or payload.get("result") or []
    files: list[ArchiveFile] = []
    for row in rows:
        if not row.get("url"):
            continue
        known = {"url", "target_name", "size", "file_type", "telescope", "center_freq"}
        files.append(
            ArchiveFile(
                url=str(row["url"]),
                target_name=str(row.get("target_name", target)),
                size_bytes=int(row.get("size", 0)),
                file_type=str(row.get("file_type", "")),
                telescope=row.get("telescope"),
                center_freq_mhz=row.get("center_freq"),
                extra={k: v for k, v in row.items() if k not in known},
            )
        )
    return files


def download_with_provenance(
    url: str,
    dest: str | Path,
    *,
    expected_sha256: str | None = None,
    chunk_bytes: int = 4 * 1024 * 1024,
    progress_every_s: float = 10.0,
) -> dict[str, Any]:
    """Download ``url`` to ``dest`` and return a provenance record.

    Existing complete files are verified rather than re-downloaded. Partial files
    are resumed with an HTTP Range request when the server supports it. If
    ``expected_sha256`` is provided the download fails loudly on mismatch.
    """

    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")

    head = urllib.request.Request(url, method="HEAD", headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(head, timeout=60) as response:
        total = int(response.headers.get("Content-Length", 0))
        accept_ranges = "bytes" in (response.headers.get("Accept-Ranges") or "")

    if dest.exists() and (total == 0 or dest.stat().st_size == total):
        digest = sha256_file(dest)
        if expected_sha256 and digest != expected_sha256:
            raise ValueError(f"SHA-256 mismatch for existing {dest}: {digest} != {expected_sha256}")
        return _provenance(url, dest, digest, total, resumed=False, cached=True)

    offset = part.stat().st_size if (part.exists() and accept_ranges) else 0
    headers = {"User-Agent": _USER_AGENT}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    request = urllib.request.Request(url, headers=headers)
    mode = "ab" if offset else "wb"
    started = last_report = time.monotonic()
    written = offset
    with urllib.request.urlopen(request, timeout=120) as response, part.open(mode) as handle:
        while chunk := response.read(chunk_bytes):
            handle.write(chunk)
            written += len(chunk)
            now = time.monotonic()
            if now - last_report >= progress_every_s:
                pct = f"{100.0 * written / total:.1f}%" if total else f"{written / 1e6:.0f} MB"
                print(f"  {dest.name}: {pct} ({written / max(1e-9, now - started) / 1e6:.1f} MB/s)")
                last_report = now

    if total and part.stat().st_size != total:
        raise IOError(f"Incomplete download: {part.stat().st_size} of {total} bytes")
    part.replace(dest)
    digest = sha256_file(dest)
    if expected_sha256 and digest != expected_sha256:
        raise ValueError(f"SHA-256 mismatch for {dest}: {digest} != {expected_sha256}")
    return _provenance(url, dest, digest, total or dest.stat().st_size, resumed=bool(offset), cached=False)


def _provenance(url: str, dest: Path, sha256: str, size: int, *, resumed: bool, cached: bool) -> dict[str, Any]:
    return {
        "url": url,
        "path": str(dest),
        "sha256": sha256,
        "size_bytes": int(size),
        "retrieved_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "resumed": resumed,
        "cached": cached,
    }


def fetch_manifest_inputs(manifest: dict[str, Any], data_dir: str | Path) -> list[dict[str, Any]]:
    """Download every observation input declared with a ``url`` in a manifest.

    Rewrites each entry's ``path`` to the local file and cross-checks the pinned
    ``sha256`` when present. Returns the list of provenance records.
    """

    data_dir = Path(data_dir)
    records: list[dict[str, Any]] = []
    for entry in manifest.get("observations", []):
        url = entry.get("url")
        if not url:
            continue
        filename = entry.get("filename") or Path(urllib.parse.urlparse(url).path).name
        record = download_with_provenance(url, data_dir / filename, expected_sha256=entry.get("sha256"))
        entry["path"] = record["path"]
        records.append(record)
    return records
