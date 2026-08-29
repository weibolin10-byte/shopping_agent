"""Smoke tests for the M0 scaffold. They guard the project's basic contract so that
`make test` has something real to check from day one."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_env_example_declares_core_keys():
    env = (ROOT / ".env.example").read_text()
    for key in ["DOMAIN", "LLM_PROVIDER", "OPENAI_COMPAT_API_KEY", "EMBED_PROVIDER",
                "QWEN_API_KEY"]:
        assert key in env, "missing {} in .env.example".format(key)


def test_project_docs_exist():
    for name in ("ARCHITECTURE.md", "EVALUATION.md", "DEPLOY.md", "INTERVIEW_GUIDE.md"):
        assert (ROOT / "docs" / name).is_file()


def test_only_chinese_domain_pack_is_present():
    packs = sorted(path.name for path in (ROOT / "domains").iterdir() if path.is_dir())
    assert packs == ["china_ecommerce"]
