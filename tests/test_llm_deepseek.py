"""Tests for DeepSeek LLM Service — provider config, model tiers, economic routing."""

from __future__ import annotations

import pytest

from backend.services.llm_deepseek import (
    DeepSeekLLMService,
    DEEPSEEK_BASE_URL,
    MODEL_TIERS,
    _convert_tools_to_openai,
)


# ── Configuration ────────────────────────────────────────────


class TestDeepSeekConfig:
    def test_base_url(self):
        assert DEEPSEEK_BASE_URL == "https://api.deepseek.com/v1"

    def test_model_tiers_keys(self):
        assert set(MODEL_TIERS.keys()) == {"fast", "default", "thinking"}

    def test_default_tier_is_chat(self):
        assert MODEL_TIERS["default"] == "deepseek-chat"

    def test_thinking_tier_is_reasoner(self):
        assert MODEL_TIERS["thinking"] == "deepseek-reasoner"

    def test_fast_tier_is_chat(self):
        assert MODEL_TIERS["fast"] == "deepseek-chat"

    def test_requires_api_key(self, monkeypatch):
        monkeypatch.setattr("backend.services.llm_deepseek.DEEPSEEK_API_KEY", "")
        with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
            DeepSeekLLMService(api_key="")

    def test_provider_name(self):
        svc = DeepSeekLLMService(api_key="test-key-123")
        assert svc.provider == "deepseek"

    def test_custom_api_key(self):
        svc = DeepSeekLLMService(api_key="sk-custom-key")
        assert svc._client.api_key == "sk-custom-key"

    def test_base_url_set(self):
        svc = DeepSeekLLMService(api_key="sk-test")
        assert str(svc._client.base_url).rstrip("/").endswith("/v1")


# ── Tool Conversion ──────────────────────────────────────────


class TestToolConversion:
    def test_openai_format_passthrough(self):
        tools = [{"type": "function", "function": {"name": "test"}}]
        result = _convert_tools_to_openai(tools)
        assert result == tools

    def test_anthropic_format_converted(self):
        tools = [{
            "name": "get_weather",
            "description": "Get weather for a city",
            "input_schema": {"type": "object", "properties": {"city": {"type": "string"}}},
        }]
        result = _convert_tools_to_openai(tools)
        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "get_weather"
        assert result[0]["function"]["description"] == "Get weather for a city"

    def test_empty_tools(self):
        assert _convert_tools_to_openai([]) == []

    def test_mixed_formats(self):
        tools = [
            {"type": "function", "function": {"name": "oai_tool"}},
            {"name": "anthropic_tool", "description": "desc", "input_schema": {}},
        ]
        result = _convert_tools_to_openai(tools)
        assert len(result) == 2
        assert result[0]["function"]["name"] == "oai_tool"
        assert result[1]["function"]["name"] == "anthropic_tool"


# ── Economic Router Integration ──────────────────────────────


class TestDeepSeekEconomicRouting:
    def test_no_router_still_works(self):
        svc = DeepSeekLLMService(api_key="sk-test", economic_router=None)
        assert svc._economic_router is None

    def test_router_injected(self):
        class FakeRouter:
            pass
        svc = DeepSeekLLMService(api_key="sk-test", economic_router=FakeRouter())
        assert svc._economic_router is not None

    def test_cost_tracker_injected(self):
        class FakeTracker:
            pass
        svc = DeepSeekLLMService(api_key="sk-test", cost_tracker=FakeTracker())
        assert svc._cost_tracker is not None


# ── Cost Tracker Pricing ─────────────────────────────────────


class TestDeepSeekPricing:
    def test_chat_pricing_exists(self):
        from backend.core.cost_tracker import _PRICING
        assert "deepseek-chat" in _PRICING
        assert _PRICING["deepseek-chat"]["input"] == 0.14
        assert _PRICING["deepseek-chat"]["output"] == 0.28

    def test_reasoner_pricing_exists(self):
        from backend.core.cost_tracker import _PRICING
        assert "deepseek-reasoner" in _PRICING
        assert _PRICING["deepseek-reasoner"]["input"] == 0.55
        assert _PRICING["deepseek-reasoner"]["output"] == 2.19

    def test_deepseek_cost_computation(self):
        from backend.core.cost_tracker import compute_cost
        # 1M input + 1M output tokens on deepseek-chat
        cost = compute_cost("deepseek-chat", 1_000_000, 1_000_000)
        assert cost == pytest.approx(0.42, abs=0.01)

    def test_deepseek_reasoner_cost(self):
        from backend.core.cost_tracker import compute_cost
        # 1M input + 1M output tokens on deepseek-reasoner
        cost = compute_cost("deepseek-reasoner", 1_000_000, 1_000_000)
        assert cost == pytest.approx(2.74, abs=0.01)

    def test_deepseek_much_cheaper_than_claude(self):
        from backend.core.cost_tracker import compute_cost
        ds_cost = compute_cost("deepseek-chat", 100_000, 100_000)
        claude_cost = compute_cost("claude-sonnet-4-20250514", 100_000, 100_000)
        assert ds_cost < claude_cost * 0.1  # DeepSeek is >10x cheaper


# ── Config Validation ────────────────────────────────────────


class TestDeepSeekConfig2:
    def test_config_has_deepseek_key(self):
        from backend.config import DEEPSEEK_API_KEY
        assert isinstance(DEEPSEEK_API_KEY, str)

    def test_config_has_deepseek_models(self):
        from backend.config import (
            DEEPSEEK_DEFAULT_MODEL,
            DEEPSEEK_THINKING_MODEL,
            DEEPSEEK_FAST_MODEL,
        )
        assert DEEPSEEK_DEFAULT_MODEL == "deepseek-chat"
        assert DEEPSEEK_THINKING_MODEL == "deepseek-reasoner"
        assert DEEPSEEK_FAST_MODEL == "deepseek-chat"
