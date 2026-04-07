#!/usr/bin/env python3
"""
Download the full Figma file JSON (same shape as File → Save local copy for plugins).

Writes project root `figma_raw.json` and is what `scripts/extract_figma_wardrobe.py` expects.

Usage:
  export FIGMA_TOKEN=figd_...
  python3 scripts/fetch_figma_file.py

Optional env:
  FIGMA_FILE_KEY   default: fjctaZ8WnOnMwH9JcMEjyc (Anya's Wardrobe)
  FIGMA_OUT        default: figma_raw.json (relative to project root)

Then run:
  python3 scripts/extract_figma_wardrobe.py

Warning: re-extracting overwrites data/items.json, data/clusters.json, data/top_matches.json
from the Catalog + Looks pages — any hand-edited outfit rules will be replaced.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILE_KEY = os.environ.get("FIGMA_FILE_KEY", "fjctaZ8WnOnMwH9JcMEjyc")
OUT_NAME = os.environ.get("FIGMA_OUT", "figma_raw.json")


def main():
    token = os.environ.get("FIGMA_TOKEN") or os.environ.get("FIGMA_API_KEY")
    if not token:
        print(
            "Missing FIGMA_TOKEN or FIGMA_API_KEY.\n"
            "  export FIGMA_TOKEN=your_personal_access_token\n"
            "  python3 scripts/fetch_figma_file.py\n",
            file=sys.stderr,
        )
        sys.exit(1)

    url = f"https://api.figma.com/v1/files/{FILE_KEY}"
    req = urllib.request.Request(url, headers={"X-Figma-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        print(f"HTTP {e.code}: {body[:800]}", file=sys.stderr)
        sys.exit(1)

    out_path = ROOT / OUT_NAME
    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    name = data.get("name", "?")
    last = data.get("lastModified", "?")
    pages = [c.get("name") for c in (data.get("document") or {}).get("children") or []]
    print(f"Wrote {out_path}")
    print(f"  file: {name}")
    print(f"  lastModified: {last}")
    print(f"  pages: {', '.join(pages)}")


if __name__ == "__main__":
    main()
