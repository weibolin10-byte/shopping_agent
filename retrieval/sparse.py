"""Stateless lexical sparse encoder for hybrid search.

Emits per-token term-frequency weights with saturation, so repeating a word helps less each
time. Inverse document frequency is applied server-side by Qdrant (sparse vector modifier
"idf"), so there is no corpus state to fit and query-time encoding is fully reproducible.
Not a neural model, so no download and no GPU, which keeps the no-local-models rule.
Tokens are hashed into a fixed index space.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass

_TOKEN = re.compile(r"[a-z0-9]+")
# Match runs of CJK unified ideographs
_CJK = re.compile(r"[\u4e00-\u9fff]+")


def tokenize(text: str) -> list[str]:
    # Strip diacritics so accented and unaccented spellings share tokens (helps French).
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    tokens = _TOKEN.findall(text.lower())
    # Chinese character bigrams: lightweight CJK tokenization without external dependencies.
    # Each run of CJK characters produces overlapping 2-char tokens, giving reasonable
    # recall for Chinese/Japanese text without a dictionary-based segmenter.
    for run in _CJK.findall(text):
        if len(run) == 1:
            tokens.append(run)
        else:
            for i in range(len(run) - 1):
                tokens.append(run[i:i + 2])
    return tokens


@dataclass
class SparseVector:
    indices: list[int]
    values: list[float]


class SparseEncoder:
    def __init__(self, dim: int = 2 ** 16, k1: float = 1.5) -> None:
        self.dim = dim
        self.k1 = k1

    def _bucket(self, token: str) -> int:
        return int(hashlib.md5(token.encode()).hexdigest(), 16) % self.dim

    def encode(self, text: str) -> SparseVector:
        freq: dict[str, int] = {}
        for token in tokenize(text):
            freq[token] = freq.get(token, 0) + 1
        weights: dict[int, float] = {}
        for token, tf in freq.items():
            # saturating term frequency; Qdrant multiplies in the idf at query time
            weight = tf * (self.k1 + 1) / (tf + self.k1)
            bucket = self._bucket(token)
            weights[bucket] = weights.get(bucket, 0.0) + weight
        indices = sorted(weights)
        return SparseVector(indices=indices, values=[weights[i] for i in indices])
