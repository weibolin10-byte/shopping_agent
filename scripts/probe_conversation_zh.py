#!/usr/bin/env python3
"""Chinese-compatible multi-turn conversation quality check.

Re-runs the probe produced by scripts/probe_conversation.py but fixes two
detectors that assume whitespace tokenization:

  * repeat_ask uses character bigram Jaccard instead of English word Jaccard,
    so a Chinese reply that ends with a clarifying question is not falsely
    flagged because the whole sentence was treated as one token.
  * The "last question" extractor recognises both ASCII ? and full-width ？.

Gender-leak detection is left untouched (it works on product names from the
CSV, which are language-independent).

Usage:
    PYTHONPATH=. uv run python scripts/probe_conversation_zh.py \
        --out domains/china_ecommerce/eval/reports/conversations_zh_fixed.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

# Reuse the production probe's building blocks so we do not duplicate pipeline
# wiring.  We only override the repeat-ask detector after the fact.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.probe_conversation import (  # noqa: E402
    _build,
    _product_gender_map,
    run_scenario,
)


def _zh_last_question(text: str) -> str:
    """Return the last genuine clarifying question, normalised to CJK bigrams + ASCII words.

    A "question" must end with ？/? or contain a question particle (吗/呢/嘛).
    Pure statements after the last 。 are ignored.  Courtesy closings such as
    "需要我帮你看看颜色或尺码吗" are also excluded because they are not
    clarifying questions — they are the assistant's standard sign-off.
    """
    if not text:
        return ""
    # Split on Chinese and ASCII sentence-ending punctuation.
    sents = re.split(r"[。！？!?\n]+", text)
    candidates = [s.strip() for s in sents if s.strip()]
    # Walk backwards to find the last sentence that looks like a question.
    for s in reversed(candidates):
        if not re.search(r"[？?]|吗|呢|嘛|如何|怎么|怎样|什么|哪|几|多少|是否", s):
            continue
        # Exclude courtesy closings / sign-off offers.
        if re.search(
            r"(需要我|要不要我|我帮你|帮您|看看.*颜色|看看.*尺码|还有什么|还有其他|随时)",
            s,
        ):
            continue
        tokens: list[str] = []
        tokens.extend(re.findall(r"[a-zA-Z0-9]+", s.lower()))
        cjk = "".join(re.findall(r"[\u4e00-\u9fff]", s))
        tokens.extend(cjk[i : i + 2] for i in range(len(cjk) - 1))
        return " ".join(tokens)
    return ""


def _jaccard(a: str, b: str) -> float:
    sa, sb = set(a.split()), set(b.split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _reflag_repeat(turns: list[dict]) -> int:
    """Recompute repeat_ask on every turn with the CJK-aware tokenizer.

    Returns the number of turns flagged as repeated questions.
    """
    prior: list[str] = []
    repeats = 0
    for t in turns:
        q = _zh_last_question(t.get("answer", ""))
        is_repeat = bool(q) and any(_jaccard(q, pq) >= 0.6 for pq in prior)
        if q:
            prior.append(q)
        t["repeat_ask"] = is_repeat
        if is_repeat:
            repeats += 1
    return repeats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--domain", default=os.environ.get("DOMAIN", "china_ecommerce"))
    args = ap.parse_args()

    if args.scenarios:
        with open(args.scenarios, encoding="utf-8") as f:
            scenarios = json.load(f)
    else:
        path = os.path.join("domains", args.domain, "eval", "conversations.json")
        with open(path, encoding="utf-8") as f:
            scenarios = json.load(f)

    gmap = _product_gender_map(args.domain)
    comp, small = _build()

    results = []
    total_leaks = 0
    total_repeats = 0
    total_errors = 0

    for sc in scenarios:
        out = run_scenario(comp, small, sc, gmap)
        # Re-flag repeat_ask with CJK tokenizer.
        n_rep = _reflag_repeat(out["turns"])
        out["repeat_asks"] = n_rep
        total_repeats += n_rep
        total_leaks += out.get("gender_leaks", 0)
        total_errors += out.get("errors", 0)
        results.append(out)

        lanes = [t.get("lane") for t in out["turns"]]
        print(
            "  {:<38} leaks={} repeats={} errors={}  lanes={}".format(
                out["name"],
                out.get("gender_leaks", 0),
                n_rep,
                out.get("errors", 0),
                lanes,
            )
        )

    report = {
        "summary": {
            "scenarios": len(results),
            "gender_leaks": total_leaks,
            "repeat_asks": total_repeats,
            "errors": total_errors,
        },
        "results": results,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("\nwrote {}".format(args.out))
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
