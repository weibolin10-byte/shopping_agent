import json

import pytest

from evaluation.generation_set import (
    aggregate_contract_scores,
    generation_set_summary,
    load_generation_set,
    score_generation_contract,
    validate_generation_case,
)


def _case(**overrides):
    case = {
        "id": "GEN001",
        "question": "这双鞋多少钱？",
        "lane": "answers",
        "difficulty": "common",
        "expected_action": "answer",
        "reference_answer": "这双鞋售价899元。",
        "required_facts": {"price_cny": 899},
        "required_answer_terms": ["899"],
        "forbidden_answer_terms": [],
        "citation_targets": ["P001"],
        "tags": ["price"],
    }
    case.update(overrides)
    return case


def test_generation_case_requires_machine_checkable_answer_terms():
    with pytest.raises(ValueError, match="required_answer_terms"):
        validate_generation_case(_case(required_answer_terms=[]))


def test_generation_loader_rejects_duplicate_questions(tmp_path):
    path = tmp_path / "generation.jsonl"
    rows = [_case(), _case(id="GEN002", question="这 双鞋 多少钱？")]
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate generation question"):
        load_generation_set(path)


def test_formal_loader_rejects_pending_candidate(tmp_path):
    path = tmp_path / "generation.jsonl"
    path.write_text(json.dumps(_case(review_status="pending"), ensure_ascii=False),
                    encoding="utf-8")
    with pytest.raises(ValueError, match="not approved"):
        load_generation_set(path, require_approved=True)


def test_contract_score_supports_wording_alternatives_and_forbidden_claims():
    case = _case(
        required_answer_terms=["899", "有货|现货"],
        forbidden_answer_terms=["永久保修"],
    )
    score = score_generation_contract(
        case, answer="目前有现货，售价 899 元，并非永久保修。", actual_action="answer"
    )
    assert score["required_fact_recall"] == 1.0
    assert score["forbidden_claim_free"] is False
    assert score["forbidden_claims"] == ["永久保修"]


def test_contract_aggregate_exposes_denominators():
    summary = aggregate_contract_scores([
        {"action_correct": True, "required_fact_recall": 1.0,
         "forbidden_claim_free": True},
        {"action_correct": False, "required_fact_recall": 0.5,
         "forbidden_claim_free": True},
    ])
    assert summary == {
        "count": 2,
        "action_accuracy": 0.5,
        "required_fact_recall": 0.75,
        "forbidden_claim_free_rate": 1.0,
    }


def test_checked_in_smoke_set_is_valid_and_explicit():
    rows = load_generation_set(
        "domains/china_ecommerce/eval/generation_smoke.jsonl"
    )
    assert len(rows) == 11
    assert {row["lane"] for row in rows} == {"answers", "stylist"}
    assert all(row.get("legacy_source_id") for row in rows)


def test_candidate_batch_is_valid_pending_data_with_expected_coverage():
    rows = load_generation_set(
        "domains/china_ecommerce/eval/generation_candidates.jsonl"
    )
    summary = generation_set_summary(rows)
    assert summary["count"] == 30
    assert summary["by_lane"] == {"answers": 21, "stylist": 9}
    assert summary["by_action"] == {"abstain": 2, "answer": 28}
    assert summary["by_review_status"] == {"pending": 30}
    assert all(row.get("source_refs") for row in rows)
