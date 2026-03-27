"""
Polymarket Quant Playbook — 6 Hedge Fund Formulas Backtested

Implements and backtests the full quant stack:
1. LMSR Pricing Model — AMM impact analysis
2. Kelly Criterion — Optimal position sizing
3. EV Gap Scanner — Mispricing detector
4. KL-Divergence — Correlation arb scanner
5. Kelly Bankroll Simulation — Full vs Half vs Quarter Kelly
6. Bayesian Update — Dynamic probability adjustment

Simulates 365 days of Polymarket-style prediction markets.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

np.random.seed(42)
random.seed(42)


# ── Formula 1: LMSR Pricing Model ────────────────────────────

def lmsr_price(q: np.ndarray, b: float) -> np.ndarray:
    """LMSR price for each outcome given quantity vector q and liquidity b."""
    exp_q = np.exp(q / b)
    return exp_q / np.sum(exp_q)


def lmsr_cost(q_before: np.ndarray, q_after: np.ndarray, b: float) -> float:
    """Cost of moving from q_before to q_after."""
    return b * (np.log(np.sum(np.exp(q_after / b))) - np.log(np.sum(np.exp(q_before / b))))


def lmsr_impact_analysis():
    """Analyze price impact across different liquidity depths."""
    print("=" * 60)
    print("FORMULA 1: LMSR Price Impact Analysis")
    print("=" * 60)

    results = []
    for b in [25, 50, 100, 200, 500]:
        q = np.array([0.0, 0.0])  # binary market, start at 50/50
        buy_amount = 10
        price_before = lmsr_price(q, b)[0]
        q_after = q.copy()
        q_after[0] += buy_amount
        price_after = lmsr_price(q_after, b)[0]
        cost = lmsr_cost(q, q_after, b)
        impact_pct = (price_after - price_before) / price_before * 100

        results.append({
            "liquidity_b": b,
            "price_before": round(price_before, 4),
            "price_after": round(price_after, 4),
            "impact_pct": round(impact_pct, 2),
            "cost": round(cost, 4),
        })
        print(f"  b={b:>4}: {price_before:.4f} → {price_after:.4f} "
              f"(+{impact_pct:.2f}%) cost=${cost:.4f}")

    # Find arb opportunities: thin pools where impact is exploitable
    print(f"\n  ARB EDGE: b<50 pools show >{results[0]['impact_pct']:.1f}% impact "
          f"on 10-share buy = exploitable mispricing")
    print(f"  RISK: b<25 pools can be whale-manipulated")
    return results


# ── Formula 2: Kelly Criterion ────────────────────────────────

def kelly_fraction(p: float, odds: float) -> float:
    """Optimal Kelly fraction. p=win probability, odds=net payout ratio."""
    f = (p * odds - (1 - p)) / odds
    return max(0.0, f)  # Never bet negative


def kelly_analysis():
    """Kelly criterion analysis for prediction market sizing."""
    print("\n" + "=" * 60)
    print("FORMULA 2: Kelly Criterion Analysis")
    print("=" * 60)

    scenarios = [
        ("Conservative edge (p=0.55, price=0.50)", 0.55, 0.50),
        ("Moderate edge (p=0.60, price=0.50)", 0.60, 0.50),
        ("Strong edge (p=0.25, price=0.21)", 0.25, 0.21),  # Vance example
        ("Small edge (p=0.52, price=0.47)", 0.52, 0.47),  # Iran example
        ("Large edge (p=0.70, price=0.50)", 0.70, 0.50),
    ]

    results = []
    for name, p, price in scenarios:
        odds = (1 / price) - 1
        f_full = kelly_fraction(p, odds)
        f_half = f_full / 2
        f_quarter = f_full / 4
        ev = (p - price) * (1 / price)

        results.append({
            "scenario": name,
            "edge_p": p,
            "market_price": price,
            "ev": round(ev, 4),
            "full_kelly": round(f_full, 4),
            "half_kelly": round(f_half, 4),
            "quarter_kelly": round(f_quarter, 4),
        })
        print(f"  {name}")
        print(f"    EV={ev:.4f} | Full Kelly={f_full:.2%} | "
              f"Half={f_half:.2%} | Quarter={f_quarter:.2%}")

    return results


# ── Formula 3: EV Gap Scanner ─────────────────────────────────

@dataclass(frozen=True)
class Market:
    name: str
    market_price: float
    true_prob: float
    volume: float
    resolution: bool  # actual outcome


def generate_simulated_markets(n: int = 500) -> list[Market]:
    """Generate n simulated prediction markets with realistic parameters."""
    categories = [
        "Politics", "Crypto", "Sports", "Tech", "Econ",
        "Entertainment", "Weather", "Science", "Geopolitics", "Elections"
    ]
    markets = []
    for i in range(n):
        # True probability
        true_p = np.random.beta(2, 2)  # Centered distribution
        # Market price has noise around true prob
        noise = np.random.normal(0, 0.08)
        market_price = np.clip(true_p + noise, 0.02, 0.98)
        # Volume follows power law
        volume = np.random.pareto(1.5) * 10000 + 1000
        # Resolution based on true probability
        resolution = random.random() < true_p

        cat = random.choice(categories)
        markets.append(Market(
            name=f"{cat}_{i:03d}",
            market_price=round(market_price, 4),
            true_prob=round(true_p, 4),
            volume=round(volume, 2),
            resolution=resolution,
        ))
    return markets


def ev_gap_scan(markets: list[Market], fee_rate: float = 0.02) -> list[dict]:
    """Scan markets for +EV opportunities above threshold."""
    print("\n" + "=" * 60)
    print("FORMULA 3: EV Gap Scanner")
    print("=" * 60)

    opportunities = []
    for m in markets:
        ev = (m.true_prob - m.market_price) * (1 / m.market_price)
        ev_after_fees = ev - fee_rate

        if ev_after_fees > 0.05:  # Minimum threshold
            opportunities.append({
                "market": m.name,
                "market_price": m.market_price,
                "model_p": m.true_prob,
                "ev": round(ev, 4),
                "ev_after_fees": round(ev_after_fees, 4),
                "volume": m.volume,
                "resolution": m.resolution,
            })

    opportunities.sort(key=lambda x: x["ev_after_fees"], reverse=True)

    print(f"  Scanned {len(markets)} markets")
    print(f"  Found {len(opportunities)} opportunities with EV > 0.05 after fees")
    print(f"\n  Top 10 opportunities:")
    for opp in opportunities[:10]:
        win = "WIN" if opp["resolution"] else "LOSS"
        print(f"    {opp['market']:>20}: price={opp['market_price']:.2f} "
              f"model={opp['model_p']:.2f} EV={opp['ev_after_fees']:.4f} "
              f"vol=${opp['volume']:,.0f} → {win}")

    return opportunities


# ── Formula 4: KL-Divergence ─────────────────────────────────

def kl_divergence(p: np.ndarray, q: np.ndarray) -> float:
    """KL divergence D_KL(P||Q). Handles zeros with small epsilon."""
    eps = 1e-10
    p = np.clip(p, eps, 1 - eps)
    q = np.clip(q, eps, 1 - eps)
    return float(np.sum(p * np.log(p / q)))


def kl_correlation_scan(markets: list[Market]) -> list[dict]:
    """Scan correlated market pairs for arbitrage via KL divergence."""
    print("\n" + "=" * 60)
    print("FORMULA 4: KL-Divergence Correlation Scanner")
    print("=" * 60)

    # Group by category
    from collections import defaultdict
    cats: dict[str, list[Market]] = defaultdict(list)
    for m in markets:
        cat = m.name.split("_")[0]
        cats[cat].append(m)

    arb_opportunities = []
    for cat, cat_markets in cats.items():
        if len(cat_markets) < 2:
            continue
        for i in range(len(cat_markets)):
            for j in range(i + 1, min(i + 5, len(cat_markets))):
                m1, m2 = cat_markets[i], cat_markets[j]
                p = np.array([m1.market_price, 1 - m1.market_price])
                q = np.array([m2.market_price, 1 - m2.market_price])
                kl = kl_divergence(p, q)

                if kl > 0.20:  # Actionable threshold
                    arb_opportunities.append({
                        "market_1": m1.name,
                        "market_2": m2.name,
                        "price_1": m1.market_price,
                        "price_2": m2.market_price,
                        "kl_divergence": round(kl, 4),
                        "category": cat,
                    })

    arb_opportunities.sort(key=lambda x: x["kl_divergence"], reverse=True)

    print(f"  Scanned {sum(len(v) for v in cats.values())} markets in {len(cats)} categories")
    print(f"  Found {len(arb_opportunities)} pairs with KL > 0.20")
    for opp in arb_opportunities[:5]:
        print(f"    {opp['market_1']} vs {opp['market_2']}: "
              f"KL={opp['kl_divergence']:.4f} ({opp['price_1']:.2f} vs {opp['price_2']:.2f})")

    return arb_opportunities


# ── Formula 5: Kelly Bankroll Simulation ──────────────────────

def simulate_kelly_bankroll(
    p: float,
    odds: float,
    n_bets: int,
    n_sims: int,
    fractions: list[float],
) -> dict[str, dict]:
    """Monte Carlo simulation of Kelly variants."""
    print("\n" + "=" * 60)
    print("FORMULA 5: Kelly Bankroll Simulation (Monte Carlo)")
    print("=" * 60)

    results = {}
    for frac_mult, label in zip(fractions, ["Full Kelly", "Half Kelly", "Quarter Kelly"]):
        f = kelly_fraction(p, odds) * frac_mult

        final_bankrolls = []
        max_drawdowns = []
        ruin_count = 0

        for _ in range(n_sims):
            bankroll = 1.0
            peak = 1.0
            max_dd = 0.0
            ruined = False

            for _ in range(n_bets):
                if bankroll < 0.01:
                    ruined = True
                    break
                bet_size = f * bankroll
                if random.random() < p:
                    bankroll += bet_size * odds
                else:
                    bankroll -= bet_size
                peak = max(peak, bankroll)
                dd = (peak - bankroll) / peak
                max_dd = max(max_dd, dd)

            final_bankrolls.append(bankroll)
            max_drawdowns.append(max_dd)
            if ruined:
                ruin_count += 1

        final_arr = np.array(final_bankrolls)
        dd_arr = np.array(max_drawdowns)

        results[label] = {
            "fraction": round(f, 4),
            "median_final": round(float(np.median(final_arr)), 4),
            "mean_final": round(float(np.mean(final_arr)), 4),
            "p90_final": round(float(np.percentile(final_arr, 90)), 4),
            "p10_final": round(float(np.percentile(final_arr, 10)), 4),
            "avg_max_drawdown": round(float(np.mean(dd_arr)), 4),
            "p95_max_drawdown": round(float(np.percentile(dd_arr, 95)), 4),
            "ruin_rate": round(ruin_count / n_sims, 4),
        }

        print(f"\n  {label} (f={f:.4f}):")
        print(f"    Median final: {results[label]['median_final']:.2f}x")
        print(f"    Mean final:   {results[label]['mean_final']:.2f}x")
        print(f"    90th pctl:    {results[label]['p90_final']:.2f}x")
        print(f"    10th pctl:    {results[label]['p10_final']:.2f}x")
        print(f"    Avg max DD:   {results[label]['avg_max_drawdown']:.1%}")
        print(f"    95th pctl DD: {results[label]['p95_max_drawdown']:.1%}")
        print(f"    Ruin rate:    {results[label]['ruin_rate']:.1%}")

    return results


# ── Formula 6: Bayesian Update ────────────────────────────────

def bayesian_update(prior: float, likelihood_if_true: float, likelihood_if_false: float) -> float:
    """Single Bayesian update. Returns posterior probability."""
    p_evidence = likelihood_if_true * prior + likelihood_if_false * (1 - prior)
    posterior = (likelihood_if_true * prior) / p_evidence
    return posterior


def bayesian_simulation():
    """Simulate Bayesian updates on a prediction market with evidence stream."""
    print("\n" + "=" * 60)
    print("FORMULA 6: Bayesian Update Simulation")
    print("=" * 60)

    # Simulate an event (e.g., election or crypto event)
    true_outcome = True  # Unknown to us, drives evidence generation
    prior = 0.50

    # Evidence stream: tweets, polls, news
    evidence_types = [
        ("Tweet from insider", 0.75, 0.40),
        ("Poll results", 0.80, 0.35),
        ("News article", 0.65, 0.45),
        ("Expert opinion", 0.70, 0.40),
        ("Contrary report", 0.30, 0.70),
        ("Strong poll", 0.85, 0.25),
        ("Social sentiment spike", 0.72, 0.38),
        ("Leaked memo", 0.90, 0.15),
        ("Market correction", 0.55, 0.50),
        ("Final poll", 0.82, 0.30),
    ]

    current_p = prior
    trajectory = [(0, current_p, "Prior")]

    print(f"  Starting prior: {current_p:.2%}")
    for i, (evidence, lt, lf) in enumerate(evidence_types, 1):
        # Generate evidence based on true outcome
        if true_outcome:
            observed_strength = lt + np.random.normal(0, 0.05)
        else:
            observed_strength = lf + np.random.normal(0, 0.05)
        observed_strength = np.clip(observed_strength, 0.01, 0.99)

        current_p = bayesian_update(current_p, observed_strength,
                                     1 - observed_strength)
        trajectory.append((i, round(current_p, 4), evidence))
        print(f"  Step {i:>2}: {evidence:>25} → P={current_p:.2%}")

    # Calculate trading edge
    market_price = prior  # Market starts at prior
    for step, p, ev in trajectory:
        if step > 0:
            ev_gap = (p - market_price) * (1 / market_price)
            if abs(ev_gap) > 0.05:
                direction = "BUY YES" if ev_gap > 0 else "BUY NO"
                odds = (1 / market_price) - 1
                k = kelly_fraction(p, odds) if ev_gap > 0 else 0
                print(f"    → SIGNAL at step {step}: {direction}, "
                      f"EV={ev_gap:.4f}, Kelly={k:.2%}")
            # Market slowly adjusts (with lag)
            market_price = market_price * 0.85 + p * 0.15

    print(f"\n  Final posterior: {current_p:.2%}")
    print(f"  True outcome: {'YES' if true_outcome else 'NO'}")
    print(f"  Model accuracy: {'CORRECT' if (current_p > 0.5) == true_outcome else 'WRONG'}")

    return trajectory


# ── Full Backtest: Combined Quant Stack ───────────────────────

def full_backtest(starting_capital: float = 500.0, n_days: int = 90):
    """Full backtest of the combined quant stack over simulated markets."""
    print("\n" + "=" * 60)
    print("FULL BACKTEST: Combined Quant Stack")
    print(f"Starting Capital: ${starting_capital:.0f} | Days: {n_days}")
    print("=" * 60)

    bankroll = starting_capital
    peak = bankroll
    max_dd = 0.0
    trades = []
    daily_equity = [bankroll]

    total_bets = 0
    wins = 0
    losses = 0

    for day in range(1, n_days + 1):
        # Generate 3-8 markets per day
        n_markets = random.randint(3, 8)
        day_markets = generate_simulated_markets(n_markets)

        for market in day_markets:
            # Step 1: EV Gap scan
            ev = (market.true_prob - market.market_price) * (1 / market.market_price)
            fee = 0.02
            ev_after_fees = ev - fee

            if ev_after_fees < 0.05:
                continue  # Skip low-EV

            # Step 2: Kelly sizing (half Kelly for safety)
            odds = (1 / market.market_price) - 1
            f_full = kelly_fraction(market.true_prob, odds)
            f_half = f_full / 2

            bet_size = bankroll * min(f_half, 0.15)  # Cap at 15%
            if bet_size < 1:
                continue

            # Step 3: Bayesian update (simulate 1-3 evidence pieces)
            adjusted_p = market.true_prob
            n_evidence = random.randint(1, 3)
            for _ in range(n_evidence):
                strength = 0.6 + random.random() * 0.3
                noise = random.gauss(0, 0.05)
                if market.resolution:
                    obs = min(0.95, max(0.05, strength + noise))
                else:
                    obs = min(0.95, max(0.05, (1 - strength) + noise))
                adjusted_p = bayesian_update(adjusted_p, obs, 1 - obs)

            # Re-check EV with updated probability
            ev_updated = (adjusted_p - market.market_price) * (1 / market.market_price)
            if ev_updated < 0.03:
                continue

            # Execute trade
            total_bets += 1
            payout = bet_size * odds

            if market.resolution:  # YES wins
                bankroll += payout - (bet_size * fee)
                wins += 1
                result = "WIN"
            else:
                bankroll -= bet_size + (bet_size * fee)
                losses += 1
                result = "LOSS"

            trades.append({
                "day": day,
                "market": market.name,
                "bet_size": round(bet_size, 2),
                "odds": round(odds, 2),
                "ev": round(ev_after_fees, 4),
                "result": result,
                "bankroll": round(bankroll, 2),
            })

            # Drawdown tracking
            peak = max(peak, bankroll)
            dd = (peak - bankroll) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)

            # Ruin check
            if bankroll < 5:
                print(f"  RUIN on day {day} after {total_bets} bets")
                break

        daily_equity.append(round(bankroll, 2))
        if bankroll < 5:
            break

    # Results
    total_return = (bankroll - starting_capital) / starting_capital
    win_rate = wins / total_bets if total_bets > 0 else 0
    avg_win = np.mean([t["bet_size"] * t["odds"] for t in trades if t["result"] == "WIN"]) if wins > 0 else 0
    avg_loss = np.mean([t["bet_size"] for t in trades if t["result"] == "LOSS"]) if losses > 0 else 0

    # Sharpe approximation
    daily_returns = []
    for i in range(1, len(daily_equity)):
        if daily_equity[i - 1] > 0:
            daily_returns.append((daily_equity[i] - daily_equity[i - 1]) / daily_equity[i - 1])
    sharpe = (np.mean(daily_returns) / np.std(daily_returns) * np.sqrt(252)
              if daily_returns and np.std(daily_returns) > 0 else 0)

    print(f"\n  RESULTS:")
    print(f"  {'─' * 40}")
    print(f"  Starting capital:  ${starting_capital:.0f}")
    print(f"  Final bankroll:    ${bankroll:.2f}")
    print(f"  Total return:      {total_return:.1%}")
    print(f"  Total bets:        {total_bets}")
    print(f"  Win rate:          {win_rate:.1%} ({wins}W / {losses}L)")
    print(f"  Avg win:           ${avg_win:.2f}")
    print(f"  Avg loss:          ${avg_loss:.2f}")
    print(f"  Profit factor:     {(avg_win * wins) / (avg_loss * losses):.2f}" if losses > 0 and avg_loss > 0 else "  Profit factor:     N/A")
    print(f"  Max drawdown:      {max_dd:.1%}")
    print(f"  Sharpe ratio:      {sharpe:.2f}")
    print(f"  Days traded:       {min(day, n_days)}")

    # Monthly breakdown
    print(f"\n  Monthly P&L:")
    month_size = 30
    for m in range(0, n_days, month_size):
        start_eq = daily_equity[m] if m < len(daily_equity) else daily_equity[-1]
        end_idx = min(m + month_size, len(daily_equity) - 1)
        end_eq = daily_equity[end_idx]
        month_ret = (end_eq - start_eq) / start_eq if start_eq > 0 else 0
        print(f"    Month {m // month_size + 1}: ${start_eq:.0f} → ${end_eq:.0f} ({month_ret:+.1%})")

    return {
        "starting_capital": starting_capital,
        "final_bankroll": round(bankroll, 2),
        "total_return": round(total_return, 4),
        "total_bets": total_bets,
        "win_rate": round(win_rate, 4),
        "max_drawdown": round(max_dd, 4),
        "sharpe": round(sharpe, 2),
        "daily_equity": daily_equity,
        "trades": trades,
    }


# ── Main ──────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  POLYMARKET QUANT PLAYBOOK — Full Backtest")
    print("  6 Hedge Fund Formulas Applied to Prediction Markets")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    # Run all formulas
    lmsr_results = lmsr_impact_analysis()
    kelly_results = kelly_analysis()

    # Generate simulated markets
    markets = generate_simulated_markets(500)
    ev_opps = ev_gap_scan(markets)
    kl_opps = kl_correlation_scan(markets)

    # Kelly Monte Carlo
    kelly_sim = simulate_kelly_bankroll(
        p=0.55, odds=1.0,  # 55% edge on even-money bets
        n_bets=100, n_sims=10000,
        fractions=[1.0, 0.5, 0.25],
    )

    # Bayesian update simulation
    bayes_trajectory = bayesian_simulation()

    # Full combined backtest
    backtest_results = full_backtest(starting_capital=500, n_days=90)

    # Save results
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "lmsr_impact": lmsr_results,
        "kelly_scenarios": kelly_results,
        "ev_opportunities_found": len(ev_opps),
        "kl_arb_pairs_found": len(kl_opps),
        "kelly_simulation": kelly_sim,
        "backtest": {
            k: v for k, v in backtest_results.items()
            if k not in ("daily_equity", "trades")
        },
    }

    report_path = Path("data/learning_reports/polymarket_backtest.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"\n  Report saved: {report_path}")

    print("\n" + "=" * 60)
    print("  VERDICT")
    print("=" * 60)
    print(f"  The combined stack (EV scan → Kelly sizing → Bayesian updates)")
    sr = backtest_results['sharpe']
    ret = backtest_results['total_return']
    if sr > 1.5 and ret > 0:
        print(f"  PASSED: Sharpe {sr:.2f} > 1.5, Return {ret:.1%}")
        print(f"  RECOMMENDATION: Scale from $500, deploy with fractional Kelly")
    elif sr > 1.0 and ret > 0:
        print(f"  MARGINAL: Sharpe {sr:.2f}, Return {ret:.1%}")
        print(f"  RECOMMENDATION: Continue paper trading, refine edge estimation")
    else:
        print(f"  FAILED: Sharpe {sr:.2f}, Return {ret:.1%}")
        print(f"  RECOMMENDATION: Edge insufficient, improve model accuracy")


if __name__ == "__main__":
    main()
