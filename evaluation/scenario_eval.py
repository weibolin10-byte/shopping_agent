"""Stateful multi-turn evaluation built on the identity-aware orchestration runner."""
from __future__ import annotations

import json
import re
from pathlib import Path

from evaluation.generation_set import validate_generation_case
from evaluation.identity_eval import run_identity_case
from rag.conversation import ConversationState


def load_scenarios(path: str | Path) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError("multi-turn scenario file must contain a non-empty JSON array")
    ids: set[str] = set()
    for scenario in data:
        scenario_id = str(scenario.get("id") or "")
        if not scenario_id or scenario_id in ids:
            raise ValueError(f"invalid or duplicate scenario id: {scenario_id!r}")
        ids.add(scenario_id)
        turns = scenario.get("turns")
        if not isinstance(turns, list) or len(turns) < 2:
            raise ValueError(f"scenario {scenario_id!r} requires at least two turns")
        for index, turn in enumerate(turns, 1):
            case = _turn_case(scenario, turn, index)
            validate_generation_case(case)
    return data


def _turn_case(scenario: dict, turn: dict, index: int) -> dict:
    expected_lane = turn["expected_lane"]
    return {
        **turn,
        "id": f"{scenario['id']}-T{index:02d}",
        "question": turn["query"],
        "lane": expected_lane,
        "identity": turn.get("identity", scenario.get("identity", {"signed_in": False})),
        "tags": list(dict.fromkeys(["multi_turn", *scenario.get("tags", []),
                                     *turn.get("tags", [])])),
    }


def run_scenario(scenario: dict, *, embedder, store, llm, order_store,
                 trace_path: str, small_llm=None, domain: str = "china_ecommerce",
                 catalog_store=None) -> dict:
    identity = scenario.get("identity") or {"signed_in": False}
    owner_id = str(identity.get("user_id") or "anonymous")
    tenant_id = str(identity.get("tenant_id") or "default")
    state = ConversationState(session_id=scenario["id"], owner_id=owner_id,
                              tenant_id=tenant_id)
    history: list[dict] = []
    results = []
    last_clarification = ""
    repeated_clarifications = 0
    for index, turn in enumerate(scenario["turns"], 1):
        case = _turn_case(scenario, turn, index)
        result = run_identity_case(
            case, embedder=embedder, store=store, llm=llm, order_store=order_store,
            small_llm=small_llm, trace_path=trace_path, domain=domain,
            catalog_store=catalog_store, history=history, conversation_state=state,
        )
        answer = result["answer"]
        if result["action"] == "clarify":
            normalized = re.sub(r"\s+", "", answer).casefold()
            if (last_clarification and normalized == last_clarification
                    and not scenario.get("allow_repeated_clarification")):
                repeated_clarifications += 1
            last_clarification = normalized
            state.clarification_count += 1
        state.lane = result["lane"]
        if result["action"] == "escalate":
            state.task_status = "escalated"
        state.evidence_ids = [str(c.get("id")) for c in result["citations"] if c.get("id")]
        history.extend([
            {"role": "user", "content": case["question"]},
            {"role": "assistant", "content": answer},
        ])
        state.recent_turns = history[-12:]
        results.append(result)
    return {
        "id": scenario["id"],
        "turn_count": len(results),
        "turns": results,
        "repeated_clarifications": repeated_clarifications,
        "final_state": {
            "lane": state.lane,
            "task_status": state.task_status,
            "clarification_count": state.clarification_count,
            "evidence_ids": list(state.evidence_ids),
        },
    }


def aggregate_scenarios(results: list[dict]) -> dict:
    turns = [turn for result in results for turn in result["turns"]]
    if not turns:
        return {"scenario_count": 0, "turn_count": 0, "lane_accuracy": None,
                "action_accuracy": None, "privacy_safe_rate": None,
                "repeated_clarification_rate": None}
    repeated = sum(result["repeated_clarifications"] for result in results)
    clarifications = sum(
        1 for turn in turns if turn["action"] == "clarify"
    )
    return {
        "scenario_count": len(results),
        "turn_count": len(turns),
        "lane_accuracy": round(sum(bool(t["lane_correct"]) for t in turns) / len(turns), 3),
        "action_accuracy": round(sum(
            bool(t["contract_scores"]["action_correct"]) for t in turns
        ) / len(turns), 3),
        "privacy_safe_rate": round(sum(bool(t["privacy_safe"]) for t in turns) / len(turns), 3),
        "repeated_clarification_rate": (
            round(repeated / clarifications, 3) if clarifications else 0.0
        ),
    }
