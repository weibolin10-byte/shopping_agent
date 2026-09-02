"""Neutralize prompt-injection attempts in retrieved (user-generated) text before it reaches
the model. Retrieved content is data, never instructions.

Layers: NFKC-normalize and strip zero-width characters (defeats homoglyph and invisible-char
bypasses), collapse whitespace (so a chunk cannot forge prompt structure), then redact
instruction-like spans up to the sentence end (so legitimate text after an injection
survives). English, French and Chinese are covered by the same deterministic boundary.

This is defense in depth alongside the system prompt and the untrusted-data reminder, not a
replacement. Known limits (covered by the system prompt, revisited at M6/M8): a payload split
into a separate sentence from its trigger survives, and novel phrasings or other languages are
not matched. Over-matching legitimate review sentences (for example "disregard the previous
review") is accepted as the safe trade-off.
"""
from __future__ import annotations

import re
import unicodedata

# zero-width joiners/spaces and BOM, used to break up trigger words invisibly
_ZERO_WIDTH = dict.fromkeys([0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF], None)
# Leave the sentence terminator in place.  If the replacement consumes it, a later overlapping
# pattern can run through ``[removed]`` into the following legitimate sentence and over-redact it.
_TAIL = r"[^.!?。！？]*"  # match to, but not including, the offending sentence boundary

_INJECTION_PATTERNS = [
    # English
    re.compile(r"(ignore|disregard)\s+(all\s+)?(the\s+)?(previous|prior|above)\b"
               r"(\s+instructions?)?" + _TAIL, re.IGNORECASE),
    re.compile(r"forget\s+(everything|all|the\s+above|previous)" + _TAIL, re.IGNORECASE),
    re.compile(r"(you\s+are\s+now|from\s+now\s+on)\b" + _TAIL, re.IGNORECASE),
    re.compile(r"pretend\s+(you\s+are|to\s+be)" + _TAIL, re.IGNORECASE),
    re.compile(r"act\s+as\s+(an?\s+)?(assistant|admin|manager|system)" + _TAIL, re.IGNORECASE),
    re.compile(r"(system|developer)\s*(prompt|message)\s*:" + _TAIL, re.IGNORECASE),
    re.compile(r"new\s+instructions?\s*:" + _TAIL, re.IGNORECASE),
    # French
    re.compile(r"ignore[rz]?\s+(toutes?\s+)?(les\s+)?instructions\s+"
               r"(pr[ée]c[ée]dentes|ci-dessus)" + _TAIL, re.IGNORECASE),
    re.compile(r"oublie[rz]?\s+(tout|toutes|le\s+reste)" + _TAIL, re.IGNORECASE),
    re.compile(r"(tu\s+es|vous\s+[êe]tes)\s+maintenant" + _TAIL, re.IGNORECASE),
    re.compile(r"(nouvelles?\s+instructions?\s*:|d[ée]sormais\b)" + _TAIL, re.IGNORECASE),
    # Chinese
    re.compile(r"(忽略|无视|不要管|跳过)[^.!?。！？]{0,8}"
               r"(之前|上面|以上|先前|原来)[^.!?。！？]{0,6}"
               r"(指令|要求|规则|提示词|系统消息)?" + _TAIL),
    re.compile(r"(忘掉|忘记|清除)[^.!?。！？]{0,8}"
               r"(之前|上面|以上|所有)[^.!?。！？]{0,6}"
               r"(指令|要求|规则|内容|提示词)?" + _TAIL),
    re.compile(r"(从现在开始|现在起|你现在是|假装你是|扮演)"
               r"[^.!?。！？]{0,20}" + _TAIL),
    re.compile(r"(系统|开发者|管理员)(提示词|消息|指令)\s*[:：]" + _TAIL),
    re.compile(r"(新的?指令|新规则|最高优先级)\s*[:：]" + _TAIL),
]
_REDACTED = "[removed]"


def sanitize_context(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(_ZERO_WIDTH)
    cleaned = " ".join(text.split())  # collapse whitespace, kill forged newlines
    for pattern in _INJECTION_PATTERNS:
        cleaned = pattern.sub(_REDACTED, cleaned)
    return " ".join(cleaned.split())  # tidy any doubled spaces from redaction
