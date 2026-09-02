"""Contracts and deterministic checks for answer-generation evaluation sets.

Generation quality is deliberately stored separately from retrieval golden data.  The loader
rejects incomplete or duplicate cases before an online evaluation can spend model budget, while
the deterministic scorer complements an LLM judge for facts and response actions that should not
depend on subjective grading.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ALLOWED_ACTIONS = {"answer", "abstain", "clarify", "escalate"}
ALLOWED_LANES = {"answers", "stylist", "care", "complaint", "escalation"}
ALLOWED_DIFFICULTIES = {"common", "semi", "edge"}
ALLOWED_REVIEW_STATUSES = {"pending", "approved", "rejected"}
REQUIRED_FIELDS = {"id", "question", "lane", "difficulty", "expected_action", "tags"}


def _string_list(value, *, allow_empty: bool = False) -> bool:
    return (isinstance(value, list) and (allow_empty or bool(value))
            and all(isinstance(v, str) and v.strip() for v in value))


def validate_generation_case(case: dict, *, line_number: int | None = None) -> None:
    """Raise ``ValueError`` when a generation-eval record violates the public schema."""
    where = f" at line {line_number}" if line_number is not None else ""
    missing = sorted(REQUIRED_FIELDS - set(case))
    if missing:
        raise ValueError(f"generation case{where} is missing fields: {', '.join(missing)}")
    if not isinstance(case["id"], str) or not case["id"].strip():
        raise ValueError(f"generation case{where} has an invalid id")
    if not isinstance(case["question"], str) or not case["question"].strip():
        raise ValueError(f"generation case {case['id']!r} has an empty question")
    if case["lane"] not in ALLOWED_LANES:
        raise ValueError(f"generation case {case['id']!r} has invalid lane {case['lane']!r}")
    if case["difficulty"] not in ALLOWED_DIFFICULTIES:
        raise ValueError(
            f"generation case {case['id']!r} has invalid difficulty {case['difficulty']!r}"
        )
    if case["expected_action"] not in ALLOWED_ACTIONS:
        raise ValueError(
            f"generation case {case['id']!r} has invalid action {case['expected_action']!r}"
        )
    if not _string_list(case["tags"]):
        raise ValueError(f"generation case {case['id']!r} must have non-empty string tags")

    for field in ("required_answer_terms", "forbidden_answer_terms", "citation_targets",
                  "must_not_disclose"):
        if field in case and not _string_list(case[field], allow_empty=True):
            raise ValueError(f"generation case {case['id']!r} has invalid {field}")
    facts = case.get("required_facts", {})
    if not isinstance(facts, dict) or any(not str(k).strip() for k in facts):
        raise ValueError(f"generation case {case['id']!r} has invalid required_facts")
    review_status = case.get("review_status")
    if review_status is not None and review_status not in ALLOWED_REVIEW_STATUSES:
        raise ValueError(
            f"generation case {case['id']!r} has invalid review_status {review_status!r}"
        )
    if "source_refs" in case and not _string_list(case["source_refs"]):
        raise ValueError(f"generation case {case['id']!r} has invalid source_refs")
    expected_lane = case.get("expected_lane")
    if expected_lane is not None and expected_lane not in ALLOWED_LANES:
        raise ValueError(f"generation case {case['id']!r} has invalid expected_lane")
    identity = case.get("identity")
    if identity is not None:
        if not isinstance(identity, dict) or not isinstance(identity.get("signed_in"), bool):
            raise ValueError(f"generation case {case['id']!r} has invalid identity")
        if identity["signed_in"] and not all(
            str(identity.get(key) or "").strip() for key in ("name", "user_id", "tenant_id")
        ):
            raise ValueError(
                f"signed-in generation case {case['id']!r} requires name, user_id and tenant_id"
            )
    if case["expected_action"] == "answer":
        if not str(case.get("reference_answer", "")).strip():
            raise ValueError(f"answer case {case['id']!r} requires reference_answer")
        if not case.get("required_answer_terms"):
            raise ValueError(f"answer case {case['id']!r} requires required_answer_terms")


def load_generation_set(path: str | Path, *, require_approved: bool = False) -> list[dict]:
    """Load and validate a JSONL generation set, rejecting duplicate ids and questions."""
    rows: list[dict] = []
    seen_ids: set[str] = set()
    seen_questions: set[str] = set()
    with open(path, encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            try:
                case = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid generation JSON at line {line_number}: {exc}") from exc
            if not isinstance(case, dict):
                raise ValueError(f"generation case at line {line_number} must be an object")
            validate_generation_case(case, line_number=line_number)
            if require_approved and case.get("review_status") != "approved":
                raise ValueError(
                    f"generation case {case['id']!r} is not approved for formal evaluation"
                )
            if case["id"] in seen_ids:
                raise ValueError(f"duplicate generation id: {case['id']}")
            normalized_question = re.sub(r"\s+", "", case["question"]).casefold()
            if normalized_question in seen_questions:
                raise ValueError(f"duplicate generation question: {case['question']}")
            seen_ids.add(case["id"])
            seen_questions.add(normalized_question)
            rows.append(case)
    if not rows:
        raise ValueError(f"generation set is empty: {path}")
    return rows


def generation_set_summary(rows: list[dict]) -> dict:
    """Return coverage counts used during dataset review and CI validation."""
    def counts(field: str) -> dict[str, int]:
        out: dict[str, int] = {}
        for row in rows:
            value = str(row.get(field) or "unspecified")
            out[value] = out.get(value, 0) + 1
        return dict(sorted(out.items()))

    tags: dict[str, int] = {}
    for row in rows:
        for tag in row.get("tags", []):
            tags[tag] = tags.get(tag, 0) + 1
    return {
        "count": len(rows),
        "by_lane": counts("lane"),
        "by_action": counts("expected_action"),
        "by_difficulty": counts("difficulty"),
        "by_review_status": counts("review_status"),
        "by_tag": dict(sorted(tags.items())),
    }


def score_generation_contract(case: dict, *, answer: str, actual_action: str) -> dict:
    """Score exact facts and action choice without an LLM judge.

    ``required_answer_terms`` may contain alternatives separated by ``|``.  For example,
    ``"不建议|避免"`` passes when either expression appears.  This keeps deterministic checks
    tolerant of harmless wording changes while retaining exact validation for prices and dates.
    """
    normalized_answer = re.sub(r"\s+", "", answer).casefold()
    groups = case.get("required_answer_terms") or []
    term_results = []
    for group in groups:
        alternatives = [re.sub(r"\s+", "", part).casefold() for part in group.split("|")]
        term_results.append(any(part in normalized_answer for part in alternatives))
    forbidden_hits = [
        term for term in case.get("forbidden_answer_terms", [])
        if re.sub(r"\s+", "", term).casefold() in normalized_answer
    ]
    return {
        "action_correct": actual_action == case["expected_action"],
        "required_fact_recall": (
            round(sum(term_results) / len(term_results), 3) if term_results else None
        ),
        "forbidden_claims": forbidden_hits,
        "forbidden_claim_free": not forbidden_hits,
    }


def aggregate_contract_scores(rows: list[dict]) -> dict:
    """Aggregate deterministic checks, keeping denominators visible in the report."""
    if not rows:
        return {"count": 0, "action_accuracy": None, "required_fact_recall": None,
                "forbidden_claim_free_rate": None}
    fact_scores = [r["required_fact_recall"] for r in rows
                   if r.get("required_fact_recall") is not None]
    return {
        "count": len(rows),
        "action_accuracy": round(sum(bool(r["action_correct"]) for r in rows) / len(rows), 3),
        "required_fact_recall": (
            round(sum(fact_scores) / len(fact_scores), 3) if fact_scores else None
        ),
        "forbidden_claim_free_rate": round(
            sum(bool(r["forbidden_claim_free"]) for r in rows) / len(rows), 3
        ),
    }
