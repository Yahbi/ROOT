---
name: Data Governance Framework
description: Implement data governance policies, data cataloging, access controls, and compliance frameworks
version: "1.0.0"
author: ROOT
tags: [data-engineering, governance, compliance, data-catalog, GDPR, lineage]
platforms: [all]
difficulty: intermediate
---

# Data Governance Framework

Data governance defines who can access what data, ensures data quality,
and maintains compliance with regulations (GDPR, CCPA, HIPAA).

## Governance Pillars

| Pillar | Description | Tools |
|--------|-------------|-------|
| Data Catalog | Discover and understand available data | Datahub, Atlan, Alation |
| Access Control | Who can see what data | Ranger, Lake Formation, IAM |
| Data Lineage | Track data origin and transformations | OpenLineage, Datahub |
| Data Quality | Ensure accuracy and completeness | Great Expectations, dbt tests |
| Data Classification | Tag sensitivity level | Custom + cloud DLP tools |
| Privacy Compliance | GDPR/CCPA/HIPAA requirements | Legal + technical controls |

## Data Classification Schema

```python
from enum import Enum

class DataSensitivity(Enum):
    PUBLIC = "public"           # No restriction (marketing copy, public pricing)
    INTERNAL = "internal"       # Employees only (internal docs, aggregate metrics)
    CONFIDENTIAL = "confidential"  # Need-to-know (financials, HR data)
    RESTRICTED = "restricted"   # Strict controls (PII, PHI, credentials)

PII_FIELDS = {
    "email", "full_name", "phone_number", "ssn", "credit_card_number",
    "ip_address", "date_of_birth", "home_address", "passport_number",
    "driver_license", "bank_account_number"
}

def classify_table(table_schema: dict) -> dict:
    """Classify table sensitivity based on columns present."""
    pii_columns = set(table_schema["columns"]) & PII_FIELDS
    if pii_columns:
        return {
            "sensitivity": DataSensitivity.RESTRICTED,
            "pii_columns": list(pii_columns),
            "requires_masking": True,
            "gdpr_relevant": True
        }
    return {"sensitivity": DataSensitivity.INTERNAL, "pii_columns": []}
```

## Data Masking for PII

```python
import hashlib
import re

def mask_pii(df: pd.DataFrame, masking_rules: dict) -> pd.DataFrame:
    """Apply masking to PII columns based on consumer role."""
    df = df.copy()

    for column, rule in masking_rules.items():
        if column not in df.columns:
            continue

        if rule == "hash":
            # Irreversible — for analytics where identity doesn't matter
            df[column] = df[column].apply(
                lambda x: hashlib.sha256(str(x).encode()).hexdigest()[:16] if pd.notna(x) else x
            )
        elif rule == "partial_mask":
            # Email: j***@example.com — enough for debugging, not identifying
            if column == "email":
                df[column] = df[column].apply(
                    lambda x: re.sub(r"(^.{1})(.+)(@)", r"\1***\3", str(x)) if pd.notna(x) else x
                )
        elif rule == "redact":
            # Complete removal
            df[column] = "[REDACTED]"
        elif rule == "tokenize":
            # Reversible pseudonymization for internal operations
            df[column] = df[column].apply(
                lambda x: tokenize(x) if pd.notna(x) else x
            )

    return df

# Define masking rules per consumer role
MASKING_RULES_BY_ROLE = {
    "data_scientist": {
        "email": "hash", "phone_number": "hash",
        "full_name": "partial_mask", "ssn": "redact"
    },
    "data_analyst": {
        "email": "partial_mask", "phone_number": "redact",
        "full_name": "partial_mask", "ssn": "redact"
    },
    "support_agent": {
        "email": "show", "phone_number": "show",
        "full_name": "show", "ssn": "redact"  # Need email/phone for support
    }
}
```

## Data Lineage Tracking

```python
from openlineage.client import OpenLineageClient, RunEvent, RunState, Run, Job

client = OpenLineageClient.from_environment()

def track_pipeline_lineage(job_name: str, input_datasets: list, output_datasets: list):
    """Track data lineage using OpenLineage standard."""
    import uuid

    run_id = str(uuid.uuid4())

    # Report job start
    client.emit(RunEvent(
        eventType=RunState.START,
        eventTime=datetime.now().isoformat() + "Z",
        run=Run(runId=run_id),
        job=Job(namespace="data-warehouse", name=job_name),
        inputs=[Dataset(namespace="postgresql", name=ds) for ds in input_datasets],
        outputs=[Dataset(namespace="bigquery", name=ds) for ds in output_datasets]
    ))

    return run_id

def track_pipeline_complete(run_id: str, job_name: str, row_count: int):
    client.emit(RunEvent(
        eventType=RunState.COMPLETE,
        eventTime=datetime.now().isoformat() + "Z",
        run=Run(runId=run_id,
                facets={"output_statistics": {"rowCount": row_count}}),
        job=Job(namespace="data-warehouse", name=job_name)
    ))
```

## GDPR Compliance Requirements

```python
class GDPRComplianceManager:
    def handle_right_to_erasure(self, user_id: str) -> dict:
        """Execute GDPR Article 17 — Right to Erasure (Right to be Forgotten)."""
        deleted_records = {}

        # Find all tables containing this user's data
        tables_with_pii = self.catalog.find_tables_with_user_data(user_id)

        for table in tables_with_pii:
            if table["can_delete"]:
                count = self.db.delete_user_data(table["name"], user_id)
                deleted_records[table["name"]] = count
            elif table["can_anonymize"]:
                count = self.db.anonymize_user_data(table["name"], user_id)
                deleted_records[f"{table['name']}_anonymized"] = count

        # Log the erasure for compliance audit trail
        self.audit_log.record_erasure(user_id, deleted_records)

        # Notify downstream systems (email provider, analytics, etc.)
        self.propagate_erasure_request(user_id)

        return {"user_id": user_id, "records_processed": deleted_records,
                "completed_at": datetime.now().isoformat()}

    def handle_data_portability_request(self, user_id: str) -> str:
        """GDPR Article 20 — Provide user's data in machine-readable format."""
        user_data = {}
        for table in self.catalog.find_tables_with_user_data(user_id):
            user_data[table["name"]] = self.db.get_user_data(table["name"], user_id)

        export_path = f"s3://user-exports/{user_id}/export_{datetime.now().date()}.json"
        upload_to_s3(json.dumps(user_data, default=str), export_path)
        return export_path
```

## Data Retention Policies

```python
RETENTION_POLICIES = {
    "transaction_logs": {
        "hot_retention_days": 90,     # Keep in primary database
        "warm_retention_days": 730,   # Move to S3-IA after 90 days
        "cold_retention_days": 2555,  # Move to S3 Glacier after 2 years
        "delete_after_days": 2555,    # Delete after 7 years (financial regulations)
        "exceptions": ["fraud_flagged_records"]  # Never delete — legal hold
    },
    "user_behavior_events": {
        "hot_retention_days": 30,
        "warm_retention_days": 365,
        "delete_after_days": 730,     # 2 years
        "gdpr_applies": True          # Must honor erasure requests
    },
    "application_logs": {
        "hot_retention_days": 7,
        "warm_retention_days": 30,
        "delete_after_days": 90
    }
}
```

## Data Catalog Template

```yaml
# metadata/tables/fact_orders.yaml
name: fact_orders
description: One row per customer order — primary revenue fact table
owner: data-engineering@company.com
domain: commerce
sensitivity: confidential
contains_pii: false  # Customer IDs are pseudonymized
freshness_sla_hours: 4
source_system: order-management-service
primary_key: order_key
row_count_estimate: 50000000
storage_size_gb: 120

columns:
  order_key:
    description: Surrogate key — auto-generated
    type: bigint
    is_nullable: false
  customer_key:
    description: FK to dim_customers (SCD Type 2 surrogate key)
    type: bigint
    is_nullable: false
  total_amount:
    description: Total order value in USD including tax, excluding refunds
    type: numeric(10,2)
    is_nullable: false

lineage:
  upstream: [stg_orders, dim_customers, dim_products, dim_date]
  downstream: [agg_daily_revenue, rpt_monthly_sales, ml_feature_store]
```
