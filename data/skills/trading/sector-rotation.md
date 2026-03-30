---
name: Sector Rotation
description: Rotate capital across sectors based on economic cycle positioning
version: "1.0.0"
author: ROOT
tags: [trading, sectors, macro, cycles]
platforms: [all]
---

# Sector Rotation Strategy

Allocate capital to sectors that historically outperform at each phase of the economic cycle.

## Economic Cycle Phases and Sector Mapping

### Early Recovery (GDP accelerating, rates low)
- **Overweight**: Consumer Discretionary, Financials, Real Estate, Industrials
- **Underweight**: Utilities, Consumer Staples, Healthcare
- **Signal**: ISM rising above 50, yield curve steepening, credit spreads narrowing

### Mid-Cycle Expansion (GDP strong, rates rising)
- **Overweight**: Technology, Industrials, Materials, Energy
- **Underweight**: Utilities, Consumer Staples
- **Signal**: Employment strong, corporate earnings accelerating, Fed tightening

### Late Cycle (GDP peaking, inflation rising)
- **Overweight**: Energy, Materials, Healthcare, Consumer Staples
- **Underweight**: Technology, Consumer Discretionary, Real Estate
- **Signal**: Yield curve flattening, wage growth accelerating, PMI plateauing

### Recession (GDP contracting, rates falling)
- **Overweight**: Utilities, Consumer Staples, Healthcare, Treasuries
- **Underweight**: Financials, Industrials, Consumer Discretionary
- **Signal**: Yield curve inverted, ISM below 45, unemployment rising

## Implementation

1. **Identify current phase** using leading indicators (ISM, yield curve, LEI)
2. **Allocate via sector ETFs**: XLK, XLF, XLE, XLV, XLU, XLP, XLY, XLI, XLB, XLRE
3. **Rebalance monthly** — cycle phases last 12-24 months on average
4. **Use relative strength** — compare each sector ETF to SPY on 3-month basis
5. **Confirm with breadth** — sector should have >60% stocks above 50-day MA

## Risk Management

- Max 30% allocation to any single sector
- Always hold 2-3 defensive sectors as portfolio insurance
- Reduce total equity exposure by 20% when cycle transitions to late/recession
- Use 200-day MA on SPY as regime filter — below = reduce risk
