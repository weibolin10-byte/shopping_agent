"""Identity-aware generation evaluation over the real orchestration boundary.

Private order cases must not call the public RAG-only evaluator.  This runner supplies a verified
identity and tenant to ``stream_omni``, lets the lane policy query the private ``OrderStore``, and
scores the final action and privacy contract without copying order records into a vector index.
"""
from __future__ import annotations

from evaluation.generation_set import score_generation_contract
from rag.omni import stream_omni


def run_identity_case(case: dict, *, embedder, store, llm, order_store,
                      small_llm=None, trace_path: str, domain: str = "china_ecommerce",
                      catalog_store=None, history: list[dict] | None = None,
                      conversation_state=None) -> dict:
    identity = case.get("identity") or {"signed_in": False}
    signed_in = bool(identity.get("signed_in"))
    user_id = str(identity.get("user_id") or "") if signed_in else None
    tenant_id = str(identity.get("tenant_id") or "default")
    auth_identity = ((str(identity.get("name") or ""), user_id)
                     if signed_in and user_id else None)
    events = list(stream_omni(
        case["question"], embedder=embedder, store=store, llm=llm,
        small_llm=small_llm, order_store=order_store, auth_identity=auth_identity,
        user_scope=user_id, tenant_scope=tenant_id, domain=domain,
        trace_path=trace_path, catalog_store=catalog_store, history=history,
        conversation_state=conversation_state,
    ))
    finals = [event for event in events if event.get("type") == "final"]
    if len(finals) != 1:
        raise RuntimeError(
            f"identity evaluation {case['id']} expected one final event, got {len(finals)}"
        )
    final = finals[0]
    answer = str(final.get("answer") or "")
    action = str(final.get("action") or
                 ("abstain" if final.get("tier") == "abstain" else "answer"))
    contract = score_generation_contract(case, answer=answer, actual_action=action)
    forbidden_private_hits = [
        value for value in case.get("must_not_disclose", []) if value and value in answer
    ]
    expected_lane = case.get("expected_lane")
    return {
        "id": case["id"],
        "question": case["question"],
        "answer": answer,
        "lane": final.get("lane"),
        "action": action,
        "expected_lane": expected_lane,
        "lane_correct": expected_lane is None or final.get("lane") == expected_lane,
        "contract_scores": contract,
        "privacy_safe": not forbidden_private_hits,
        "private_leaks": forbidden_private_hits,
        "citations": final.get("citations") or [],
        "clarification": final.get("clarification"),
    }


def aggregate_identity_results(rows: list[dict]) -> dict:
    if not rows:
        return {"count": 0, "action_accuracy": None, "lane_accuracy": None,
                "privacy_safe_rate": None}
    return {
        "count": len(rows),
        "action_accuracy": round(sum(
            bool(row["contract_scores"]["action_correct"]) for row in rows
        ) / len(rows), 3),
        "lane_accuracy": round(sum(bool(row["lane_correct"]) for row in rows) / len(rows), 3),
        "privacy_safe_rate": round(sum(bool(row["privacy_safe"]) for row in rows) / len(rows), 3),
    }
