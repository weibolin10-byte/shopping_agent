"""OpenAI-compatible chat completions adapter.

Works with any provider that exposes an OpenAI-compatible /chat/completions endpoint:
  - DeepSeek:  https://api.deepseek.com/v1
  - Qwen/DashScope compatible mode: https://dashscope.aliyuncs.com/compatible-mode/v1
  - Groq:      https://api.groq.com/openai/v1

Configure via environment variables:
  LLM_PROVIDER=openai_compat
  OPENAI_COMPAT_API_KEY=sk-...
  OPENAI_COMPAT_BASE_URL=https://api.deepseek.com/v1
  OPENAI_COMPAT_MODEL=deepseek-chat          # primary (large) model
  OPENAI_COMPAT_MODEL_SMALL=qwen-turbo       # optional small/fast model
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Iterator

from ._http import _USER_AGENT
from .base import LLMResult
from .observability import observe, update_generation

_CALL_TIMEOUT = 30  # Chinese providers can be a bit slower than Groq


class OpenAICompatClient:
    """Generic OpenAI-compatible chat client."""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.model = model or os.getenv("OPENAI_COMPAT_MODEL", "deepseek-chat")
        self.api_key = api_key or os.getenv("OPENAI_COMPAT_API_KEY", "")
        self.base_url = (
            base_url
            or os.getenv("OPENAI_COMPAT_BASE_URL", "https://api.deepseek.com/v1")
        ).rstrip("/")

    def _messages(self, prompt: str, system: str | None) -> list[dict]:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _body(self, prompt: str, system: str | None, max_tokens: int,
              *, stream: bool = False) -> dict:
        body = {
            "model": self.model,
            "messages": self._messages(prompt, system),
            "max_tokens": max_tokens,
            "temperature": 0,
        }
        # DeepSeek V4 enables thinking by default. The shopping response contract needs a short
        # visible answer within a bounded output budget, not hidden reasoning that can consume the
        # whole budget and leave content empty. Other OpenAI-compatible providers may reject this
        # vendor extension, so send it only to DeepSeek.
        if "api.deepseek.com" in self.base_url:
            thinking = os.getenv("OPENAI_COMPAT_THINKING", "disabled").strip().lower()
            body["thinking"] = {"type": "enabled" if thinking == "enabled" else "disabled"}
        if stream:
            body["stream"] = True
            body["stream_options"] = {"include_usage": True}
        return body

    @observe(
        as_type="generation",
        name="openai_compat.generate",
        capture_input=False,
        capture_output=False,
    )
    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 512,
    ) -> LLMResult:
        if not self.api_key:
            raise RuntimeError(
                "OPENAI_COMPAT_API_KEY is not set; put it in .env"
            )
        body = self._body(prompt, system, max_tokens)
        req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(body).encode(),
            method="POST",
        )
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", _USER_AGENT)
        req.add_header("Authorization", "Bearer " + self.api_key)
        try:
            with urllib.request.urlopen(req, timeout=_CALL_TIMEOUT) as resp:  # noqa: S310
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:2000]
            raise RuntimeError(
                "openai_compat generate -> HTTP {}: {}".format(exc.code, detail)
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                "openai_compat generate failed: {}".format(exc.reason)
            ) from exc

        text = data["choices"][0]["message"].get("content") or ""
        if not text.strip():
            raise RuntimeError("openai_compat generate returned empty final content")
        usage = data.get("usage", {})
        update_generation(
            model=self.model,
            input=prompt,
            output=text,
            usage_details={
                "input": usage.get("prompt_tokens", 0),
                "output": usage.get("completion_tokens", 0),
            },
        )
        return LLMResult(
            text=text,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            model=self.model,
        )

    def stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 512,
        usage_out: dict | None = None,
    ) -> Iterator[str]:
        if not self.api_key:
            raise RuntimeError(
                "OPENAI_COMPAT_API_KEY is not set; put it in .env"
            )
        body = self._body(prompt, system, max_tokens, stream=True)
        req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(body).encode(),
            method="POST",
        )
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", _USER_AGENT)
        req.add_header("Authorization", "Bearer " + self.api_key)
        try:
            resp = urllib.request.urlopen(req, timeout=_CALL_TIMEOUT)  # noqa: S310
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:2000]
            raise RuntimeError(
                "openai_compat stream -> HTTP {}: {}".format(exc.code, detail)
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                "openai_compat stream failed: {}".format(exc.reason)
            ) from exc
        emitted = False
        with resp:
            for raw in resp:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                data_str = line[len("data:"):].strip()
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                if usage_out is not None and isinstance(chunk.get("usage"), dict):
                    usage_out.update(chunk["usage"])
                    usage_out.setdefault("model", chunk.get("model") or self.model)
                choices = chunk.get("choices") or []
                if choices:
                    delta = choices[0].get("delta", {})
                    piece = delta.get("content")
                    if piece:
                        emitted = True
                        yield piece
        if not emitted:
            raise RuntimeError("openai_compat stream returned empty final content")
