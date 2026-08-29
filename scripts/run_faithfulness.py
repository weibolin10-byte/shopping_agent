#!/usr/bin/env python3
"""Drain the online faithfulness queue: score sampled live answers with an independently configured
judge model, append the results to traces/faithfulness.jsonl, and log the aggregate to MLflow.

This is the offline half of the faithfulness ladder. The request path only appends candidates to the
queue after the answer is sent, so nothing here ever blocks a served turn. Run: make faithfulness.
Without judge credentials the task is a no-op.
"""
from __future__ import annotations

import os
import sys

from adapters.config import get_settings
from mlops.faithfulness import drain_queue


def _judge():
    api_key = os.getenv("JUDGE_API_KEY", "")
    if not api_key:
        return None
    from adapters.openai_compat import OpenAICompatClient
    return OpenAICompatClient(
        model=os.getenv("JUDGE_MODEL", "qwen-plus"),
        api_key=api_key,
        base_url=os.getenv(
            "JUDGE_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
    )


def _log_mlflow(summary: dict) -> None:
    settings = get_settings()
    tracking_uri = settings.mlflow_url or "./mlruns"
    if not tracking_uri.startswith(("http://", "https://")):
        os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
    try:
        import mlflow
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment("shopping-agent-faithfulness")
        with mlflow.start_run():
            mlflow.log_metric("scored", summary["scored"])
            mlflow.log_metric("flagged", summary["flagged"])
            if summary["mean"] is not None:
                mlflow.log_metric("faithfulness_mean", summary["mean"])
    except Exception as exc:  # never let an MLflow hiccup hide the result
        print("mlflow logging skipped ({}: {})".format(type(exc).__name__, str(exc)[:100]),
              file=sys.stderr)


def main() -> int:
    judge = _judge()
    if judge is None:
        print("no judge credentials; faithfulness scoring skipped (queue left intact)",
              file=sys.stderr)
        return 0
    summary = drain_queue(judge)
    print("faithfulness: scored {scored}, flagged {flagged} (< 0.8), mean {mean}".format(**summary))
    _log_mlflow(summary)
    # a low mean faithfulness is a hallucination signal a scheduled job can alert on
    return 1 if (summary["mean"] is not None and summary["mean"] < 0.8) else 0


if __name__ == "__main__":
    sys.exit(main())
