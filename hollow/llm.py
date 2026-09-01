"""
Thin LLM client over the OpenAI-compatible chat API (no SDK dependency).

Works with OpenAI, OpenRouter, Anthropic (OpenAI-compatible endpoint), Gemini
and any local server exposing /chat/completions. The provider is picked from
whichever key is present; MODEL selects the model. With no key at all the
pipeline runs in offline mode (see agent.py), which is also what the
reproducible numbers in the PR were produced with.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

_PROVIDERS = [
    ("OPENAI_API_KEY", "https://api.openai.com/v1", "gpt-4o-mini"),
    ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1", "openai/gpt-4o-mini"),
    ("ANTHROPIC_API_KEY", "https://api.anthropic.com/v1", "claude-3-5-haiku-latest"),
    ("GOOGLE_API_KEY", "https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.0-flash"),
]


class LLMError(RuntimeError):
    pass


def config() -> dict | None:
    """Return {base_url, key, model} or None when no provider is configured."""
    for env, url, default_model in _PROVIDERS:
        key = os.getenv(env)
        if key:
            return {
                "base_url": os.getenv("LLM_BASE_URL", url),
                "key": key,
                "model": os.getenv("MODEL") or default_model,
            }
    return None


def enabled() -> bool:
    return config() is not None and os.getenv("HOLLOW_OFFLINE", "0") != "1"


def chat(messages: list[dict], tools: list[dict] | None = None,
         temperature: float = 0.0, timeout: int = 60) -> dict:
    """One chat completion. Returns the assistant message dict plus usage."""
    cfg = config()
    if cfg is None:
        raise LLMError("no LLM provider configured")
    body = {"model": cfg["model"], "messages": messages, "temperature": temperature}
    if tools:
        body["tools"] = tools
    req = urllib.request.Request(
        f"{cfg['base_url'].rstrip('/')}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {cfg['key']}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise LLMError(f"provider returned {exc.code}: {exc.read()[:300]!r}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise LLMError(f"provider unreachable: {exc}") from exc
    choice = data["choices"][0]["message"]
    usage = data.get("usage", {})
    return {
        "message": choice,
        "tokens_in": usage.get("prompt_tokens", 0),
        "tokens_out": usage.get("completion_tokens", 0),
    }
