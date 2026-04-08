---
name: Regulatory Tracking
description: Monitor SEC filings, FDA approvals, antitrust actions, and policy changes for investment impact assessment
version: "1.0.0"
author: ROOT
tags: [research, regulatory, SEC, FDA, policy, compliance]
platforms: [all]
---

# Regulatory Tracking

Systematically monitor regulatory actions and policy changes to identify investment opportunities and risks before they are priced in.

## SEC Filings Intelligence

### Critical Filing Types
- **8-K (Current Report)**: Material events — M&A, executive changes, delisting, bankruptcy; most time-sensitive
- **13F (Institutional Holdings)**: Quarterly hedge fund positions; 45-day filing lag; tracks smart money
- **13D/13G (Beneficial Ownership)**: >5% ownership stake; 13D = activist intent; 13G = passive
- **SC 13D Amendments**: Changes to activist positions; increasing stake = escalation signal
- **Form 4 (Insider Transactions)**: Officer/director buys/sells; cluster buying by multiple insiders is strongly bullish
- **DEF 14A (Proxy)**: Executive compensation, shareholder proposals, governance changes
- **S-1/F-1 (Registration)**: IPO filings; watch for pricing amendments and roadshow timing

### Filing Analysis Framework
1. **Speed**: Process 8-K filings within minutes; first-mover advantage on material events
2. **Context**: Compare current filing to historical filings by same issuer (XBRL delta analysis)
3. **Cluster detection**: Multiple related companies filing similar events = systemic trend
4. **Insider scoring**: `signal_strength = num_insiders_buying * avg_purchase_size / market_cap`
5. **EDGAR full-text search**: Monitor keyword alerts (restructuring, investigation, restatement, going concern)

## FDA Approval Tracking

- **PDUFA dates**: Prescription Drug User Fee Act target dates; binary events with 30-50% stock moves
- **Advisory committee votes**: Non-binding but predictive; favorable vote = 85%+ chance of approval
- **Complete Response Letter (CRL)**: Rejection with resubmission path; stock drops 30-70% on average
- **Accelerated approval**: Breakthrough therapy, fast track, priority review designations signal urgency
- **Pipeline tracking**: Map Phase 1/2/3 trials to PDUFA dates; calculate probability-adjusted NPV
- **Biosimilar approvals**: Impact originator revenue; track ANDA and BLA filings for competitive threats

## Antitrust and Competition

- **Merger review**: HSR filing → second request → DOJ/FTC challenge → settlement or block
- **Second request**: Issued in ~3% of deals; signals regulatory concern; extends review by 3-6 months
- **Consent decree**: Behavioral or structural remedies; usually means deal closes with conditions
- **Block signals**: Pre-merger market concentration (HHI > 2500 + delta > 200 = likely challenge)
- **Section 5 FTC actions**: Unfair competition charges; can signal broader industry scrutiny
- **International coordination**: EU DG Competition, UK CMA often more aggressive than US; monitor parallel reviews

## Policy Impact Assessment Framework

| Policy Area | Primary Affected Sectors | Signal Source |
|-------------|------------------------|---------------|
| Interest rates | Financials, REITs, Utilities | Fed statements, dot plot, futures |
| Trade/tariffs | Industrials, Tech, Agriculture | Executive orders, USTR filings |
| Healthcare reform | Pharma, Hospitals, Insurers | Congressional bills, CMS rulings |
| Energy policy | Oil, Gas, Renewables, Utilities | EPA regulations, DOE directives |
| Tech regulation | FAANG, Social media, Fintech | Congressional hearings, EU DSA/DMA |
| Banking regulation | Banks, Fintech, Asset managers | Basel rules, Dodd-Frank amendments |

## Monitoring Infrastructure

- **EDGAR RSS feeds**: Real-time filing alerts via SEC RSS; filter by form type and CIK
- **Federal Register**: Daily publication of proposed and final rules; 60-90 day comment periods
- **Congress.gov**: Bill tracking from introduction through committee to floor vote
- **Regulatory.gov**: Comment periods on proposed rules; high comment volume = contentious issue
- **Court dockets**: PACER for federal cases; key antitrust and IP litigation tracking
- **Automated alerts**: Set keyword triggers for company names, industry terms, regulatory actions

## Risk Management

- **Binary event sizing**: Max 1% of portfolio at risk on any single regulatory decision (FDA, antitrust)
- **Options for binary events**: Buy straddles or strangles for PDUFA dates; defined risk, unlimited upside
- **Policy lag**: Regulations take 6-18 months from proposal to implementation; trade the announcement, hedge the implementation
- **Political risk**: Election cycles shift regulatory priorities; position for likely policy changes post-election
- **Compliance monitoring**: Track your own portfolio for regulatory filing requirements (13F, Reg SHO)
- **Information asymmetry decay**: Regulatory intelligence edge shrinks as more firms automate EDGAR monitoring
