"""Plugin registration modules for ROOT's built-in plugins."""

from backend.core.plugins.system_plugins import register_system_plugins
from backend.core.plugins.trading_plugins import register_trading_plugins
from backend.core.plugins.utility_plugins import register_utility_plugins
from backend.core.plugins.agent_tools_plugins import register_agent_tools_plugins
from backend.core.plugins.polymarket_plugins import register_polymarket_plugins

__all__ = [
    "register_system_plugins",
    "register_trading_plugins",
    "register_utility_plugins",
    "register_agent_tools_plugins",
    "register_polymarket_plugins",
]
