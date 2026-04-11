---
name: Patent Intelligence
description: Patent filing analysis for technology scouting, competitive moat identification, and investment signals
version: "1.0.0"
author: ROOT
tags: [research, patents, technology, competitive-analysis, IP]
platforms: [all]
---

# Patent Intelligence

Extract investment and competitive intelligence from patent filings to identify technology trends, innovation moats, and early-stage disruption signals.

## Patent Filing Analysis

- **Filing vs grant**: Filing date (18 months before publication) provides earlier signal than grant date
- **Provisional applications**: Filed to establish priority; indicates research direction 12-18 months ahead
- **Patent families**: Group related filings across jurisdictions; large families = high-value invention
- **Citation analysis**: Forward citations measure impact; backward citations reveal technology foundations
- **Claim breadth**: Broad independent claims = stronger moat; narrow claims = incremental improvement
- **Continuation filings**: Multiple continuations suggest the company is defending a valuable technology space

## Data Sources and Tools

| Source | Coverage | Key Use |
|--------|----------|---------|
| USPTO PATFT/AppFT | US patents and applications | Full-text search, free |
| Google Patents | Global (100+ offices) | Cross-jurisdiction search, CPC classification |
| Espacenet | EPO worldwide | Patent families, legal status |
| Lens.org | Global, academic links | Citation analysis, scholarly connections |
| PatSnap / Relecura | Commercial analytics | Landscape mapping, valuation models |
| WIPO PATENTSCOPE | PCT international | Early-stage global filings |

## Technology Scouting

- **CPC classification**: Use Cooperative Patent Classification codes to track specific technology areas
- **Filing velocity**: Track quarterly filing counts by company; acceleration = increased R&D investment
- **New entrant detection**: Flag companies filing in CPC codes outside their historical domain
- **Inventor tracking**: Prolific inventors changing employers signals technology transfer between companies
- **Geographic shifts**: Patent filings in new jurisdictions indicate market entry plans
- **Keyword emergence**: Track new technical terms appearing in patent abstracts; early trend indicator

## Competitive Moat Assessment

- **Patent portfolio depth**: `moat_score = num_patents * avg_forward_citations * avg_remaining_life`
- **Claim coverage**: Map claims to product features; identify freedom-to-operate gaps for competitors
- **Blocking patents**: Patents that competitors cannot design around; strongest competitive barrier
- **Trade secret complement**: Companies with few patents but high R&D spend may rely on trade secrets
- **Licensing revenue potential**: Broad patents in growing fields = potential royalty streams
- **Litigation history**: Frequent patent assertion = aggressive IP strategy; check PACER for outcomes

## Investment Signal Extraction

### Bullish Patent Signals
- **Filing surge**: 50%+ YoY increase in filings in a new technology area = major R&D pivot
- **Key hire patents**: Newly acquired inventor with strong citation history files under new employer
- **Broad claims granted**: Examiner allowed broad independent claims = strong defensible position
- **International expansion**: PCT filings entering national phase in major markets (US, EU, CN, JP, KR)

### Bearish Patent Signals
- **Filing decline**: Sustained decrease in patent activity = reduced R&D commitment or strategic retreat
- **Narrow claim amendments**: Examiner forced claim narrowing = weaker IP position than market assumes
- **Patent expiry cliff**: Major revenue-generating patents expiring within 2-3 years without replacements
- **Competitor leapfrog**: Competitor filing volume and citation quality surpassing incumbent

## Quantitative Patent Metrics

- **Patent quality index**: `PQI = (forward_citations / age) * claim_count * family_size`
- **Innovation velocity**: `IV = new_filings_12mo / total_portfolio` — higher = more active R&D
- **Technology diversity**: `TD = 1 - HHI(CPC_codes)` — Herfindahl index of technology concentration
- **Citation latency**: Time from filing to first forward citation; shorter = faster technology adoption
- **Maintenance rate**: Percentage of patents maintained through all fee stages; <70% = portfolio pruning

## Risk Management

- **Patent trolls**: Distinguish operating companies from non-practicing entities in citation analysis
- **Publication lag**: 18-month delay between filing and publication; data is inherently stale
- **Jurisdiction differences**: Patent strength varies by country; US and DE are strongest enforcement venues
- **False positives**: Filing activity does not guarantee commercial success; combine with revenue/product data
- **Sector specificity**: Patent moats strongest in pharma/biotech; weakest in software (fast-moving, broad prior art)
