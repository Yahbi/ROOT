"""ROOT configuration — all settings from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
_env_path = Path(__file__).parent.parent / ".env"
load_dotenv(_env_path)

# Version
VERSION = "1.0.0"

# Paths
ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
MEMORY_DB_PATH = DATA_DIR / "memory.db"
REFLECTIONS_DIR = DATA_DIR / "reflections"

# Server
HOST = os.getenv("ROOT_HOST", "127.0.0.1")
PORT = int(os.getenv("ROOT_PORT", "9000"))

# LLM — supports Anthropic (Claude), OpenAI (GPT), and DeepSeek
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
LLM_PROVIDER = os.getenv("ROOT_LLM_PROVIDER", "auto")  # "anthropic", "openai", "deepseek", or "auto"

# Anthropic models
DEFAULT_MODEL = os.getenv("ROOT_MODEL", "claude-sonnet-4-6")
THINKING_MODEL = os.getenv("ROOT_THINKING_MODEL", "claude-opus-4-6")
FAST_MODEL = os.getenv("ROOT_FAST_MODEL", "claude-haiku-4-5-20251001")

# OpenAI models
OPENAI_DEFAULT_MODEL = os.getenv("ROOT_OPENAI_MODEL", "gpt-4o")
OPENAI_THINKING_MODEL = os.getenv("ROOT_OPENAI_THINKING_MODEL", "gpt-4o")
OPENAI_FAST_MODEL = os.getenv("ROOT_OPENAI_FAST_MODEL", "gpt-4o-mini")

# DeepSeek models (open-source, cost-effective)
DEEPSEEK_DEFAULT_MODEL = os.getenv("ROOT_DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_THINKING_MODEL = os.getenv("ROOT_DEEPSEEK_THINKING_MODEL", "deepseek-reasoner")
DEEPSEEK_FAST_MODEL = os.getenv("ROOT_DEEPSEEK_FAST_MODEL", "deepseek-chat")

# Ollama local models (free, no rate limits, full privacy)
# Install models: ollama pull llama3.1:8b && ollama pull deepseek-r1:8b && ollama pull llama3.2:3b
# Available: llama3.1:8b/70b, llama3.2:3b, llama3.3:70b, deepseek-r1:8b/14b/32b,
#   mistral:7b, mixtral:8x7b, codellama:13b/34b, qwen2.5:7b/14b, gemma2:9b, phi3:14b
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_DEFAULT_MODEL = os.getenv("ROOT_OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_THINKING_MODEL = os.getenv("ROOT_OLLAMA_THINKING_MODEL", "deepseek-r1:8b")
OLLAMA_FAST_MODEL = os.getenv("ROOT_OLLAMA_FAST_MODEL", "llama3.2:3b")
OLLAMA_CODE_MODEL = os.getenv("ROOT_OLLAMA_CODE_MODEL", "codellama:13b")
OLLAMA_ENABLED = os.getenv("ROOT_OLLAMA_ENABLED", "true").lower() in ("true", "1", "yes")

# Groq (free tier: 30 RPM, very fast inference for open-source models)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_DEFAULT_MODEL = os.getenv("ROOT_GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_FAST_MODEL = os.getenv("ROOT_GROQ_FAST_MODEL", "llama-3.1-8b-instant")
GROQ_THINKING_MODEL = os.getenv("ROOT_GROQ_THINKING_MODEL", "deepseek-r1-distill-llama-70b")

# Together AI (generous free tier, open-source model hosting)
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY", "")
TOGETHER_DEFAULT_MODEL = os.getenv("ROOT_TOGETHER_MODEL", "meta-llama/Llama-3.3-70B-Instruct-Turbo")
TOGETHER_FAST_MODEL = os.getenv("ROOT_TOGETHER_FAST_MODEL", "meta-llama/Llama-3.1-8B-Instruct-Turbo")
TOGETHER_THINKING_MODEL = os.getenv("ROOT_TOGETHER_THINKING_MODEL", "deepseek-ai/DeepSeek-R1-Distill-Llama-70B")

# Memory
MEMORY_MAX_ENTRIES = int(os.getenv("ROOT_MEMORY_MAX", "10000"))
REFLECTION_INTERVAL_SECONDS = int(os.getenv("ROOT_REFLECTION_INTERVAL", "3600"))

# External services (existing systems ROOT can talk to)
HERMES_DIR = os.getenv("HERMES_DIR", os.path.expanduser("~/Desktop/HERMES"))
ASTRA_URL = os.getenv("ASTRA_URL", "http://localhost:5555")
MIRO_URL = os.getenv("MIRO_URL", "http://localhost:8080")
SWARM_DIR = os.getenv("SWARM_DIR", os.path.expanduser("~/Desktop/swarm-temp"))
OPENCLAW_URL = os.getenv("OPENCLAW_URL", "http://localhost:3000")

# Security
API_KEY = os.getenv("ROOT_API_KEY", "")  # Empty = no auth (dev mode)
RATE_LIMIT_RPM = int(os.getenv("ROOT_RATE_LIMIT", "600"))
CORS_ORIGINS = os.getenv("ROOT_CORS_ORIGINS", "http://localhost:9000,http://127.0.0.1:9000").split(",")

# Notifications
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# Email (SMTP)
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = os.getenv("SMTP_PORT", "587")
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "")
NOTIFICATION_EMAIL = os.getenv("NOTIFICATION_EMAIL", "")

# Slack
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

# Owner
OWNER_NAME = os.getenv("ROOT_OWNER", "Yohan Bismuth")


# Proactive engine intervals (seconds) — override via env
PROACTIVE_INTERVALS = {
    "health_monitor": int(os.getenv("ROOT_HEALTH_INTERVAL", "300")),
    "knowledge_consolidation": int(os.getenv("ROOT_KNOWLEDGE_INTERVAL", "3600")),
    "goal_tracker": int(os.getenv("ROOT_GOAL_INTERVAL", "1800")),
    "opportunity_scanner": int(os.getenv("ROOT_OPPORTUNITY_INTERVAL", "7200")),
    "agent_evolution": int(os.getenv("ROOT_EVOLUTION_INTERVAL", "3600")),
    "skill_discovery": int(os.getenv("ROOT_SKILL_INTERVAL", "1800")),
    "market_scanner": int(os.getenv("ROOT_MARKET_INTERVAL", "600")),
    "github_scanner": int(os.getenv("ROOT_GITHUB_INTERVAL", "7200")),
    "self_rewrite": int(os.getenv("ROOT_REWRITE_INTERVAL", "14400")),
    "miro_prediction": int(os.getenv("ROOT_MIRO_INTERVAL", "1800")),
    "data_intelligence": int(os.getenv("ROOT_DATA_INTERVAL", "7200")),
    "task_queue_drainer": int(os.getenv("ROOT_QUEUE_INTERVAL", "120")),
    "auto_trade_cycle": int(os.getenv("ROOT_TRADE_INTERVAL", "600")),
    "goal_assessment": int(os.getenv("ROOT_GOAL_ASSESS_INTERVAL", "3600")),
    "survival_economics": int(os.getenv("ROOT_SURVIVAL_INTERVAL", "7200")),
    "miro_continuous": int(os.getenv("ROOT_MIRO_CONT_INTERVAL", "1800")),
    "business_discovery": int(os.getenv("ROOT_BUSINESS_INTERVAL", "14400")),
    "experiment_proposer": int(os.getenv("ROOT_EXPERIMENT_PROPOSE_INTERVAL", "7200")),
    "revenue_seeder": int(os.getenv("ROOT_REVENUE_SEED_INTERVAL", "86400")),
    "ecosystem_scanner": int(os.getenv("ROOT_ECOSYSTEM_INTERVAL", "3600")),
    "experiment_runner": int(os.getenv("ROOT_EXPERIMENT_RUN_INTERVAL", "3600")),
    "code_scanner": int(os.getenv("ROOT_CODE_SCAN_INTERVAL", "7200")),
    "revenue_tracker": int(os.getenv("ROOT_REVENUE_TRACK_INTERVAL", "3600")),
    "project_correlator": int(os.getenv("ROOT_CORRELATOR_INTERVAL", "14400")),
    "strategy_validator": int(os.getenv("ROOT_STRATEGY_INTERVAL", "3600")),
    "deploy_promoted": int(os.getenv("ROOT_DEPLOY_PROMOTED_INTERVAL", "3600")),
    "scalp_trade_cycle": int(os.getenv("ROOT_SCALP_INTERVAL", "90")),
    "polymarket_scanner": int(os.getenv("ROOT_POLYMARKET_SCAN_INTERVAL", "600")),
    "polymarket_trade_cycle": int(os.getenv("ROOT_POLYMARKET_TRADE_INTERVAL", "1800")),
    "polymarket_monitor": int(os.getenv("ROOT_POLYMARKET_MONITOR_INTERVAL", "300")),
    "miro_world_intelligence": int(os.getenv("ROOT_MIRO_WORLD_INTERVAL", "14400")),
    "miro_daily_briefing": int(os.getenv("ROOT_MIRO_BRIEFING_INTERVAL", "86400")),
}

# Financial thresholds
SURVIVAL_BUDGET = float(os.getenv("ROOT_SURVIVAL_BUDGET", "400.0"))
HEDGE_FUND_MAX_POSITION_PCT = float(os.getenv("ROOT_MAX_POSITION_PCT", "0.05"))
HEDGE_FUND_MAX_PORTFOLIO_RISK_PCT = float(os.getenv("ROOT_MAX_PORTFOLIO_RISK_PCT", "0.15"))
HEDGE_FUND_MAX_DAILY_LOSS_PCT = float(os.getenv("ROOT_MAX_DAILY_LOSS_PCT", "0.03"))


def validate_config() -> list[str]:
    """Validate configuration at startup. Returns list of warnings."""
    warnings: list[str] = []
    if not ANTHROPIC_API_KEY and not OPENAI_API_KEY and not DEEPSEEK_API_KEY:
        warnings.append("No LLM API key set — ROOT will run in offline mode only")
    return warnings
