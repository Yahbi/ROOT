"""Tests for the Hedge Fund Engine — signal validation, risk controls, position monitoring, trade recording."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import FrozenInstanceError
from unittest.mock import AsyncMock, MagicMock

import pytest

import backend.core.hedge_fund as hf_mod
from backend.core.hedge_fund import (
    HedgeFundEngine,
    Position,
    Signal,
    StrategyPerformance,
    RISK_LIMITS,
    _now_iso,
)


# ── Fixtures ────────────────────────────────────────────────


@pytest.fixture
def hedge_fund(tmp_path, monkeypatch):
    """Provide a started HedgeFundEngine with a temp database."""
    monkeypatch.setattr(hf_mod, "HEDGE_FUND_DB", tmp_path / "hedge_fund.db")
    engine = HedgeFundEngine()
    engine.start()
    yield engine
    engine.stop()


@pytest.fixture
def make_signal():
    """Factory fixture for creating Signal instances with defaults."""
    def _make(
        symbol="AAPL",
        direction="long",
        confidence=0.80,
        source="miro",
        reasoning="bullish breakout pattern",
        **kwargs,
    ) -> Signal:
        return Signal(
            id=kwargs.pop("id", f"sig_{uuid.uuid4().hex[:8]}"),
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            source=source,
            reasoning=reasoning,
            **kwargs,
        )
    return _make


@pytest.fixture
def seeded_engine(hedge_fund, make_signal):
    """Hedge fund engine pre-loaded with confirming signals for AAPL long."""
    sig_a = make_signal(id="sig_a", source="miro")
    sig_b = make_signal(id="sig_b", source="swarm")
    sig_c = make_signal(id="sig_c", source="researcher")
    hedge_fund._signals = [sig_a, sig_b, sig_c]
    return hedge_fund, sig_a


def _insert_open_trade(engine, symbol="AAPL", direction="long", entry_price=150.0,
                        quantity=10, stop_loss=None, take_profit=None, strategy="ai_hedge_fund"):
    """Helper to insert an open trade directly into the database."""
    trade_id = f"trade_{uuid.uuid4().hex[:8]}"
    engine.conn.execute(
        """INSERT INTO trades
           (id, symbol, direction, quantity, entry_price, stop_loss,
            take_profit, status, strategy, opened_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)""",
        (trade_id, symbol, direction, quantity, entry_price,
         stop_loss, take_profit, strategy, _now_iso()),
    )
    engine.conn.commit()
    return trade_id


# ── 1. Signal Dataclass: Immutability ───────────────────────


class TestSignalDataclass:

    def test_signal_creation(self, make_signal):
        sig = make_signal(symbol="TSLA", direction="short", confidence=0.72)
        assert sig.symbol == "TSLA"
        assert sig.direction == "short"
        assert sig.confidence == 0.72

    def test_signal_is_frozen(self, make_signal):
        sig = make_signal()
        with pytest.raises(FrozenInstanceError):
            sig.confidence = 0.99  # type: ignore[misc]

    def test_signal_defaults(self, make_signal):
        sig = make_signal()
        assert sig.timeframe == "swing"
        assert sig.entry_price is None
        assert sig.stop_loss is None
        assert sig.take_profit is None
        assert sig.created_at  # non-empty timestamp

    def test_position_is_frozen(self):
        pos = Position(id="p1", symbol="BTC", direction="long", quantity=1.0, entry_price=50000.0)
        with pytest.raises(FrozenInstanceError):
            pos.status = "closed"  # type: ignore[misc]

    def test_strategy_performance_is_frozen(self):
        sp = StrategyPerformance(
            strategy_name="momentum", total_trades=10, winning_trades=7,
            losing_trades=3, win_rate=0.7, avg_return_pct=2.5,
            total_pnl=1500.0, sharpe_ratio=1.2, max_drawdown_pct=5.0,
        )
        with pytest.raises(FrozenInstanceError):
            sp.weight = 2.0  # type: ignore[misc]


# ── 2. Risk Controls ────────────────────────────────────────


class TestRiskControls:

    def test_reject_below_min_confidence(self, hedge_fund, make_signal):
        sig = make_signal(confidence=0.50)
        ok, reason = hedge_fund.check_risk(sig, 100_000)
        assert ok is False
        assert "Confidence" in reason

    def test_reject_at_max_open_positions(self, hedge_fund, make_signal):
        for i in range(RISK_LIMITS["max_open_positions"]):
            _insert_open_trade(hedge_fund, symbol=f"SYM{i}")
        sig = make_signal(confidence=0.80)
        ok, reason = hedge_fund.check_risk(sig, 100_000)
        assert ok is False
        assert "Max open positions" in reason

    def test_reject_daily_loss_limit(self, hedge_fund, make_signal):
        hedge_fund._daily_pnl = -5000.0  # 5% of 100k, exceeds 3% limit
        sig = make_signal(confidence=0.80)
        ok, reason = hedge_fund.check_risk(sig, 100_000)
        assert ok is False
        assert "Daily loss limit" in reason

    def test_reject_existing_position_in_symbol(self, hedge_fund, make_signal):
        _insert_open_trade(hedge_fund, symbol="AAPL")
        sig = make_signal(symbol="AAPL", confidence=0.80)
        ok, reason = hedge_fund.check_risk(sig, 100_000)
        assert ok is False
        assert "Already have open position" in reason

    def test_reject_insufficient_confirmations(self, hedge_fund, make_signal):
        sig = make_signal(id="sig_alone", confidence=0.80)
        hedge_fund._signals = [sig]  # only one signal, needs 2
        ok, reason = hedge_fund.check_risk(sig, 100_000)
        assert ok is False
        assert "confirmations" in reason

    def test_pass_all_checks(self, seeded_engine):
        engine, sig = seeded_engine
        ok, reason = engine.check_risk(sig, 100_000)
        assert ok is True
        assert reason == "Risk check passed"

    def test_reject_confidence_boundary(self, hedge_fund, make_signal):
        """Confidence exactly at the boundary (0.65) should still pass the >= check."""
        # 0.65 is NOT less than 0.65, so it should pass the confidence check
        # but may fail on confirmations
        sig = make_signal(confidence=0.65)
        hedge_fund._signals = [sig, make_signal(id="sig2", confidence=0.70)]
        ok, reason = hedge_fund.check_risk(sig, 100_000)
        assert ok is True


# ── 3. Position Monitoring ──────────────────────────────────


class TestMonitorPositions:

    @pytest.mark.asyncio
    async def test_stop_loss_hit_long(self, hedge_fund, make_signal):
        trade_id = _insert_open_trade(
            hedge_fund, symbol="AAPL", direction="long",
            entry_price=150.0, quantity=10, stop_loss=140.0,
        )
        mock_plugins = MagicMock()
        quote_result = MagicMock()
        quote_result.success = True
        quote_result.output = {"quotes": {"AAPL": {"ask": 139.0, "bid": 139.0}}}
        mock_plugins.invoke = AsyncMock(return_value=quote_result)
        hedge_fund._plugins = mock_plugins

        summary = await hedge_fund.monitor_positions()
        assert summary["stopped_out"] == 1
        assert summary["still_open"] == 0

        trade = hedge_fund.conn.execute(
            "SELECT status FROM trades WHERE id = ?", (trade_id,)
        ).fetchone()
        assert trade["status"] == "closed"

    @pytest.mark.asyncio
    async def test_take_profit_hit_short(self, hedge_fund):
        trade_id = _insert_open_trade(
            hedge_fund, symbol="TSLA", direction="short",
            entry_price=200.0, quantity=5, take_profit=180.0,
        )
        mock_plugins = MagicMock()
        quote_result = MagicMock()
        quote_result.success = True
        quote_result.output = {"quotes": {"TSLA": {"ask": 175.0, "bid": 175.0}}}
        mock_plugins.invoke = AsyncMock(return_value=quote_result)
        hedge_fund._plugins = mock_plugins

        summary = await hedge_fund.monitor_positions()
        assert summary["take_profit_hit"] == 1

    @pytest.mark.asyncio
    async def test_position_still_open(self, hedge_fund):
        _insert_open_trade(
            hedge_fund, symbol="MSFT", direction="long",
            entry_price=300.0, quantity=5, stop_loss=280.0, take_profit=350.0,
        )
        mock_plugins = MagicMock()
        quote_result = MagicMock()
        quote_result.success = True
        quote_result.output = {"quotes": {"MSFT": {"ask": 310.0, "bid": 310.0}}}
        mock_plugins.invoke = AsyncMock(return_value=quote_result)
        hedge_fund._plugins = mock_plugins

        summary = await hedge_fund.monitor_positions()
        assert summary["still_open"] == 1
        assert summary["stopped_out"] == 0
        assert summary["take_profit_hit"] == 0

    @pytest.mark.asyncio
    async def test_no_open_positions(self, hedge_fund):
        summary = await hedge_fund.monitor_positions()
        assert summary["checked"] == 0
        assert summary["still_open"] == 0

    @pytest.mark.asyncio
    async def test_no_plugin_keeps_position_open(self, hedge_fund):
        """Without plugins, price is 0 and positions stay open."""
        _insert_open_trade(hedge_fund, symbol="AAPL", stop_loss=140.0)
        hedge_fund._plugins = None
        summary = await hedge_fund.monitor_positions()
        assert summary["checked"] == 1
        assert summary["still_open"] == 1


# ── 4. Trade Outcome Recording ──────────────────────────────


class TestRecordTradeOutcome:

    def test_winning_long_trade(self, hedge_fund):
        trade_id = _insert_open_trade(
            hedge_fund, symbol="AAPL", direction="long",
            entry_price=100.0, quantity=10,
        )
        result = hedge_fund.record_trade_outcome(trade_id, exit_price=120.0)
        assert result is not None
        assert result["status"] == "win"
        assert result["pnl"] == 200.0  # (120 - 100) * 10
        assert result["pnl_pct"] == 20.0

    def test_losing_long_trade(self, hedge_fund):
        trade_id = _insert_open_trade(
            hedge_fund, symbol="AAPL", direction="long",
            entry_price=100.0, quantity=10,
        )
        result = hedge_fund.record_trade_outcome(trade_id, exit_price=90.0)
        assert result is not None
        assert result["status"] == "loss"
        assert result["pnl"] == -100.0  # (90 - 100) * 10
        assert result["pnl_pct"] == -10.0

    def test_winning_short_trade(self, hedge_fund):
        trade_id = _insert_open_trade(
            hedge_fund, symbol="TSLA", direction="short",
            entry_price=200.0, quantity=5,
        )
        result = hedge_fund.record_trade_outcome(trade_id, exit_price=180.0)
        assert result is not None
        assert result["status"] == "win"
        assert result["pnl"] == 100.0  # (200 - 180) * 5

    def test_losing_short_trade(self, hedge_fund):
        trade_id = _insert_open_trade(
            hedge_fund, symbol="TSLA", direction="short",
            entry_price=200.0, quantity=5,
        )
        result = hedge_fund.record_trade_outcome(trade_id, exit_price=220.0)
        assert result is not None
        assert result["status"] == "loss"
        assert result["pnl"] == -100.0

    def test_nonexistent_trade_returns_none(self, hedge_fund):
        result = hedge_fund.record_trade_outcome("nonexistent_id", 100.0)
        assert result is None

    def test_strategy_weight_bayesian_update(self, hedge_fund):
        trade_id = _insert_open_trade(
            hedge_fund, symbol="AAPL", direction="long",
            entry_price=100.0, quantity=10,
        )
        hedge_fund.record_trade_outcome(trade_id, exit_price=110.0)

        weights = hedge_fund.get_strategy_weights()
        assert len(weights) == 1
        assert weights[0]["wins"] == 1
        assert weights[0]["losses"] == 0
        # Bayesian for first-time insert win: weight = 0.67
        assert weights[0]["weight"] == pytest.approx(0.67, abs=0.01)

    def test_strategy_weight_updates_on_second_trade(self, hedge_fund):
        t1 = _insert_open_trade(hedge_fund, symbol="AAPL", direction="long",
                                entry_price=100.0, quantity=10)
        hedge_fund.record_trade_outcome(t1, exit_price=110.0)

        t2 = _insert_open_trade(hedge_fund, symbol="TSLA", direction="long",
                                entry_price=100.0, quantity=10)
        hedge_fund.record_trade_outcome(t2, exit_price=90.0)

        weights = hedge_fund.get_strategy_weights()
        assert len(weights) == 1
        w = weights[0]
        assert w["wins"] == 1
        assert w["losses"] == 1
        # Bayesian update: (1+1)/(1+1+2) = 0.5
        assert w["weight"] == pytest.approx(0.5, abs=0.01)

    def test_daily_pnl_accumulates(self, hedge_fund):
        assert hedge_fund._daily_pnl == 0.0
        t1 = _insert_open_trade(hedge_fund, symbol="AAPL", direction="long",
                                entry_price=100.0, quantity=10)
        hedge_fund.record_trade_outcome(t1, exit_price=110.0)
        assert hedge_fund._daily_pnl == pytest.approx(10.0)  # pnl per share = 10

        t2 = _insert_open_trade(hedge_fund, symbol="TSLA", direction="long",
                                entry_price=100.0, quantity=5)
        hedge_fund.record_trade_outcome(t2, exit_price=90.0)
        # daily_pnl = 10 + (-10) = 0
        assert hedge_fund._daily_pnl == pytest.approx(0.0)


# ── 5. Signal Parsing (Heuristic) ───────────────────────────


class TestParseSignalsHeuristic:

    def test_parse_bullish_signal(self, hedge_fund):
        text = "AAPL is showing strong bullish momentum with a breakout above resistance."
        signals = hedge_fund._parse_signals_heuristic(text, "test")
        assert len(signals) >= 1
        aapl_sigs = [s for s in signals if s.symbol == "AAPL"]
        assert len(aapl_sigs) == 1
        assert aapl_sigs[0].direction == "long"

    def test_parse_bearish_signal(self, hedge_fund):
        text = "TSLA is bearish with a breakdown below support, expecting further downside and drop."
        signals = hedge_fund._parse_signals_heuristic(text, "test")
        tsla_sigs = [s for s in signals if s.symbol == "TSLA"]
        assert len(tsla_sigs) == 1
        assert tsla_sigs[0].direction == "short"

    def test_no_signals_from_neutral_text(self, hedge_fund):
        text = "The weather is nice today."
        signals = hedge_fund._parse_signals_heuristic(text, "test")
        assert signals == []

    def test_multiple_symbols_parsed(self, hedge_fund):
        text = (
            "Buy SPY now, strong bullish rally upside. "
            "Sell TSLA short, bearish breakdown drop."
        )
        signals = hedge_fund._parse_signals_heuristic(text, "test")
        symbols = {s.symbol for s in signals}
        assert "SPY" in symbols
        assert "TSLA" in symbols

    def test_signal_confidence_bounded(self, hedge_fund):
        text = "BTC buy long bullish upside rally breakout support"  # many long keywords
        signals = hedge_fund._parse_signals_heuristic(text, "test")
        for sig in signals:
            assert sig.confidence <= 0.9
            assert sig.confidence >= 0.5

    def test_btc_usd_normalized(self, hedge_fund):
        text = "BTC-USD is showing bullish momentum and rally."
        signals = hedge_fund._parse_signals_heuristic(text, "test")
        btc_sigs = [s for s in signals if s.symbol == "BTC"]
        assert len(btc_sigs) >= 1


# ── 6. Portfolio Stats ──────────────────────────────────────


class TestPortfolioStats:

    def test_get_performance_empty(self, hedge_fund):
        perf = hedge_fund.get_performance()
        assert perf["total_trades"] == 0
        assert perf["win_rate"] == 0
        assert perf["total_pnl"] == 0

    def test_get_performance_with_closed_trades(self, hedge_fund):
        t1 = _insert_open_trade(hedge_fund, symbol="AAPL", direction="long",
                                entry_price=100.0, quantity=10)
        hedge_fund.record_trade_outcome(t1, exit_price=110.0)

        t2 = _insert_open_trade(hedge_fund, symbol="TSLA", direction="long",
                                entry_price=100.0, quantity=10)
        hedge_fund.record_trade_outcome(t2, exit_price=90.0)

        perf = hedge_fund.get_performance()
        assert perf["total_trades"] == 2
        assert perf["winning_trades"] == 1
        assert perf["losing_trades"] == 1
        assert perf["win_rate"] == 50.0

    def test_get_signals_empty(self, hedge_fund):
        signals = hedge_fund.get_signals()
        assert signals == []

    def test_get_signals_stored(self, hedge_fund, make_signal):
        sig = make_signal(symbol="AAPL")
        hedge_fund._store_signal(sig)
        signals = hedge_fund.get_signals()
        assert len(signals) == 1
        assert signals[0]["symbol"] == "AAPL"

    def test_get_trades_all(self, hedge_fund):
        _insert_open_trade(hedge_fund, symbol="AAPL")
        _insert_open_trade(hedge_fund, symbol="TSLA")
        trades = hedge_fund.get_trades(status="all")
        assert len(trades) == 2

    def test_get_trades_filtered_by_status(self, hedge_fund):
        t1 = _insert_open_trade(hedge_fund, symbol="AAPL", entry_price=100.0, quantity=10)
        _insert_open_trade(hedge_fund, symbol="TSLA")
        hedge_fund.record_trade_outcome(t1, exit_price=110.0)

        open_trades = hedge_fund.get_trades(status="open")
        assert len(open_trades) == 1
        assert open_trades[0]["symbol"] == "TSLA"

        closed_trades = hedge_fund.get_trades(status="closed")
        assert len(closed_trades) == 1
        assert closed_trades[0]["symbol"] == "AAPL"

    def test_get_strategy_weights_empty(self, hedge_fund):
        weights = hedge_fund.get_strategy_weights()
        assert weights == []

    def test_get_open_positions_summary(self, hedge_fund):
        _insert_open_trade(hedge_fund, symbol="AAPL", entry_price=150.0, quantity=10)
        summary = hedge_fund.get_open_positions_summary()
        assert len(summary) == 1
        assert summary[0]["symbol"] == "AAPL"
        assert "pnl_display" in summary[0]


# ── 7. Lifecycle ────────────────────────────────────────────


class TestLifecycle:

    def test_start_creates_tables(self, tmp_path, monkeypatch):
        monkeypatch.setattr(hf_mod, "HEDGE_FUND_DB", tmp_path / "hf_test.db")
        engine = HedgeFundEngine()
        engine.start()
        try:
            tables = engine.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {r["name"] for r in tables}
            assert "signals" in table_names
            assert "trades" in table_names
            assert "portfolio_snapshots" in table_names
            assert "strategy_weights" in table_names
        finally:
            engine.stop()

    def test_stop_closes_connection(self, tmp_path, monkeypatch):
        monkeypatch.setattr(hf_mod, "HEDGE_FUND_DB", tmp_path / "hf_test.db")
        engine = HedgeFundEngine()
        engine.start()
        engine.stop()
        assert engine._conn is None

    def test_conn_property_raises_if_not_started(self):
        engine = HedgeFundEngine()
        with pytest.raises(RuntimeError, match="not started"):
            _ = engine.conn

    def test_stats_delegates_to_get_performance(self, hedge_fund):
        result = hedge_fund.stats()
        assert "total_trades" in result
        assert result == hedge_fund.get_performance()

    def test_start_creates_parent_directory(self, tmp_path, monkeypatch):
        db_path = tmp_path / "nested" / "dir" / "hf.db"
        monkeypatch.setattr(hf_mod, "HEDGE_FUND_DB", db_path)
        engine = HedgeFundEngine()
        engine.start()
        try:
            assert db_path.parent.exists()
        finally:
            engine.stop()
