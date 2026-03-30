---
name: DCF Valuation
description: Discounted cash flow methodology for intrinsic value estimation
version: "1.0.0"
author: ROOT
tags: [financial, valuation, dcf, fundamental]
platforms: [all]
---

# Discounted Cash Flow (DCF) Valuation

Estimate intrinsic value by discounting projected future free cash flows to present value.

## Step-by-Step Process

### 1. Calculate Free Cash Flow (FCF)
```
FCF = Operating Income * (1 - Tax Rate)
    + Depreciation & Amortization
    - Capital Expenditures
    - Change in Net Working Capital
```

### 2. Project FCF (5-10 years)
- Use revenue growth rates: historical trend + analyst consensus + TAM analysis
- Apply operating margin trajectory (expanding, stable, or compressing)
- Model capex as % of revenue (compare to sector median)
- Year 1-3: higher confidence, company-specific drivers
- Year 4-10: revert toward industry averages

### 3. Calculate Discount Rate (WACC)
```
WACC = (E/V * Re) + (D/V * Rd * (1 - Tax))

Re = Risk-Free Rate + Beta * Equity Risk Premium
```
- Risk-free rate: 10-year Treasury yield
- Equity risk premium: 5-6% (Damodaran estimate)
- Beta: 5-year monthly regression vs S&P 500

### 4. Compute Terminal Value
**Gordon Growth Model**: TV = FCF_final * (1 + g) / (WACC - g)
- Terminal growth rate (g): 2-3% (should not exceed GDP growth)
- Verify: terminal value should be 50-75% of total enterprise value

### 5. Sum to Enterprise Value
```
Enterprise Value = Sum(FCF_t / (1+WACC)^t) + TV / (1+WACC)^n
Equity Value = Enterprise Value - Net Debt + Cash
Price Per Share = Equity Value / Diluted Shares Outstanding
```

## Sensitivity Analysis

- Build a matrix varying WACC (+/- 1%) and terminal growth (+/- 0.5%)
- If >60% of matrix scenarios show undervaluation, the stock is attractive
- Margin of safety: require 20-30% discount to fair value before buying

## Common Pitfalls

- Over-optimistic revenue growth beyond year 3
- Terminal value > 80% of total = model is unreliable
- Ignoring stock-based compensation dilution
- Using trailing FCF without cyclical adjustment
- Not stress-testing assumptions against bear case
