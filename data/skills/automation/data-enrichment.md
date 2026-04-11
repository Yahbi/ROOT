---
name: Data Enrichment
description: API chaining, entity resolution, deduplication strategies, and data quality scoring
version: "1.0.0"
author: ROOT
tags: [automation, data, enrichment, deduplication, quality, ETL]
platforms: [all]
---

# Data Enrichment

Transform raw data into high-value intelligence through systematic API enrichment, entity resolution, deduplication, and quality scoring.

## API Chaining Architecture

### Sequential Enrichment Pipeline
1. **Ingest**: Raw record enters pipeline (e.g., company name, email, ticker)
2. **Normalize**: Standardize fields (lowercase, trim, format dates, validate types)
3. **Identify**: Resolve entity to canonical ID (LEI for companies, CUSIP/ISIN for securities, email domain for contacts)
4. **Enrich**: Chain API calls to append missing fields (firmographics, technographics, financials)
5. **Score**: Assess completeness and confidence of enriched record
6. **Store**: Write to data warehouse with provenance metadata (source, timestamp, confidence)

### API Orchestration Patterns
- **Waterfall**: Try primary source first; fall back to secondary if primary returns null; minimize API costs
- **Fan-out**: Query multiple sources in parallel; merge results by confidence; better coverage, higher cost
- **Conditional**: Only call expensive API if cheap source returns insufficient data (e.g., skip Dun & Bradstreet if Clearbit sufficient)
- **Rate limiting**: Respect API limits; use token bucket algorithm; batch requests where API supports bulk endpoints
- **Caching**: Cache API responses with TTL (24h for firmographics, 1h for market data, 5min for real-time)
- **Cost tracking**: Log cost per enrichment; `cost_per_record = SUM(api_calls * price_per_call)`; set budget alerts

## Entity Resolution

- **Problem**: Same entity represented differently across sources ("Apple Inc.", "APPLE INC", "Apple Computer")
- **Blocking**: Reduce candidate pairs using cheap filters (first 3 chars of name, same country, same industry)
- **Similarity metrics**: Jaro-Winkler (names, 0.85+ threshold), TF-IDF cosine (descriptions), exact match (IDs)
- **Composite scoring**: `match_score = w1*name_sim + w2*address_sim + w3*id_match + w4*domain_sim`
- **Threshold tuning**: Manual review of borderline matches (score 0.7-0.9); optimize precision vs recall
- **Transitive closure**: If A matches B and B matches C, then A matches C; build connected components
- **Canonical record**: Merge matched records into golden record; prefer most recent, most complete, highest authority source

## Deduplication Strategies

### Detection Methods
- **Exact dedup**: Hash entire record or key fields; O(n) with hash table; catches perfect duplicates
- **Fuzzy dedup**: Block + compare using similarity metrics; catches near-duplicates ("Jon Smith" vs "John Smith")
- **Record linkage**: Cross-source dedup; match records across databases using entity resolution pipeline
- **Temporal dedup**: Same entity at different time points; keep most recent or merge time-series

### Merge Strategies
- **Keep newest**: Use most recently updated record as canonical; simple but may lose historical data
- **Keep most complete**: Use record with fewest nulls; best for initial enrichment
- **Field-level merge**: For each field, pick value from most authoritative source; most accurate but complex
- **Confidence-weighted**: `final_value = argmax(confidence_score * recency_weight)` per field

## Data Quality Scoring

### Completeness Score
- `completeness = filled_fields / total_fields`; weight critical fields higher
- **Critical fields** (weight 2x): Name, identifier, primary contact, revenue
- **Important fields** (weight 1x): Address, industry, employee count, website
- **Optional fields** (weight 0.5x): Social profiles, secondary contacts, descriptions

### Accuracy Scoring
- **Format validation**: Email regex, phone format, date parsing, URL reachability; binary pass/fail
- **Range validation**: Revenue > 0, employee count > 0, founding year < current year; flag outliers
- **Cross-field consistency**: Country matches phone prefix, currency matches country, industry matches description
- **Freshness**: `freshness_score = exp(-lambda * days_since_update)` with lambda = 0.01 (halflife ~70 days)

### Composite Quality Score
- `quality = 0.4 * completeness + 0.3 * accuracy + 0.2 * freshness + 0.1 * source_authority`
- **Grade**: A (>0.9), B (0.7-0.9), C (0.5-0.7), D (<0.5); reject D-grade records from production use
- **Track over time**: Quality trends reveal data pipeline degradation; alert if average quality drops >5%

## Enrichment Sources by Domain

| Domain | Sources | Key Fields |
|--------|---------|------------|
| Company | Clearbit, Crunchbase, D&B, LinkedIn | Revenue, employees, funding, tech stack |
| Financial | Bloomberg, Refinitiv, SEC EDGAR | Financials, filings, ownership, credit |
| Contact | Hunter.io, Apollo, ZoomInfo | Email, phone, title, social profiles |
| IP/Domain | Whois, BuiltWith, SimilarWeb | Tech stack, traffic, registration |
| Location | Google Maps, HERE, Census | Geocode, demographics, foot traffic |

## Risk Management

- **API dependency**: No single enrichment source should be critical path; always have fallback providers
- **Data privacy**: Enrichment must comply with GDPR/CCPA; only enrich data you have legal basis to process
- **Cost overruns**: Set per-record and monthly budget caps; expensive APIs (D&B, Bloomberg) can cost $0.10-5.00/record
- **Stale data**: Set TTL on all cached enrichment; force re-enrichment on critical decisions
- **Bias in enrichment**: Coverage varies by geography and company size; acknowledge gaps in analysis
