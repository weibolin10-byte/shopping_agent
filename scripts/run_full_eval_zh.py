#!/usr/bin/env python3
"""Full Chinese RAG evaluation: routing + RAGAS answer quality + dense-vs-hybrid ablation.

Runs three evaluations against the Chinese ecommerce domain:

1. Routing accuracy — cheap, deterministic, exercises rag.router.route().
2. RAGAS answer quality — selects a stratified subset of golden questions,
   generates answers through the real answer_question() pipeline with
   DeepSeek, then judges faithfulness / answer_relevance /
   context_precision / context_recall using DeepSeek as the LLM judge and
   qwen-embedding for answer-relevance similarity.
3. Retrieval ablation — compares hybrid (dense+sparse) vs dense-only
   retrieval on every golden answerable question, reporting hit@k,
   entity_recall@k and MRR for each.

Results are written to domains/china_ecommerce/eval/reports/full_eval.json
and a human-readable summary is printed.

Usage:
    uv run python scripts/run_full_eval_zh.py
"""
from __future__ import annotations

import json
import os
import pickle
import random
import sys
import time
from pathlib import Path

# Ensure project root on sys.path so `uv run python scripts/...` works
# regardless of cwd.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from adapters.config import get_settings  # noqa: E402
from adapters.factory import make_embedder, make_llm, make_small_llm  # noqa: E402
from evaluation.agent_eval import evaluate_routing, load_cases  # noqa: E402
from evaluation.metrics import hit_at_k, mean, reciprocal_rank  # noqa: E402
from evaluation.ragas_eval import evaluate_ragas  # noqa: E402
from pipeline.answer import (  # noqa: E402
    DEFAULT_MIN_CONFIDENCE,
    answer_question,
    retrieve,
)

DOMAIN_PACK = ROOT / "domains" / "china_ecommerce"
REPORT_DIR = DOMAIN_PACK / "eval" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
PKL_PATH = DOMAIN_PACK / "memory_seed.pkl"
GOLDEN_PATH = DOMAIN_PACK / "eval" / "golden.jsonl"
ROUTING_PATH = DOMAIN_PACK / "eval" / "routing.jsonl"

# Stratified subset for RAGAS: at most N per route to keep cost bounded.
RAGAS_PER_ROUTE = {"factual": 4, "qualitative": 3, "relational": 2,
                   "stylist": 2, "care": 1}
RAGAS_MAX = 14


# ---------------------------------------------------------------------------
# Store / embedder bootstrap
# ---------------------------------------------------------------------------

def load_store():
    print("loading store from", PKL_PATH.relative_to(ROOT), "...")
    with open(PKL_PATH, "rb") as f:
        data = pickle.load(f)
    return data["store"]


def load_golden() -> list[dict]:
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def contexts_from_hits(hits):
    return [{"n": i + 1, "id": (h.get("payload") or {}).get("id"),
             "text": (h.get("payload") or {}).get("text", ""),
             "source": (h.get("payload") or {}).get("source", ""),
             "doc_type": (h.get("payload") or {}).get("doc_type", "")}
            for i, h in enumerate(hits)]


# ---------------------------------------------------------------------------
# 1. Routing
# ---------------------------------------------------------------------------

def eval_routing(small_llm) -> dict:
    cases = load_cases(str(ROUTING_PATH))
    deterministic = evaluate_routing(cases, small_llm=None, mode="deterministic")
    with_tiebreak = evaluate_routing(cases, small_llm=small_llm,
                                      mode="with_tiebreak")
    print(f"\n[routing] deterministic accuracy={deterministic['accuracy']:.3f} "
          f"({deterministic['graded']} graded, "
          f"det_rate={deterministic['deterministic_decision_rate']:.2f})")
    print(f"[routing] with tiebreak accuracy={with_tiebreak['accuracy']:.3f}, "
          f"tiebreak_calls={with_tiebreak['tiebreak_calls']}, "
          f"cost≈${with_tiebreak['tiebreak_cost_usd']:.4f}")
    if with_tiebreak["confusion"]:
        print(f"[routing] confusion (intended->got): {with_tiebreak['confusion']}")
    return {"deterministic": deterministic, "with_tiebreak": with_tiebreak}


# ---------------------------------------------------------------------------
# 2. RAGAS answer quality
# ---------------------------------------------------------------------------

def _reference_answer(g: dict) -> str:
    """Synthesise a short reference answer from golden expected fields for
    context_recall scoring."""
    parts = []
    if g.get("expected_answer_contains"):
        parts.append("答案应包含：" + "、".join(g["expected_answer_contains"]))
    if g.get("expected_entities"):
        parts.append("涉及实体：" + "、".join(g["expected_entities"]))
    return " ".join(parts) or g["question"]


def _select_ragas_subset(golden: list[dict]) -> list[dict]:
    by_route: dict[str, list[dict]] = {}
    for g in golden:
        if g.get("type") != "answerable":
            continue
        by_route.setdefault(g.get("route", "unknown"), []).append(g)
    selected = []
    for route, items in by_route.items():
        n = RAGAS_PER_ROUTE.get(route, 1)
        selected.extend(items[:n])
    random.seed(42)
    random.shuffle(selected)
    return selected[:RAGAS_MAX]


def eval_ragas(embedder, llm, judge, store, golden) -> dict:
    subset = _select_ragas_subset(golden)
    print(f"\n[ragas] generating answers for {len(subset)} questions "
          f"(DeepSeek + judge)...")
    items = []
    for i, g in enumerate(subset, 1):
        q = g["question"]
        t0 = time.time()
        try:
            result = answer_question(
                q, embedder=embedder, store=store, llm=llm,
                top_k=8, top_k_in=50,
                min_confidence=DEFAULT_MIN_CONFIDENCE,
            )
        except Exception as exc:
            print(f"  [{i}/{len(subset)}] {g['id']} ANSWER ERROR: {exc}")
            continue
        dt = time.time() - t0
        answer = result.answer
        contexts = [c["text"] for c in result.contexts]
        items.append({
            "id": g["id"],
            "question": q,
            "answer": answer,
            "contexts": contexts,
            "ground_truth": _reference_answer(g),
            "lang": g.get("lang", "zh"),
            "difficulty": g.get("difficulty", "untagged"),
            "route": g.get("route", "unknown"),
            "abstained": result.tier == "abstain",
            "confidence": result.confidence,
            "grounding": result.grounding,
            "latency_s": round(dt, 2),
        })
        flag = "ABSTAIN" if result.tier == "abstain" else f"{len(answer)}字"
        print(f"  [{i}/{len(subset)}] {g['id']} [{g.get('route','?'):<11}] "
              f"{flag} conf={result.confidence:.2f} ground={result.grounding:.2f} "
              f"({dt:.1f}s)")

    print("[ragas] judging with DeepSeek (faithfulness / answer_relevance / "
          "context_precision / context_recall)...")
    ragas = evaluate_ragas(items, judge=judge, embedder=embedder)
    print(f"[ragas] overall: {ragas['overall']}")
    for lang, s in ragas["by_language"].items():
        print(f"  lang={lang}: {s}")
    return {"subset_size": len(items), "items": items, "scores": ragas}


# ---------------------------------------------------------------------------
# 3. Dense vs hybrid ablation
# ---------------------------------------------------------------------------

ENTITY_FIELDS = ["product_id", "store_id", "supplier_id"]


def _relevance(hits, expected):
    wanted = {str(e) for e in expected}
    return [bool({str((h.get("payload") or {}).get(f)) for f in ENTITY_FIELDS} & wanted)
            for h in hits]


def _entity_recall(hits, expected):
    if not expected:
        return 0.0
    wanted = {str(e) for e in expected}
    covered = set()
    for h in hits:
        for f in ENTITY_FIELDS:
            v = (h.get("payload") or {}).get(f)
            if v is not None and str(v) in wanted:
                covered.add(str(v))
    return len(covered) / len(wanted)


def eval_ablation(embedder, store, golden) -> dict:
    answerable = [g for g in golden if g.get("type") == "answerable"
                  and g.get("expected_entities")]
    print(f"\n[ablation] running on {len(answerable)} questions with "
          f"expected entities...")
    hybrid_rows, dense_rows = [], []
    for i, g in enumerate(answerable, 1):
        q = g["question"]
        expected = g["expected_entities"]
        h_hits = retrieve(q, embedder, store, 8, top_k_in=50, dense_only=False)
        d_hits = retrieve(q, embedder, store, 8, top_k_in=50, dense_only=True)
        h_flags = _relevance(h_hits, expected)
        d_flags = _relevance(d_hits, expected)
        hybrid_rows.append({
            "id": g["id"], "route": g.get("route"),
            "hit": hit_at_k(h_flags), "rr": reciprocal_rank(h_flags),
            "erecall": _entity_recall(h_hits, expected),
        })
        dense_rows.append({
            "id": g["id"], "route": g.get("route"),
            "hit": hit_at_k(d_flags), "rr": reciprocal_rank(d_flags),
            "erecall": _entity_recall(d_hits, expected),
        })
        if i % 8 == 0 or i == len(answerable):
            print(f"  [{i}/{len(answerable)}] done")

    def agg(rows):
        return {
            "hit@8": round(mean([r["hit"] for r in rows]), 3),
            "entity_recall@8": round(mean([r["erecall"] for r in rows]), 3),
            "mrr": round(mean([r["rr"] for r in rows]), 3),
            "n": len(rows),
        }
    by_route = {}
    for route in sorted({r["route"] for r in hybrid_rows if r["route"]}):
        h = [r for r in hybrid_rows if r["route"] == route]
        d = [r for r in dense_rows if r["route"] == route]
        by_route[route] = {"hybrid": agg(h), "dense": agg(d)}
    summary = {"hybrid": agg(hybrid_rows), "dense": agg(dense_rows),
               "by_route": by_route}
    print(f"[ablation] hybrid : {summary['hybrid']}")
    print(f"[ablation] dense  : {summary['dense']}")
    return summary


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    settings = get_settings()
    print(f"=== Full Chinese evaluation (domain={settings.domain}) ===")
    store = load_store()
    embedder = make_embedder()
    small_llm = make_small_llm()
    big_llm = make_llm()
    # Use the big model for both generation and judging. In a stricter eval
    # we'd cross-check with a different vendor, but DeepSeek is the only
    # chat model configured and the original project also defaults to the
    # primary LLM as judge.
    judge = big_llm
    golden = load_golden()
    answerable_count = sum(1 for g in golden if g.get("type") == "answerable")
    abstain_count = sum(
        1 for g in golden if g.get("type") in ("unanswerable", "out_of_domain")
    )
    print(f"golden set: {len(golden)} items "
          f"({answerable_count} answerable, {abstain_count} abstain)")

    t0 = time.time()
    report = {
        "domain": settings.domain,
        "model": {"big": getattr(big_llm, "model", "?"),
                  "small": getattr(small_llm, "model", "?")},
        "embedding": settings.embed_model,
    }
    report["routing"] = eval_routing(small_llm)
    report["ragas"] = eval_ragas(embedder, big_llm, judge, store, golden)
    report["ablation"] = eval_ablation(embedder, store, golden)
    report["duration_s"] = round(time.time() - t0, 1)

    out = REPORT_DIR / "full_eval.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n=== Done in {report['duration_s']}s ===")
    print(f"Report saved to {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
