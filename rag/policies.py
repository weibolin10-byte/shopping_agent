"""Manifest-backed lane policies with fail-closed validation and safe defaults."""
from __future__ import annotations

import os
from functools import lru_cache

from data.lakehouse import load_manifest
from rag.contracts import LanePolicy, RetrievalPlan
from rag.understand import heuristic_route

_DEFAULTS = {
    "stylist": dict(intents=("recommend", "compare", "gift"), priority=30,
                    allowed_sources=("catalog", "guide", "review", "graph"),
                    preferred_sources=("catalog", "guide"), retrieval_mode="hybrid",
                    personalization=True, failure_action="clarify"),
    "care": dict(intents=("order", "account"), priority=80, auth_required=True,
                 allowed_sources=("order", "policy"), preferred_sources=("order",),
                 retrieval_mode="order_service", failure_action="clarify"),
    "complaint": dict(intents=("complaint", "refund"), priority=100,
                      allowed_sources=("order", "policy", "guide"),
                      preferred_sources=("order", "policy"), retrieval_mode="hybrid",
                      failure_action="escalate"),
    "answers": dict(intents=("fact", "policy"), priority=20,
                    allowed_sources=("catalog", "policy", "guide", "graph", "review"),
                    preferred_sources=("policy", "catalog"), retrieval_mode="hybrid",
                    failure_action="abstain"),
    "escalation": dict(intents=("human",), priority=120, allowed_sources=(),
                       preferred_sources=(), retrieval_mode="none", failure_action="escalate"),
}

_SOURCE_TO_DOC_TYPES = {
    "catalog": ("product",), "policy": ("policy",), "guide": ("guide",),
    "order": ("order",), "review": ("review",),
    "graph": ("graph", "supplier", "store"),
    "metric": ("metric",),
}


def _tuple(value) -> tuple:
    return tuple(value or ())


@lru_cache(maxsize=16)
def load_lane_policies(domain: str, domains_dir: str = "domains") -> dict[str, LanePolicy]:
    manifest = load_manifest(os.path.join(domains_dir, domain))
    configured = manifest.get("lanes", {}) or {}
    policies: dict[str, LanePolicy] = {}
    for name, defaults in _DEFAULTS.items():
        row = {**defaults, **(configured.get(name, {}) or {})}
        for key in ("intents", "required_slots", "allowed_sources", "preferred_sources"):
            row[key] = _tuple(row.get(key))
        policy = LanePolicy(name=name, **row)
        unknown = set(policy.allowed_sources) - set(_SOURCE_TO_DOC_TYPES)
        if unknown:
            raise ValueError(f"lane {name} has unknown sources: {sorted(unknown)}")
        if not 1 <= policy.top_k <= policy.top_k_in <= 200:
            raise ValueError(f"lane {name} has invalid top-k bounds")
        valid_modes = {"structured", "dense", "sparse", "hybrid", "order_service", "none"}
        unknown_query_types = set(policy.retrieval_modes) - {
            "factual", "relational", "qualitative", "metric"
        }
        unknown_modes = set(policy.retrieval_modes.values()) - valid_modes
        if unknown_query_types or unknown_modes:
            raise ValueError(
                f"lane {name} has invalid query-type retrieval modes: "
                f"types={sorted(unknown_query_types)}, modes={sorted(unknown_modes)}"
            )
        policies[name] = policy
    return policies


def retrieval_plan(lane: str, domain: str, *, signed_in: bool = False,
                   tenant_id: str | None = None, user_id: str | None = None,
                   query: str | None = None) -> RetrievalPlan:
    policy = load_lane_policies(domain).get(lane) or load_lane_policies(domain)["answers"]
    query_type = heuristic_route(query or "")
    mode = policy.retrieval_modes.get(query_type, policy.retrieval_mode)
    filters = {"tenant_scope": tenant_id} if tenant_id else {}
    if policy.auth_required and signed_in and user_id:
        filters["user_scope"] = user_id
    return RetrievalPlan(
        lane=policy.name, mode=mode,
        allowed_sources=policy.allowed_sources,
        preferred_sources=policy.preferred_sources, top_k=policy.top_k,
        top_k_in=policy.top_k_in, min_confidence=policy.min_confidence,
        filters=filters, query_type=query_type,
        reason=("authenticated" if signed_in else "anonymous")
        + f" lane policy; query_type={query_type}; mode={mode}")


def allowed_doc_types(plan: RetrievalPlan) -> tuple[str, ...]:
    out: list[str] = []
    for source in plan.allowed_sources:
        out.extend(_SOURCE_TO_DOC_TYPES[source])
    return tuple(dict.fromkeys(out))
