#!/usr/bin/env python3
"""Synchronize README metrics with the one canonical evaluation report."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evaluation.readme_metrics import sync_readme  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    ok = sync_readme(ROOT / "README.md",
                     ROOT / "domains/china_ecommerce/eval/reports/current.json",
                     check=args.check)
    if args.check and not ok:
        print("README metrics are stale; run scripts/update_readme_metrics.py")
        return 1
    print("README metrics match current.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
