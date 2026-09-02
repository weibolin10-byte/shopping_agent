from evaluation.generation_set import load_generation_set
from evaluation.resilience_eval import (
    aggregate_resilience,
    load_resilience_cases,
    run_resilience_case,
)
from evaluation.scenario_eval import load_scenarios

PUBLIC_PATH = "domains/china_ecommerce/eval/generation_candidates.jsonl"
IDENTITY_PATH = "domains/china_ecommerce/eval/generation_identity_candidates.jsonl"
MULTITURN_PATH = "domains/china_ecommerce/eval/generation_multiturn_candidates.json"
RESILIENCE_PATH = "domains/china_ecommerce/eval/generation_resilience_candidates.jsonl"


def test_resilience_candidate_set_has_eighteen_pending_cases():
    rows = load_resilience_cases(RESILIENCE_PATH)
    assert len(rows) == 18
    assert all(row["review_status"] == "pending" for row in rows)
    assert {row["profile"] for row in rows} == {
        "context_injection", "input_attack", "evidence_conflict",
        "dependency_failure", "forged_history",
    }


def test_every_resilience_fixture_passes_offline_contract():
    results = [run_resilience_case(case) for case in load_resilience_cases(RESILIENCE_PATH)]
    summary = aggregate_resilience(results)
    assert summary["count"] == 18
    assert summary["pass_rate"] == 1.0
    assert summary["secret_safe_rate"] == 1.0


def test_first_regression_candidate_inventory_totals_eighty_cases():
    public = len(load_generation_set(PUBLIC_PATH))
    identity = len(load_generation_set(IDENTITY_PATH))
    multiturn = sum(len(scenario["turns"]) for scenario in load_scenarios(MULTITURN_PATH))
    resilience = len(load_resilience_cases(RESILIENCE_PATH))
    assert {"public": public, "identity": identity,
            "multiturn": multiturn, "resilience": resilience} == {
                "public": 30, "identity": 12, "multiturn": 20, "resilience": 18,
            }
    assert public + identity + multiturn + resilience == 80
