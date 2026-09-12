"""Download LEMMA-RCA baselines code repository from GitHub."""
import urllib.request
import os

url = "https://github.com/KnowledgeDiscovery/rca_baselines/archive/refs/heads/main.zip"
out_dir = os.path.dirname(os.path.abspath(__file__))
out = os.path.join(out_dir, "lemma-rca-baselines-main.zip")

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
