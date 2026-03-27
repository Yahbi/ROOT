"""Alpaca paper trading plugin builder."""

from __future__ import annotations

import logging
import os

import httpx

from backend.core.plugin_engine import Plugin, PluginTool

logger = logging.getLogger("root.plugins")


def register_trading_plugins(engine, memory_engine=None, skill_engine=None) -> None:
    """Register Alpaca trading plugin (only if API key is configured)."""
    alpaca_key = os.getenv("ALPACA_API_KEY", "")
    alpaca_secret = os.getenv("ALPACA_API_SECRET", "")
    alpaca_base = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

    if not alpaca_key:
        logger.info("Alpaca Trading plugin: SKIPPED (no ALPACA_API_KEY)")
        return

    async def _alpaca_request(method: str, path: str, body: dict | None = None) -> dict:
        """Make authenticated request to Alpaca API."""
        headers = {
            "APCA-API-KEY-ID": alpaca_key,
            "APCA-API-SECRET-KEY": alpaca_secret,
            "Content-Type": "application/json",
        }
        url = f"{alpaca_base}{path}"
        async with httpx.AsyncClient(timeout=15) as client:
            if method == "GET":
                resp = await client.get(url, headers=headers)
            elif method == "POST":
                resp = await client.post(url, headers=headers, json=body or {})
            elif method == "DELETE":
                resp = await client.delete(url, headers=headers)
            else:
                return {"error": f"Unsupported method: {method}"}
            if resp.status_code >= 400:
                return {"error": f"Alpaca {resp.status_code}: {resp.text[:300]}"}
            return resp.json() if resp.text else {"status": "ok"}

    async def alpaca_account(args):
        """Get Alpaca paper trading account info."""
        data = await _alpaca_request("GET", "/v2/account")
        if "error" in data:
            return data
        return {
            "status": data.get("status"),
            "cash": float(data.get("cash", 0)),
            "portfolio_value": float(data.get("portfolio_value", 0)),
            "buying_power": float(data.get("buying_power", 0)),
            "equity": float(data.get("equity", 0)),
            "last_equity": float(data.get("last_equity", 0)),
            "day_trade_count": data.get("daytrade_count", 0),
            "currency": data.get("currency", "USD"),
        }

    async def alpaca_positions(args):
        """Get all open positions."""
        data = await _alpaca_request("GET", "/v2/positions")
        if isinstance(data, dict) and "error" in data:
            return data
        return {
            "count": len(data),
            "positions": [
                {
                    "symbol": p["symbol"],
                    "qty": float(p["qty"]),
                    "side": p["side"],
                    "market_value": float(p["market_value"]),
                    "cost_basis": float(p["cost_basis"]),
                    "unrealized_pl": float(p["unrealized_pl"]),
                    "unrealized_plpc": round(float(p["unrealized_plpc"]) * 100, 2),
                    "current_price": float(p["current_price"]),
                    "avg_entry_price": float(p["avg_entry_price"]),
                }
                for p in data
            ],
        }

    async def alpaca_place_order(args):
        """Place a paper trade order on Alpaca."""
        symbol = args.get("symbol", "").upper()
        qty = args.get("qty")
        side = args.get("side", "buy").lower()
        order_type = args.get("type", "market").lower()
        time_in_force = args.get("time_in_force", "day").lower()

        if not symbol or not qty:
            return {"error": "symbol and qty are required"}

        order_body = {
            "symbol": symbol,
            "qty": str(qty),
            "side": side,
            "type": order_type,
            "time_in_force": time_in_force,
        }

        limit_price = args.get("limit_price")
        if limit_price and order_type == "limit":
            order_body["limit_price"] = str(limit_price)

        stop_price = args.get("stop_price")
        if stop_price and order_type in ("stop", "stop_limit"):
            order_body["stop_price"] = str(stop_price)

        data = await _alpaca_request("POST", "/v2/orders", order_body)
        if "error" in data:
            return data
        return {
            "id": data.get("id"),
            "symbol": data.get("symbol"),
            "qty": data.get("qty"),
            "side": data.get("side"),
            "type": data.get("type"),
            "status": data.get("status"),
            "time_in_force": data.get("time_in_force"),
            "created_at": data.get("created_at"),
        }

    async def alpaca_orders(args):
        """Get recent orders."""
        status = args.get("status", "all")
        limit = args.get("limit", 20)
        data = await _alpaca_request("GET", f"/v2/orders?status={status}&limit={limit}")
        if isinstance(data, dict) and "error" in data:
            return data
        return {
            "count": len(data),
            "orders": [
                {
                    "id": o["id"],
                    "symbol": o["symbol"],
                    "qty": o.get("qty"),
                    "filled_qty": o.get("filled_qty"),
                    "side": o["side"],
                    "type": o["type"],
                    "status": o["status"],
                    "filled_avg_price": o.get("filled_avg_price"),
                    "created_at": o.get("created_at"),
                }
                for o in data
            ],
        }

    async def alpaca_cancel_order(args):
        """Cancel an open order by ID."""
        order_id = args.get("order_id", "")
        if not order_id:
            return {"error": "order_id is required"}
        return await _alpaca_request("DELETE", f"/v2/orders/{order_id}")

    async def alpaca_market_data(args):
        """Get latest quote/price for symbols."""
        symbols = args.get("symbols", "")
        if not symbols:
            return {"error": "symbols is required (comma-separated)"}
        data_url = "https://data.alpaca.markets/v2"
        headers = {
            "APCA-API-KEY-ID": alpaca_key,
            "APCA-API-SECRET-KEY": alpaca_secret,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{data_url}/stocks/quotes/latest",
                headers=headers,
                params={"symbols": symbols},
            )
            if resp.status_code >= 400:
                return {"error": f"Alpaca data {resp.status_code}: {resp.text[:200]}"}
            quotes = resp.json().get("quotes", {})
            return {
                "quotes": {
                    sym: {
                        "bid": q.get("bp"),
                        "ask": q.get("ap"),
                        "bid_size": q.get("bs"),
                        "ask_size": q.get("as"),
                        "timestamp": q.get("t"),
                    }
                    for sym, q in quotes.items()
                }
            }

    engine.register(Plugin(
        id="alpaca",
        name="Alpaca Trading",
        description="Paper trading via Alpaca — account, positions, orders, market data",
        version="1.0.0",
        category="trading",
        tags=["trading", "alpaca", "stocks", "crypto", "paper"],
        tools=[
            PluginTool(
                name="alpaca_account",
                description="Get Alpaca paper trading account info (cash, equity, buying power, portfolio value)",
                handler=alpaca_account,
                parameters={"type": "object", "properties": {}},
            ),
            PluginTool(
                name="alpaca_positions",
                description="Get all open positions with P&L",
                handler=alpaca_positions,
                parameters={"type": "object", "properties": {}},
            ),
            PluginTool(
                name="alpaca_place_order",
                description="Place a paper trade order (buy/sell stocks or crypto)",
                handler=alpaca_place_order,
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "Ticker symbol (e.g. AAPL, BTC/USD)"},
                        "qty": {"type": "number", "description": "Quantity to trade"},
                        "side": {"type": "string", "description": "buy or sell", "default": "buy"},
                        "type": {"type": "string", "description": "market, limit, stop, stop_limit", "default": "market"},
                        "time_in_force": {"type": "string", "description": "day, gtc, ioc, fok", "default": "day"},
                        "limit_price": {"type": "number", "description": "Limit price (for limit orders)"},
                        "stop_price": {"type": "number", "description": "Stop price (for stop orders)"},
                    },
                    "required": ["symbol", "qty"],
                },
            ),
            PluginTool(
                name="alpaca_orders",
                description="Get recent orders (open, closed, or all)",
                handler=alpaca_orders,
                parameters={
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "description": "all, open, or closed", "default": "all"},
                        "limit": {"type": "integer", "description": "Max orders to return", "default": 20},
                    },
                },
            ),
            PluginTool(
                name="alpaca_cancel_order",
                description="Cancel an open order by its ID",
                handler=alpaca_cancel_order,
                parameters={
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string", "description": "The order ID to cancel"},
                    },
                    "required": ["order_id"],
                },
            ),
            PluginTool(
                name="alpaca_market_data",
                description="Get latest bid/ask quotes for stock symbols",
                handler=alpaca_market_data,
                parameters={
                    "type": "object",
                    "properties": {
                        "symbols": {"type": "string", "description": "Comma-separated symbols (AAPL,TSLA,SPY)"},
                    },
                    "required": ["symbols"],
                },
            ),
        ],
    ))
    logger.info("Alpaca Trading plugin: ACTIVE (paper mode)")
