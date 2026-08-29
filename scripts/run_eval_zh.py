#!/usr/bin/env python3
"""Chinese-domain offline evaluation against the seeded in-memory vector store.

This extends evaluation/harness.py in two ways:
  * every answerable route (factual / relational / qualitative / stylist / care)
    is measured, not just the qualitative subset;
  * care/order questions carry the demo user's auth text + email so the PII gate
    in retrieve() can match.

Output: a scorecard plus per-question pass/fail detail.
"""
from __future__ import annotations

import json
import os
import pickle
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

from adapters.factory import make_embedder  # noqa: E402
from api.resilience import ResilientEmbedder  # noqa: E402
from evaluation.metrics import mean  # noqa: E402
from pipeline.answer import (  # noqa: E402
    DEFAULT_MIN_CONFIDENCE,
    retrieve,
    should_abstain,
)

DOMAIN = os.getenv("DOMAIN", "china_ecommerce")
PACK = Path("domains") / DOMAIN
PICKLE = PACK / "memory_seed.pkl"

DEMO_NAME = os.getenv("DEMO_CUSTOMER_NAME", "张伟")
DEMO_EMAIL = os.getenv("DEMO_CUSTOMER_EMAIL", "zhangwei@example.com")
AUTH_TEXT = f"{DEMO_NAME} {DEMO_EMAIL}"

TOP_K = 8
TOP_K_IN = 50

# Routes that we can measure from the hybrid vector store.  The original harness
# only covered "qualitative"; factual/relational answers live in the same chunks,
# and care/account answers require an auth context but are still retrievable.
RETRIEVABLE_ROUTES = {
    "factual",
    "relational",
    "qualitative",
    "stylist",
    "care",
    "answerable",
}


def load_store():
    with open(PICKLE, "rb") as f:
        data = pickle.load(f)
    return data["store"] if isinstance(data, dict) else data


def load_golden():
    rows = []
    with open(PACK / "eval" / "golden.jsonl", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def entity_fields() -> list[str]:
    with open(PACK / "domain.yaml", encoding="utf-8") as f:
        manifest = yaml.safe_load(f) or {}
    fields: set[str] = set()
    for src in (manifest.get("sources", {}) or {}).get("unstructured", []) or []:
        fields.update(src.get("entity_ref", []) or [])
    return sorted(fields)


def _contexts(hits):
    return [{"text": (h.get("payload") or {}).get("text", "")} for h in hits]


def _entity_recall(hits, expected, fields):
    if not expected:
        return 0.0
    wanted = {str(e) for e in expected}
    covered = set()
    for h in hits:
        p = h.get("payload") or {}
        for f in fields:
            v = p.get(f)
            if v is not None and str(v) in wanted:
                covered.add(str(v))
    return len(covered) / len(wanted)


def _hit_at_k(hits, expected, fields):
    if not expected:
        return 0.0
    wanted = {str(e) for e in expected}
    for h in hits:
        p = h.get("payload") or {}
        got = {str(p.get(f)) for f in fields if p.get(f) is not None}
        if got & wanted:
            return 1.0
    return 0.0


def _mrr(hits, expected, fields):
    if not expected:
        return 0.0
    wanted = {str(e) for e in expected}
    for i, h in enumerate(hits, 1):
        p = h.get("payload") or {}
        got = {str(p.get(f)) for f in fields if p.get(f) is not None}
        if got & wanted:
            return 1.0 / i
    return 0.0


def _answer_contains(hits, expected_terms):
    """For factual/relational questions, check if any retrieved chunk text
    contains the expected answer terms."""
    if not expected_terms:
        return None  # not applicable
    blob = "\n".join((h.get("payload") or {}).get("text", "") for h in hits)
    return all(str(term) in blob for term in expected_terms)


def score_one(g, embedder, store, fields):
    q = g["question"]
    route = g.get("route", "")
    is_care = (route == "care" or "订单" in q
               or "我的" in q and ("订单" in q or "快递" in q or "物流" in q))
    auth = AUTH_TEXT if is_care else None
    rq = f"{q} {DEMO_EMAIL}" if is_care else q

    hits = retrieve(rq, embedder, store, TOP_K, top_k_in=TOP_K_IN, auth_text=auth)

    expected_entities = g.get("expected_entities") or []
    expected_terms = g.get("expected_answer_contains") or []

    hit = _hit_at_k(hits, expected_entities, fields)
    rr = _mrr(hits, expected_entities, expected_entities and fields)
    erecall = _entity_recall(hits, expected_entities, fields)

    contains = _answer_contains(hits, expected_terms)
    contexts = _contexts(hits)
    abstained, reason = should_abstain(q, contexts, DEFAULT_MIN_CONFIDENCE)

    # A question "passes" if either entities or answer terms appear AND we did
    # not false-abstain.
    retrieval_ok = bool(hit >= 1.0 or (contains is True))
    passed = retrieval_ok and not abstained

    return {
        "id": g["id"],
        "lang": g.get("lang", "?"),
        "route": route,
        "type": g.get("type", "?"),
        "difficulty": g.get("difficulty", "?"),
        "question": q,
        "nhits": len(hits),
        "entity_hit": hit,
        "entity_recall": erecall,
        "mrr": rr,
        "answer_contains": contains,
        "abstained": abstained,
        "abstain_reason": reason if abstained else "",
        "passed": passed,
        "top_snippet": ((hits[0].get("payload") or {}).get("text", "")[:120] if hits else ""),
    }


def score_abstain(g, embedder, store):
    q = g["question"]
    hits = retrieve(q, embedder, store, TOP_K, top_k_in=TOP_K_IN)
    contexts = _contexts(hits)
    abstained, reason = should_abstain(q, contexts, DEFAULT_MIN_CONFIDENCE)
    return {
        "id": g["id"],
        "question": q,
        "abstained": abstained,
        "reason": reason,
        "passed": abstained,
    }


def main():
    if not PICKLE.exists():
        print(f"memory seed not found at {PICKLE}; run seed_memory.py first", file=sys.stderr)
        return 1

    print(f"loading store from {PICKLE} ...")
    store = load_store()
    embedder = ResilientEmbedder(make_embedder())
    fields = entity_fields()
    print(f"entity fields used for matching: {fields}")

    golden = load_golden()
    answerable = [g for g in golden if g.get("type") == "answerable"]
    abstain_set = [g for g in golden if g.get("type") in ("unanswerable", "out_of_domain")]

    print(f"\nanswerable: {len(answerable)}  abstain-set: {len(abstain_set)}")
    print("embedding queries ...\n")

    results = []
    for i, g in enumerate(answerable, 1):
        r = score_one(g, embedder, store, fields)
        results.append(r)
        flag = "✅" if r["passed"] else "❌"
        contains = ""
        if r["answer_contains"] is not None:
            contains = f" contains={r['answer_contains']}"
        print(f"  {flag} {r['id']:>4} [{r['route']:<11}] hits={r['nhits']} "
              f"ent_hit={r['entity_hit']:.0f} recall={r['entity_recall']:.2f} "
              f"mrr={r['mrr']:.2f} abstain={r['abstained']}{contains}  | {r['question'][:50]}")

    print("\n--- abstain set ---")
    a_results = []
    for g in abstain_set:
        r = score_abstain(g, embedder, store)
        a_results.append(r)
        flag = "✅" if r["passed"] else "❌"
        print(f"  {flag} {r['id']:>4} abstained={r['abstained']}  | {r['question'][:60]}")

    # aggregate
    n_pass = sum(1 for r in results if r["passed"])
    n_total = len(results)
    hit_rate = mean([r["entity_hit"] for r in results])
    erecall = mean([r["entity_recall"] for r in results])
    mrr = mean([r["mrr"] for r in results])
    false_abstain = mean([1.0 if r["abstained"] else 0.0 for r in results])
    abstain_recall = mean([1.0 if r["abstained"] else 0.0 for r in a_results]) if a_results else 0.0

    # answer-contains pass rate for those that have expected terms
    with_terms = [r for r in results if r["answer_contains"] is not None]
    contains_rate = (mean([1.0 if r["answer_contains"] else 0.0 for r in with_terms])
                     if with_terms else 0.0)

    print("\n" + "=" * 72)
    print(f"CHINESE EVAL SCORECARD  (domain={DOMAIN}, top_k={TOP_K})")
    print("=" * 72)
    print(f"  answerable pass rate     : {n_pass}/{n_total} = {n_pass/n_total:.3f}")
    print(f"  entity hit@k             : {hit_rate:.3f}   (n={n_total})")
    print(f"  entity recall@k          : {erecall:.3f}")
    print(f"  MRR                      : {mrr:.3f}")
    print(f"  answer-contains rate     : {contains_rate:.3f}   (n={len(with_terms)})")
    print(f"  false-abstain rate       : {false_abstain:.3f}")
    print(f"  abstain recall (gate)    : {abstain_recall:.3f}   (n={len(a_results)})")

    # by route
    print("\n  by route:")
    for route in sorted({r["route"] for r in results}):
        sub = [r for r in results if r["route"] == route]
        p = sum(1 for r in sub if r["passed"])
        print(f"    {route:<12} pass {p}/{len(sub)}  "
              f"hit={mean([r['entity_hit'] for r in sub]):.2f}  "
              f"recall={mean([r['entity_recall'] for r in sub]):.2f}")

    # save report
    report_dir = PACK / "eval" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "zh_eval_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "domain": DOMAIN,
            "top_k": TOP_K,
            "summary": {
                "answerable_pass_rate": round(n_pass / n_total, 4) if n_total else 0,
                "entity_hit_at_k": round(hit_rate, 4),
                "entity_recall_at_k": round(erecall, 4),
                "mrr": round(mrr, 4),
                "answer_contains_rate": round(contains_rate, 4),
                "false_abstain_rate": round(false_abstain, 4),
                "abstain_recall": round(abstain_recall, 4),
            },
            "answerable_results": results,
            "abstain_results": a_results,
        }, f, ensure_ascii=False, indent=2)
    print(f"\nreport saved to {report_path}")
    return 0 if n_pass == n_total else 0  # don't fail CI; informational


if __name__ == "__main__":
    sys.exit(main())
