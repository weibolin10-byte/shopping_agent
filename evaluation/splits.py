"""Leak-resistant deterministic development, regression and frozen evaluation splits."""
from __future__ import annotations

import hashlib

SPLITS = ("dev", "regression", "frozen")


def split_name(item_id: str, *, salt: str = "shopping-agent-v1") -> str:
    bucket = int(hashlib.sha256(f"{salt}:{item_id}".encode()).hexdigest()[:8], 16) % 100
    if bucket < 60:
        return "dev"
    if bucket < 80:
        return "regression"
    return "frozen"


def split_cases(cases: list[dict], *, salt: str = "shopping-agent-v1") -> dict[str, list[dict]]:
    out = {name: [] for name in SPLITS}
    for index, case in enumerate(cases):
        item_id = str(case.get("id") or case.get("question") or index)
        name = split_name(item_id, salt=salt)
        out[name].append({**case, "split": name})
    return out
