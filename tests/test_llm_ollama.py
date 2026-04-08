"""Tests for Ollama LLM Service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.llm_ollama import OllamaLLMService, _convert_tools_to_openai
from backend.config import OLLAMA_DEFAULT_MODEL, OLLAMA_FAST_MODEL


# ===========================================================================
# _convert_tools_to_openai tests
# ===========================================================================

class TestConvertToolsToOpenai:

    def test_passthrough_openai_format(self):
        """Tools already in OpenAI format should pass through unchanged."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get weather",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
        result = _convert_tools_to_openai(tools)
        assert result == tools

    def test_converts_anthropic_format(self):
        """Anthropic-style tool defs should be converted to OpenAI format."""
        tools = [
            {
                "name": "search",
                "description": "Search the web",
                "input_schema": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                },
            }
        ]
        result = _convert_tools_to_openai(tools)
        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "search"
        assert result[0]["function"]["description"] == "Search the web"
        assert result[0]["function"]["parameters"]["type"] == "object"

    def test_converts_mixed_formats(self):
        """Mix of both formats should be handled correctly."""
        tools = [
            {"function": {"name": "a"}, "type": "function"},
            {"name": "b", "description": "B tool", "input_schema": {}},
        ]
        result = _convert_tools_to_openai(tools)
        assert len(result) == 2
        assert result[0]["function"]["name"] == "a"
        assert result[1]["function"]["name"] == "b"

    def test_empty_tools_list(self):
        assert _convert_tools_to_openai([]) == []

    def test_missing_fields_use_defaults(self):
        """Tools missing optional fields should get safe defaults."""
        tools = [{"some_field": "value"}]
        result = _convert_tools_to_openai(tools)
        assert result[0]["function"]["name"] == "unknown"
        assert result[0]["function"]["description"] == ""
        assert result[0]["function"]["parameters"] == {}


# ===========================================================================
# OllamaLLMService._resolve_model tests
# ===========================================================================

class TestResolveModel:

    @patch("backend.services.llm_ollama.OLLAMA_DEFAULT_MODEL", "llama3.1:8b")
    @patch("backend.services.llm_ollama.OLLAMA_FAST_MODEL", "mistral:7b")
    @patch("backend.services.llm_ollama.OLLAMA_THINKING_MODEL", "deepseek-r1:8b")
    @patch("backend.services.llm_ollama.MODEL_TIERS", {
        "fast": "mistral:7b",
        "default": "llama3.1:8b",
        "thinking": "deepseek-r1:8b",
    })
    def _make_service(self):
        """Create an OllamaLLMService with mocked openai client."""
        with patch("openai.AsyncOpenAI"):
            svc = OllamaLLMService(base_url="http://localhost:11434")
        return svc

    def test_resolve_default_tier(self):
        svc = self._make_service()
        svc._available_models = []
        model = svc._resolve_model("default")
        assert model == OLLAMA_DEFAULT_MODEL

    def test_resolve_fast_tier(self):
        svc = self._make_service()
        svc._available_models = []
        model = svc._resolve_model("fast")
        assert model == OLLAMA_FAST_MODEL

    def test_resolve_unknown_tier_falls_back_to_default(self):
        svc = self._make_service()
        svc._available_models = []
        model = svc._resolve_model("nonexistent")
        assert model == OLLAMA_DEFAULT_MODEL

    def test_resolve_model_available(self):
        svc = self._make_service()
        svc._available_models = ["llama3.1:8b", "mistral:7b"]
        model = svc._resolve_model("default")
        assert model == "llama3.1:8b"

    def test_resolve_model_unavailable_base_match(self):
        """When exact model not available but base name matches another."""
        svc = self._make_service()
        svc._available_models = ["llama3.1:70b", "mistral:7b"]
        model = svc._resolve_model("default")  # wants llama3.1:8b
        assert model == "llama3.1:70b"

    def test_resolve_model_unavailable_no_match_uses_first(self):
        """When no base match, falls back to first available model."""
        svc = self._make_service()
        svc._available_models = ["gemma2:9b", "qwen2.5:7b"]
        model = svc._resolve_model("default")  # wants llama3.1:8b
        assert model == "gemma2:9b"


# ===========================================================================
# OllamaLLMService requires openai package
# ===========================================================================

class TestOllamaRequiresOpenAI:

    def test_import_error_when_openai_missing(self):
        """Should raise ImportError if openai package is not installed."""
        with patch.dict("sys.modules", {"openai": None}):
            with patch("builtins.__import__", side_effect=_selective_import_error):
                with pytest.raises(ImportError, match="openai package required"):
                    OllamaLLMService(base_url="http://localhost:11434")


def _selective_import_error(name, *args, **kwargs):
    """Only block the 'openai' import, let everything else through."""
    if name == "openai":
        raise ImportError("No module named 'openai'")
    return original_import(name, *args, **kwargs)


import builtins
original_import = builtins.__import__
