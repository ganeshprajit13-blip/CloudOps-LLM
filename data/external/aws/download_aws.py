"""One-time script to download aws-samples/sample-rca-deep-investigations."""
import urllib.request
import os

url = "https://github.com/aws-samples/sample-rca-deep-investigations/archive/refs/heads/main.zip"
out = os.path.join(os.path.dirname(__file__), "aws-sample-rca-deep-investigations-main.zip")

print(f"Trying: {url}")
try:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    with open(out, "wb") as f:
        f.write(data)
    print(f"OK: {len(data)} bytes saved to {out}")
except Exception as e:
    print(f"FAILED: {e}")
