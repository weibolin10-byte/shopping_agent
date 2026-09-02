"""README 的中文核心数字必须来自唯一正式评测报告。"""
from pathlib import Path

from evaluation.readme_metrics import sync_readme

ROOT = Path(__file__).resolve().parents[1]


def test_readme_headline_numbers_match_site_stats():
    assert sync_readme(
        ROOT / "README.md",
        ROOT / "domains/china_ecommerce/eval/reports/current.json",
        check=True,
    )
