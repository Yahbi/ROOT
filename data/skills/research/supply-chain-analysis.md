---
name: Supply Chain Analysis
description: Extract investment signals from shipping data, inventory cycles, and bottleneck identification
version: "1.0.0"
author: ROOT
tags: [research, supply-chain, shipping, inventory, alternative-data]
platforms: [all]
---

# Supply Chain Analysis

Use supply chain data as leading indicators for corporate earnings, sector rotation, and macro economic shifts.

## Shipping and Freight Data

- **Baltic Dry Index (BDI)**: Measures bulk commodity shipping costs; leading indicator for global trade and industrial activity
- **Container rates (SCFI, FBX)**: Shanghai Containerized Freight Index tracks export costs; spikes signal demand surge or capacity constraint
- **AIS vessel tracking**: Automatic Identification System data reveals real-time ship positions, port congestion, trade route changes
- **Port dwell times**: Average days at port; increasing = congestion/bottleneck; decreasing = normalization
- **Blank sailings**: Cancelled container voyages by shipping lines signal demand weakness; track weekly
- **Air freight rates**: Premium indicator; spikes when surface freight is insufficient (emergency restocking signal)

## Inventory Cycle Analysis

- **Bullwhip effect**: Small demand changes amplify into large inventory swings up the supply chain
- **Inventory-to-sales ratio**: `I/S = total_inventory / monthly_sales`; rising ratio = destocking ahead; falling = restocking
- **Days inventory outstanding**: `DIO = (inventory / COGS) * 365`; compare to 5-year average for sector
- **Restocking cycle**: Typically lasts 12-18 months after a destocking period; benefits suppliers first
- **Channel checks**: Distributor inventory levels (available via industry surveys) lead manufacturer reports by 1-2 quarters
- **Semiconductor inventory**: Chip inventory weeks-of-supply is key leading indicator for tech hardware sector

## Bottleneck Identification

### Detection Methods
- **Lead time monitoring**: Supplier delivery times from ISM/PMI; readings > 55 indicate lengthening
- **Price-quantity divergence**: Rising input prices with flat/declining volumes = supply constraint
- **Capacity utilization**: Industry capacity > 85% = bottleneck forming; > 90% = critical constraint
- **Single-source dependencies**: Map companies to critical single-source suppliers; failure point analysis
- **Geographic concentration**: Identify chokepoints (Suez Canal, Strait of Malacca, Taiwan Strait)

### Investment Implications
- **Bottleneck beneficiaries**: Companies with pricing power during shortages; capacity leaders
- **Bottleneck victims**: Companies dependent on constrained inputs with no substitute; margin compression
- **Second-order effects**: Bottleneck in component A delays product B; map entire dependency chain
- **Resolution timing**: Most bottlenecks resolve in 6-18 months; position for normalization after peak

## Alternative Data Sources

| Data Source | Signal | Lead Time |
|------------|--------|-----------|
| Satellite imagery (ports/factories) | Activity levels, inventory piles | 1-4 weeks |
| Truck tonnage index | Domestic freight demand | 1-2 months |
| Railroad carloadings (AAR) | Industrial/agricultural volumes | 2-4 weeks |
| Import/export customs data | Trade flow changes | 1-3 months |
| Purchasing managers surveys | Order backlogs, delivery times | Coincident |
| Job postings (warehouse/logistics) | Capacity expansion plans | 3-6 months |

## Sector-Specific Supply Chain Signals

- **Automotive**: Semiconductor supply → production schedules → dealer inventory → incentive levels
- **Retail**: Container bookings → port arrivals → distribution center throughput → shelf availability
- **Energy**: Rig counts → drilling activity → pipeline capacity → storage levels → pricing
- **Agriculture**: Planting progress → weather models → harvest estimates → export inspections → futures
- **Pharmaceuticals**: API sourcing → manufacturing lead times → distribution → pharmacy inventory

## Analytical Framework

1. **Map the chain**: For target company, identify Tier 1-3 suppliers and key logistics paths
2. **Monitor leading indicators**: Track shipping rates, supplier lead times, inventory data weekly
3. **Quantify impact**: Estimate earnings impact: `EPS_delta = volume_impact * margin_sensitivity`
4. **Compare to consensus**: If supply chain data implies different volumes than Street estimate, trade the gap
5. **Time the trade**: Supply chain signals lead earnings by 1-3 months; enter before reporting season

## Risk Management

- **Data latency**: Most supply chain data has 1-4 week lag; markets may partially price in by publication
- **Noise vs signal**: Short-term shipping rate spikes can be weather-related; filter for 3+ week trends
- **Geopolitical overlay**: Sanctions, trade wars, and conflicts disrupt normal supply chain relationships
- **Model decay**: Supply chain relationships change over time (nearshoring, diversification); update maps quarterly
- **Position sizing**: Supply chain thesis takes 1-3 months to play out; size for potential adverse moves during wait
