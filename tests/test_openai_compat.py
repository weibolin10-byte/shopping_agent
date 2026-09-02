"""Provider-specific OpenAI-compatible request behavior."""
from __future__ import annotations

import json

import adapters.openai_compat as compat_mod
from adapters.openai_compat import OpenAICompatClient


class _Response:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


def test_deepseek_v4_disables_thinking_by_default(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout=30):
        seen.update(json.loads(request.data.decode()))
        return _Response({"choices": [{"message": {"content": "OK"}}], "usage": {}})

    monkeypatch.delenv("OPENAI_COMPAT_THINKING", raising=False)
    monkeypatch.setattr(compat_mod.urllib.request, "urlopen", fake_urlopen)
    client = OpenAICompatClient(model="deepseek-v4-flash", api_key="test-key",
                                base_url="https://api.deepseek.com/v1")

    assert client.generate("test").text == "OK"
    assert seen["thinking"] == {"type": "disabled"}


def test_non_deepseek_provider_does_not_receive_vendor_thinking_parameter(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout=30):
        seen.update(json.loads(request.data.decode()))
        return _Response({"choices": [{"message": {"content": "OK"}}], "usage": {}})

    monkeypatch.setattr(compat_mod.urllib.request, "urlopen", fake_urlopen)
    client = OpenAICompatClient(model="qwen-turbo", api_key="test-key",
                                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")

    client.generate("test")
    assert "thinking" not in seen
