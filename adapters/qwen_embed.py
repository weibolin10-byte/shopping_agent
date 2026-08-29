"""Qwen (DashScope compatible-mode) embeddings behind the Embedder interface.

Uses the OpenAI-compatible /embeddings endpoint:
  POST https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings

Configure via environment variables:
  EMBED_PROVIDER=qwen
  QWEN_API_KEY=sk-...
  QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
  EMBED_MODEL=text-embedding-v3        # 1024 dims (default dimensions)
  # or:
  EMBED_MODEL=text-embedding-v4        # supports configurable dimensions
  QWEN_EMBED_DIM=1024                  # optional, for v4 models
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from ._http import _USER_AGENT

_DEFAULT_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
_DEFAULT_MODEL = "text-embedding-v3"
_DEFAULT_DIM = 1024
_EMBED_BATCH = 25  # Qwen has a lower batch limit than Cohere

# Known model -> dimension mapping (for v3 the dim is fixed at 1024)
_MODEL_DIMS = {
    "text-embedding-v1": 1536,
    "text-embedding-v2": 1536,
    "text-embedding-v3": 1024,
}


class QwenEmbedder:
    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.model = model or os.getenv("EMBED_MODEL", _DEFAULT_MODEL)
        self.api_key = api_key or os.getenv("QWEN_API_KEY", "")
        self.base_url = (
            base_url
            or os.getenv("QWEN_BASE_URL", _DEFAULT_BASE)
        ).rstrip("/")
        if self.model in _MODEL_DIMS:
            self._dim = _MODEL_DIMS[self.model]
        else:
            # For v4 or newer, allow override via env; otherwise default to 1024
            self._dim = int(os.getenv("QWEN_EMBED_DIM", _DEFAULT_DIM))

    @property
    def dim(self) -> int:
        return self._dim

    def embed(
        self, texts: list[str], input_type: str = "document"
    ) -> list[list[float]]:
        if not self.api_key:
            raise RuntimeError("QWEN_API_KEY is not set; put it in .env")
        texts = list(texts)
        out: list[list[float]] = []
        for start in range(0, len(texts), _EMBED_BATCH):
            batch = texts[start : start + _EMBED_BATCH]
            body: dict = {
                "model": self.model,
                "input": batch,
            }
            # v4+ supports encoding_format and dimensions parameter
            if "v4" in self.model:
                body["dimensions"] = self._dim
            req = urllib.request.Request(
                self.base_url + "/embeddings",
                data=json.dumps(body).encode(),
                method="POST",
            )
            req.add_header("Content-Type", "application/json")
            req.add_header("User-Agent", _USER_AGENT)
            req.add_header("Authorization", "Bearer " + self.api_key)
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
                    data = json.loads(resp.read().decode())
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode(errors="replace")[:2000]
                raise RuntimeError(
                    "qwen embed -> HTTP {}: {}".format(exc.code, detail)
                ) from exc
            except urllib.error.URLError as exc:
                raise RuntimeError(
                    "qwen embed failed: {}".format(exc.reason)
                ) from exc
            # OpenAI-compatible response: {"data": [{"embedding": [...], "index": 0}, ...]}
            items = sorted(data["data"], key=lambda x: x.get("index", 0))
            out.extend(item["embedding"] for item in items)
        return out
