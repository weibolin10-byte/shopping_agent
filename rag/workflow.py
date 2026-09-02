"""Deterministic fast-path versus corrective LangGraph selection."""
from __future__ import annotations

import re

from pipeline.text import lexical_units
from rag.router import route

_CONFLICT = re.compile(r"(说法|信息|数据|结果).{0,8}(不一致|冲突|矛盾)|到底哪个|"
                       r"conflicting|contradict|inconsistent", re.I)


def workflow_for(query: str, history: list[dict] | None = None) -> tuple[str, str]:
    """Select graph only for genuine hard-tail correction; common turns remain fast."""
    decision = route(query, history=history, small_llm=None)
    if decision.tasks:
        return "omni", "deterministic multi-intent fan-out"
    if decision.lane in ("care", "complaint", "escalation"):
        return "omni", "deterministic protected workflow"
    if _CONFLICT.search(query or ""):
        return "graph", "explicit evidence conflict"
    if decision.lane == "answers" and len(lexical_units(query)) > 40:
        return "graph", "long weakly-routed hard-tail query"
    return "omni", "single-intent fast path"
