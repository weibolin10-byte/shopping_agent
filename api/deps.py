"""Build the retrieval/answer components once from config. Tests override this dependency
with offline fakes and a seeded store."""
from __future__ import annotations

import logging
import os
import pickle
from functools import lru_cache

from adapters.config import get_settings
from adapters.factory import (
    make_embedder,
    make_graph,
    make_llm,
    make_reranker,
    make_small_llm,
    make_store,
    make_transcriber,
)
from api.resilience import (
    CachingEmbedder,
    CachingReranker,
    ResilientEmbedder,
    ResilientLLM,
    ResilientReranker,
    ResilientStore,
)
from data.catalog_store import StructuredCatalogStore
from data.metrics import MetricResolver
from data.orders import make_order_store
from ingest.naming import collection_name
from rag.answer_cache import RedisAnswerCache, SemanticAnswerCache
from rag.conversation import make_conversation_store
from rag.hitl import ReviewQueue
from retrieval.graph import make_graph_retriever

_log = logging.getLogger("shopping_agent.api")


def _build_graph_retriever(domain: str):
    # Builds a name index by scanning the graph, so a graph that is down or unbuilt must not take
    # the whole app down; degrade to no graph evidence and log it.
    try:
        return make_graph_retriever(domain, make_graph())
    except Exception as exc:  # noqa: BLE001 - any backend error should degrade, not crash chat
        _log.warning("graph retriever unavailable (%s); answers will not use the graph", exc)
        return None


@lru_cache
def get_components() -> dict:
    settings = get_settings()
    lakehouse_db = os.getenv("LAKEHOUSE_DB", "lakehouse.duckdb")
    # Chat still works vector-only without a lakehouse, but a missing one silently disables the
    # metric layer. Log it once so the loss is visible instead of a mystery in production.
    if not os.path.exists(lakehouse_db):
        _log.warning("lakehouse not found at %s; metric answers are disabled. Run make lakehouse.",
                     lakehouse_db)
    reranker = make_reranker()  # may be None when RERANK_PROVIDER=none
    # cache query embeds (fewer metered calls), then retry transient failures
    embedder = CachingEmbedder(ResilientEmbedder(make_embedder()))

    # In memory mode, load pre-seeded vectors from pickle if available
    raw_store = make_store(collection=collection_name(settings.domain, settings.embed_model))
    if settings.vector_provider in ("memory", "fake", ""):
        seed_path = os.path.join("domains", settings.domain, "memory_seed.pkl")
        if os.path.exists(seed_path):
            try:
                with open(seed_path, "rb") as f:
                    seed = pickle.load(f)
                if isinstance(seed, dict) and "store" in seed:
                    raw_store = seed["store"]
                    _log.info("loaded memory seed from %s (%d points)",
                              seed_path, len(getattr(raw_store, "_points", {})))
            except Exception as exc:
                _log.warning("failed to load memory seed %s: %s", seed_path, exc)
    # answers-lane FAQ cache: serves a repeat anonymous, grounded answer without retrieval or
    # generation. On by default (safe and cheap; anonymous + grounded only, TTL, invalidated on
    # re-index); set ANSWER_CACHE=off to disable. Reuses the app embedder for consistent similarity.
    cache_backend = os.getenv("ANSWER_CACHE_BACKEND", "memory").strip().lower()
    if os.getenv("ANSWER_CACHE", "on").strip().lower() == "off":
        answer_cache = None
    elif cache_backend == "redis":
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError("ANSWER_CACHE_BACKEND=redis requires the production extra") from exc
        client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        answer_cache = RedisAnswerCache(
            client, knowledge_version=os.getenv("KNOWLEDGE_VERSION", settings.domain))
    else:
        answer_cache = SemanticAnswerCache(embedder)
    session_backend = os.getenv("SESSION_BACKEND", "memory").strip().lower()
    conversation_store = make_conversation_store(
        session_backend, sqlite_path=os.getenv("SESSION_DB_PATH", ".sessions.db"),
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        postgres_dsn=os.getenv("POSTGRES_DSN", ""))
    order_path = os.getenv(
        "ORDER_STORE_PATH", os.path.join("domains", settings.domain,
                                         "seed", "unstructured", "orders.jsonl"))
    catalog_path = os.getenv(
        "CATALOG_STORE_PATH", os.path.join("domains", settings.domain,
                                           "seed", "structured", "products.csv"))
    return {
        "embedder": embedder,
        "answer_cache": answer_cache,
        "store": ResilientStore(raw_store),
        "llm": ResilientLLM(make_llm(), fallback=make_small_llm()),
        # cache rerank results, retry transient failures, fall back to pre-rerank order if needed
        "reranker": ResilientReranker(CachingReranker(reranker)) if reranker is not None else None,
        "metric_resolver": MetricResolver(settings.domain, lakehouse_db),
        "graph_retriever": _build_graph_retriever(settings.domain),
        "transcriber": make_transcriber(),
        "review_queue": ReviewQueue(
            settings.review_queue_db,
            verified_path=os.getenv("VERIFIED_PATH", "traces/verified_answers.jsonl")),
        "domain": settings.domain,
        "conversation_store": conversation_store,
        "order_store": make_order_store(os.getenv("ORDER_BACKEND", "json"),
                                        json_path=order_path,
                                        postgres_dsn=os.getenv("POSTGRES_DSN", "")),
        "catalog_store": StructuredCatalogStore.from_csv(
            catalog_path, knowledge_version=os.getenv("KNOWLEDGE_VERSION", "catalog-v1")),
    }
