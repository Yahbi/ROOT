---
name: Factor Investing
description: Construct portfolios using systematic exposure to rewarded risk factors
version: "1.0.0"
author: ROOT
tags: [trading, factors, quantitative, portfolio, smart-beta]
platforms: [all]
---

# Factor Investing

Harvest systematic risk premia by building portfolios with targeted exposures to empirically validated return factors.

## Fama-French Five-Factor Model

- **Market (MKT)**: `R_i - R_f = alpha + beta_mkt * (R_m - R_f) + ...`; equity risk premium (~5-7% annualized)
- **Size (SMB)**: Small minus Big; small-cap premium (~2% historically, weaker post-publication)
- **Value (HML)**: High minus Low book-to-market; value premium (~3-4% historically)
- **Profitability (RMW)**: Robust minus Weak; high-profitability firms outperform (~3%)
- **Investment (CMA)**: Conservative minus Aggressive; low-investment firms outperform (~2%)
- **Alpha**: Intercept after controlling for all 5 factors; true manager skill

## Additional Empirically Validated Factors

- **Momentum (MOM)**: Past 12-1 month winners outperform losers by ~6-8% annually; crashes during reversals
- **Quality**: Composite of ROE stability, low leverage, earnings consistency; defensive in drawdowns
- **Low Volatility**: Minimum variance portfolios outperform on risk-adjusted basis (volatility anomaly)
- **Carry**: High-yield assets outperform low-yield; applies across equities, bonds, FX, commodities
- **Liquidity**: Illiquid assets earn a premium; Amihud illiquidity ratio as primary measure

## Factor Construction Methodology

1. **Universe**: Top 1000 stocks by market cap (avoid micro-cap noise)
2. **Signal**: Rank stocks by factor metric (e.g., B/P for value, 12-1 month return for momentum)
3. **Portfolio**: Long top quintile, short bottom quintile; market-cap or equal-weight within legs
4. **Rebalance**: Monthly for momentum, quarterly for value/quality/size
5. **Neutralization**: Sector-neutralize to isolate pure factor exposure from sector bets
6. **Winsorize**: Cap extreme signal values at 3 sigma to reduce outlier influence

## Factor Timing and Rotation

- **Valuation spread**: When value spread (cheap vs expensive) is wide, overweight value
- **Momentum crash indicator**: When momentum drawdown exceeds 20%, reduce exposure or hedge
- **Economic cycle**: Early cycle favors value + small-cap; late cycle favors quality + low-vol
- **Factor crowding**: Monitor short interest concentration; crowded factors reverse sharply
- **Correlation regime**: When factor correlations spike, diversification benefit drops — reduce allocation

## Multi-Factor Portfolio Construction

- **Intersection approach**: Select stocks that rank well on multiple factors simultaneously
- **Mixing approach**: Blend single-factor portfolios with target weights
- **Intersection preferred**: Fewer turnover, more concentrated exposures, better transaction cost profile
- **Target factor loadings**: beta_value = 0.3, beta_momentum = 0.3, beta_quality = 0.2, beta_size = 0.2
- **Tracking error budget**: 3-5% vs benchmark for institutional; up to 10% for absolute return

## Risk Management

- Monitor factor exposure drift monthly; rebalance when any factor loading deviates > 0.1 from target
- Momentum is the most dangerous factor — has fat left tail; always pair with value or quality
- Factor returns are cyclical: underperformance of 2-3 years is normal; do not abandon prematurely
- Maximum single-stock weight: 2% to prevent idiosyncratic risk dominating factor exposure
- Transaction cost budget: factor alpha must exceed 3x estimated round-trip costs after turnover
