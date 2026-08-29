#!/usr/bin/env python3
"""Cost model for the Chinese e-commerce Agentic RAG deployment.

Evaluates the cost of the *selected production architecture* only:
  - Generation LLM:  deepseek-chat (DeepSeek V3)
  - Routing:         deterministic regex (100% on Chinese eval set, zero LLM cost)
  - Embedding:       qwen text-embedding-v3 (1024-dim)
  - Reranker:        none (RERANK_PROVIDER=none)

The only comparison point is against a human customer-service agent,
which is the operational alternative the AI system replaces.

Pricing sources:
  DeepSeek V3:  $0.27 / $1.10 per 1M tokens  (howmanytokens.io)
  Qwen embed:   ¥0.7 per 1M tokens           (Alibaba Cloud Model Studio)
  Human agent:  ¥30/hour ≈ $4.17/hour        (domestic customer-service rate)

Run:
    cd <project-root>
    PYTHONPATH=. ~/.local/bin/uv run python -m mlops.cost_model_zh
"""
from __future__ import annotations

import json
import os

# ── Selected production stack ────────────────────────────────────────────────
GEN_MODEL = "deepseek-chat"
EMBED_MODEL = "qwen-text-embedding-v3"

# Prices in USD per 1M tokens
GEN_PRICE_IN = 0.27       # deepseek-chat input
GEN_PRICE_OUT = 1.10      # deepseek-chat output
EMBED_PRICE_PER_1M = 0.097  # qwen text-embedding-v3 (¥0.7 ÷ 7.2)
RERANK_COST = 0.0         # RERANK_PROVIDER=none

# ── Routing ──────────────────────────────────────────────────────────────────
# Deterministic regex achieves 100% on the 33-case Chinese routing set,
# so tie-break LLM calls are never needed in production.
ROUTING_COST = 0.0

# ── Human agent comparison ───────────────────────────────────────────────────
HUMAN_CNY_PER_HOUR = 30.0
USD_CNY_RATE = 7.2
HUMAN_USD_PER_HOUR = round(HUMAN_CNY_PER_HOUR / USD_CNY_RATE, 2)  # ~$4.17
HUMAN_AVG_MINUTES = 4.0     # average handling time per turn

# ── Per-turn usage assumptions ───────────────────────────────────────────────
PROMPT_TOKENS = 1500       # retrieved context + conversation history + system prompt
COMPLETION_TOKENS = 250    # concise answer
QUERY_EMBED_TOKENS = 25    # user query → one embedding call
SESSION_TURNS = 8          # average turns per shopping session


def _generation_cost() -> float:
    return (PROMPT_TOKENS / 1e6 * GEN_PRICE_IN
            + COMPLETION_TOKENS / 1e6 * GEN_PRICE_OUT)


def _embedding_cost() -> float:
    return QUERY_EMBED_TOKENS / 1e6 * EMBED_PRICE_PER_1M


def per_turn_breakdown() -> dict:
    """Full text-turn cost breakdown for the selected stack."""
    gen = _generation_cost()
    emb = _embedding_cost()
    total = ROUTING_COST + emb + RERANK_COST + gen
    return {
        "routing": round(ROUTING_COST, 6),
        "embedding": round(emb, 6),
        "rerank": round(RERANK_COST, 6),
        "generation": round(gen, 6),
        "total": round(total, 6),
    }


def human_per_turn() -> float:
    return round(HUMAN_AVG_MINUTES / 60 * HUMAN_USD_PER_HOUR, 4)


def build() -> dict:
    ai_turn = per_turn_breakdown()
    human_turn = human_per_turn()
    ai_session = round(ai_turn["total"] * SESSION_TURNS, 4)
    human_session = round(human_turn * SESSION_TURNS, 4)
    cost_ratio = round(human_turn / ai_turn["total"], 1) if ai_turn["total"] else None

    return {
        "stack": {
            "generation": GEN_MODEL,
            "routing": "deterministic regex",
            "embedding": EMBED_MODEL,
            "reranker": "none",
        },
        "assumptions": {
            "prompt_tokens": PROMPT_TOKENS,
            "completion_tokens": COMPLETION_TOKENS,
            "query_embed_tokens": QUERY_EMBED_TOKENS,
            "session_turns": SESSION_TURNS,
            "usd_cny_rate": USD_CNY_RATE,
            "human_cny_per_hour": HUMAN_CNY_PER_HOUR,
            "human_avg_minutes_per_turn": HUMAN_AVG_MINUTES,
        },
        "pricing_usd_per_1m": {
            GEN_MODEL: {"input": GEN_PRICE_IN, "output": GEN_PRICE_OUT},
            EMBED_MODEL: EMBED_PRICE_PER_1M,
        },
        "per_turn_breakdown": ai_turn,
        "per_turn": {
            "ai_assistant": ai_turn["total"],
            "human_agent": human_turn,
        },
        "per_session": {
            "ai_assistant": ai_session,
            "human_agent": human_session,
        },
        "cost_ratio": {
            "human_vs_ai": cost_ratio,
            "note": (f"Human agent is {cost_ratio}× more expensive per turn "
                     f"than the AI assistant"),
        },
    }


def _print_report(model: dict) -> None:
    print("\n=== Chinese E-Commerce RAG Cost Model (Selected Stack) ===\n")
    print(f"  Generation: {model['stack']['generation']}")
    print(f"  Routing:    {model['stack']['routing']}")
    print(f"  Embedding:  {model['stack']['embedding']}")
    print(f"  Reranker:   {model['stack']['reranker']}")

    print("\nPer-turn cost breakdown:")
    for k, v in model["per_turn_breakdown"].items():
        print(f"  {k:<14} ${v:.6f}")

    print("\nCost comparison (AI vs human):")
    print(f"  {'':<20} {'per-turn':>12} {'per-session':>12}")
    print(f"  {'-'*46}")
    for name in ("ai_assistant", "human_agent"):
        pt = model["per_turn"][name]
        ps = model["per_session"][name]
        label = "AI assistant" if name == "ai_assistant" else "Human agent"
        print(f"  {label:<20} ${pt:>10.6f}   ${ps:>10.4f}")

    r = model["cost_ratio"]
    print(f"\n  {r['note']}")
    print()


if __name__ == "__main__":
    model = build()
    _print_report(model)

    out_dir = os.path.join("domains", "china_ecommerce", "eval", "reports")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "cost_model_zh.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(model, f, indent=2, ensure_ascii=False)
    print(f"Saved cost model → {out_path}")
