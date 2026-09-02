"""Typed contracts at the boundaries of routing, retrieval and response planning."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

SourceType = Literal["catalog", "policy", "guide", "order", "graph", "review", "metric"]
RetrievalMode = Literal["structured", "dense", "sparse", "hybrid", "order_service", "none"]
ResponseAction = Literal["answer", "clarify", "abstain", "escalate", "workflow"]


@dataclass(frozen=True)
class LanePolicy:
    name: str
    intents: tuple[str, ...] = ()
    priority: int = 0
    auth_required: bool = False
    required_slots: tuple[str, ...] = ()
    allowed_sources: tuple[str, ...] = ()
    preferred_sources: tuple[str, ...] = ()
    retrieval_mode: RetrievalMode = "hybrid"
    retrieval_modes: dict[str, RetrievalMode] = field(default_factory=dict)
    top_k: int = 8
    top_k_in: int = 50
    min_confidence: float = 0.22
    failure_action: ResponseAction = "clarify"
    personalization: bool = False


@dataclass(frozen=True)
class RetrievalPlan:
    lane: str
    mode: RetrievalMode
    allowed_sources: tuple[str, ...]
    preferred_sources: tuple[str, ...]
    top_k: int
    top_k_in: int
    min_confidence: float
    query_type: str = "factual"
    filters: dict[str, Any] = field(default_factory=dict)
    reason: str = "lane policy"


@dataclass
class EvidenceItem:
    source_type: SourceType
    source_id: str
    content: str
    structured_fields: dict[str, Any] = field(default_factory=dict)
    authority_level: int = 1
    effective_at: str | None = None
    expires_at: str | None = None
    user_scope: str | None = None
    tenant_scope: str | None = None
    retrieval_score: float = 0.0
    rerank_score: float | None = None
    citation_id: str | None = None
    knowledge_version: str | None = None

    def expired(self, now: datetime | None = None) -> bool:
        if not self.expires_at:
            return False
        try:
            expiry = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
            return expiry <= (now or datetime.now(timezone.utc))
        except ValueError:
            return True  # malformed lifecycle metadata fails closed

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ClarificationDecision:
    required: bool
    reason: str = ""
    missing_slots: tuple[str, ...] = ()
    question: str | None = None


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    citation_coverage: float
    unsupported_claims: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    reason: str = ""
