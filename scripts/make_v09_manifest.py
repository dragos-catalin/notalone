"""Freeze the v0.9 off-source validation manifest (UTF-8, ASCII-safe)."""
import json
import pathlib
import yaml

# Off-source scans: HIP star-field pointings from the SAME GBT session/backend
# as the B0329+54 and Crab observations (AGBT17A_999_02, MJD 57792). No pulsar
# in the beam. They are analyzed AS IF they were the Crab: folded at the Crab
# period/DM. Registered expectation, declared before scanning:
#   EXPECTED: no Level-1 anomaly. Any structure that appears validates that
#   residual backend artifacts (e.g. the lag-400+ slow gain wander) exist
#   independently of the pulsar, completing the artifact attribution.
recs = {r["path"].split("\\")[-1]: r["sha256"]
        for r in json.load(open("data/offsource-provenance.json"))}

files = [
    ("OFFSRC-HIP20369-0039", "spliced_blc0001020304050607_guppi_57792_05013_HIP20369_0039.gpuspec.8.0001.h5"),
    ("OFFSRC-HIP20482-0041", "spliced_blc0001020304050607_guppi_57792_05723_HIP20482_0041.gpuspec.8.0001.h5"),
]
m = {
    "experiment_id": "gbt-offsource-validation-v0.9",
    "seed": 20260809,
    "surrogate_count": 2048,
    "observations": [],
}
for oid, fn in files:
    m["observations"].append({
        "id": oid,
        "path": "../../data/" + fn,
        "sha256": recs[fn],
        "format": "hdf5",
        "period_s": 0.0337204,       # Crab fold applied to blank sky
        "dm_pc_cm3": 56.77,
        "refine_period_fraction": None,  # nothing to refine on blank sky
        "whiten_frequency": True,
        "on_window_fraction": 0.10,
        "rfi_z_threshold": 6.0,
        "time_rfi_z_threshold": 10.0,
        "offpulse_phase_offsets": [0.25, 0.50, 0.75],
        "wrong_period_fractions": [-0.02, 0.02],
        "wrong_dm_fractions": [-0.25, 0.25],
        "control_block_size": 32,
    })

out = pathlib.Path("artifacts/survey-v0.9")
out.mkdir(parents=True, exist_ok=True)
header = (
    "# Frozen v0.9 manifest - true off-source (blank-sky) validation.\n"
    "# HIP star-field scans from the SAME session/backend as the Crab data,\n"
    "# folded at the Crab ephemeris. Registered expectation: NULL. Any\n"
    "# structure found is instrument-only and completes artifact attribution.\n"
)
(out / "manifest-offsource.yaml").write_text(
    header + yaml.dump(m, sort_keys=False), encoding="utf-8"
)
print("frozen: artifacts/survey-v0.9/manifest-offsource.yaml")
