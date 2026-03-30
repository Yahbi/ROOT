---
name: Sentiment Analysis
description: NLP-based market sentiment extraction from news, social media, and filings
version: "1.0.0"
author: ROOT
tags: [research, sentiment, NLP, alternative-data]
platforms: [all]
---

# Market Sentiment Analysis

Extract actionable trading signals from text data using NLP techniques.

## Data Sources

| Source | Signal Type | Latency | Alpha Decay |
|--------|-----------|---------|-------------|
| Twitter/X | Retail sentiment, breaking news | Seconds | Minutes |
| Reddit (WSB, investing) | Retail positioning, meme stocks | Minutes | Hours |
| News headlines | Event-driven catalysts | Seconds | Hours |
| Earnings call transcripts | Management tone, forward guidance | Hours | Days |
| SEC filings (10-K, 8-K) | Risk factors, material changes | Hours | Weeks |
| Analyst reports | Institutional consensus shifts | Hours | Days |

## Sentiment Scoring Pipeline

1. **Collect** — API ingestion (Twitter API, NewsAPI, SEC EDGAR, Reddit API)
2. **Clean** — remove boilerplate, ads, duplicates, non-English text
3. **Classify** — assign sentiment score per document:
   - FinBERT or LLM-based classification (bullish / neutral / bearish)
   - Score range: -1.0 (extreme bearish) to +1.0 (extreme bullish)
4. **Aggregate** — compute ticker-level sentiment as volume-weighted mean
5. **Normalize** — z-score against 30-day rolling baseline for the ticker
6. **Signal** — generate trade signal when z-score exceeds +/- 2.0

## Key Indicators

- **Sentiment momentum**: 3-day vs 14-day average sentiment (crossover = signal)
- **Volume spike**: >3x normal mention volume = event in progress
- **Divergence**: positive sentiment + falling price = potential accumulation
- **Fear/Greed index**: aggregate sentiment across all tracked tickers

## LLM-Enhanced Analysis

- Feed earnings transcripts to LLM with prompt: "Rate management confidence 1-10 and list specific forward commitments"
- Compare current quarter language to prior quarter — detect tone shifts
- Extract named entities and map sentiment to specific business segments
- Flag unusual hedging language in risk factor sections of 10-K filings

## Trading Rules from Sentiment

| Signal | Condition | Action |
|--------|-----------|--------|
| Bullish extreme | z-score > +2.5, volume > 3x | BUY (momentum) |
| Bearish extreme | z-score < -2.5, volume > 3x | Potential contrarian BUY |
| Sentiment reversal | 5-day trend flips sign | Close existing position |
| Divergence | Price down + sentiment up for 3+ days | Accumulate slowly |

## Pitfalls

- Social media is noisy — never trade on single data point
- Bot activity can inflate sentiment artificially
- Sentiment works best as confirmation, not primary signal
- Backtest sentiment signals with 1-day lag to avoid lookahead bias
