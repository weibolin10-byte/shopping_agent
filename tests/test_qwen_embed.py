"""Qwen embedding request shape and provider batch limit."""
from __future__ import annotations

import json

import adapters.qwen_embed as qwen_mod
from adapters.qwen_embed import QwenEmbedder


class _Response:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


def test_embed_batches_text_embedding_v3_at_ten(monkeypatch):
    batch_sizes = []

    def fake_urlopen(request, timeout=60):
        body = json.loads(request.data.decode())
        batch_sizes.append(len(body["input"]))
        rows = [
            {"embedding": [float(index)], "index": index}
            for index, _text in enumerate(body["input"])
        ]
        return _Response({"data": list(reversed(rows))})

    monkeypatch.setattr(qwen_mod.urllib.request, "urlopen", fake_urlopen)
    embedder = QwenEmbedder(model="text-embedding-v3", api_key="test-key")
    output = embedder.embed([str(index) for index in range(25)], input_type="document")

    assert batch_sizes == [10, 10, 5]
    assert len(output) == 25
    assert output[0] == [0.0]
    assert output[10] == [0.0]
