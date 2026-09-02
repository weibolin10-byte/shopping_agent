#!/usr/bin/env python3
"""Validate a generation JSONL file and print its coverage before model calls."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evaluation.generation_set import generation_set_summary, load_generation_set  # noqa: E402

DEFAULT_PATH = ROOT / "domains" / "china_ecommerce" / "eval" / "generation_candidates.jsonl"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--require-approved", action="store_true")
    args = parser.parse_args()
    rows = load_generation_set(args.path, require_approved=args.require_approved)
    print(json.dumps(generation_set_summary(rows), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
