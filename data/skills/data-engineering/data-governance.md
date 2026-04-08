---
name: Data Governance
description: Policies, standards, and practices for managing data quality, ownership, lineage, and compliance
category: data-engineering
difficulty: advanced
version: "1.0.0"
author: ROOT
tags: [data-engineering, data-governance, data-catalog, lineage, compliance, GDPR, CCPA, data-mesh]
platforms: [all]
---

# Data Governance

Establish the policies, processes, and organizational structures that ensure data is trusted, discoverable, and used responsibly.

## Governance Pillars

| Pillar | Goal | Key Mechanisms |
|--------|------|---------------|
| **Data Quality** | Data is accurate, complete, and timely | Quality rules, SLAs, DQ scoring |
| **Data Security** | Data is protected from unauthorized access | Classification, access control, encryption |
| **Data Lineage** | Know where data came from and where it goes | Catalog integration, column-level lineage |
| **Data Ownership** | Clear accountability for each data domain | Domain owners, stewards, RACI |
| **Compliance** | Meet regulatory obligations (GDPR, CCPA, HIPAA) | Data classification, retention, right to erasure |
| **Discoverability** | Data is findable and understood | Catalog, metadata, documentation |

## Data Ownership Model

### Roles
- **Data Owner**: Executive or senior manager accountable for a data domain; approves access policies
- **Data Steward**: Operational role — maintains definitions, enforces standards, coordinates quality
- **Data Producer**: Team that creates/maintains the dataset; responsible for quality at the source
- **Data Consumer**: Team or individual using the dataset; provides quality feedback
- **Data Governance Council**: Cross-functional body that sets policies and resolves disputes

### RACI Matrix (Example: Customer Data)
| Activity | Data Owner | Steward | Producer | Consumer | IT |
|----------|-----------|---------|----------|----------|-----|
| Define data standards | A | R | C | I | I |
| Approve new data access | A | R | I | I | C |
| Remediate quality issues | I | A | R | I | C |
| Update data catalog | I | A | R | I | I |

## Data Classification

### Classification Tiers
```yaml
tiers:
  public:
    description: Safe to share externally
    examples: [product catalog, public pricing, marketing content]
    controls: [none beyond standard auth]

  internal:
    description: Business use, not for external sharing
    examples: [employee directory, internal reports, aggregate metrics]
    controls: [authenticated access, role-based]

  confidential:
    description: Sensitive business or personal data
    examples: [customer PII, financial records, contracts]
    controls: [need-to-know access, encryption, audit logging]

  restricted:
    description: Highest sensitivity — breach causes serious harm
    examples: [payment card data, health records, source code]
    controls: [strict need-to-know, MFA, HSM encryption, enhanced monitoring]
```

### PII Field Tagging (DataHub / Apache Atlas)
```python
# Tag PII fields in the data catalog
from datahub.emitter.mce_builder import make_term_urn

pii_tag = make_term_urn("PII")
# Apply to dataset fields:
# - email → PII.EMAIL
# - phone → PII.PHONE
# - ip_address → PII.NETWORK_IDENTIFIER
# - full_name → PII.NAME
# - date_of_birth → PII.SENSITIVE_PERSONAL
```

## Regulatory Compliance

### GDPR Requirements
| Requirement | Implementation |
|-------------|---------------|
| Lawful basis for processing | Document purpose per data element in catalog |
| Data minimization | Only collect/store what is necessary |
| Right to erasure (RTBF) | Automated deletion workflow by user_id |
| Data portability | Export API returning user's data in JSON/CSV |
| Privacy by design | Review data model before launch; DPIAs for high-risk processing |
| Breach notification | 72-hour notification process; incident response runbook |

### Right to Be Forgotten Workflow
```python
async def handle_erasure_request(user_id: str):
    """Execute GDPR Article 17 deletion across all systems."""
    steps = [
        delete_from_operational_db(user_id),
        anonymize_in_data_warehouse(user_id),    # Replace PII with synthetic values
        delete_from_data_lake_raw(user_id),
        purge_from_ml_training_sets(user_id),
        revoke_api_tokens(user_id),
        clear_cache_entries(user_id),
        notify_third_party_processors(user_id),  # Required by GDPR
    ]
    results = await asyncio.gather(*steps, return_exceptions=True)
    log_erasure_completion(user_id, results)     # Maintain proof of deletion (no PII stored)
```

### CCPA Compliance Additions
- Opt-out of sale of personal information (Do Not Sell link required)
- Data inventory: maintain record of all data collected, purpose, third-party sharing
- Access requests: respond within 45 days (vs GDPR's 30 days)

## Data Catalog

### What to Document per Dataset
```yaml
dataset: orders
owner: data-engineering@company.com
steward: jane.smith@company.com
domain: commerce
classification: confidential
pii_fields: [user_id, shipping_address, email]
update_frequency: daily at 04:00 UTC
sla_freshness: < 6 hours
quality_score: 98.5   # Updated daily by DQ pipeline
source_systems: [postgres-orders, stripe-events]
downstream_consumers: [revenue-dashboard, finance-reporting, ml-churn-model]
schema_version: 3.1.0
description: >
  One row per order placed on the platform. Includes all order states
  from pending through delivered or cancelled. Joined with payments
  for revenue reporting.
columns:
  order_id:
    description: Unique identifier for the order
    type: string
    nullable: false
    pii: false
  user_id:
    description: References the user who placed the order
    type: string
    nullable: false
    pii: true
    pii_type: INDIRECT_IDENTIFIER
```

## Data Lineage

### Column-Level Lineage Example
```
stg_orders.amount
    ↓ (cast to DECIMAL)
int_orders_enriched.order_amount
    ↓ (SUM)
fct_daily_revenue.gross_revenue
    ↓ (displayed in)
Revenue Dashboard — Daily Revenue metric
```

### Why Column-Level Lineage Matters
- Impact analysis: if `orders.amount` changes type, find all downstream breakages
- Root cause: if `gross_revenue` is wrong, trace back to source field
- Compliance: prove which reports use PII fields

### Tools
| Tool | Open Source | Column Lineage | Catalog | Governance |
|------|------------|---------------|---------|------------|
| Apache Atlas | Yes | Yes | Yes | Partial |
| DataHub | Yes | Yes | Yes | Partial |
| OpenMetadata | Yes | Yes | Yes | Full |
| Alation | No | Yes | Yes | Full |
| Collibra | No | Yes | Yes | Full |

## Data Retention Policies

| Data Type | Operational Retention | Archival | Legal Hold |
|-----------|----------------------|---------|------------|
| Transaction data | 7 years | Glacier after 1 year | Indefinite if litigation |
| User PII | Duration of account + 30 days after deletion request | N/A | Litigation hold only |
| Security logs | 1 year | Cold storage 3 years | |
| ML training data | Until model version retired | Version-controlled | |
| Raw event logs | 90 days | S3 IA 1 year, then delete | |

## Governance Metrics

- **Data catalog coverage**: % of datasets documented in catalog (target > 90%)
- **Ownership coverage**: % of datasets with assigned owner (target 100%)
- **Quality score average**: weighted average DQ score across all datasets
- **Access request SLA**: % of access requests resolved within 2 business days
- **Erasure compliance rate**: % of GDPR/CCPA deletion requests completed within legal deadline
- **Policy exception count**: open exceptions to data classification or retention policy
