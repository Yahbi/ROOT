---
name: Academic Paper Analysis
description: Systematic methodology for reading research papers, extracting tradeable alpha, and replication checklists
version: "1.0.0"
author: ROOT
tags: [research, academic, papers, alpha, replication]
platforms: [all]
---

# Academic Paper Analysis

Systematically evaluate academic finance research to extract implementable trading strategies and avoid common pitfalls in paper-to-production translation.

## Reading Methodology (Three-Pass Approach)

### Pass 1: Triage (5 minutes)
- Read title, abstract, introduction, and conclusion only
- Identify: What anomaly? What asset class? What time period? What Sharpe ratio?
- Decision: Does the claimed alpha exceed realistic transaction costs? If not, discard
- Check publication venue: top journals (JF, JFE, RFS, JFQA) > working papers > predatory journals

### Pass 2: Critical Read (30 minutes)
- Focus on data section: universe, time period, frequency, source
- Study methodology: regression approach, factor model, portfolio sorts
- Examine Tables 1-3: summary statistics, main results, robustness
- Identify: Sample period, look-ahead bias, survivorship bias, data snooping
- Note: What benchmark? What risk adjustment? Are t-statistics > 3.0 (Harvey et al. threshold)?

### Pass 3: Replication Assessment (60 minutes)
- Map every variable to available data sources (CRSP, Compustat, Bloomberg, free alternatives)
- Identify implementation details: rebalance frequency, holding period, trading costs
- Estimate realistic slippage and market impact at strategy scale
- Calculate: Post-cost Sharpe, capacity constraints, correlation with existing strategies

## Extracting Alpha Signals

- **Signal clarity**: Can you rank stocks/assets by a single numeric score? If not, signal is too vague
- **Economic rationale**: Does the anomaly have a plausible risk-based or behavioral explanation?
- **Monotonicity**: Do returns increase monotonically across quintiles? Non-monotonic = fragile signal
- **Decay rate**: How quickly does the signal lose predictive power? Fast decay = high turnover = high cost
- **Interaction effects**: Does the alpha survive controlling for Fama-French 5 factors + momentum?
- **Out-of-sample**: Does the paper include out-of-sample tests? If only in-sample, discount heavily

## Common Pitfalls and Red Flags

- **p-hacking**: Hundreds of tested variables, only significant ones reported; require t > 3.0 (not 2.0)
- **Look-ahead bias**: Uses data unavailable at trade time (e.g., annual data available "at year-end" vs actual filing lag)
- **Survivorship bias**: Backtest only on currently listed stocks; ignores delistings (overstates returns by 1-2%/yr)
- **Data snooping**: Multiple hypothesis testing without correction; Bonferroni or BHY adjustment needed
- **Small-cap concentration**: Alpha only in smallest decile (illiquid, untradeable); check value-weighted returns
- **Short leg dominance**: Strategy profitable only because short leg works; shorting is expensive and constrained
- **Pre-2000 data**: Many anomalies disappear post-publication; verify persistence in 2010-2024 data

## Replication Checklist

1. **Data sourced**: Exact dataset identified and accessible; alternative free sources mapped
2. **Signal constructed**: Variable definitions match paper exactly; point-in-time data used
3. **Universe defined**: Same market cap filters, liquidity screens, exclusions (financials, utilities)
4. **Portfolio formed**: Same sort methodology (quintile, decile); same rebalance frequency
5. **Returns computed**: Value-weighted vs equal-weighted matches paper; excess returns vs raw
6. **Risk adjustment**: Same factor model applied; alpha and t-stats comparable to paper
7. **Transaction costs**: Realistic round-trip costs applied (10-50bps depending on liquidity)
8. **Out-of-sample**: Test on data period not in paper; require Sharpe > 0.5 after costs
9. **Capacity test**: Can the strategy absorb $10M+ without moving prices? Check ADV of holdings
10. **Correlation check**: Is this genuinely new alpha or repackaged momentum/value/quality?

## Key Data Sources for Replication

| Source | Coverage | Cost | Alternative |
|--------|----------|------|-------------|
| CRSP | US equity prices/returns | $$$$ | Yahoo Finance + manual delisting |
| Compustat | US fundamentals | $$$$ | SEC EDGAR + XBRL parsing |
| Bloomberg | Global multi-asset | $$$$ | EOD Historical Data |
| FRED | Macro/rates | Free | Direct from Fed |
| Kenneth French Data Library | Factor returns | Free | Definitive source |
| EDGAR Full-Text Search | SEC filings | Free | N/A |

## Risk Management

- Never allocate > 5% of portfolio to a single paper-derived strategy until 12 months live track record
- Paper Sharpe of 2.0 typically becomes 0.5-1.0 in practice; haircut claimed results by 50-70%
- Correlate new strategy P&L with existing portfolio; reject if correlation > 0.5 (redundant alpha)
- Set a 6-month review: if live results < 50% of backtest, investigate or abandon
