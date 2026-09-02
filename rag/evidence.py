"""Evidence normalization, lifecycle filtering, deduplication and deterministic validation."""
from __future__ import annotations

import re
from collections import defaultdict

from pipeline.text import is_evidence_claim, lexical_units, sentence_split
from rag.contracts import EvidenceItem, ValidationResult

_CITATION = re.compile(r"\[([\d,\s]+)\]")
_STRUCTURED_KEYS = ("price", "stock", "size", "status", "order_status", "effective_at")


def evidence_from_context(context: dict, *, knowledge_version: str | None = None) -> EvidenceItem:
    doc_type = context.get("doc_type") or "guide"
    source_type = {"product": "catalog", "review": "review", "order": "order",
                   "policy": "policy", "graph": "graph", "supplier": "graph",
                   "store": "graph", "metric": "metric"}.get(
                       doc_type, "guide")
    metadata = context.get("metadata") or {}
    return EvidenceItem(
        source_type=source_type, source_id=str(context.get("id") or ""),
        content=context.get("text") or "", structured_fields=metadata.get("structured_fields", {}),
        authority_level=int(metadata.get("authority_level", 1)),
        effective_at=metadata.get("effective_at"), expires_at=metadata.get("expires_at"),
        user_scope=metadata.get("user_scope"), tenant_scope=metadata.get("tenant_scope"),
        retrieval_score=float(context.get("score") or 0.0),
        rerank_score=context.get("rerank_score"), citation_id=str(context.get("n") or ""),
        knowledge_version=metadata.get("knowledge_version") or knowledge_version)


def assemble_evidence(contexts: list[dict], *, allowed_sources: tuple[str, ...] = (),
                      user_scope: str | None = None, tenant_scope: str | None = None,
                      knowledge_version: str | None = None) -> list[EvidenceItem]:
    """Normalize and filter evidence. Private scope mismatches always fail closed."""
    dedup: dict[tuple[str, str], EvidenceItem] = {}
    for context in contexts:
        item = evidence_from_context(context, knowledge_version=knowledge_version)
        if allowed_sources and item.source_type not in allowed_sources:
            continue
        if item.expired():
            continue
        if item.user_scope and item.user_scope != user_scope:
            continue
        if item.tenant_scope and item.tenant_scope != tenant_scope:
            continue
        key = (item.source_type, item.source_id)
        old = dedup.get(key)
        if old is None or (item.authority_level, item.retrieval_score) > \
                (old.authority_level, old.retrieval_score):
            dedup[key] = item
    return sorted(dedup.values(), key=lambda i: (i.authority_level, i.retrieval_score),
                  reverse=True)


def detect_conflicts(items: list[EvidenceItem]) -> tuple[str, ...]:
    """Find conflicting authoritative structured values for the same source entity."""
    values: dict[tuple[str, str], set[str]] = defaultdict(set)
    for item in items:
        entity = str(item.structured_fields.get("product_id")
                     or item.structured_fields.get("order_id")
                     or item.structured_fields.get("policy_id") or item.source_id)
        for key in _STRUCTURED_KEYS:
            if key in item.structured_fields and item.structured_fields[key] is not None:
                values[(entity, key)].add(str(item.structured_fields[key]))
    return tuple(f"{entity}.{key}: {sorted(found)}" for (entity, key), found in values.items()
                 if len(found) > 1)


def validate_answer(answer: str, items: list[EvidenceItem]) -> ValidationResult:
    sentences = [sentence for sentence in sentence_split(answer)
                 if is_evidence_claim(sentence)]
    if not sentences:
        return ValidationResult(True, 1.0, reason="no factual claims")
    by_citation = {str(item.citation_id): set(lexical_units(item.content)) for item in items
                   if item.citation_id}
    supported = 0
    unsupported: list[str] = []
    for sentence in sentences:
        citations: set[str] = set()
        for group in _CITATION.findall(sentence):
            citations.update(p.strip() for p in group.split(",") if p.strip())
        claim = set(lexical_units(_CITATION.sub("", sentence)))
        if citations and any(c in by_citation and (not claim or claim & by_citation[c])
                             for c in citations):
            supported += 1
        elif claim:
            unsupported.append(sentence)
    conflicts = detect_conflicts(items)
    coverage = supported / len(sentences)
    reason = "ok" if not unsupported and not conflicts else "evidence validation failed"
    return ValidationResult(not unsupported and not conflicts, coverage,
                            tuple(unsupported), conflicts, reason)
