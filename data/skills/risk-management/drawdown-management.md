---
name: Drawdown Management
description: Graduated position reduction and max drawdown limits to protect capital
version: "1.0.0"
author: ROOT
tags: [risk-management, drawdown, capital-preservation, position-reduction]
platforms: [all]
---

# Drawdown Management

Systematic rules to reduce exposure during drawdowns and preserve capital for recovery.

## Graduated Reduction Rules

### Drawdown Tiers
| Drawdown from Peak | Action | Position Size Multiplier |
|-------------------|--------|------------------------|
| 0-5% | Normal trading | 1.0x |
| 5-10% | Reduce new positions | 0.75x |
| 10-15% | Cut position sizes, tighten stops | 0.50x |
| 15-20% | Defensive mode — hedges only | 0.25x |
| > 20% | Circuit breaker — flatten all | 0.0x (cash) |

### Implementation
1. Track high-water mark (HWM) of portfolio equity daily
2. Compute current drawdown: `dd = (HWM - current_equity) / HWM`
3. Apply corresponding multiplier to all new position sizes
4. Review existing positions — close any with negative expected value

## Recovery Protocol

### After Circuit Breaker Triggers
1. **Pause period**: No trading for 5 business days minimum
2. **Post-mortem**: Analyze what caused the drawdown (market, strategy, sizing)
3. **Re-entry plan**: Start at 25% normal size, increase 25% per profitable week
4. **Strategy review**: If drawdown was strategy-specific, paper trade for 2 weeks before re-entry

### Time-Based Recovery Scaling
- Week 1 after pause: 25% position size
- Week 2 (if profitable): 50% position size
- Week 3 (if profitable): 75% position size
- Week 4 (if profitable): 100% position size
- Any losing week resets to previous tier

## Drawdown Psychology

### Behavioral Traps to Avoid
- **Revenge trading**: Increasing size to "make it back" — the #1 account killer
- **Averaging down**: Adding to losers without a pre-defined plan
- **Stop removal**: Moving stops wider during drawdowns to avoid taking losses
- **Strategy switching**: Abandoning a valid strategy during normal variance

### Mental Framework
- A 10% drawdown requires 11% gain to recover — manageable
- A 25% drawdown requires 33% gain — difficult
- A 50% drawdown requires 100% gain — devastating
- Prevention is exponentially more valuable than recovery

## Monitoring Checklist

- [ ] HWM tracked and updated daily
- [ ] Current drawdown calculated before each trading session
- [ ] Position size multiplier applied automatically (not manually)
- [ ] Weekly review of drawdown trajectory (improving or worsening)
- [ ] Monthly comparison of realized drawdowns vs backtested expectations
