"""Freeze the v1.0 deep Vela batch manifest from downloaded epochs.

Includes every cached Vela 0001.0001.fil with its provenance SHA-256. The
batch spans all available multibeam epochs; batch FDR operates across the
full set. Held-out policy (registered): the LAST epoch by MJD is excluded
from the batch and reserved as the recurrence epoch for any Level-2 event.
"""
import json
import pathlib
import re

import yaml

prov: dict[str, str] = {}
for pfile in ("data/vela-provenance.json", "data/vela-offsource-provenance.json"):
    try:
        for r in json.load(open(pfile)):
            prov[pathlib.Path(r["path"]).name] = r["sha256"]
    except FileNotFoundError:
        pass
batch = json.load(open("data/vela-batch-provenance.json"))
for r in batch["records"]:
    prov[pathlib.Path(r["path"]).name] = r["sha256"]

files = sorted(p.name for p in pathlib.Path("data").glob("guppi_*_J0835-4510_*_0001.0001.fil"))
mjds = {f: int(re.match(r"guppi_(\d+)_", f).group(1)) for f in files}
held_out = max(files, key=lambda f: (mjds[f], f))
print(f"{len(files)} epochs; held out for recurrence: {held_out}")

m = {
    "experiment_id": "vela-deep-batch-v1.0",
    "seed": 20260810,
    "surrogate_count": 2048,
    "observations": [],
}
for f in files:
    if f == held_out:
        continue
    if f not in prov:
        print("WARN: no pinned sha256 for", f, "- skipping")
        continue
    beam = re.search(r"_B(\d+)_", f)
    oid = f"VELA-{mjds[f]}-B{beam.group(1) if beam else 'X'}-{f.split('_')[2]}"
    m["observations"].append({
        "id": oid,
        "path": "../../data/" + f,
        "sha256": prov[f],
        "format": "filterbank",
        "period_s": 0.0893,
        "dm_pc_cm3": 67.97,
        "refine_period_fraction": 0.002,
        "whiten_frequency": True,
        "on_window_fraction": 0.10,
        "rfi_z_threshold": 6.0,
        "time_rfi_z_threshold": 10.0,
        "offpulse_phase_offsets": [0.25, 0.50, 0.75],
        "wrong_period_fractions": [-0.02, 0.02],
        "wrong_dm_fractions": [-0.25, 0.25],
        "control_block_size": 32,
    })

out = pathlib.Path("artifacts/survey-v1.0")
out.mkdir(parents=True, exist_ok=True)
header = (
    "# Frozen v1.0 deep Vela batch - all cached multibeam epochs except the\n"
    f"# held-out recurrence epoch ({held_out}), reserved BEFORE scanning.\n"
    "# Whitening ON (Amendment 1). Thresholds: PREREGISTRATION.md, unchanged.\n"
)
(out / "manifest-vela-deep.yaml").write_text(header + yaml.dump(m, sort_keys=False), encoding="utf-8")
(out / "held-out-epoch.json").write_text(
    json.dumps({"held_out": held_out, "sha256": prov.get(held_out)}, indent=2), encoding="utf-8"
)
print(f"frozen: {out / 'manifest-vela-deep.yaml'} with {len(m['observations'])} observations")
