"""README 的中文核心数字必须来自已提交的中文评测报告。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_readme_headline_numbers_match_site_stats():
    report_dir = ROOT / "domains/china_ecommerce/eval/reports"
    full = json.loads((report_dir / "full_eval.json").read_text())
    cost = json.loads((report_dir / "cost_model_zh.json").read_text())
    readme = (ROOT / "README.md").read_text()
    expected = {
        "routing cases": "33 / 33",
        "faithfulness": "{:.1%}".format(full["ragas"]["scores"]["overall"]["faithfulness"]),
        "hit@8": "{:.1%}".format(full["ablation"]["hybrid"]["hit@8"]),
        "turn cost": "${:.6f}".format(cost["per_turn"]["ai_assistant"]),
        "cost ratio": "{:.0f}".format(cost["cost_ratio"]["human_vs_ai"]),
    }
    missing = {label: value for label, value in expected.items() if value not in readme}
    assert not missing, "README numbers out of sync with site_stats.json: {}".format(missing)
