"""Compare two canonical evaluation reports from the same frozen configuration."""
from __future__ import annotations

import json
from pathlib import Path


def _load(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _metrics(report: dict) -> dict[str, float]:
    results = report["results"]
    ragas = results["ragas"]
    scores = ragas["scores"]["overall"]
    contract = ragas["deterministic_contract"]
    routing = results["routing"]["with_tiebreak"]
    return {
        "routing.accuracy": float(routing["accuracy"]),
        "generation.faithfulness": float(scores["faithfulness"]),
        "generation.answer_relevance": float(scores["answer_relevance"]),
        "generation.context_precision": float(scores["context_precision"]),
        "generation.context_recall": float(scores["context_recall"]),
        "contract.action_accuracy": float(contract["action_accuracy"]),
        "contract.required_fact_recall": float(contract["required_fact_recall"]),
        "contract.forbidden_claim_free_rate": float(
            contract["forbidden_claim_free_rate"]
        ),
    }


def compare_reports(run_a: dict, run_b: dict, *, max_absolute_delta: float = 0.02) -> dict:
    """Fail closed unless configuration hashes match and every core metric is stable."""
    manifest_a, manifest_b = run_a["manifest"], run_b["manifest"]
    comparable_fields = ("git_sha", "working_tree_hash", "domain", "dataset_hashes", "models",
                         "knowledge_version", "parameters", "seed")
    mismatches = [field for field in comparable_fields
                  if manifest_a.get(field) != manifest_b.get(field)]
    metrics_a, metrics_b = _metrics(run_a), _metrics(run_b)
    ragas_a = run_a["results"]["ragas"]
    ragas_b = run_b["results"]["ragas"]
    completeness = {
        "run_a": {
            "dataset_size": int(ragas_a["dataset_size"]),
            "evaluated_size": int(ragas_a["evaluated_size"]),
        },
        "run_b": {
            "dataset_size": int(ragas_b["dataset_size"]),
            "evaluated_size": int(ragas_b["evaluated_size"]),
        },
    }
    complete = all(row["dataset_size"] == row["evaluated_size"]
                   for row in completeness.values())
    rows = {}
    for name in metrics_a:
        delta = round(abs(metrics_b[name] - metrics_a[name]), 6)
        rows[name] = {
            "run_a": metrics_a[name], "run_b": metrics_b[name],
            "absolute_delta": delta, "stable": delta <= max_absolute_delta,
        }
    stable = not mismatches and complete and all(row["stable"] for row in rows.values())
    return {
        "stable": stable,
        "max_absolute_delta": max_absolute_delta,
        "configuration_mismatches": mismatches,
        "evaluation_complete": complete,
        "completeness": completeness,
        "metrics": rows,
    }


def compare_report_files(run_a: str | Path, run_b: str | Path,
                         *, max_absolute_delta: float = 0.02) -> dict:
    return compare_reports(_load(run_a), _load(run_b),
                           max_absolute_delta=max_absolute_delta)
