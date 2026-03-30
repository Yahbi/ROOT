"""
Ollama LLM Service — ROOT's connection to local open-source models.

Uses the OpenAI-compatible API that Ollama exposes at localhost:11434.
Zero cost, zero rate limits, full privacy. Runs on your hardware.

Models (install via `ollama pull <model>`):
- llama3.1:8b       — General purpose, good quality (~4.7GB)
- mistral:7b        — Fast general purpose (~4.1GB)
- codellama:13b     — Code generation specialist (~7.4GB)
- deepseek-r1:8b    — Reasoning model (~4.9GB)
- gemma2:9b         — Google's efficient model (~5.4GB)
- qwen2.5:7b        — Strong multilingual (~4.4GB)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from backend.config import (
    OLLAMA_BASE_URL,
    OLLAMA_DEFAULT_MODEL,
    OLLAMA_FAST_MODEL,
    OLLAMA_THINKING_MODEL,
)

logger = logging.getLogger("root.llm.ollama")

MODEL_TIERS = {
    "fast": OLLAMA_FAST_MODEL,
    "default": OLLAMA_DEFAULT_MODEL,
    "thinking": OLLAMA_THINKING_MODEL,
}

# Cost per token — zero for local models
COST_PER_INPUT_TOKEN = 0.0
COST_PER_OUTPUT_TOKEN = 0.0

MAX_RETRIES = 2
RETRY_BASE_DELAY = 0.5


class OllamaLLMService:
    """Async wrapper around Ollama's OpenAI-compatible API."""

    def __init__(self, base_url: Optional[str] = None, cost_tracker=None, economic_router=None) -> None:
        url = base_url or OLLAMA_BASE_URL
        try:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                api_key="ollama",  # Ollama doesn't need a real key
                base_url=f"{url}/v1",
            )
        except ImportError:
            raise ImportError("openai package required for Ollama (OpenAI-compatible API)")
        self._base_url = url
        self._cost_tracker = cost_tracker
        self._economic_router = economic_router
        self.provider = "ollama"
        self._available_models: list[str] = []

    async def check_health(self) -> bool:
        """Check if Ollama is running and accessible."""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self._base_url}/api/tags", timeout=aiohttp.ClientTimeout(total=3)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self._available_models = [m["name"] for m in data.get("models", [])]
                        return True
            return False
        except Exception:
            # Fallback without aiohttp
            try:
                import urllib.request
                req = urllib.request.Request(f"{self._base_url}/api/tags")
                with urllib.request.urlopen(req, timeout=3) as resp:
                    import json
                    data = json.loads(resp.read())
                    self._available_models = [m["name"] for m in data.get("models", [])]
                    return True
            except Exception:
                return False

    @property
    def available_models(self) -> list[str]:
        return list(self._available_models)

    def _track_usage(self, response, model: str, model_tier: str, method: str = "complete") -> None:
        """Record token usage (zero cost for local models)."""
        if not self._cost_tracker or not hasattr(response, "usage") or not response.usage:
            return
        try:
            self._cost_tracker.record(
                provider="ollama",
                model=model,
                input_tokens=response.usage.prompt_tokens or 0,
                output_tokens=response.usage.completion_tokens or 0,
                model_tier=model_tier,
                method=method,
            )
        except Exception as exc:
            logger.debug("Cost tracking failed: %s", exc)

    def _resolve_model(self, model_tier: str) -> str:
        """Resolve tier to model name, falling back if model not available."""
        model = MODEL_TIERS.get(model_tier, OLLAMA_DEFAULT_MODEL)
        # If we know available models and requested isn't there, pick first available
        if self._available_models and model not in self._available_models:
            # Try base name match (e.g., "llama3.1:8b" matches "llama3.1")
            base = model.split(":")[0]
            for avail in self._available_models:
                if avail.startswith(base):
                    return avail
            # Fall back to first available model
            if self._available_models:
                fallback = self._available_models[0]
                logger.warning("Model %s not available, using %s", model, fallback)
                return fallback
        return model

    async def complete(
        self,
        messages: list[dict[str, str]],
        system: str = "",
        model_tier: str = "default",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> str:
        """Send a completion request to local Ollama."""
        model = self._resolve_model(model_tier)

        ollama_messages: list[dict[str, str]] = []
        if system:
            ollama_messages.append({"role": "system", "content": system})
        ollama_messages.extend(messages)

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": ollama_messages,
            "temperature": temperature,
        }

        if tools:
            kwargs["tools"] = _convert_tools_to_openai(tools)

        for attempt in range(MAX_RETRIES):
            try:
                response = await self._client.chat.completions.create(**kwargs)
                self._track_usage(response, model, model_tier)
                return response.choices[0].message.content or ""
            except (ConnectionError, TimeoutError, OSError) as e:
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning("Ollama transient error (attempt %d/%d), retrying in %.1fs: %s",
                                   attempt + 1, MAX_RETRIES, delay, e)
                    await asyncio.sleep(delay)
                else:
                    logger.error("Ollama unavailable after %d retries: %s", MAX_RETRIES, e)
                    from backend.services.llm import LLMUnavailableError
                    raise LLMUnavailableError(str(e)) from e
            except Exception as e:
                err_str = str(e)
                # If tool_use caused an invalid message format, retry without tools
                if tools and ("invalid message format" in err_str or "400" in err_str):
                    logger.warning("Ollama tool_use unsupported by %s, retrying without tools: %s", model, e)
                    kwargs.pop("tools", None)
                    tools = None  # prevent re-adding on next attempt
                    continue
                logger.error("Ollama error: %s", e)
                return ""
        return ""

    async def complete_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        system: str = "",
        model_tier: str = "default",
        max_tokens: int = 4096,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Complete with tool use."""
        model = self._resolve_model(model_tier)

        ollama_messages: list[dict[str, str]] = []
        if system:
            ollama_messages.append({"role": "system", "content": system})
        ollama_messages.extend(messages)

        use_tools = True
        for attempt in range(MAX_RETRIES):
            try:
                call_kwargs: dict[str, Any] = {
                    "model": model,
                    "max_tokens": max_tokens,
                    "messages": ollama_messages,
                }
                if use_tools:
                    call_kwargs["tools"] = _convert_tools_to_openai(tools)

                response = await self._client.chat.completions.create(**call_kwargs)
                self._track_usage(response, model, model_tier, method="complete_with_tools")

                choice = response.choices[0].message
                text = choice.content or ""
                tool_calls = []

                if use_tools and choice.tool_calls:
                    import json
                    for tc in choice.tool_calls:
                        tool_calls.append({
                            "id": tc.id,
                            "name": tc.function.name,
                            "input": json.loads(tc.function.arguments),
                        })

                return text, tool_calls
            except (ConnectionError, TimeoutError, OSError) as e:
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_BASE_DELAY * (2 ** attempt))
                else:
                    from backend.services.llm import LLMUnavailableError
                    raise LLMUnavailableError(str(e)) from e
            except Exception as e:
                err_str = str(e)
                # If tool_use caused an invalid message format, retry without tools
                if use_tools and ("invalid message format" in err_str or "400" in err_str):
                    logger.warning("Ollama tool_use unsupported by %s, falling back to plain completion: %s", model, e)
                    use_tools = False
                    continue
                logger.error("Ollama tool_use error: %s", e)
                return "", []
        return "", []

    async def stream(
        self,
        messages: list[dict[str, str]],
        system: str = "",
        model_tier: str = "default",
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ):
        """Stream completion tokens."""
        model = self._resolve_model(model_tier)

        ollama_messages: list[dict[str, str]] = []
        if system:
            ollama_messages.append({"role": "system", "content": system})
        ollama_messages.extend(messages)

        try:
            stream = await self._client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=ollama_messages,
                temperature=temperature,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield delta.content
        except Exception as e:
            logger.error("Ollama stream error: %s", e)
            yield f"[Error: {e}]"


def _convert_tools_to_openai(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert Anthropic-style tool definitions to OpenAI format."""
    oai_tools = []
    for tool in tools:
        if "function" in tool:
            oai_tools.append(tool)
        else:
            oai_tools.append({
                "type": "function",
                "function": {
                    "name": tool.get("name", "unknown"),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {}),
                },
            })
    return oai_tools
