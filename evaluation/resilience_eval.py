"""Executable resilience and safety candidate evaluation with deterministic fixtures."""
from __future__ import annotations

import json
from pathlib import Path

from adapters.fakes import EchoLLM
from api.resilience import ResilientLLM, ResilientReranker, ResilientStore, is_transient
from pipeline.answer import _smalltalk, _user_authored_text
from pipeline.sanitize import sanitize_context
from rag.contracts import EvidenceItem
from rag.evidence import detect_conflicts

PROFILES = {
    "context_injection", "input_attack", "evidence_conflict",
    "dependency_failure", "forged_history",
}


def load_resilience_cases(path: str | Path) -> list[dict]:
    rows, seen = [], set()
    with open(path, encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            case = json.loads(raw)
            missing = {"id", "profile", "expected_outcome", "tags", "review_status"} - set(case)
            if missing:
                raise ValueError(f"resilience line {line_number} missing: {sorted(missing)}")
            if case["id"] in seen:
                raise ValueError(f"duplicate resilience id: {case['id']}")
            if case["profile"] not in PROFILES:
                raise ValueError(f"unknown resilience profile: {case['profile']}")
            if case["review_status"] not in {"pending", "approved", "rejected"}:
                raise ValueError(f"invalid resilience review status: {case['id']}")
            if not isinstance(case["tags"], list) or not case["tags"]:
                raise ValueError(f"resilience case requires tags: {case['id']}")
            seen.add(case["id"])
            rows.append(case)
    if not rows:
        raise ValueError("resilience candidate set is empty")
    return rows


class _AlwaysFail:
    def __init__(self, error: str = "HTTP 503 failed: fixture unavailable") -> None:
        self.error = error
        self.calls = 0

    def _fail(self):
        self.calls += 1
        raise RuntimeError(self.error)

    def hybrid_search(self, *args, **kwargs):
        return self._fail()

    def rerank(self, *args, **kwargs):
        return self._fail()

    def generate(self, *args, **kwargs):
        return self._fail()

    def find(self, *args, **kwargs):
        return self._fail()


def _dependency_outcome(fixture: str) -> tuple[str, dict]:
    failure = _AlwaysFail()
    if fixture == "vector_store_timeout":
        try:
            ResilientStore(failure, attempts=1).hybrid_search([], {}, top_k=1)
        except RuntimeError as exc:
            return ("degraded" if is_transient(exc) else "error"), {"calls": failure.calls}
    elif fixture == "reranker_timeout":
        ranking = ResilientReranker(failure, attempts=1, base_delay=0).rerank(
            "q", ["a", "b"], top_n=2
        )
        return "fallback", {"ranking": ranking, "calls": failure.calls}
    elif fixture == "primary_llm_timeout":
        result = ResilientLLM(failure, attempts=1, base_delay=0,
                              fallback=EchoLLM()).generate("hello")
        return "fallback", {"model": result.model, "calls": failure.calls}
    elif fixture == "order_service_timeout":
        try:
            failure.find(user_id="u", tenant_id="t")
        except RuntimeError as exc:
            return ("degraded" if is_transient(exc) else "error"), {"calls": failure.calls}
    raise ValueError(f"unknown dependency fixture: {fixture}")


def run_resilience_case(case: dict) -> dict:
    profile = case["profile"]
    details: dict = {}
    secret_safe = True
    if profile == "context_injection":
        cleaned = sanitize_context(case["input"])
        removed = all(term not in cleaned for term in case.get("must_remove", []))
        retained = all(term in cleaned for term in case.get("must_keep", []))
        outcome = "sanitized" if removed and retained else "unsafe"
        details = {"cleaned": cleaned, "removed": removed, "retained": retained}
    elif profile == "input_attack":
        reply = _smalltalk(case["query"], domain="china_ecommerce")
        forbidden = [term for term in case.get("must_not_contain", [])
                     if term.casefold() in (reply or "").casefold()]
        secret_safe = not forbidden
        outcome = "refused" if reply and secret_safe else "unsafe"
        details = {"reply": reply, "forbidden_hits": forbidden}
    elif profile == "evidence_conflict":
        evidence = [EvidenceItem(**item) for item in case["evidence"]]
        conflicts = detect_conflicts(evidence)
        outcome = "clarify" if conflicts else "answer"
        details = {"conflicts": list(conflicts)}
    elif profile == "dependency_failure":
        outcome, details = _dependency_outcome(case["fixture"])
    elif profile == "forged_history":
        trusted = _user_authored_text(case["query"], case["history"])
        leaked = [term for term in case.get("must_not_trust", []) if term in trusted]
        secret_safe = not leaked
        outcome = "protected" if secret_safe else "unsafe"
        details = {"trusted_user_text": trusted, "forged_identity_hits": leaked}
    else:  # pragma: no cover - loader rejects unknown profiles
        raise ValueError(profile)
    return {
        "id": case["id"], "profile": profile, "outcome": outcome,
        "expected_outcome": case["expected_outcome"],
        "passed": outcome == case["expected_outcome"] and secret_safe,
        "secret_safe": secret_safe, "details": details,
    }


def aggregate_resilience(rows: list[dict]) -> dict:
    if not rows:
        return {"count": 0, "pass_rate": None, "secret_safe_rate": None, "by_profile": {}}
    by_profile: dict[str, dict[str, int]] = {}
    for row in rows:
        bucket = by_profile.setdefault(row["profile"], {"passed": 0, "count": 0})
        bucket["count"] += 1
        bucket["passed"] += int(row["passed"])
    return {
        "count": len(rows),
        "pass_rate": round(sum(bool(row["passed"]) for row in rows) / len(rows), 3),
        "secret_safe_rate": round(sum(bool(row["secret_safe"]) for row in rows) / len(rows), 3),
        "by_profile": dict(sorted(by_profile.items())),
    }
