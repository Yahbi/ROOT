---
name: Data Pipeline Monitoring
description: Observability, alerting, and SLA enforcement for data pipelines and ETL workflows
category: data-engineering
difficulty: intermediate
version: "1.0.0"
author: ROOT
tags: [data-engineering, monitoring, observability, data-quality, sla, alerting, airflow, metrics]
platforms: [all]
---

# Data Pipeline Monitoring

Build comprehensive observability for data pipelines so issues are detected and resolved before they impact business decisions.

## The Four Pillars of Pipeline Observability

| Pillar | What It Measures | Tools |
|--------|-----------------|-------|
| **Freshness** | Is data up to date? | Custom queries, Monte Carlo, Bigeye |
| **Volume** | Is the expected amount of data arriving? | Row count metrics, Prometheus |
| **Quality** | Are values within expected ranges? | Great Expectations, dbt tests |
| **Lineage** | Which pipelines and sources does this depend on? | DataHub, OpenLineage |

## Metrics to Track per Pipeline

### Runtime Metrics
```python
# Store per-run metadata in a monitoring table
pipeline_runs = {
    "pipeline_id": "orders_etl",
    "run_id": "20240115_040000",
    "dag_id": "orders_etl",
    "run_date": "2024-01-15",
    "started_at": "2024-01-15T04:00:00Z",
    "completed_at": "2024-01-15T04:23:45Z",
    "duration_seconds": 1425,
    "status": "success",          # success, failed, partial
    "rows_extracted": 1_245_670,
    "rows_loaded": 1_245_670,
    "rows_rejected": 0,
    "bytes_processed": 892_340_000,
    "error_message": None,
    "cost_usd": 2.34,
}
```

### Freshness Monitoring
```sql
-- Query to check data freshness
SELECT
    table_name,
    MAX(updated_at) AS last_updated,
    EXTRACT(EPOCH FROM (NOW() - MAX(updated_at))) / 3600 AS hours_since_update,
    freshness_sla_hours,
    CASE
        WHEN EXTRACT(EPOCH FROM (NOW() - MAX(updated_at))) / 3600 > freshness_sla_hours
        THEN 'STALE'
        ELSE 'FRESH'
    END AS freshness_status
FROM data_freshness_registry
JOIN (
    SELECT 'orders' AS table_name, MAX(loaded_at) AS updated_at FROM orders
    UNION ALL
    SELECT 'users', MAX(updated_at) FROM users
) latest ON data_freshness_registry.table_name = latest.table_name
GROUP BY 1, 4;
```

### Volume Anomaly Detection
```python
import statistics

def detect_volume_anomaly(pipeline_id: str, current_rows: int, history_days: int = 14) -> dict:
    """Z-score based anomaly detection for row counts."""
    historical_counts = get_historical_row_counts(pipeline_id, days=history_days)

    mean = statistics.mean(historical_counts)
    stddev = statistics.stdev(historical_counts)

    if stddev == 0:
        return {"anomaly": False}

    z_score = (current_rows - mean) / stddev

    return {
        "anomaly": abs(z_score) > 3.0,
        "z_score": z_score,
        "current_rows": current_rows,
        "mean_rows": mean,
        "stddev": stddev,
        "deviation_pct": (current_rows - mean) / mean * 100,
    }
```

## SLA Monitoring

### Defining Pipeline SLAs
```yaml
slas:
  - pipeline: orders_etl
    sla_completion_by: "06:00 UTC"      # Must complete by 6 AM
    max_duration_minutes: 120
    min_rows: 50000
    max_freshness_hours: 6

  - pipeline: revenue_summary
    sla_completion_by: "07:00 UTC"
    max_duration_minutes: 45
    dependencies: [orders_etl, payments_etl]   # Must run after these

  - pipeline: hourly_events
    sla_completion_by: "+30m"    # Must complete within 30 min of start
    max_duration_minutes: 25
```

### SLA Breach Alerting (Airflow)
```python
from airflow.models import SLA
from datetime import timedelta

with DAG(
    "orders_etl",
    sla_miss_callback=sla_miss_alert,    # Called when SLA is missed
    default_args={"sla": timedelta(hours=2)},
) as dag:
    pass

def sla_miss_alert(dag, task_list, blocking_task_list, slas, blocking_tis):
    message = f"SLA missed for {dag.dag_id}: tasks {task_list}"
    send_pagerduty_alert(message, severity="high")
    send_slack_message("#data-alerts", message)
```

## Alerting Strategy

### Alert Severity Matrix
| Condition | Severity | Response | Channel |
|-----------|---------|---------|---------|
| Pipeline failed | HIGH | Acknowledge within 15 min | PagerDuty |
| SLA missed | HIGH | Acknowledge within 30 min | PagerDuty + Slack |
| Data freshness > 2x SLA | HIGH | Acknowledge within 1 hour | PagerDuty |
| Volume anomaly (z > 3) | MEDIUM | Review within 4 hours | Slack |
| Quality score < 90% | MEDIUM | Review within 4 hours | Slack |
| Pipeline duration > 2x median | LOW | Review next business day | Email |

### Alert Design Principles
- Include actionable context: what failed, when, impact, runbook link
- Set meaningful thresholds — avoid alert fatigue from noisy alerts
- Group related alerts to reduce noise (alert on pipeline, not every failed task)
- Deduplicate: same alert twice in 30 min → suppress second

### Slack Alert Template
```python
def send_pipeline_alert(pipeline: str, issue: str, details: dict):
    message = {
        "text": f":red_circle: Pipeline Alert: {pipeline}",
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": f"Pipeline Alert: {pipeline}"}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Issue:*\n{issue}"},
                {"type": "mrkdwn", "text": f"*Run Date:*\n{details['run_date']}"},
                {"type": "mrkdwn", "text": f"*Duration:*\n{details['duration']}"},
                {"type": "mrkdwn", "text": f"*Impact:*\n{details['impact']}"},
            ]},
            {"type": "section", "text": {"type": "mrkdwn",
                "text": f"<{details['runbook_url']}|View Runbook> | <{details['airflow_url']}|View in Airflow>"}},
        ]
    }
    requests.post(SLACK_WEBHOOK, json=message)
```

## Dashboard Design

### Pipeline Health Dashboard (Grafana / Superset)
- **Top panel**: Count of active, failed, and delayed pipelines (last 24h)
- **SLA compliance**: % of pipelines meeting SLA (rolling 7 days)
- **Freshness heatmap**: Grid of tables × hours, colored by freshness status
- **Duration trend**: P50/P95 pipeline duration over 30 days, alert on regression
- **Error rate**: Failed runs / total runs per pipeline over time
- **Cost trend**: Compute cost per pipeline per day

## Data Observability with OpenLineage

### Emitting Lineage Events
```python
from openlineage.client import OpenLineageClient
from openlineage.client.run import RunEvent, RunState, Run, Job
from openlineage.client.facet import DataQualityMetricsFacet

client = OpenLineageClient.from_environment()

# Emit START event
client.emit(RunEvent(
    eventType=RunState.START,
    run=Run(runId=run_id),
    job=Job(namespace="data-engineering", name="orders_etl"),
    inputs=[InputDataset(namespace="postgres", name="orders")],
    outputs=[OutputDataset(namespace="s3", name="cleansed/orders",
             facets={"dataQuality": DataQualityMetricsFacet(
                 rowCount=1_245_670, bytes=892_340_000)})],
))
```

## Runbook: Common Pipeline Failures

### Data Freshness Breach
1. Check Airflow for pipeline run status
2. If pipeline ran: check row counts — was it a genuine data gap at source?
3. If pipeline didn't run: check Airflow scheduler health, DAG paused state, trigger manually
4. Notify downstream consumers with ETA for resolution
5. Post-mortem if breach > 2x SLA

### Volume Anomaly
1. Check source system: is this a genuine low/high volume period?
2. Check for pipeline failures in the extraction phase
3. Check for source schema changes breaking the extraction query
4. If confirmed anomaly: quarantine affected partition; backfill from source

### Quality Score Drop
1. Run quality checks manually with verbose output to identify failing rules
2. Trace failing records to source system
3. Determine if issue is in source or transformation layer
4. Apply quarantine tag to affected records
5. Fix root cause; backfill and re-validate
