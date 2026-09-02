"""Render the README's canonical metric block from the canonical evaluation report."""
from __future__ import annotations

import json
from pathlib import Path

START = "<!-- EVAL_METRICS:START -->"
END = "<!-- EVAL_METRICS:END -->"


def render_metrics(report: dict) -> str:
    results = report["results"]
    routing = results["routing"]["with_tiebreak"]
    ragas = results["ragas"]["scores"]
    overall = ragas["overall"]
    valid = ragas.get("valid_counts", {})
    ablation = results["ablation"]
    generation = results["ragas"]
    ragas_n = generation.get("evaluated_size", generation.get("subset_size", ragas["count"]))
    suite = generation.get("suite", "legacy")
    contract = generation.get("deterministic_contract", {})

    def pct(value: float) -> str:
        return f"{value:.1%}"

    def measured(metric: str) -> str:
        count = valid.get(metric)
        return f"；有效评分 {count}/{ragas_n}" if count is not None else ""

    rows = [
        "| 评测维度 | 当前成绩 | 口径 |",
        "| --- | --- | --- |",
        (f"| 意图路由准确率 | **{pct(routing['accuracy'])}** | "
         f"{routing['graded']} 条中文路由样本；含 {routing['tiebreak_calls']} 次小模型裁决 |"),
        (f"| RAGAS 忠实度 | **{pct(overall['faithfulness'])}** | "
         f"{ragas_n} 条真实生成样本（{suite} 集）{measured('faithfulness')} |"),
        (f"| RAGAS 答案相关性 | **{pct(overall['answer_relevance'])}** | "
         f"独立 Judge + Embedding{measured('answer_relevance')} |"),
        (f"| RAGAS 上下文精度 | **{pct(overall['context_precision'])}** | "
         f"检索块有效性{measured('context_precision')} |"),
        (f"| RAGAS 上下文召回 | **{pct(overall['context_recall'])}** | "
         f"参考答案事实覆盖{measured('context_recall')} |"),
        (f"| 确定性事实召回 | **{pct(contract['required_fact_recall'])}** | "
         f"价格、商品名等机器可核验字段；n={contract['count']} |")
        if contract.get("required_fact_recall") is not None else None,
        (f"| Dense 检索 | **Hit@8 {pct(ablation['dense']['hit@8'])} / "
         f"MRR {ablation['dense']['mrr']:.3f}** | n={ablation['dense']['n']} |"),
        (f"| Hybrid 检索 | **Hit@8 {pct(ablation['hybrid']['hit@8'])} / "
         f"MRR {ablation['hybrid']['mrr']:.3f}** | n={ablation['hybrid']['n']}；"
         "不预设优于 Dense |"),
    ]
    return START + "\n" + "\n".join(row for row in rows if row is not None) + "\n" + END


def sync_readme(readme_path: str | Path, report_path: str | Path, *, check: bool = False) -> bool:
    readme_path = Path(readme_path)
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    text = readme_path.read_text(encoding="utf-8")
    start = text.find(START)
    end = text.find(END)
    if start < 0 or end < start:
        raise RuntimeError("README canonical metric markers are missing")
    end += len(END)
    updated = text[:start] + render_metrics(report) + text[end:]
    if check:
        return updated == text
    if updated != text:
        readme_path.write_text(updated, encoding="utf-8")
    return True
