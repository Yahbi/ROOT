"""
Polymarket CLOB trading plugin — prediction market trading via py-clob-client.

Provides tools for:
- Market discovery (Gamma API — no auth)
- Order book data and pricing (CLOB API — no auth)
- Trading: place/cancel orders, check positions (CLOB API — L2 auth)
- Balance and account info
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from backend.core.plugin_engine import Plugin, PluginTool

logger = logging.getLogger("root.plugins.polymarket")

# Gamma API for market discovery (no auth needed)
GAMMA_BASE = "https://gamma-api.polymarket.com"


def register_polymarket_plugins(engine, **kwargs) -> None:
    """Register Polymarket trading plugin (requires POLYMARKET_PRIVATE_KEY)."""
    private_key = os.getenv("POLYMARKET_PRIVATE_KEY", "")

    if not private_key:
        logger.info("Polymarket plugin: SKIPPED (no POLYMARKET_PRIVATE_KEY)")
        return

    # Lazy-init the CLOB client (heavy import)
    _client_cache: dict[str, Any] = {}

    def _get_client():
        if "client" not in _client_cache:
            from py_clob_client.client import ClobClient

            client = ClobClient(
                host="https://clob.polymarket.com",
                key=private_key,
                chain_id=137,
                signature_type=0,  # EOA wallet
            )
            # Derive L2 API credentials for trading
            try:
                creds = client.create_or_derive_api_creds()
                client.set_api_creds(creds)
                logger.info("Polymarket: L2 API credentials derived")
            except Exception as e:
                logger.warning("Polymarket: failed to derive API creds: %s", e)
            _client_cache["client"] = client
        return _client_cache["client"]

    # ── Market Discovery (Gamma API, no auth) ──────────────────

    async def polymarket_markets(args: dict) -> dict:
        """Search active Polymarket markets."""
        limit = args.get("limit", 20)
        order = args.get("order", "volume_24hr")
        tag = args.get("tag", "")
        search = args.get("search", "")

        params: dict[str, Any] = {
            "active": "true",
            "closed": "false",
            "limit": min(limit, 50),
        }
        if tag:
            params["tag_id"] = tag
        if search:
            params["slug"] = search

        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.get(f"{GAMMA_BASE}/markets", params=params)
            if resp.status_code >= 400:
                return {"error": f"Gamma API {resp.status_code}: {resp.text[:200]}"}
            data = resp.json()

        if not isinstance(data, list):
            return {"error": "Unexpected response format", "raw": str(data)[:300]}

        markets = []
        for m in data:
            prices = m.get("outcomePrices", "")
            if isinstance(prices, str):
                try:
                    import json
                    prices = json.loads(prices)
                except Exception:
                    prices = []

            markets.append({
                "condition_id": m.get("conditionId", ""),
                "question": m.get("question", ""),
                "slug": m.get("slug", ""),
                "yes_price": float(prices[0]) if prices else 0,
                "no_price": float(prices[1]) if len(prices) > 1 else 0,
                "volume": float(m.get("volume", 0) or 0),
                "volume_24hr": float(m.get("volume24hr", 0) or 0),
                "liquidity": float(m.get("liquidity", 0) or 0),
                "end_date": m.get("endDate", ""),
                "token_ids": m.get("clobTokenIds", []),
                "outcomes": m.get("outcomes", []),
            })

        return {"count": len(markets), "markets": markets}

    async def polymarket_events(args: dict) -> dict:
        """Get Polymarket events (groups of related markets)."""
        limit = args.get("limit", 10)
        tag = args.get("tag", "")

        params: dict[str, Any] = {
            "active": "true",
            "closed": "false",
            "limit": min(limit, 30),
        }
        if tag:
            params["tag"] = tag

        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.get(f"{GAMMA_BASE}/events", params=params)
            if resp.status_code >= 400:
                return {"error": f"Gamma API {resp.status_code}: {resp.text[:200]}"}
            data = resp.json()

        if not isinstance(data, list):
            return {"error": "Unexpected response", "raw": str(data)[:300]}

        events = []
        for ev in data:
            events.append({
                "id": ev.get("id", ""),
                "title": ev.get("title", ""),
                "slug": ev.get("slug", ""),
                "volume": float(ev.get("volume", 0) or 0),
                "liquidity": float(ev.get("liquidity", 0) or 0),
                "market_count": len(ev.get("markets", [])),
                "end_date": ev.get("endDate", ""),
            })

        return {"count": len(events), "events": events}

    # ── Order Book & Pricing (CLOB API, no auth) ──────────────

    def polymarket_orderbook(args: dict) -> dict:
        """Get order book for a market token."""
        token_id = args.get("token_id", "")
        if not token_id:
            return {"error": "token_id is required"}

        client = _get_client()
        try:
            book = client.get_order_book(token_id)
            mid = client.get_midpoint(token_id)
            spread = client.get_spread(token_id)
            last = client.get_last_trade_price(token_id)

            bids = book.bids[:5] if hasattr(book, 'bids') else []
            asks = book.asks[:5] if hasattr(book, 'asks') else []

            return {
                "token_id": token_id,
                "midpoint": float(mid) if mid else 0,
                "spread": float(spread) if spread else 0,
                "last_trade": float(last) if last else 0,
                "best_bid": float(bids[0].price) if bids else 0,
                "best_ask": float(asks[0].price) if asks else 0,
                "bid_depth": sum(float(b.size) for b in bids),
                "ask_depth": sum(float(a.size) for a in asks),
                "bids": [{"price": float(b.price), "size": float(b.size)} for b in bids],
                "asks": [{"price": float(a.price), "size": float(a.size)} for a in asks],
            }
        except Exception as e:
            return {"error": f"Order book fetch failed: {str(e)[:200]}"}

    def polymarket_price(args: dict) -> dict:
        """Get current price and spread for a token."""
        token_id = args.get("token_id", "")
        if not token_id:
            return {"error": "token_id is required"}

        client = _get_client()
        try:
            mid = client.get_midpoint(token_id)
            buy = client.get_price(token_id, side="BUY")
            sell = client.get_price(token_id, side="SELL")
            spread = client.get_spread(token_id)
            tick = client.get_tick_size(token_id)
            neg_risk = client.get_neg_risk(token_id)

            return {
                "token_id": token_id,
                "midpoint": float(mid) if mid else 0,
                "buy_price": float(buy) if buy else 0,
                "sell_price": float(sell) if sell else 0,
                "spread": float(spread) if spread else 0,
                "tick_size": str(tick),
                "neg_risk": bool(neg_risk),
            }
        except Exception as e:
            return {"error": f"Price fetch failed: {str(e)[:200]}"}

    # ── Trading (CLOB API, L2 auth) ───────────────────────────

    def polymarket_balance(args: dict) -> dict:
        """Get USDC balance and allowance info."""
        client = _get_client()
        try:
            balance_wei = client.get_balance()
            balance_usdc = int(balance_wei) / 1e6 if balance_wei else 0
            allowance = client.get_balance_allowance()
            return {
                "balance_usdc": balance_usdc,
                "balance_raw": str(balance_wei),
                "allowance": str(allowance) if allowance else "unknown",
            }
        except Exception as e:
            return {"error": f"Balance fetch failed: {str(e)[:200]}"}

    def polymarket_positions(args: dict) -> dict:
        """Get all open positions."""
        client = _get_client()
        try:
            positions = client.get_positions()
            if not positions:
                return {"count": 0, "positions": []}

            result = []
            for p in positions:
                result.append({
                    "asset": p.get("asset", ""),
                    "size": float(p.get("size", 0)),
                    "avg_price": float(p.get("avgPrice", 0)),
                    "side": p.get("side", ""),
                    "cur_price": float(p.get("curPrice", 0)) if p.get("curPrice") else None,
                })
            return {"count": len(result), "positions": result}
        except Exception as e:
            return {"error": f"Positions fetch failed: {str(e)[:200]}"}

    def polymarket_place_order(args: dict) -> dict:
        """Place a limit order on Polymarket."""
        token_id = args.get("token_id", "")
        price = args.get("price")
        size = args.get("size")
        side = args.get("side", "BUY").upper()

        if not token_id or price is None or size is None:
            return {"error": "token_id, price, and size are required"}
        if price <= 0 or price >= 1:
            return {"error": "price must be between 0 and 1 (exclusive)"}
        if size <= 0:
            return {"error": "size must be positive"}

        client = _get_client()
        try:
            from py_clob_client.clob_types import OrderArgs, OrderType
            from py_clob_client.order_builder.constants import BUY as CLOB_BUY, SELL as CLOB_SELL

            order_side = CLOB_BUY if side == "BUY" else CLOB_SELL
            order_args = OrderArgs(
                token_id=token_id,
                price=float(price),
                size=float(size),
                side=order_side,
            )
            signed = client.create_order(order_args)
            resp = client.post_order(signed, OrderType.GTC)

            return {
                "order_id": resp.get("orderID", resp.get("id", "")),
                "status": resp.get("status", "unknown"),
                "token_id": token_id,
                "side": side,
                "price": price,
                "size": size,
            }
        except Exception as e:
            return {"error": f"Order placement failed: {str(e)[:300]}"}

    def polymarket_market_order(args: dict) -> dict:
        """Place a market order (FOK) on Polymarket."""
        token_id = args.get("token_id", "")
        amount = args.get("amount")  # USDC for buy, shares for sell
        side = args.get("side", "BUY").upper()

        if not token_id or amount is None:
            return {"error": "token_id and amount are required"}
        if amount <= 0:
            return {"error": "amount must be positive"}

        client = _get_client()
        try:
            from py_clob_client.clob_types import MarketOrderArgs, OrderType
            from py_clob_client.order_builder.constants import BUY as CLOB_BUY, SELL as CLOB_SELL

            order_side = CLOB_BUY if side == "BUY" else CLOB_SELL
            market_args = MarketOrderArgs(
                token_id=token_id,
                amount=float(amount),
                side=order_side,
            )
            signed = client.create_market_order(market_args)
            resp = client.post_order(signed, OrderType.FOK)

            return {
                "order_id": resp.get("orderID", resp.get("id", "")),
                "status": resp.get("status", "unknown"),
                "token_id": token_id,
                "side": side,
                "amount": amount,
                "type": "FOK",
            }
        except Exception as e:
            return {"error": f"Market order failed: {str(e)[:300]}"}

    def polymarket_cancel_order(args: dict) -> dict:
        """Cancel an open order."""
        order_id = args.get("order_id", "")
        if not order_id:
            return {"error": "order_id is required"}

        client = _get_client()
        try:
            resp = client.cancel(order_id)
            return {"cancelled": True, "order_id": order_id, "response": str(resp)[:200]}
        except Exception as e:
            return {"error": f"Cancel failed: {str(e)[:200]}"}

    def polymarket_cancel_all(args: dict) -> dict:
        """Cancel all open orders."""
        client = _get_client()
        try:
            resp = client.cancel_all()
            return {"cancelled_all": True, "response": str(resp)[:200]}
        except Exception as e:
            return {"error": f"Cancel all failed: {str(e)[:200]}"}

    def polymarket_open_orders(args: dict) -> dict:
        """Get all open orders."""
        client = _get_client()
        try:
            orders = client.get_orders()
            if not orders:
                return {"count": 0, "orders": []}

            result = []
            for o in orders:
                result.append({
                    "id": o.get("id", ""),
                    "status": o.get("status", ""),
                    "side": o.get("side", ""),
                    "price": o.get("price", ""),
                    "size": o.get("original_size", o.get("size", "")),
                    "size_matched": o.get("size_matched", ""),
                    "token_id": o.get("asset_id", ""),
                    "created_at": o.get("created_at", ""),
                })
            return {"count": len(result), "orders": result}
        except Exception as e:
            return {"error": f"Orders fetch failed: {str(e)[:200]}"}

    # ── Register Plugin ───────────────────────────────────────

    engine.register(Plugin(
        id="polymarket",
        name="Polymarket Trading",
        description="Prediction market trading on Polymarket — markets, orders, positions, pricing",
        version="1.0.0",
        category="trading",
        tags=["trading", "polymarket", "prediction_markets", "crypto", "polygon"],
        tools=[
            PluginTool(
                name="polymarket_markets",
                description="Search active Polymarket prediction markets (sorted by volume)",
                handler=polymarket_markets,
                parameters={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Max results (1-50)", "default": 20},
                        "order": {"type": "string", "description": "Sort: volume_24hr, liquidity, end_date", "default": "volume_24hr"},
                        "tag": {"type": "string", "description": "Filter by tag (e.g. politics, crypto, sports)"},
                        "search": {"type": "string", "description": "Search by slug/keyword"},
                    },
                },
            ),
            PluginTool(
                name="polymarket_events",
                description="Get Polymarket events (groups of related markets)",
                handler=polymarket_events,
                parameters={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Max results (1-30)", "default": 10},
                        "tag": {"type": "string", "description": "Filter by tag"},
                    },
                },
            ),
            PluginTool(
                name="polymarket_orderbook",
                description="Get order book, midpoint, spread for a market token",
                handler=polymarket_orderbook,
                parameters={
                    "type": "object",
                    "properties": {
                        "token_id": {"type": "string", "description": "CLOB token ID (YES or NO token)"},
                    },
                    "required": ["token_id"],
                },
            ),
            PluginTool(
                name="polymarket_price",
                description="Get current price, spread, and tick size for a token",
                handler=polymarket_price,
                parameters={
                    "type": "object",
                    "properties": {
                        "token_id": {"type": "string", "description": "CLOB token ID"},
                    },
                    "required": ["token_id"],
                },
            ),
            PluginTool(
                name="polymarket_balance",
                description="Get USDC balance on Polymarket",
                handler=polymarket_balance,
                parameters={"type": "object", "properties": {}},
            ),
            PluginTool(
                name="polymarket_positions",
                description="Get all open positions on Polymarket",
                handler=polymarket_positions,
                parameters={"type": "object", "properties": {}},
            ),
            PluginTool(
                name="polymarket_place_order",
                description="Place a GTC limit order on Polymarket (buy/sell YES or NO shares)",
                handler=polymarket_place_order,
                parameters={
                    "type": "object",
                    "properties": {
                        "token_id": {"type": "string", "description": "YES or NO token ID"},
                        "price": {"type": "number", "description": "Price per share (0.01-0.99)"},
                        "size": {"type": "number", "description": "Number of shares"},
                        "side": {"type": "string", "description": "BUY or SELL", "default": "BUY"},
                    },
                    "required": ["token_id", "price", "size"],
                },
            ),
            PluginTool(
                name="polymarket_market_order",
                description="Place a FOK market order on Polymarket (instant fill or cancel)",
                handler=polymarket_market_order,
                parameters={
                    "type": "object",
                    "properties": {
                        "token_id": {"type": "string", "description": "YES or NO token ID"},
                        "amount": {"type": "number", "description": "USDC to spend (buy) or shares to sell"},
                        "side": {"type": "string", "description": "BUY or SELL", "default": "BUY"},
                    },
                    "required": ["token_id", "amount"],
                },
            ),
            PluginTool(
                name="polymarket_cancel_order",
                description="Cancel an open Polymarket order",
                handler=polymarket_cancel_order,
                parameters={
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string", "description": "Order ID to cancel"},
                    },
                    "required": ["order_id"],
                },
            ),
            PluginTool(
                name="polymarket_cancel_all",
                description="Cancel all open Polymarket orders",
                handler=polymarket_cancel_all,
                parameters={"type": "object", "properties": {}},
            ),
            PluginTool(
                name="polymarket_open_orders",
                description="Get all open orders on Polymarket",
                handler=polymarket_open_orders,
                parameters={"type": "object", "properties": {}},
            ),
        ],
    ))
    logger.info("Polymarket plugin: ACTIVE (11 tools)")
