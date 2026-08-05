"""Fetch all remaining Vela 0001.0001.fil epochs for the v1.0 batch survey."""
import json
import urllib.parse
import urllib.request
from pathlib import Path

from pulsarnet.acquisition import download_with_provenance

API = "http://seti.berkeley.edu/opendata/api/query-files"
params = urllib.parse.urlencode({"target": "J0835-4510", "limit": 200})
req = urllib.request.Request(f"{API}?{params}", headers={"User-Agent": "pulsarnet/1.0"})
rows = json.load(urllib.request.urlopen(req, timeout=60)).get("data", [])
urls = sorted({r["url"] for r in rows if r["url"].endswith("0001.0001.fil")})
print(f"{len(urls)} total Vela filterbanks in archive")

have = {p.name for p in Path("data").glob("*.fil")}
records = []
failures = []
for url in urls:
    name = url.rsplit("/", 1)[-1]
    if name in have:
        print("skip (cached):", name)
        continue
    try:
        rec = download_with_provenance(url, f"data/{name}", progress_every_s=30)
        records.append(rec)
        print("OK", name, rec["sha256"][:16])
    except Exception as exc:  # noqa: BLE001 — continue past dead mirrors
        failures.append({"url": url, "error": str(exc)})
        print("FAIL", name, str(exc)[:100])

json.dump({"records": records, "failures": failures},
          open("data/vela-batch-provenance.json", "w"), indent=2)
print(f"downloaded {len(records)}, failed {len(failures)}")
