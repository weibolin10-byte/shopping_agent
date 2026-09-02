#!/usr/bin/env python3
"""Full Chinese RAG evaluation: routing + RAGAS answer quality + dense-vs-hybrid ablation.

Runs three evaluations against the Chinese ecommerce domain:

1. Routing accuracy — cheap, deterministic, exercises rag.router.route().
2. RAGAS answer quality — loads an explicit generation suite that is separate from the
   retrieval golden set, generates answers through the real answer_question() pipeline with
   the configured answer model, then judges faithfulness / answer_relevance /
   context_precision / context_recall using an independently configured LLM judge and
   qwen-embedding for answer-relevance similarity.
3. Retrieval ablation — compares hybrid (dense+sparse) vs dense-only
   retrieval on every golden answerable question, reporting hit@k,
   entity_recall@k and MRR for each.

The canonical result is written to domains/china_ecommerce/eval/reports/current.json with a
reproducibility manifest (git, data, model and knowledge versions).
and a human-readable summary is printed.

Usage:
    uv run python scripts/run_full_eval_zh.py
    GENERATION_EVAL_SUITE=regression uv run python scripts/run_full_eval_zh.py

The default ``smoke`` suite keeps local runs inexpensive.  ``regression`` and ``frozen`` fail
closed until their reviewed JSONL files exist; a small smoke set must not be reported as a
production-quality benchmark.
"""
from __future__ import annotations

import json
import os
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
from adapters.factory import make_embedder, make_llm, make_small_llm, make_store  # noqa: E402
from adapters.openai_compat import OpenAICompatClient  # noqa: E402
from api.resilience import ResilientEmbedder, ResilientLLM  # noqa: E402
from data.catalog_store import StructuredCatalogStore  # noqa: E402
from evaluation.agent_eval import evaluate_routing, load_cases  # noqa: E402
from evaluation.generation_set import (  # noqa: E402
    aggregate_contract_scores,
    load_generation_set,
    score_generation_contract,
)
from evaluation.metrics import hit_at_k, mean, reciprocal_rank  # noqa: E402
from evaluation.provenance import build_manifest, write_canonical_report  # noqa: E402
from evaluation.ragas_eval import evaluate_ragas  # noqa: E402
from evaluation.readme_metrics import sync_readme  # noqa: E402
from ingest.naming import collection_name  # noqa: E402
from pipeline.answer import (  # noqa: E402
    DEFAULT_MIN_CONFIDENCE,
    answer_question,
    retrieve,
)
from rag.policies import retrieval_plan  # noqa: E402

DOMAIN_PACK = ROOT / "domains" / "china_ecommerce"
REPORT_DIR = DOMAIN_PACK / "eval" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
GOLDEN_PATH = DOMAIN_PACK / "eval" / "golden.jsonl"
ROUTING_PATH = DOMAIN_PACK / "eval" / "routing.jsonl"
GENERATION_SET_PATHS = {
    "smoke": DOMAIN_PACK / "eval" / "generation_smoke.jsonl",
    "regression": DOMAIN_PACK / "eval" / "generation_regression.jsonl",
    "frozen": DOMAIN_PACK / "eval" / "generation_frozen.jsonl",
}

# Legacy selector retained for compatibility with older callers.  The formal runner no longer
# uses it: generation evaluation now loads an explicit, separately versioned suite.
RAGAS_PER_ROUTE = {"factual": 4, "qualitative": 3, "relational": 2,
                   "stylist": 2}
DEFAULT_GENERATION_SUITE = "smoke"
RAGAS_MAX = 11  # compatibility only; the formal runner uses the explicit suite size


# ---------------------------------------------------------------------------
# Store / embedder bootstrap
# ---------------------------------------------------------------------------

def load_store(settings):
    """Use the configured live index; a formal report must never read the fake memory seed."""
    name = collection_name(settings.domain, settings.embed_model)
    print("loading configured vector store", settings.vector_provider, name, "...")
    return make_store(collection=name)


def make_judge() -> OpenAICompatClient:
    api_key = os.getenv("JUDGE_API_KEY", "")
    base_url = os.getenv("JUDGE_BASE_URL", "")
    model = os.getenv("JUDGE_MODEL", "")
    if not (api_key and base_url and model):
        raise RuntimeError("formal evaluation requires JUDGE_API_KEY, JUDGE_BASE_URL and "
                           "JUDGE_MODEL for an independent judge")
    return OpenAICompatClient(model=model, api_key=api_key, base_url=base_url)


def load_golden() -> list[dict]:
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def contexts_from_hits(hits):
    return [{"n": i + 1, "id": ((h.get("payload") or {}).get("chunk_id")
                                  or (h.get("payload") or {}).get("id")),
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

def load_generation_cases(suite: str | None = None) -> tuple[str, Path, list[dict]]:
    """Load an explicit generation set; never derive it from retrieval golden data."""
    suite = suite or os.getenv("GENERATION_EVAL_SUITE", DEFAULT_GENERATION_SUITE)
    path = GENERATION_SET_PATHS.get(suite)
    if path is None:
        allowed = ", ".join(sorted(GENERATION_SET_PATHS))
        raise ValueError(f"unknown generation suite {suite!r}; choose one of: {allowed}")
    if not path.is_file():
        raise RuntimeError(
            f"generation suite {suite!r} is not ready: {path.relative_to(ROOT)} does not exist"
        )
    return suite, path, load_generation_set(path, require_approved=suite != "smoke")


def _select_ragas_subset(golden: list[dict]) -> list[dict]:
    by_route: dict[str, list[dict]] = {}
    for g in golden:
        if g.get("type") != "answerable":
            continue
        by_route.setdefault(g.get("route", "unknown"), []).append(g)
    selected = []
    for route, items in by_route.items():
        n = RAGAS_PER_ROUTE.get(route, 0)
        selected.extend(items[:n])
    random.seed(42)
    random.shuffle(selected)
    return selected[:RAGAS_MAX]


def eval_ragas(embedder, llm, judge, store, generation_cases, catalog_store,
               *, suite: str) -> dict:
    print(f"\n[ragas] generating answers for {len(generation_cases)} {suite} questions "
          f"({getattr(llm, 'model', '?')} + independent judge "
          f"{getattr(judge, 'model', '?')})...")
    items = []
    contract_rows = []
    case_attempts = max(1, int(os.getenv("GENERATION_CASE_ATTEMPTS", "2")))
    for i, g in enumerate(generation_cases, 1):
        q = g["question"]
        t0 = time.time()
        result = None
        last_error = None
        for attempt in range(1, case_attempts + 1):
            try:
                lane = g["lane"]
                plan = retrieval_plan(lane, "china_ecommerce", query=q)
                result = answer_question(
                    q, embedder=embedder, store=store, llm=llm,
                    top_k=8, top_k_in=50,
                    min_confidence=DEFAULT_MIN_CONFIDENCE,
                    retrieval_plan=plan,
                    catalog_store=catalog_store,
                    allow_retrieval_fallback=False,
                )
                break
            except Exception as exc:
                last_error = exc
                print(f"  [{i}/{len(generation_cases)}] {g['id']} attempt "
                      f"{attempt}/{case_attempts} ERROR: {exc}")
        if result is None:
            print(f"  [{i}/{len(generation_cases)}] {g['id']} FINAL ANSWER ERROR: {last_error}")
            continue
        dt = time.time() - t0
        answer = result.answer
        contexts = [c["text"] for c in result.contexts]
        actual_action = "abstain" if result.tier == "abstain" else "answer"
        contract = score_generation_contract(
            g, answer=answer, actual_action=actual_action,
        )
        contract_rows.append({"id": g["id"], **contract})
        items.append({
            "id": g["id"],
            "question": q,
            "answer": answer,
            "contexts": contexts,
            "ground_truth": g.get("reference_answer", ""),
            "retrieval_mode": plan.mode,
            "lang": g.get("lang", "zh"),
            "difficulty": g.get("difficulty", "untagged"),
            "lane": lane,
            "tags": g.get("tags", []),
            "expected_action": g["expected_action"],
            "actual_action": actual_action,
            "required_facts": g.get("required_facts", {}),
            "citation_targets": g.get("citation_targets", []),
            "contract_scores": contract,
            "abstained": result.tier == "abstain",
            "confidence": result.confidence,
            "grounding": result.grounding,
            "latency_s": round(dt, 2),
        })
        flag = "ABSTAIN" if result.tier == "abstain" else f"{len(answer)}字"
        print(f"  [{i}/{len(generation_cases)}] {g['id']} [{lane:<11}] "
              f"{flag} conf={result.confidence:.2f} ground={result.grounding:.2f} "
              f"({dt:.1f}s)")

    if len(items) != len(generation_cases):
        raise RuntimeError(
            "formal generation evaluation is incomplete: "
            f"evaluated {len(items)}/{len(generation_cases)} cases"
        )

    print(f"[ragas] judging with {getattr(judge, 'model', '?')} "
          "(faithfulness / answer_relevance / "
          "context_precision / context_recall)...")
    ragas = evaluate_ragas(items, judge=judge, embedder=embedder)
    expected_valid = {
        "faithfulness": sum(not item["abstained"] and bool(item["contexts"])
                            for item in items),
        "answer_relevance": sum(not item["abstained"] for item in items),
        "context_precision": sum(bool(item["contexts"]) for item in items),
        "context_recall": sum(bool(item["contexts"]) and bool(item["ground_truth"])
                              for item in items),
    }
    incomplete_metrics = {
        metric: {"expected": expected, "valid": ragas["valid_counts"].get(metric, 0)}
        for metric, expected in expected_valid.items()
        if ragas["valid_counts"].get(metric, 0) != expected
    }
    if incomplete_metrics:
        raise RuntimeError(f"formal judge evaluation is incomplete: {incomplete_metrics}")
    print(f"[ragas] overall: {ragas['overall']}")
    for lang, s in ragas["by_language"].items():
        print(f"  lang={lang}: {s}")
    return {
        "suite": suite,
        "dataset_size": len(generation_cases),
        "evaluated_size": len(items),
        "items": items,
        "scores": ragas,
        "deterministic_contract": aggregate_contract_scores(contract_rows),
    }


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
    if settings.llm_provider in ("", "fake") or settings.embed_provider in ("", "fake"):
        raise RuntimeError("formal evaluation refuses fake LLM or embedding providers")
    if settings.vector_provider != "qdrant":
        raise RuntimeError("formal evaluation requires VECTOR_PROVIDER=qdrant so it measures "
                           "the deployed retrieval backend")
    print(f"=== Full Chinese evaluation (domain={settings.domain}) ===")
    store = load_store(settings)
    embedder = ResilientEmbedder(make_embedder(), attempts=3)
    small_llm = make_small_llm()
    big_llm = make_llm()
    judge = ResilientLLM(make_judge(), attempts=3, fallback=None)
    golden = load_golden()
    generation_suite, generation_path, generation_cases = load_generation_cases()
    catalog_store = StructuredCatalogStore.from_csv(
        DOMAIN_PACK / "seed" / "structured" / "products.csv",
        knowledge_version=os.getenv("KNOWLEDGE_VERSION", "catalog-v1"),
    )
    answerable_count = sum(1 for g in golden if g.get("type") == "answerable")
    abstain_count = sum(
        1 for g in golden if g.get("type") in ("unanswerable", "out_of_domain")
    )
    print(f"golden set: {len(golden)} items "
          f"({answerable_count} answerable, {abstain_count} abstain)")
    print(f"generation set: {generation_suite} ({len(generation_cases)} items)")

    t0 = time.time()
    report = {
        "domain": settings.domain,
        "model": {"big": getattr(big_llm, "model", "?"),
                  "small": getattr(small_llm, "model", "?"),
                  "judge": getattr(judge, "model", "?")},
        "embedding": settings.embed_model,
    }
    report["routing"] = eval_routing(small_llm)
    report["ragas"] = eval_ragas(
        embedder, big_llm, judge, store, generation_cases, catalog_store,
        suite=generation_suite,
    )
    report["ablation"] = eval_ablation(embedder, store, golden)
    report["duration_s"] = round(time.time() - t0, 1)

    manifest = build_manifest(
        domain=settings.domain, dataset_paths=[GOLDEN_PATH, ROUTING_PATH, generation_path],
        models={"answer": getattr(big_llm, "model", "?"),
                "router": getattr(small_llm, "model", "?"),
                "judge": getattr(judge, "model", "?"),
                "embedding": settings.embed_model},
        knowledge_version=os.getenv("KNOWLEDGE_VERSION", "policy-2026-01"),
        parameters={"retrieval_eval_top_k": 8, "generation_top_k": {"answers": 6,
                                                                     "stylist": 6},
                    "top_k_in": 50, "generation_suite": generation_suite,
                    "generation_size": len(generation_cases)}, seed=42,
        root=ROOT)
    configured_out = os.getenv("EVAL_REPORT_OUT", "").strip()
    out = Path(configured_out) if configured_out else REPORT_DIR / "current.json"
    if not out.is_absolute():
        out = ROOT / out
    write_canonical_report(out, manifest=manifest, results=report)
    if out.resolve() == (REPORT_DIR / "current.json").resolve():
        sync_readme(ROOT / "README.md", out)
    print(f"\n=== Done in {report['duration_s']}s ===")
    print(f"Report saved to {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
