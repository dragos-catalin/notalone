"""List HTR files in a BL session directory (looks for OFF/blank-sky scans)."""
import re
import sys
import urllib.request

url = sys.argv[1] if len(sys.argv) > 1 else "https://bldata.berkeley.edu/pipeline/AGBT17A_999_02/holding/"
req = urllib.request.Request(url, headers={"User-Agent": "pulsarnet/0.9"})
html = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", errors="replace")
names = sorted(set(re.findall(r'href="([^"]*?8\.0001\.h5)"', html)))
print(f"{len(names)} HTR files at {url}")
for n in names:
    print(" ", n)
