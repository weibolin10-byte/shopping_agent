"""Language-aware text primitives shared by ingestion, retrieval and evaluation.

The project is Chinese-first, so whitespace cannot be used as a proxy for words, sentences or
length.  These helpers intentionally have no third-party tokenizer dependency: they provide a
stable deterministic contract for online routing and offline evaluation.
"""
from __future__ import annotations

import re
import unicodedata

_SENTENCE_BOUNDARY = re.compile(r"(?<=[。！？!?；;\.])\s*|\n+")
_LATIN_TOKEN = re.compile(r"[A-Za-z0-9]+(?:[-_'.][A-Za-z0-9]+)*")
_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_STANDALONE_INTENT = re.compile(
    r"(政策|退换货|退货|换货|包邮|运费|支付方式|发票|会员规则|"
    r"查询?.{0,4}(我的)?(订单|快递|物流)|[A-Z]{2}\d{4,})",
    re.I,
)
_FOLLOWUP_CUE = re.compile(
    r"^(that|this|it|they|them|those|these|the (first|second|other|cheaper)|what about|"
    r"how about|and |but |when will it|where is it|which one)\b"
    r"|\b(which|what) (is|one is) (cheaper|better|warmer|larger|smaller)\b"
    r"|^(那|那么|这个|这款|这双|它|他|她|上一个|刚才|前面)"
    r"|^(物流单号|运单号|快递公司|预计日期|至少告诉我|只告诉我)"
    r"|(哪个|哪款|哪双).{0,8}(更|便宜|好|合适)"
    r"|^(多少钱|有货吗|有什么码|什么时候到|多久到|怎么样)",
    re.I,
)
_SOCIAL_TURN = re.compile(
    r"(你好|您好|嗨|好问题|没问题|当然可以|我来帮你|我帮你|需要我|要不要我|"
    r"还想了解|告诉我|你主要|你是想|方便的话)"
    r"|\b(hello|hi|great question|let me help|would you like|do you want me to|tell me)\b",
    re.I,
)


def normalize_text(text: str) -> str:
    """NFKC-normalize while preserving meaningful CJK sentence boundaries."""
    return re.sub(r"[ \t\r\f\v]+", " ", unicodedata.normalize("NFKC", text or "")).strip()


def sentence_split(text: str) -> list[str]:
    """Split Chinese, Latin and mixed text without requiring whitespace after punctuation."""
    clean = normalize_text(text)
    return [part.strip() for part in _SENTENCE_BOUNDARY.split(clean) if part.strip()]


def estimate_tokens(text: str) -> int:
    """Conservative model-independent estimate for CJK and Latin mixed text."""
    clean = normalize_text(text)
    if not clean:
        return 0
    cjk = len(_CJK.findall(clean))
    latin = len(_LATIN_TOKEN.findall(_CJK.sub(" ", clean)))
    punctuation = sum(1 for ch in clean if unicodedata.category(ch).startswith("P"))
    return max(1, cjk + round(latin * 1.3) + punctuation // 3)


def lexical_units(text: str) -> list[str]:
    """Return stable lexical units; CJK bigrams retain meaning without a segmenter."""
    clean = normalize_text(text).lower()
    units = _LATIN_TOKEN.findall(clean)
    runs = re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]+", clean)
    for run in runs:
        units.extend(list(run) if len(run) == 1 else [run[i:i + 2] for i in range(len(run) - 1)])
    return units


def is_short_query(text: str, *, max_units: int = 12) -> bool:
    """Whether a query is short enough to require conversation-based expansion."""
    return len(lexical_units(text)) <= max_units


def is_contextual_followup(text: str) -> bool:
    """Whether a turn is elliptical enough that retrieval should inherit prior turns.

    A complete but short FAQ such as ``退换货政策是什么`` must stand alone; treating every
    short Chinese sentence as a follow-up pollutes its query with the previous product.
    """
    clean = normalize_text(text)
    if not clean:
        return False
    if _STANDALONE_INTENT.search(clean):
        return False
    if re.fullmatch(r"[\w.+-]+@[\w-]+\.[\w.-]+", clean):
        return True
    if len(lexical_units(clean)) <= 2:
        return True
    return bool(_FOLLOWUP_CUE.search(clean))


def expand_retrieval_query(text: str, *, query_type: str = "factual") -> str:
    """Add narrow, deterministic Chinese ecommerce synonyms for retrieval only."""
    query = normalize_text(text)
    additions: list[str] = []
    if "偏码" in query:
        additions.extend(("尺码", "偏大", "偏小", "偏窄", "脚宽", "大半码", "小半码"))
    if query_type == "relational" and any(cue in query for cue in ("供应", "生产", "制造")):
        additions.extend(("供应商", "生产", "制造", "代工"))
    missing = [unit for unit in additions if unit not in query]
    return (query + (" " + " ".join(missing) if missing else "")).strip()


def is_evidence_claim(sentence: str) -> bool:
    """Whether a response sentence makes a claim that needs evidence and a citation."""
    clean = normalize_text(re.sub(r"\[[\d,\s]+\]", "", sentence or ""))
    clean = re.sub(r"^[\s\-*#>]+", "", clean).strip()
    if not lexical_units(clean):
        return False
    if clean.endswith(("?", "？")):
        return False
    if _SOCIAL_TURN.search(clean):
        # A sentence containing a concrete number/currency or an explicit citation-bearing fact is
        # not dismissed merely because it also says "我帮你".
        factual_marker = re.search(r"\d|元|价格|库存|状态|政策|供应商|尺码", clean)
        if not factual_marker:
            return False
    return True


def hard_split(text: str, max_tokens: int) -> list[str]:
    """Split a single oversized sentence, preferring punctuation and then character windows."""
    if estimate_tokens(text) <= max_tokens:
        return [text]
    pieces: list[str] = []
    current = ""
    for ch in text:
        candidate = current + ch
        if current and estimate_tokens(candidate) > max_tokens:
            pieces.append(current.strip())
            current = ch
        else:
            current = candidate
    if current.strip():
        pieces.append(current.strip())
    return pieces
