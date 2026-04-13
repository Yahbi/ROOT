"""
Quantitative Trading Models — mathematically proven, backtestable edges.

Models:
- Kelly Criterion (fractional) for optimal position sizing
- LMSR / Softmax pricing for market scoring / arbitrage detection
- Expected Value + Arbitrage bounds
- Brier Score / Bayesian calibration + Monte Carlo simulation
- ARIMA/GARCH for volatility + directional forecasting
- Cointegration for pairs/stat-arb

All models are pure math — no LLM dependency. Used by ThesisEngine and
InvestmentAgents for quantitative signal generation.
"""

from __future__ import annotations

import logging
import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import numpy as np

logger = logging.getLogger("root.quant_models")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ════════════════════════════════════════════════════════════════
# 1. Kelly Criterion (Fractional)
# ════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class KellyResult:
    """Output of Kelly position sizing."""
    full_kelly_fraction: float  # f* = (p*b - q) / b
    fractional_kelly: float     # f* * fraction (e.g. 0.25)
    fraction_used: float        # e.g. 0.25
    edge: float                 # p*b - q (expected profit per $1 bet)
    probability: float
    odds: float
    recommended_pct: float      # As portfolio % (0-100)
    max_position_usd: float     # Given portfolio_value


def kelly_criterion(
    win_probability: float,
    win_loss_ratio: float = 1.0,
    fraction: float = 0.25,
    portfolio_value: float = 100_000.0,
    max_position_pct: float = 5.0,
) -> KellyResult:
    """Fractional Kelly Criterion for optimal position sizing.

    f* = (p * b - q) / b
    where p = win probability, q = 1-p, b = win/loss ratio (odds).

    Uses fractional Kelly (default 1/4) for robustness against
    probability estimation errors.

    Args:
        win_probability: Estimated probability of winning (0.0-1.0).
        win_loss_ratio: Ratio of average win to average loss (b).
        fraction: Kelly fraction (0.25 = quarter-Kelly, safer).
        portfolio_value: Total portfolio value in USD.
        max_position_pct: Hard cap on position size as % of portfolio.
    """
    p = max(0.001, min(0.999, win_probability))
    q = 1.0 - p
    b = max(0.01, win_loss_ratio)

    edge = p * b - q
    full_kelly = edge / b if edge > 0 else 0.0
    frac_kelly = full_kelly * fraction

    # Cap at max_position_pct
    recommended_pct = min(frac_kelly * 100, max_position_pct)
    max_position = portfolio_value * (recommended_pct / 100.0)

    return KellyResult(
        full_kelly_fraction=full_kelly,
        fractional_kelly=frac_kelly,
        fraction_used=fraction,
        edge=edge,
        probability=p,
        odds=b,
        recommended_pct=recommended_pct,
        max_position_usd=max_position,
    )


def kelly_prediction_market(
    true_probability: float,
    market_price: float,
    fraction: float = 0.25,
    portfolio_value: float = 100_000.0,
    max_position_pct: float = 5.0,
) -> KellyResult:
    """Kelly for prediction markets (simplified form).

    f* = (p - q) / (1 - q)  where p=true prob, q=market implied prob.
    Positive = buy YES, negative = buy NO.
    """
    p = max(0.001, min(0.999, true_probability))
    q = max(0.001, min(0.999, market_price))

    # Win/loss ratio in prediction market: payout = 1/q, cost = q
    # So b = (1 - q) / q  (you pay q, win 1-q net)
    b = (1.0 - q) / q
    edge = p * b - (1.0 - p)
    full_kelly = edge / b if edge > 0 else 0.0
    frac_kelly = full_kelly * fraction

    recommended_pct = min(abs(frac_kelly) * 100, max_position_pct)
    max_position = portfolio_value * (recommended_pct / 100.0)

    return KellyResult(
        full_kelly_fraction=full_kelly,
        fractional_kelly=frac_kelly,
        fraction_used=fraction,
        edge=edge,
        probability=p,
        odds=b,
        recommended_pct=recommended_pct,
        max_position_usd=max_position,
    )


# ════════════════════════════════════════════════════════════════
# 2. LMSR (Logarithmic Market Scoring Rule) / Softmax Pricing
# ════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class LMSRResult:
    """LMSR market pricing output."""
    prices: list[float]           # Implied probability per outcome
    cost_to_buy: float            # Cost to buy 1 unit of target outcome
    arbitrage_detected: bool      # True if prices sum != 1 (within tolerance)
    arbitrage_profit: float       # Risk-free profit if arb exists
    liquidity_param: float        # b parameter


def lmsr_prices(
    quantities: list[float],
    liquidity: float = 100.0,
) -> list[float]:
    """Compute LMSR outcome prices (softmax-like).

    p_k(q) = exp(q_k / b) / sum_i(exp(q_i / b))

    Args:
        quantities: Current quantity held in each outcome.
        liquidity: b parameter (higher = more liquid, tighter spreads).
    """
    b = max(0.01, liquidity)
    # Numerically stable softmax
    q_arr = np.array(quantities, dtype=np.float64)
    q_scaled = q_arr / b
    q_scaled -= q_scaled.max()  # numerical stability
    exp_q = np.exp(q_scaled)
    prices = exp_q / exp_q.sum()
    return prices.tolist()


def lmsr_cost(
    quantities_before: list[float],
    quantities_after: list[float],
    liquidity: float = 100.0,
) -> float:
    """Cost of moving from quantities_before to quantities_after.

    C(q) = b * ln(sum(exp(q_i / b)))
    Cost = C(q_after) - C(q_before)
    """
    b = max(0.01, liquidity)

    def _cost_fn(q: list[float]) -> float:
        q_arr = np.array(q, dtype=np.float64) / b
        max_val = q_arr.max()
        q_shifted = q_arr - max_val
        return b * (max_val + np.log(np.sum(np.exp(q_shifted))))

    return _cost_fn(quantities_after) - _cost_fn(quantities_before)


def detect_arbitrage(
    prices: list[float],
    tolerance: float = 0.02,
) -> LMSRResult:
    """Detect arbitrage in prediction market prices.

    If sum(prices) < 1 - tolerance: buy all outcomes (risk-free).
    If sum(prices) > 1 + tolerance: sell all outcomes (risk-free).
    """
    total = sum(prices)
    arb = abs(total - 1.0) > tolerance
    profit = abs(1.0 - total) if arb else 0.0

    return LMSRResult(
        prices=prices,
        cost_to_buy=prices[0] if prices else 0.0,
        arbitrage_detected=arb,
        arbitrage_profit=profit,
        liquidity_param=0.0,
    )


# ════════════════════════════════════════════════════════════════
# 3. Expected Value + Arbitrage Bounds
# ════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class EVResult:
    """Expected value calculation result."""
    expected_value: float
    true_probability: float
    market_price: float
    edge: float                  # EV - cost
    edge_pct: float              # edge as % of cost
    is_positive_ev: bool
    kelly_size: Optional[KellyResult] = None


def expected_value(
    true_probability: float,
    payout: float,
    cost: float,
) -> EVResult:
    """Calculate expected value of a bet/trade.

    EV = p(true) * payout - cost
    """
    p = max(0.0, min(1.0, true_probability))
    ev = p * payout - cost
    edge = ev
    edge_pct = (edge / cost * 100) if cost > 0 else 0.0

    return EVResult(
        expected_value=ev,
        true_probability=p,
        market_price=cost / payout if payout > 0 else 0.0,
        edge=edge,
        edge_pct=edge_pct,
        is_positive_ev=ev > 0,
    )


def logical_arbitrage(
    correlated_prices: dict[str, float],
    constraint: str = "sum_equals_one",
    tolerance: float = 0.02,
) -> dict:
    """Detect logical arbitrage across correlated markets.

    Checks constraints like:
    - P(A) + P(not A) should = 1
    - P(A or B) >= max(P(A), P(B))
    - Sum of mutually exclusive outcomes = 1

    Returns arbitrage opportunities with expected profit.
    """
    total = sum(correlated_prices.values())
    opportunities = []

    if constraint == "sum_equals_one":
        if total < 1.0 - tolerance:
            # Buy all outcomes: guaranteed payout of 1, cost < 1
            opportunities.append({
                "type": "buy_all",
                "cost": total,
                "guaranteed_payout": 1.0,
                "risk_free_profit": 1.0 - total,
                "profit_pct": ((1.0 - total) / total) * 100 if total > 0 else 0,
            })
        elif total > 1.0 + tolerance:
            # Sell all outcomes: receive > 1, max payout = 1
            opportunities.append({
                "type": "sell_all",
                "revenue": total,
                "max_liability": 1.0,
                "risk_free_profit": total - 1.0,
                "profit_pct": ((total - 1.0) / 1.0) * 100,
            })

    return {
        "prices": correlated_prices,
        "total": total,
        "constraint": constraint,
        "arbitrage_found": len(opportunities) > 0,
        "opportunities": opportunities,
    }


# ════════════════════════════════════════════════════════════════
# 4. Brier Score / Bayesian Calibration + Monte Carlo
# ════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class CalibrationResult:
    """Calibration assessment result."""
    brier_score: float           # Lower is better (0 = perfect)
    calibration_error: float     # Mean absolute calibration error
    overconfidence: float        # Positive = overconfident
    bucket_scores: dict          # Per-bucket calibration
    total_predictions: int


def brier_score(
    predictions: list[tuple[float, int]],
) -> float:
    """Calculate Brier Score for probability predictions.

    BS = (1/N) * sum((p_i - o_i)^2)
    where p_i = predicted probability, o_i = actual outcome (0 or 1).

    Perfect = 0.0, worst = 1.0, random = 0.25.
    """
    if not predictions:
        return float('nan')
    n = len(predictions)
    return sum((p - o) ** 2 for p, o in predictions) / n


def calibration_analysis(
    predictions: list[tuple[float, int]],
    n_buckets: int = 10,
) -> CalibrationResult:
    """Analyze prediction calibration across confidence buckets.

    Groups predictions into buckets and compares predicted probability
    against actual hit rate per bucket.
    """
    if not predictions:
        return CalibrationResult(
            brier_score=0.5, calibration_error=0.5,
            overconfidence=0.0, bucket_scores={}, total_predictions=0,
        )

    bs = brier_score(predictions)

    # Bucket predictions
    buckets: dict[str, list[tuple[float, int]]] = {}
    for prob, outcome in predictions:
        bucket_idx = min(int(prob * n_buckets), n_buckets - 1)
        bucket_key = f"{bucket_idx / n_buckets:.1f}-{(bucket_idx + 1) / n_buckets:.1f}"
        buckets.setdefault(bucket_key, []).append((prob, outcome))

    bucket_scores = {}
    errors = []
    overconf_sum = 0.0
    for key, items in buckets.items():
        avg_predicted = statistics.mean(p for p, _ in items)
        actual_rate = statistics.mean(o for _, o in items)
        error = abs(avg_predicted - actual_rate)
        errors.append(error)
        overconf_sum += avg_predicted - actual_rate
        bucket_scores[key] = {
            "avg_predicted": round(avg_predicted, 3),
            "actual_rate": round(actual_rate, 3),
            "error": round(error, 3),
            "count": len(items),
        }

    cal_error = statistics.mean(errors) if errors else 0.5
    overconfidence = overconf_sum / len(buckets) if buckets else 0.0

    return CalibrationResult(
        brier_score=round(bs, 4),
        calibration_error=round(cal_error, 4),
        overconfidence=round(overconfidence, 4),
        bucket_scores=bucket_scores,
        total_predictions=len(predictions),
    )


def bayesian_update(
    prior: float,
    likelihood_if_true: float,
    likelihood_if_false: float,
) -> float:
    """Bayesian probability update.

    P(H|E) = P(E|H) * P(H) / [P(E|H)*P(H) + P(E|~H)*P(~H)]
    """
    p_h = max(0.001, min(0.999, prior))
    p_e_h = max(0.001, likelihood_if_true)
    p_e_nh = max(0.001, likelihood_if_false)

    numerator = p_e_h * p_h
    denominator = numerator + p_e_nh * (1 - p_h)

    return numerator / denominator if denominator > 0 else prior


def monte_carlo_simulation(
    historical_returns: list[float],
    n_simulations: int = 10_000,
    n_days: int = 30,
    initial_value: float = 100_000.0,
) -> dict:
    """Monte Carlo simulation for price/portfolio path forecasting.

    Uses empirical distribution of historical returns to simulate
    future paths. Returns percentile outcomes.
    """
    if not historical_returns or len(historical_returns) < 5:
        return {"error": "Insufficient historical data (need >= 5 returns)"}

    returns = np.array(historical_returns)
    mean_ret = np.mean(returns)
    std_ret = np.std(returns, ddof=1)

    # Simulate paths, track per-path max drawdown
    final_values = []
    max_drawdowns = []
    for _ in range(n_simulations):
        simulated_returns = np.random.normal(mean_ret, std_ret, n_days)
        cum_path = initial_value * np.cumprod(1 + simulated_returns)
        final_values.append(cum_path[-1])
        # Max drawdown for this path
        running_max = np.maximum.accumulate(cum_path)
        drawdowns = (cum_path - running_max) / running_max
        max_drawdowns.append(float(np.min(drawdowns)))

    final_values = np.array(final_values)
    total_returns = (final_values - initial_value) / initial_value
    max_drawdowns = np.array(max_drawdowns)

    return {
        "initial_value": initial_value,
        "n_simulations": n_simulations,
        "n_days": n_days,
        "mean_final": round(float(np.mean(final_values)), 2),
        "median_final": round(float(np.median(final_values)), 2),
        "p5_final": round(float(np.percentile(final_values, 5)), 2),
        "p25_final": round(float(np.percentile(final_values, 25)), 2),
        "p75_final": round(float(np.percentile(final_values, 75)), 2),
        "p95_final": round(float(np.percentile(final_values, 95)), 2),
        "mean_return": round(float(np.mean(total_returns)), 4),
        "median_return": round(float(np.median(total_returns)), 4),
        "p5_return": round(float(np.percentile(total_returns, 5)), 4),
        "p95_return": round(float(np.percentile(total_returns, 95)), 4),
        "prob_profit": round(float(np.mean(total_returns > 0)), 4),
        "prob_loss_gt_10pct": round(float(np.mean(total_returns < -0.10)), 4),
        "max_drawdown_median": round(float(np.median(max_drawdowns)), 4),
    }


# ════════════════════════════════════════════════════════════════
# 5. ARIMA / GARCH for Volatility + Direction
# ════════════════════════════════════════════════════════════════

def simple_arima_forecast(
    prices: list[float],
    forecast_days: int = 5,
    lookback: int = 60,
) -> dict:
    """Simplified ARIMA(1,1,1)-like forecast using differencing + AR.

    Uses numpy only (no statsmodels dependency). Good enough for
    directional signals when combined with other models.
    """
    if len(prices) < max(10, lookback):
        return {"error": "Insufficient price history"}

    recent = np.array(prices[-lookback:], dtype=np.float64)

    # First difference (d=1)
    diff = np.diff(recent)

    # AR(1) coefficient via autocorrelation
    if len(diff) < 3:
        return {"error": "Too few data points after differencing"}

    mean_diff = np.mean(diff)
    diff_centered = diff - mean_diff

    # Autocorrelation at lag 1
    if np.var(diff_centered) > 0:
        ar1 = np.corrcoef(diff_centered[:-1], diff_centered[1:])[0, 1]
    else:
        ar1 = 0.0

    ar1 = max(-0.99, min(0.99, ar1))

    # Forecast
    last_price = prices[-1]
    last_diff = diff[-1]
    forecasted_prices = [last_price]

    for _ in range(forecast_days):
        next_diff = mean_diff + ar1 * (last_diff - mean_diff)
        next_price = forecasted_prices[-1] + next_diff
        forecasted_prices.append(next_price)
        last_diff = next_diff

    forecasted_prices = forecasted_prices[1:]  # Remove starting price

    # Direction signal
    price_change = forecasted_prices[-1] - prices[-1]
    pct_change = (price_change / prices[-1]) * 100

    return {
        "current_price": round(prices[-1], 2),
        "forecast_prices": [round(p, 2) for p in forecasted_prices],
        "forecast_final": round(forecasted_prices[-1], 2),
        "price_change": round(price_change, 2),
        "pct_change": round(pct_change, 4),
        "direction": "bullish" if price_change > 0 else "bearish" if price_change < 0 else "neutral",
        "ar1_coefficient": round(ar1, 4),
        "mean_daily_change": round(mean_diff, 4),
        "forecast_days": forecast_days,
    }


def garch_volatility(
    returns: list[float],
    omega: float = 0.00001,
    alpha: float = 0.1,
    beta: float = 0.85,
    forecast_days: int = 5,
) -> dict:
    """GARCH(1,1) volatility estimation and forecast.

    sigma^2_t = omega + alpha * r^2_{t-1} + beta * sigma^2_{t-1}

    Args:
        returns: Historical log returns.
        omega, alpha, beta: GARCH parameters (default = typical equity).
        forecast_days: Number of days to forecast volatility.
    """
    if len(returns) < 10:
        return {"error": "Insufficient return history (need >= 10)"}

    ret = np.array(returns, dtype=np.float64)

    # Estimate conditional variance series
    n = len(ret)
    sigma2 = np.zeros(n)
    sigma2[0] = np.var(ret, ddof=1)  # Initialize with sample variance

    for t in range(1, n):
        sigma2[t] = omega + alpha * ret[t - 1] ** 2 + beta * sigma2[t - 1]

    current_vol = math.sqrt(max(0.0, sigma2[-1]))
    annualized_vol = current_vol * math.sqrt(252)

    # Warn if non-stationary
    persistence = alpha + beta
    if persistence >= 1.0:
        logger.warning("GARCH non-stationary: alpha+beta=%.3f >= 1.0", persistence)

    # Forecast variance
    forecast_var = []
    last_var = sigma2[-1]
    last_ret2 = ret[-1] ** 2
    unconditional_var = omega / (1 - persistence) if persistence < 1 else np.var(ret, ddof=1)

    # 1-step-ahead forecast
    one_step = omega + alpha * last_ret2 + beta * last_var
    forecast_var.append(one_step)

    for i in range(1, forecast_days):
        # Multi-step: converges to unconditional variance
        next_var = unconditional_var + persistence ** i * (one_step - unconditional_var)
        forecast_var.append(next_var)

    forecast_vol = [math.sqrt(max(0.0, v)) for v in forecast_var]
    forecast_vol_annual = [v * math.sqrt(252) for v in forecast_vol]

    # Regime detection
    long_term_vol = math.sqrt(max(0.0, unconditional_var)) * math.sqrt(252)
    vol_ratio = annualized_vol / long_term_vol if long_term_vol > 0 else 1.0

    if vol_ratio > 1.5:
        regime = "high_volatility"
    elif vol_ratio < 0.7:
        regime = "low_volatility"
    else:
        regime = "normal"

    return {
        "current_daily_vol": round(current_vol, 6),
        "current_annual_vol": round(annualized_vol, 4),
        "long_term_annual_vol": round(long_term_vol, 4),
        "vol_ratio": round(vol_ratio, 3),
        "regime": regime,
        "forecast_daily_vol": [round(v, 6) for v in forecast_vol],
        "forecast_annual_vol": [round(v, 4) for v in forecast_vol_annual],
        "garch_params": {"omega": omega, "alpha": alpha, "beta": beta},
        "persistence": round(alpha + beta, 4),
    }


# ════════════════════════════════════════════════════════════════
# 6. Cointegration / Pairs Trading (stat arb)
# ════════════════════════════════════════════════════════════════

def cointegration_test(
    series_a: list[float],
    series_b: list[float],
    lookback: int = 60,
) -> dict:
    """Simplified cointegration test for pairs trading.

    Uses OLS regression + Augmented Dickey-Fuller-like test on residuals.
    """
    if len(series_a) < lookback or len(series_b) < lookback:
        return {"error": "Insufficient data for cointegration test"}

    a = np.array(series_a[-lookback:], dtype=np.float64)
    b = np.array(series_b[-lookback:], dtype=np.float64)

    # OLS: a = beta * b + alpha + residuals
    b_with_const = np.column_stack([b, np.ones(len(b))])
    beta_alpha, residuals, _, _ = np.linalg.lstsq(b_with_const, a, rcond=None)
    hedge_ratio = beta_alpha[0]
    intercept = beta_alpha[1]

    # Spread (residuals)
    spread = a - hedge_ratio * b - intercept
    spread_mean = np.mean(spread)
    spread_std = np.std(spread)

    # Current z-score
    current_z = (spread[-1] - spread_mean) / spread_std if spread_std > 0 else 0.0

    # Half-life of mean reversion (AR(1) on spread via OLS, not correlation)
    spread_lag = spread[:-1]
    spread_curr = spread[1:]
    var_lag = np.var(spread_lag)
    if var_lag > 0:
        phi = np.cov(spread_lag, spread_curr)[0, 1] / var_lag
        half_life = -math.log(2) / math.log(phi) if 0 < phi < 1 else float('inf')
    else:
        phi = 0.0
        half_life = float('inf')

    # Simplified stationarity check (ADF-like)
    # If |phi| < 1, spread is mean-reverting → cointegrated
    is_cointegrated = abs(phi) < 0.95 and half_life < lookback

    # Trading signal
    if is_cointegrated:
        if current_z > 2.0:
            signal = "short_spread"  # Sell A, buy B
        elif current_z < -2.0:
            signal = "long_spread"  # Buy A, sell B
        elif abs(current_z) < 0.5:
            signal = "close"  # Mean reverted
        else:
            signal = "hold"
    else:
        signal = "no_trade"

    return {
        "is_cointegrated": is_cointegrated,
        "hedge_ratio": round(hedge_ratio, 4),
        "intercept": round(intercept, 4),
        "current_z_score": round(current_z, 3),
        "spread_mean": round(spread_mean, 4),
        "spread_std": round(spread_std, 4),
        "half_life_days": round(half_life, 1) if half_life != float('inf') else None,
        "ar1_coefficient": round(phi, 4),
        "signal": signal,
        "lookback": lookback,
    }


# ════════════════════════════════════════════════════════════════
# 7. Technical Indicators (standalone, no external deps)
# ════════════════════════════════════════════════════════════════

def compute_indicators(
    prices: list[float],
    volumes: Optional[list[float]] = None,
) -> dict:
    """Compute common technical indicators from price series.

    Returns: SMA, EMA, RSI, MACD, Bollinger Bands, ATR-proxy, VWAP.
    """
    if len(prices) < 26:
        return {"error": "Need at least 26 prices for indicators"}

    arr = np.array(prices, dtype=np.float64)

    # SMA
    sma_10 = float(np.mean(arr[-10:]))
    sma_20 = float(np.mean(arr[-20:]))
    sma_50 = float(np.mean(arr[-50:])) if len(arr) >= 50 else None
    sma_200 = float(np.mean(arr[-200:])) if len(arr) >= 200 else None

    # EMA
    def _ema(data, span):
        alpha = 2.0 / (span + 1)
        ema = [data[0]]
        for price in data[1:]:
            ema.append(alpha * price + (1 - alpha) * ema[-1])
        return ema

    ema_12 = _ema(prices, 12)
    ema_26 = _ema(prices, 26)

    # MACD
    macd_line = [a - b for a, b in zip(ema_12[-len(ema_26):], ema_26)]
    macd_signal = _ema(macd_line, 9) if len(macd_line) >= 9 else macd_line
    macd_hist = macd_line[-1] - macd_signal[-1] if macd_signal else 0.0

    # RSI (14-period, Wilder's smoothing)
    deltas = np.diff(arr)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    # Seed with SMA of first 14, then Wilder smooth the rest
    avg_gain = float(np.mean(gains[:14])) if len(gains) >= 14 else float(np.mean(gains))
    avg_loss = float(np.mean(losses[:14])) if len(losses) >= 14 else float(np.mean(losses))
    for i in range(14, len(gains)):
        avg_gain = (avg_gain * 13 + gains[i]) / 14
        avg_loss = (avg_loss * 13 + losses[i]) / 14
    avg_loss = max(avg_loss, 0.001)
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    # Bollinger Bands (20-period, 2 std)
    bb_period = arr[-20:]
    bb_mid = float(np.mean(bb_period))
    bb_std = float(np.std(bb_period, ddof=1))
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std
    bb_pct = (prices[-1] - bb_lower) / (bb_upper - bb_lower) if (bb_upper - bb_lower) > 0 else 0.5

    # Trend determination
    current = prices[-1]
    trend_signals = []
    if sma_50 and current > sma_50:
        trend_signals.append("above_sma50")
    if sma_200 and current > sma_200:
        trend_signals.append("above_sma200")
    if sma_50 and sma_200 and sma_50 > sma_200:
        trend_signals.append("golden_cross")
    elif sma_50 and sma_200 and sma_50 < sma_200:
        trend_signals.append("death_cross")

    if rsi > 70:
        trend_signals.append("overbought")
    elif rsi < 30:
        trend_signals.append("oversold")

    bullish = sum(1 for s in trend_signals if s in ("above_sma50", "above_sma200", "golden_cross", "oversold"))
    bearish = sum(1 for s in trend_signals if s in ("death_cross", "overbought"))
    if bullish > bearish:
        trend = "bullish"
    elif bearish > bullish:
        trend = "bearish"
    else:
        trend = "neutral"

    return {
        "current_price": round(current, 2),
        "sma_10": round(sma_10, 2),
        "sma_20": round(sma_20, 2),
        "sma_50": round(sma_50, 2) if sma_50 else None,
        "sma_200": round(sma_200, 2) if sma_200 else None,
        "ema_12": round(ema_12[-1], 2),
        "ema_26": round(ema_26[-1], 2),
        "macd": round(macd_line[-1], 4),
        "macd_signal": round(macd_signal[-1], 4),
        "macd_histogram": round(macd_hist, 4),
        "rsi_14": round(float(rsi), 2),
        "bollinger_upper": round(bb_upper, 2),
        "bollinger_mid": round(bb_mid, 2),
        "bollinger_lower": round(bb_lower, 2),
        "bollinger_pct": round(bb_pct, 4),
        "trend_signals": trend_signals,
        "trend": trend,
    }


# ════════════════════════════════════════════════════════════════
# 8. Risk Metrics (Sharpe, Sortino, Max Drawdown, VaR)
# ════════════════════════════════════════════════════════════════

def risk_metrics(
    returns: list[float],
    risk_free_rate: float = 0.02,
) -> dict:
    """Compute portfolio risk metrics from return series."""
    if len(returns) < 5:
        return {"error": "Need at least 5 returns"}

    ret = np.array(returns, dtype=np.float64)
    mean_ret = float(np.mean(ret))
    std_ret = float(np.std(ret, ddof=1))
    annual_ret = mean_ret * 252
    annual_vol = std_ret * math.sqrt(252)

    # Sharpe
    sharpe = (annual_ret - risk_free_rate) / annual_vol if annual_vol > 0 else 0.0

    # Sortino (downside deviation: sqrt of mean of squared negative excess returns)
    downside_diff = np.minimum(ret - risk_free_rate / 252, 0)
    downside_std = float(np.sqrt(np.mean(downside_diff ** 2))) * math.sqrt(252)
    sortino = (annual_ret - risk_free_rate) / downside_std if downside_std > 0 else 0.0

    # Max Drawdown
    cum_returns = np.cumprod(1 + ret)
    rolling_max = np.maximum.accumulate(cum_returns)
    drawdowns = (cum_returns - rolling_max) / rolling_max
    max_dd = float(np.min(drawdowns))

    # VaR (95% and 99%)
    var_95 = float(np.percentile(ret, 5))
    var_99 = float(np.percentile(ret, 1))

    # CVaR (Expected Shortfall)
    cvar_95 = float(np.mean(ret[ret <= var_95])) if len(ret[ret <= var_95]) > 0 else var_95

    return {
        "annual_return": round(annual_ret, 4),
        "annual_volatility": round(annual_vol, 4),
        "sharpe_ratio": round(sharpe, 3),
        "sortino_ratio": round(sortino, 3),
        "max_drawdown": round(max_dd, 4),
        "var_95": round(var_95, 4),
        "var_99": round(var_99, 4),
        "cvar_95": round(cvar_95, 4),
        "win_rate": round(float(np.mean(ret > 0)), 4),
        "avg_win": round(float(np.mean(ret[ret > 0])), 4) if len(ret[ret > 0]) > 0 else 0.0,
        "avg_loss": round(float(np.mean(ret[ret < 0])), 4) if len(ret[ret < 0]) > 0 else 0.0,
        "profit_factor": round(
            float(np.sum(ret[ret > 0]) / abs(np.sum(ret[ret < 0]))) if np.sum(ret[ret < 0]) != 0 else float('inf'),
            3,
        ),
        "total_trades": len(returns),
    }
