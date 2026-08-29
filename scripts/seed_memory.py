#!/usr/bin/env python3
"""Seed the in-memory hybrid store with domain data and persist to a pickle file.

In memory mode (VECTOR_PROVIDER=memory), the Qdrant-based `make ingest` doesn't apply.
This script reads the domain manifest, chunks all unstructured sources, embeds them
with the configured embedder, and writes a pickle that deps.py loads on startup.

Also builds the in-memory graph from ontology + structured CSVs.

Run: uv run python scripts/seed_memory.py
"""
from __future__ import annotations

import json
import os
import pickle
import sys

import yaml

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.config import get_settings
from adapters.factory import make_embedder
from adapters.fakes import InMemoryHybridStore
from api.resilience import ResilientEmbedder
from ingest.chunk import chunk_records
from retrieval.sparse import SparseEncoder


def load_jsonl(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main() -> int:
    settings = get_settings()
    pack = os.path.join("domains", settings.domain)
    manifest_path = os.path.join(pack, "domain.yaml")
    if not os.path.isfile(manifest_path):
        print(f"no domain pack at {pack}")
        return 1

    with open(manifest_path, encoding="utf-8") as f:
        manifest = yaml.safe_load(f)

    # --- 1. Chunk + embed unstructured sources ---
    sources = (manifest.get("sources", {}) or {}).get("unstructured", []) or []
    all_chunks = []
    for src in sources:
        rows = load_jsonl(os.path.join(pack, src["file"]))
        chunks = chunk_records(
            rows,
            id_field=src["id_field"],
            text_field=src["text_field"],
            lang_field=src.get("lang_field"),
            meta_fields=src.get("meta_fields", []),
            doc_type=src.get("doc_type", "doc"),
            context_fields=src.get("context_fields", []),
        )
        print(f"  {src['file']}: {len(rows)} rows -> {len(chunks)} chunks")
        all_chunks.extend(chunks)

    if not all_chunks:
        print("no chunks to embed")
        return 1

    print(f"\nTotal chunks: {len(all_chunks)}")
    print("Embedding with", settings.embed_provider, "...")

    embedder = ResilientEmbedder(make_embedder())
    embed_texts = [(c.metadata.get("context", "") + " " + c.text).strip() for c in all_chunks]
    # Embed in batches to avoid timeouts
    batch_size = 10
    dense = []
    for i in range(0, len(embed_texts), batch_size):
        batch = embed_texts[i:i + batch_size]
        vecs = embedder.embed(batch, input_type="document")
        dense.extend(vecs)
        print(f"  embedded {min(i + batch_size, len(embed_texts))}/{len(embed_texts)}")

    sparse_encoder = SparseEncoder()
    points = []
    for c, d in zip(all_chunks, dense):
        sp = sparse_encoder.encode((c.metadata.get("context", "") + " " + c.text).strip())
        points.append({
            "id": c.id,
            "text": c.text,
            "payload": c.metadata,
            "dense": d,
            "sparse": {"indices": sp.indices, "values": sp.values},
        })

    # Build in-memory store
    store = InMemoryHybridStore()
    store.ensure_collection(len(dense[0]) if dense else 1024)
    store.upsert(points)
    print(f"\nSeeded {len(points)} vectors into InMemoryHybridStore")

    # --- 2. Persist (graph is optional; degrades gracefully without lakehouse) ---
    out_path = os.path.join("domains", settings.domain, "memory_seed.pkl")
    with open(out_path, "wb") as f:
        pickle.dump({"store": store}, f)
    print(f"\nSaved memory seed to {out_path}")
    print(f"File size: {os.path.getsize(out_path) / 1024 / 1024:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
