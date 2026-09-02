from evaluation.repeatability import compare_reports


def _report(*, context_precision=0.81, working_tree_hash="same"):
    return {
        "manifest": {
            "git_sha": "abc", "working_tree_hash": working_tree_hash,
            "domain": "china_ecommerce", "dataset_hashes": {"set": "hash"},
            "models": {"answer": "a", "judge": "j"},
            "knowledge_version": "v1", "parameters": {"top_k": 8}, "seed": 42,
        },
        "results": {
            "routing": {"with_tiebreak": {"accuracy": 1.0}},
            "ragas": {
                "dataset_size": 30, "evaluated_size": 30,
                "scores": {"overall": {
                    "faithfulness": .95, "answer_relevance": .83,
                    "context_precision": context_precision, "context_recall": .97,
                }},
                "deterministic_contract": {
                    "action_accuracy": 1.0, "required_fact_recall": 1.0,
                    "forbidden_claim_free_rate": 1.0,
                },
            },
        },
    }


def test_repeatability_accepts_delta_at_threshold():
    result = compare_reports(_report(context_precision=.80),
                             _report(context_precision=.82))
    assert result["stable"]
    assert result["metrics"]["generation.context_precision"]["absolute_delta"] == .02


def test_repeatability_fails_metric_or_configuration_drift():
    metric_drift = compare_reports(_report(context_precision=.80),
                                   _report(context_precision=.821))
    assert not metric_drift["stable"]
    config_drift = compare_reports(_report(), _report(working_tree_hash="changed"))
    assert not config_drift["stable"]
    assert config_drift["configuration_mismatches"] == ["working_tree_hash"]


def test_repeatability_fails_an_incomplete_run_even_when_scores_are_stable():
    run_b = _report()
    run_b["results"]["ragas"]["evaluated_size"] = 29
    result = compare_reports(_report(), run_b)
    assert not result["stable"]
    assert not result["evaluation_complete"]
