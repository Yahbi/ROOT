---
name: Social Media Intelligence
description: Extract trading signals from Reddit, Twitter sentiment, unusual volume detection, and narrative tracking
version: "1.0.0"
author: ROOT
tags: [research, social-media, sentiment, alternative-data, Reddit, Twitter]
platforms: [all]
---

# Social Media Intelligence

Extract actionable trading signals from social media discourse by quantifying sentiment, detecting anomalous activity, and tracking narrative evolution.

## Reddit Sentiment Analysis

- **Key subreddits**: r/wallstreetbets (retail momentum), r/stocks (moderate), r/investing (long-term), r/options (derivatives flow)
- **Mention velocity**: Track ticker mention frequency; 3x spike over 7-day average = anomalous attention
- **Sentiment scoring**: Classify posts as bullish/bearish/neutral using NLP; `net_sentiment = (bull - bear) / total`
- **DD quality**: Distinguish due-diligence posts (>500 words, data-backed) from memes; weight DD 5x in sentiment
- **Award signal**: Heavily awarded DDs on r/wallstreetbets precede retail buying waves by 1-3 days
- **Short squeeze tracking**: Monitor short interest mentions, "diamond hands" frequency, cost-to-borrow discussion

## Twitter/X Signal Extraction

- **FinTwit universe**: Follow top 200 finance accounts by engagement; weight by historical signal accuracy
- **Cashtag volume**: $TICKER mention counts; normalize by market cap to find disproportionate attention
- **Influential account signals**: Track buys/sells announced by accounts with >50K followers and verified track records
- **News velocity**: First mention of material event on Twitter leads traditional media by 5-30 minutes
- **Bot detection**: Filter accounts with <6 months age, <50 followers, posting pattern >20 tickers/day
- **Hashtag clustering**: Coordinated hashtag campaigns (#squeeze, #tothemoon) signal organized retail activity

## Unusual Volume Detection

- **Social volume vs market volume**: When social mention spike precedes trading volume spike, retail is leading
- **Pre-market correlation**: Social media sentiment at 8AM ET correlates 0.3-0.5 with opening direction
- **After-hours narrative**: Track sentiment shift between market close and next day open; gap risk indicator
- **Cross-platform confirmation**: Signal strongest when Reddit + Twitter + StockTwits all spike simultaneously
- **Volume anomaly formula**: `z_social = (mentions_today - MA_30) / StdDev_30`; z > 3 = significant anomaly
- **Lead-lag**: Social media leads price by 1-3 days for small-caps; same-day or lagging for large-caps

## Narrative Tracking and Evolution

### Narrative Lifecycle
1. **Emergence**: New thesis appears on niche forums or single viral post; <100 mentions
2. **Amplification**: Picked up by FinTwit influencers and Reddit frontpage; 100-1000 mentions
3. **Peak attention**: Mainstream media coverage, CNBC mentions; max social volume; price often peaks here
4. **Decay**: Mentions decline, counter-narratives emerge; smart money exiting
5. **Resolution**: Thesis confirmed or refuted; narrative either dies or becomes consensus

### Tradeable Narratives
- **Short squeeze narratives**: Entry at amplification stage; exit at peak attention (sell the news)
- **Macro narratives**: "Recession", "soft landing", "pivot" — track narrative momentum for sector rotation
- **Sector themes**: "AI", "GLP-1", "nuclear" — early narrative detection enables sector positioning weeks early
- **Anti-consensus**: When sentiment is > 90% one direction, contrarian positioning has highest expected value

## Quantitative Social Signals

| Signal | Calculation | Interpretation |
|--------|------------|----------------|
| Social momentum | 3-day MA / 14-day MA of mentions | >2.0 = breakout attention |
| Sentiment divergence | Price up + sentiment down | Exhaustion / distribution |
| Engagement ratio | Comments / posts | >50 = highly debated, volatile |
| Influencer consensus | % of top-100 accounts bullish | >80% = contrarian short signal |
| Cross-platform spread | Days from Reddit to CNBC | Shorter spread = faster alpha decay |

## Data Collection Infrastructure

- **Reddit API**: PRAW library; rate limit 60 requests/min; archive via Pushshift for historical
- **Twitter API**: v2 academic access for full archive; streaming API for real-time; 500K tweets/month on basic
- **StockTwits API**: Free sentiment data; pre-labeled bull/bear; useful but noisy
- **NLP pipeline**: FinBERT for financial sentiment (87% accuracy); VADER for quick baseline; GPT for nuanced analysis
- **Storage**: Time-series database (InfluxDB, TimescaleDB) for mention counts; document store for full text

## Risk Management

- **Manipulation awareness**: Coordinated pump-and-dump campaigns exist; verify fundamental catalysts before trading social signals
- **Sentiment reversals**: Retail sentiment can flip in hours; use tight stops on social-media-driven trades
- **Regulatory risk**: SEC monitors social media for market manipulation; ensure all trading is based on public information
- **Alpha decay**: Social media edges degrade quickly as more quant funds monitor these signals; verify edge persistence quarterly
- **Position sizing**: Social-signal trades max 1% of portfolio; these are short-duration, high-variance bets
- **Confirmation requirement**: Never trade social sentiment alone; require at least one confirming signal (volume, options flow, technical)
