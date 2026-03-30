---
name: Alternative Data
description: Non-traditional data sources for alpha generation in trading
version: "1.0.0"
author: ROOT
tags: [research, alternative-data, alpha, non-traditional]
platforms: [all]
---

# Alternative Data for Trading

Use non-traditional data sources to gain informational edge before it shows up in earnings.

## Data Categories and Sources

### Satellite and Geospatial
- **Parking lot counts**: foot traffic at retail locations (Walmart, Target)
- **Oil storage levels**: satellite imagery of floating-roof tank shadows
- **Construction activity**: track new builds, crane counts in key metros
- **Crop health**: NDVI vegetation indices for agricultural commodities
- **Shipping traffic**: AIS vessel tracking for global trade flow

### Web and App Analytics
- **Web traffic**: SimilarWeb, SEMrush — proxy for customer acquisition
- **App downloads**: Sensor Tower, App Annie — mobile engagement trends
- **Job postings**: Indeed, LinkedIn — hiring = expansion, layoffs = contraction
- **Product reviews**: Amazon review velocity and rating trends
- **Pricing data**: scrape competitor pricing for margin analysis

### Transaction and Consumer
- **Credit card data**: aggregated spend by merchant category (Mastercard, Second Measure)
- **Email receipt data**: order volume and average basket size
- **Geolocation data**: foot traffic patterns from mobile devices
- **Flight bookings**: airline demand proxy from aggregator data

### Government and Regulatory
- **Patent filings**: innovation pipeline signal for pharma/tech
- **FDA calendar**: PDUFA dates for biotech catalysts
- **Lobbying spend**: regulatory risk proxy
- **Government contracts**: FPDS awards signal revenue visibility

## Evaluation Framework

For each dataset, assess:
1. **Alpha potential**: does it predict earnings surprise? (backtest required)
2. **Decay rate**: how quickly does the signal lose value after publication?
3. **Coverage**: does it cover enough tickers to be useful?
4. **Cost**: free (web scraping) vs expensive (satellite = $50K-$500K/yr)
5. **Legal risk**: ensure compliance with data privacy and securities law

## Implementation

1. Acquire data feed (API, vendor, or build scraper)
2. Map data to specific tickers or sectors
3. Build historical dataset (minimum 3 years for backtesting)
4. Create signal: z-score of metric vs trailing baseline
5. Combine with fundamental/technical signals (ensemble model)
6. Paper trade for 3 months before deploying capital

## Key Rule

Alternative data works best when combined with traditional analysis. No single
alternative dataset is sufficient — build a mosaic of signals.
