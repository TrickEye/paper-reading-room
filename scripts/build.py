#!/usr/bin/env python3
"""Rebuild paper pages from local data, then validate the publication directory."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    catalog = json.loads((ROOT / "data/catalog.json").read_text(encoding="utf-8"))
    # ACE is a maintained HTML reference; other builders reuse its reader shell.
    for paper in catalog:
        if paper["builder"]:
            subprocess.run(
                [sys.executable, "-B", str(ROOT / "scripts/builders" / paper["builder"])],
                cwd=ROOT, env=env, check=True,
            )
    subprocess.run(
        [sys.executable, "-B", str(ROOT / "scripts/check.py")],
        cwd=ROOT, env=env, check=True,
    )


if __name__ == "__main__":
    main()
