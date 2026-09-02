from adapters.fakes import EchoLLM, HashEmbedder, InMemoryHybridStore
from data.orders import JsonOrderStore
from evaluation.scenario_eval import aggregate_scenarios, load_scenarios, run_scenario

SCENARIO_PATH = "domains/china_ecommerce/eval/generation_multiturn_candidates.json"
ORDER_PATH = "domains/china_ecommerce/seed/unstructured/orders.jsonl"


def _run(scenario, tmp_path):
    return run_scenario(
        scenario,
        embedder=HashEmbedder(),
        store=InMemoryHybridStore(),
        llm=EchoLLM(),
        order_store=JsonOrderStore.from_path(ORDER_PATH),
        trace_path=str(tmp_path / "scenario-traces.jsonl"),
    )


def test_multiturn_candidate_file_has_five_scenarios_and_twenty_turns():
    scenarios = load_scenarios(SCENARIO_PATH)
    assert len(scenarios) == 5
    assert sum(len(scenario["turns"]) for scenario in scenarios) == 20
    assert all(scenario.get("review_status") == "pending" for scenario in scenarios)


def test_order_followups_retain_lane_and_order_entity(tmp_path):
    result = _run(load_scenarios(SCENARIO_PATH)[0], tmp_path)
    assert all(turn["lane"] == "care" for turn in result["turns"])
    assert all(turn["action"] == "answer" for turn in result["turns"])
    assert {c["id"] for c in result["turns"][2]["citations"]} == {"RF100011"}
    assert result["final_state"]["evidence_ids"] == ["RF100012"]


def test_multiturn_authorization_scenarios_never_leak(tmp_path):
    scenarios = load_scenarios(SCENARIO_PATH)
    results = [_run(scenario, tmp_path) for scenario in scenarios[1:4]]
    turns = [turn for result in results for turn in result["turns"]]
    assert all(turn["privacy_safe"] for turn in turns)
    assert all(not turn["citations"] for turn in turns)
    assert all(turn["action"] == "clarify" for turn in turns)


def test_multiturn_offline_contract_baseline_is_complete(tmp_path):
    results = [_run(scenario, tmp_path) for scenario in load_scenarios(SCENARIO_PATH)]
    summary = aggregate_scenarios(results)
    assert summary == {
        "scenario_count": 5,
        "turn_count": 20,
        "lane_accuracy": 1.0,
        "action_accuracy": 1.0,
        "privacy_safe_rate": 1.0,
        "repeated_clarification_rate": 0.0,
    }
