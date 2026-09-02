from adapters.fakes import EchoLLM, HashEmbedder, InMemoryHybridStore
from data.orders import JsonOrderStore, order_id_from_query
from evaluation.generation_set import generation_set_summary, load_generation_set
from evaluation.identity_eval import aggregate_identity_results, run_identity_case

IDENTITY_PATH = "domains/china_ecommerce/eval/generation_identity_candidates.jsonl"
ORDER_PATH = "domains/china_ecommerce/seed/unstructured/orders.jsonl"


def _run(case, tmp_path):
    return run_identity_case(
        case,
        embedder=HashEmbedder(),
        store=InMemoryHybridStore(),
        llm=EchoLLM(),
        order_store=JsonOrderStore.from_path(ORDER_PATH),
        trace_path=str(tmp_path / "identity-traces.jsonl"),
    )


def test_identity_candidate_batch_is_valid_and_pending():
    rows = load_generation_set(IDENTITY_PATH)
    summary = generation_set_summary(rows)
    assert summary["count"] == 12
    assert summary["by_review_status"] == {"pending": 12}
    assert summary["by_lane"] == {"care": 8, "complaint": 3, "escalation": 1}


def test_order_id_is_extracted_when_touching_chinese_text():
    assert order_id_from_query("订单RF100011到哪了？") == "RF100011"
    assert order_id_from_query("查询RF100012。") == "RF100012"
    assert order_id_from_query("商品XRF100011不是订单号") is None


def test_json_order_store_indexes_business_order_id_not_document_id():
    store = JsonOrderStore.from_path(ORDER_PATH)
    rows = store.find(user_id="zhangwei@example.com", tenant_id="default",
                      order_id="RF100011")
    assert [row.order_id for row in rows] == ["RF100011"]


def test_anonymous_order_query_clarifies_without_private_data(tmp_path):
    case = load_generation_set(IDENTITY_PATH)[1]
    result = _run(case, tmp_path)
    assert result["lane"] == "care"
    assert result["action"] == "clarify"
    assert result["privacy_safe"] is True
    assert not result["citations"]


def test_verified_owner_can_read_only_their_order(tmp_path):
    case = load_generation_set(IDENTITY_PATH)[2]
    result = _run(case, tmp_path)
    assert result["action"] == "answer"
    assert result["lane_correct"] is True
    assert "RF100011" in result["answer"]
    assert result["contract_scores"]["required_fact_recall"] == 1.0
    assert {c["id"] for c in result["citations"]} == {"RF100011"}


def test_cross_user_and_cross_tenant_order_queries_fail_closed(tmp_path):
    rows = load_generation_set(IDENTITY_PATH)
    results = [_run(rows[index], tmp_path) for index in (6, 7)]
    assert all(result["action"] == "clarify" for result in results)
    assert all(result["privacy_safe"] for result in results)
    assert all(not result["citations"] for result in results)
    summary = aggregate_identity_results(results)
    assert summary["privacy_safe_rate"] == 1.0
    assert summary["action_accuracy"] == 1.0
