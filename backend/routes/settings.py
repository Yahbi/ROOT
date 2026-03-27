"""Settings API — user preferences CRUD via StateStore."""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/settings", tags=["settings"])

# Default settings schema
_DEFAULTS = {
    "llm_provider": "auto",
    "model_default": "claude-sonnet-4-6",
    "model_thinking": "claude-opus-4-6",
    "model_fast": "claude-haiku-4-5-20251001",
    "theme": "brown",
    "autonomous_loop_enabled": True,
    "proactive_engine_enabled": True,
    "builder_enabled": True,
    "directive_engine_enabled": True,
    "continuous_learning_enabled": True,
    "notifications_telegram": True,
    "notifications_discord": True,
    "notifications_in_app": True,
    "notification_min_level": "medium",
    "cost_alert_daily_usd": 10.0,
    "cost_alert_monthly_usd": 200.0,
    "hedge_fund_enabled": True,
    "hedge_fund_max_position_pct": 0.05,
    "hedge_fund_max_portfolio_risk_pct": 0.15,
    "hedge_fund_max_daily_loss_pct": 0.03,
    "chat_streaming": True,
    "chat_show_process_cards": True,
    "memory_auto_decay": True,
    "reflection_interval_hours": 1,
}

_STORE_KEY = "user_settings"


class SettingsUpdate(BaseModel):
    """Partial settings update — only provided fields are changed."""
    llm_provider: str | None = None
    model_default: str | None = None
    model_thinking: str | None = None
    model_fast: str | None = None
    theme: str | None = None
    autonomous_loop_enabled: bool | None = None
    proactive_engine_enabled: bool | None = None
    builder_enabled: bool | None = None
    directive_engine_enabled: bool | None = None
    continuous_learning_enabled: bool | None = None
    notifications_telegram: bool | None = None
    notifications_discord: bool | None = None
    notifications_in_app: bool | None = None
    notification_min_level: str | None = None
    cost_alert_daily_usd: float | None = None
    cost_alert_monthly_usd: float | None = None
    hedge_fund_enabled: bool | None = None
    hedge_fund_max_position_pct: float | None = None
    hedge_fund_max_portfolio_risk_pct: float | None = None
    hedge_fund_max_daily_loss_pct: float | None = None
    chat_streaming: bool | None = None
    chat_show_process_cards: bool | None = None
    memory_auto_decay: bool | None = None
    reflection_interval_hours: int | None = None


def _load(request: Request) -> dict:
    """Load settings from StateStore, merging with defaults."""
    import json as _json
    store = getattr(request.app.state, "state_store", None)
    if store is None:
        return dict(_DEFAULTS)
    raw = store.get_meta(_STORE_KEY, "{}")
    try:
        saved = _json.loads(raw)
    except Exception:
        saved = {}
    return {**_DEFAULTS, **saved}


def _save(request: Request, settings: dict) -> None:
    """Persist settings to StateStore."""
    import json as _json
    store = getattr(request.app.state, "state_store", None)
    if store is not None:
        store.set_meta(_STORE_KEY, _json.dumps(settings))


@router.get("")
async def get_settings(request: Request):
    """Get all current settings."""
    return {"settings": _load(request)}


@router.patch("")
async def update_settings(request: Request, body: SettingsUpdate):
    """Update specific settings (partial merge)."""
    current = _load(request)
    updates = body.model_dump(exclude_none=True)
    merged = {**current, **updates}
    _save(request, merged)
    return {"settings": merged, "updated": list(updates.keys())}


@router.post("/reset")
async def reset_settings(request: Request):
    """Reset all settings to defaults."""
    _save(request, {})
    return {"settings": {**_DEFAULTS}, "message": "Settings reset to defaults"}


@router.get("/schema")
async def get_settings_schema():
    """Get settings schema with defaults and descriptions."""
    schema = {
        "groups": [
            {
                "id": "llm",
                "label": "LLM Configuration",
                "fields": [
                    {"key": "llm_provider", "type": "select", "label": "Provider", "options": ["auto", "anthropic", "openai", "deepseek"], "default": "auto"},
                    {"key": "model_default", "type": "text", "label": "Default Model", "default": "claude-sonnet-4-6"},
                    {"key": "model_thinking", "type": "text", "label": "Thinking Model", "default": "claude-opus-4-6"},
                    {"key": "model_fast", "type": "text", "label": "Fast Model", "default": "claude-haiku-4-5-20251001"},
                ],
            },
            {
                "id": "autonomy",
                "label": "Autonomous Systems",
                "fields": [
                    {"key": "autonomous_loop_enabled", "type": "toggle", "label": "Autonomous Loop", "default": True},
                    {"key": "proactive_engine_enabled", "type": "toggle", "label": "Proactive Engine", "default": True},
                    {"key": "builder_enabled", "type": "toggle", "label": "Builder Agent", "default": True},
                    {"key": "directive_engine_enabled", "type": "toggle", "label": "Directive Engine", "default": True},
                    {"key": "continuous_learning_enabled", "type": "toggle", "label": "Continuous Learning", "default": True},
                ],
            },
            {
                "id": "notifications",
                "label": "Notifications",
                "fields": [
                    {"key": "notifications_telegram", "type": "toggle", "label": "Telegram", "default": True},
                    {"key": "notifications_discord", "type": "toggle", "label": "Discord", "default": True},
                    {"key": "notifications_in_app", "type": "toggle", "label": "In-App", "default": True},
                    {"key": "notification_min_level", "type": "select", "label": "Min Level", "options": ["low", "medium", "high", "critical"], "default": "medium"},
                ],
            },
            {
                "id": "costs",
                "label": "Cost Alerts",
                "fields": [
                    {"key": "cost_alert_daily_usd", "type": "number", "label": "Daily Alert ($)", "default": 10.0},
                    {"key": "cost_alert_monthly_usd", "type": "number", "label": "Monthly Alert ($)", "default": 200.0},
                ],
            },
            {
                "id": "trading",
                "label": "Trading & Risk",
                "fields": [
                    {"key": "hedge_fund_enabled", "type": "toggle", "label": "Hedge Fund Active", "default": True},
                    {"key": "hedge_fund_max_position_pct", "type": "number", "label": "Max Position %", "default": 0.05, "step": 0.01},
                    {"key": "hedge_fund_max_portfolio_risk_pct", "type": "number", "label": "Max Portfolio Risk %", "default": 0.15, "step": 0.01},
                    {"key": "hedge_fund_max_daily_loss_pct", "type": "number", "label": "Max Daily Loss %", "default": 0.03, "step": 0.01},
                ],
            },
            {
                "id": "chat",
                "label": "Chat & Display",
                "fields": [
                    {"key": "chat_streaming", "type": "toggle", "label": "Stream Responses", "default": True},
                    {"key": "chat_show_process_cards", "type": "toggle", "label": "Show Process Cards", "default": True},
                    {"key": "theme", "type": "select", "label": "Theme", "options": ["brown", "dark", "light", "midnight"], "default": "brown"},
                ],
            },
            {
                "id": "memory",
                "label": "Memory & Learning",
                "fields": [
                    {"key": "memory_auto_decay", "type": "toggle", "label": "Auto Memory Decay", "default": True},
                    {"key": "reflection_interval_hours", "type": "number", "label": "Reflection Interval (hrs)", "default": 1, "step": 1},
                ],
            },
            {
                "id": "sandbox",
                "label": "Sandbox / Live Mode",
                "description": "Controls whether ROOT can impact external systems. Sandbox = simulated, Live = real.",
                "fields": [
                    {"key": "sandbox_global_mode", "type": "select", "label": "Global Mode", "options": ["sandbox", "live"], "default": "sandbox"},
                    {"key": "sandbox_trading", "type": "select", "label": "Trading", "options": ["global", "sandbox", "live"], "default": "global"},
                    {"key": "sandbox_notifications", "type": "select", "label": "Notifications", "options": ["global", "sandbox", "live"], "default": "global"},
                    {"key": "sandbox_code_deploy", "type": "select", "label": "Code Deploy", "options": ["global", "sandbox", "live"], "default": "global"},
                    {"key": "sandbox_revenue", "type": "select", "label": "Revenue", "options": ["global", "sandbox", "live"], "default": "global"},
                    {"key": "sandbox_proactive", "type": "select", "label": "Proactive Actions", "options": ["global", "sandbox", "live"], "default": "global"},
                    {"key": "sandbox_plugins", "type": "select", "label": "Plugins", "options": ["global", "sandbox", "live"], "default": "global"},
                    {"key": "sandbox_file_system", "type": "select", "label": "File System", "options": ["global", "sandbox", "live"], "default": "global"},
                ],
            },
        ],
    }
    return schema
