"""Fetch two same-session GBT blank-sky (OFF cadence) scans for v0.9."""
import json
from pulsarnet.acquisition import download_with_provenance

BASE = "https://bldata.berkeley.edu/pipeline/AGBT17A_999_02/holding/"
FILES = [
    "spliced_blc0001020304050607_guppi_57792_05013_HIP20369_0039.gpuspec.8.0001.h5",
    "spliced_blc0001020304050607_guppi_57792_05723_HIP20482_0041.gpuspec.8.0001.h5",
]
records = []
for name in FILES:
    rec = download_with_provenance(BASE + name, "data/" + name)
    records.append(rec)
    print("OK", name, rec["sha256"])
json.dump(records, open("data/offsource-provenance.json", "w"), indent=2)
