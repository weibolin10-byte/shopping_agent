#!/usr/bin/env python3
"""Compare two same-version canonical reports and optionally persist the result."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evaluation.repeatability import compare_report_files  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_a", type=Path)
    parser.add_argument("run_b", type=Path)
    parser.add_argument("--max-delta", type=float, default=0.02)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = compare_report_files(args.run_a, args.run_b,
                                  max_absolute_delta=args.max_delta)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if result["stable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
