#!/usr/bin/env python3
"""Routing model-selection ablation for the Chinese e-commerce domain.

Compares small vs large models *within the same model family* (Qwen) for the
tie-break routing task, mirroring the source project's 8B vs 70B ablation:

  1. deterministic      — regex only, zero LLM calls, zero cost
  2. qwen-turbo (small) — cheap, fast model resolves ambiguous turns
  3. qwen-plus  (large) — bigger, more capable model resolves the same turns

After evaluation the script recomputes tiebreak_cost_usd with the correct
Qwen pricing (the framework's built-in constants use Groq 8B USD prices).

Pricing (CNY per 1M tokens, China mainland):
  qwen-turbo : input ¥0.3,  output ¥0.6
  qwen-plus  : input ¥0.8,  output ¥2.0
Source: https://help.aliyun.com/zh/model-studio/qwen-model-billing-notice

Run:
    cd <project-root>
    PYTHONPATH=. ~/.local/bin/uv run python scripts/run_routing_ablation_zh.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

from adapters.openai_compat import OpenAICompatClient  # noqa: E402
from evaluation.agent_eval import evaluate_routing, load_cases  # noqa: E402

# ── paths ────────────────────────────────────────────────────────────────────
DOMAIN_PACK = os.path.join("domains", "china_ecommerce")
CASES_PATH = os.path.join(DOMAIN_PACK, "eval", "routing.jsonl")
ABLATION_OUT = os.path.join(DOMAIN_PACK, "eval", "reports",
                            "routing_ablation_zh.json")
FULL_EVAL_PATH = os.path.join(DOMAIN_PACK, "eval", "reports", "full_eval.json")

# ── pricing (CNY per 1M tokens → USD at ¥7.2/$) ─────────────────────────────
USD_CNY = 7.2

PRICING_CNY = {
    "qwen-turbo": {"input": 0.3, "output": 0.6},   # small model
    "qwen-plus":  {"input": 0.8, "output": 2.0},   # large model
}
PRICING_USD = {
    model: {
        "input": round(p["input"] / USD_CNY, 4),
        "output": round(p["output"] / USD_CNY, 4),
    }
    for model, p in PRICING_CNY.items()
}

# Per-call token estimate (matches the framework's conservative estimate).
TIEBREAK_INPUT_TOKENS = 80
TIEBREAK_OUTPUT_TOKENS = 12


def _make_qwen_client(model: str) -> OpenAICompatClient:
    """Create an OpenAICompatClient pointing at DashScope for a given Qwen model."""
    api_key = (os.getenv("OPENAI_COMPAT_SMALL_API_KEY")
               or os.getenv("DASHSCOPE_API_KEY")
               or os.getenv("OPENAI_COMPAT_API_KEY", ""))
    base_url = (os.getenv("OPENAI_COMPAT_SMALL_BASE_URL")
                or "https://dashscope.aliyuncs.com/compatible-mode/v1")
    return OpenAICompatClient(model=model, api_key=api_key, base_url=base_url)


def _recompute_cost(scorecard: dict, price_in: float, price_out: float) -> dict:
    """Overwrite tiebreak_cost_usd with the correct per-model figure."""
    calls = scorecard["tiebreak_calls"]
    cost = calls * (
        TIEBREAK_INPUT_TOKENS / 1e6 * price_in
        + TIEBREAK_OUTPUT_TOKENS / 1e6 * price_out
    )
    scorecard["tiebreak_cost_usd"] = round(cost, 6)
    return scorecard


def _print_table(scorecards: list[dict]) -> None:
    header = (
        f"{'mode':<24} {'acc':>6} {'det%':>6} {'tb':>4} "
        f"{'tb_cost':>10} {'esc_p':>6} {'esc_r':>6}"
    )
    print("\n" + "=" * len(header))
    print(header)
    print("-" * len(header))
    for sc in scorecards:
        print(
            f"{sc['mode']:<24} "
            f"{sc['accuracy']:>6.4f} "
            f"{sc['deterministic_decision_rate']:>6.2%} "
            f"{sc['tiebreak_calls']:>4d} "
            f"${sc['tiebreak_cost_usd']:>9.6f} "
            f"{sc['escalation']['precision']:>6.4f} "
            f"{sc['escalation']['recall']:>6.4f}"
        )
    print("=" * len(header) + "\n")


def main() -> int:
    # ── load cases ──────────────────────────────────────────────────────────
    cases = load_cases(CASES_PATH)
    print(f"Loaded {len(cases)} routing cases from {CASES_PATH}")

    # ── 1. deterministic (no LLM) ───────────────────────────────────────────
    print("Running deterministic routing …")
    sc_det = evaluate_routing(cases)
    sc_det = _recompute_cost(sc_det, 0.0, 0.0)

    # ── 2. qwen-turbo (small model) tiebreak ────────────────────────────────
    print("Running qwen-turbo (small) tiebreak …")
    small = _make_qwen_client("qwen-turbo")
    sc_small = evaluate_routing(
        cases, small_llm=small, mode="tiebreak_qwen_turbo"
    )
    sc_small = _recompute_cost(
        sc_small,
        PRICING_USD["qwen-turbo"]["input"],
        PRICING_USD["qwen-turbo"]["output"],
    )

    # ── 3. qwen-plus (large model) tiebreak ─────────────────────────────────
    print("Running qwen-plus (large) tiebreak …")
    large = _make_qwen_client("qwen-plus")
    sc_large = evaluate_routing(
        cases, small_llm=large, mode="tiebreak_qwen_plus"
    )
    sc_large = _recompute_cost(
        sc_large,
        PRICING_USD["qwen-plus"]["input"],
        PRICING_USD["qwen-plus"]["output"],
    )

    scorecards = [sc_det, sc_small, sc_large]
    _print_table(scorecards)

    # ── per-stratum breakdown ───────────────────────────────────────────────
    print("Per-stratum accuracy:")
    strata = sorted({s for sc in scorecards for s in sc.get("by_stratum", {})})
    hdr = (f"{'stratum':<14}"
           + "".join(f"{sc['mode']:>24}" for sc in scorecards))
    print(hdr)
    print("-" * len(hdr))
    for st in strata:
        row = f"{st:<14}"
        for sc in scorecards:
            v = sc.get("by_stratum", {}).get(st)
            row += f"{v if v is not None else '—':>24}"
        print(row)
    print()

    # ── finding ─────────────────────────────────────────────────────────────
    small_acc = sc_small["accuracy"]
    large_acc = sc_large["accuracy"]
    small_cost = sc_small["tiebreak_cost_usd"]
    large_cost = sc_large["tiebreak_cost_usd"]
    cost_ratio = (large_cost / small_cost) if small_cost > 0 else float("inf")

    if small_acc >= large_acc:
        finding = (
            f"The small model (qwen-turbo) matches or exceeds the large model "
            f"(qwen-plus) on routing accuracy ({small_acc:.1%} vs {large_acc:.1%}) "
            f"at {cost_ratio:.1f}x lower cost. A bigger model is not worth it "
            f"for classification — the cheap model is the right choice for "
            f"production tie-break routing."
        )
    else:
        finding = (
            f"The large model (qwen-plus) achieves {large_acc:.1%} vs the small "
            f"model's {small_acc:.1%}, but at {cost_ratio:.1f}x the cost "
            f"(${large_cost:.6f} vs ${small_cost:.6f})."
        )
    print(f"Finding: {finding}\n")

    # ── assemble output ─────────────────────────────────────────────────────
    result = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "domain": "china_ecommerce",
        "n_cases": len(cases),
        "model_family": "Qwen (Alibaba Cloud)",
        "pricing_cny_per_1m": PRICING_CNY,
        "pricing_usd_per_1m": PRICING_USD,
        "usd_cny_rate": USD_CNY,
        "tiebreak_token_estimate": {
            "input": TIEBREAK_INPUT_TOKENS,
            "output": TIEBREAK_OUTPUT_TOKENS,
        },
        "routing": {
            "deterministic": sc_det,
            "tiebreak_qwen_turbo": sc_small,
            "tiebreak_qwen_plus": sc_large,
        },
        "finding": finding,
    }

    os.makedirs(os.path.dirname(ABLATION_OUT), exist_ok=True)
    with open(ABLATION_OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"Saved ablation report → {ABLATION_OUT}")

    # ── update full_eval.json ───────────────────────────────────────────────
    full_eval: dict = {}
    if os.path.isfile(FULL_EVAL_PATH):
        with open(FULL_EVAL_PATH, encoding="utf-8") as f:
            full_eval = json.load(f)
    full_eval["routing"] = result["routing"]
    with open(FULL_EVAL_PATH, "w", encoding="utf-8") as f:
        json.dump(full_eval, f, indent=2, ensure_ascii=False)
    print(f"Updated routing section in → {FULL_EVAL_PATH}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
