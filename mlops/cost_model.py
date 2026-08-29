"""中文方案的成本估算与线上 Trace 实测校准。

静态估算复用 ``cost_model_zh`` 的 DeepSeek + 千问口径；实测模式从请求 Trace 计算
token 与单轮成本的 p50/p95，用于判断估算假设是否已偏离真实流量。
"""
from __future__ import annotations

import json
import os
from collections import Counter

from mlops.cost_model_zh import COMPLETION_TOKENS, PROMPT_TOKENS, build, per_turn_breakdown


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * p
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def measured_from_traces(trace_path: str | None = None) -> dict | None:
    """读取已计量请求；没有有效样本时返回 None，避免把缺数据误报成零成本。"""
    path = trace_path or os.getenv("TRACE_PATH", "traces/requests.jsonl")
    if not os.path.exists(path):
        return None
    rows = []
    with open(path, encoding="utf-8") as source:
        for line in source:
            try:
                row = json.loads(line)
            except (json.JSONDecodeError, TypeError):
                continue
            if row.get("cost") is not None and row.get("prompt_tokens"):
                rows.append(row)
    if not rows:
        return None

    prompt = [row["prompt_tokens"] for row in rows]
    completion = [row.get("completion_tokens", 0) or 0 for row in rows]
    costs = [row["cost"] for row in rows]
    return {
        "n": len(rows),
        "prompt_tokens": {
            "p50": round(_percentile(prompt, 0.5)),
            "p95": round(_percentile(prompt, 0.95)),
        },
        "completion_tokens": {
            "p50": round(_percentile(completion, 0.5)),
            "p95": round(_percentile(completion, 0.95)),
        },
        "cost_per_turn": {
            "p50": round(_percentile(costs, 0.5), 6),
            "p95": round(_percentile(costs, 0.95), 6),
            "mean": round(sum(costs) / len(costs), 6),
        },
        "models": dict(Counter(row.get("model") for row in rows)),
    }


def estimate_vs_measured(trace_path: str | None = None, tolerance: float = 0.25) -> dict:
    measured = measured_from_traces(trace_path)
    if measured is None:
        return {"measured": None, "note": "尚无计量请求，请先产生真实流量"}

    def deviation(assumed: float, actual: float | None) -> float | None:
        return None if not actual else round((actual - assumed) / assumed, 3)

    prompt_delta = deviation(PROMPT_TOKENS, measured["prompt_tokens"]["p50"])
    completion_delta = deviation(COMPLETION_TOKENS, measured["completion_tokens"]["p50"])
    flags = []
    if prompt_delta is not None and abs(prompt_delta) > tolerance:
        flags.append("prompt_tokens assumption {} off by {:+.0%}".format(
            PROMPT_TOKENS, prompt_delta))
    if completion_delta is not None and abs(completion_delta) > tolerance:
        flags.append("completion_tokens assumption {} off by {:+.0%}".format(
            COMPLETION_TOKENS, completion_delta))
    return {
        "measured": measured,
        "assumptions": {
            "prompt_tokens": PROMPT_TOKENS,
            "completion_tokens": COMPLETION_TOKENS,
        },
        "prompt_tokens_off_by": prompt_delta,
        "completion_tokens_off_by": completion_delta,
        "flags": flags,
    }


def text_turn_cost() -> dict:
    """兼容统一成本入口，返回中文生产方案的单轮明细。"""
    return per_turn_breakdown()


if __name__ == "__main__":
    report = build()
    report["measured_vs_estimate"] = estimate_vs_measured()
    output = "domains/china_ecommerce/eval/reports/cost_model_zh.json"
    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, "w", encoding="utf-8") as target:
        json.dump(report, target, indent=2, ensure_ascii=False)
    print(json.dumps(report, indent=2, ensure_ascii=False))
