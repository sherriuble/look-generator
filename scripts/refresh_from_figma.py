#!/usr/bin/env python3
"""
One-shot: download latest Figma file → extract wardrobe JSON → export PNGs.

Token resolution (first match wins):
  1. FIGMA_TOKEN or FIGMA_API_KEY in the environment
  2. Path in FIGMA_TOKEN_FILE
  3. Project file .figma_token (single line, no newline issues)

  echo 'figd_your_token' > .figma_token   # gitignored

Usage:
  python3 scripts/refresh_from_figma.py
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def resolve_token():
    t = os.environ.get("FIGMA_TOKEN") or os.environ.get("FIGMA_API_KEY")
    if t:
        return t.strip()
    path = os.environ.get("FIGMA_TOKEN_FILE")
    if path:
        p = Path(path).expanduser()
        if p.is_file():
            return p.read_text(encoding="utf-8").strip().splitlines()[0].strip()
    p = ROOT / ".figma_token"
    if p.is_file():
        return p.read_text(encoding="utf-8").strip().splitlines()[0].strip()
    return None


def main():
    token = resolve_token()
    if not token:
        print(
            "No Figma token found.\n"
            "  • export FIGMA_TOKEN=figd_...\n"
            "  • or create FitMaker/.figma_token with one line (your PAT)\n",
            file=sys.stderr,
        )
        sys.exit(1)

    env = os.environ.copy()
    env["FIGMA_TOKEN"] = token

    steps = [
        (sys.executable, str(ROOT / "scripts" / "fetch_figma_file.py")),
        (sys.executable, str(ROOT / "scripts" / "extract_figma_wardrobe.py")),
        (sys.executable, str(ROOT / "scripts" / "export_figma_images.py")),
    ]
    for cmd in steps:
        print("→", " ".join(cmd))
        r = subprocess.run(cmd, cwd=ROOT, env=env)
        if r.returncode != 0:
            sys.exit(r.returncode)

    cmp = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "compare_figma_to_data.py")],
        cwd=ROOT,
    )
    sys.exit(cmp.returncode)


if __name__ == "__main__":
    main()
