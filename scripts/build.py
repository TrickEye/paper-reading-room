#!/usr/bin/env python3
"""Rebuild paper pages from local data, then validate the publication directory."""
import json
import os
from pathlib import Path
import subprocess
import sys
import argparse

from paper_document import emit_paper, publish

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview', action='store_true', help='Build parallel preview without replacing existing paper pages')
    args = parser.parse_args()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    catalog = json.loads((ROOT / "data/catalog.json").read_text(encoding="utf-8"))
    emit_paper('ace', (ROOT / 'data/ace/article.html').read_text(),
               json.loads((ROOT / 'data/ace/toc.json').read_text()))
    for paper in catalog:
        if paper["builder"]:
            subprocess.run(
                [sys.executable, "-B", str(ROOT / "scripts/builders" / paper["builder"])],
                cwd=ROOT, env=env, check=True,
            )
    publish(preview=args.preview)
    subprocess.run(
        [sys.executable, "-B", str(ROOT / "scripts/check.py")],
        cwd=ROOT, env=env, check=True,
    )


if __name__ == "__main__":
    main()
