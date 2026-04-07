#!/usr/bin/env python3
"""Deprecated: use scripts/refresh_from_figma.py (fetch + extract + images + compare)."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "refresh_from_figma.py")], cwd=ROOT)
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
