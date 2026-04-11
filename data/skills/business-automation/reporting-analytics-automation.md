---
name: Reporting and Analytics Automation
description: Automate business reporting, KPI dashboards, and stakeholder updates with scheduled data pipelines
version: "1.0.0"
author: ROOT
tags: [business-automation, reporting, analytics, dashboards, BI, data-automation]
platforms: [all]
difficulty: intermediate
---

# Reporting and Analytics Automation

Replace manual spreadsheet reports with automated pipelines that deliver
accurate, timely insights to the right people automatically.

## Report Automation Architecture

```
Data Sources → ETL Pipeline → Data Warehouse → BI Layer → Scheduled Delivery
(CRM, DB, API)  (daily/hourly)  (BigQuery/Snowflake)  (Looker/Metabase)  (email/Slack)
```

## Automated KPI Calculation

```python
import pandas as pd
from datetime import datetime, timedelta

class KPIDashboard:
    def compute_weekly_kpis(self, week_start=None) -> dict:
        if week_start is None:
            week_start = datetime.now() - timedelta(weeks=1)
        week_end = week_start + timedelta(weeks=1)

        return {
            "period": {"start": week_start.isoformat(), "end": week_end.isoformat()},
            "revenue": self.compute_revenue_metrics(week_start, week_end),
            "sales": self.compute_sales_metrics(week_start, week_end),
            "marketing": self.compute_marketing_metrics(week_start, week_end),
            "product": self.compute_product_metrics(week_start, week_end),
        }

    def compute_revenue_metrics(self, start, end) -> dict:
        payments = self.stripe.get_payments(start, end)
        return {
            "new_mrr": sum(p.amount for p in payments if p.type == "new"),
            "expansion_mrr": sum(p.amount for p in payments if p.type == "expansion"),
            "churn_mrr": sum(p.amount for p in payments if p.type == "churn"),
            "total_revenue": sum(p.amount for p in payments),
            "collection_rate": self.compute_collection_rate(start, end),
        }
```

## AI-Written Executive Summaries

```python
from anthropic import Anthropic

client = Anthropic()

def generate_executive_summary(kpis: dict, previous_kpis: dict) -> str:
    changes = compute_changes(kpis, previous_kpis)
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        messages=[{
            "role": "user",
            "content": f"""Write a concise executive summary of this week's business performance.
Be specific with numbers. Flag concerns. Lead with the headline number.

Current week KPIs: {json.dumps(kpis, indent=2)}
Week-over-week changes: {json.dumps(changes, indent=2)}

Format: 3-4 paragraphs. Wins. Concerns. What to watch."""
        }]
    ).content[0].text
    return response
```

## Scheduled Delivery

### Slack Daily Metrics

```python
def post_daily_metrics_to_slack(kpis: dict, channel: str = "#metrics"):
    blocks = [
        {"type": "header", "text": {"type": "plain_text",
         "text": f"Daily Metrics — {datetime.now().strftime('%b %d')}"}},
        {"type": "section", "fields": [
            {"type": "mrkdwn", "text": f"*Revenue*\n${kpis['revenue']['total_revenue']:,.0f}"},
            {"type": "mrkdwn", "text": f"*New Deals*\n{kpis['sales']['new_deals_closed']}"},
            {"type": "mrkdwn", "text": f"*New Signups*\n{kpis['product']['new_signups']}"},
        ]}
    ]
    requests.post(SLACK_WEBHOOK_URL, json={"channel": channel, "blocks": blocks})
```

### APScheduler Integration

```python
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

# Daily metrics at 8am
scheduler.add_job(
    func=post_daily_metrics_to_slack,
    trigger="cron", hour=8, minute=0,
    id="daily_slack_metrics"
)

# Weekly report every Monday at 9am
scheduler.add_job(
    func=lambda: send_weekly_report(compute_weekly_kpis(), EXEC_TEAM_EMAILS),
    trigger="cron", day_of_week="mon", hour=9,
    id="weekly_exec_report"
)

# Monthly board report on 1st of month
scheduler.add_job(
    func=generate_monthly_board_report,
    trigger="cron", day=1, hour=7,
    id="monthly_board_report"
)

scheduler.start()
```

## Anomaly Detection

```python
def detect_metric_anomalies(current_kpis: dict, historical_kpis: list) -> list:
    """Flag metrics deviating significantly from historical patterns."""
    anomalies = []
    for metric_path in get_all_metric_paths(current_kpis):
        current_val = get_nested_value(current_kpis, metric_path)
        historical_vals = [get_nested_value(week, metric_path) for week in historical_kpis
                          if get_nested_value(week, metric_path) is not None]

        if len(historical_vals) < 4:
            continue

        mean = sum(historical_vals) / len(historical_vals)
        std = pd.Series(historical_vals).std()

        if std > 0:
            z_score = (current_val - mean) / std
            if abs(z_score) > 2:
                anomalies.append({
                    "metric": metric_path,
                    "current": current_val,
                    "historical_mean": mean,
                    "z_score": z_score,
                    "severity": "high" if abs(z_score) > 3 else "medium"
                })

    return sorted(anomalies, key=lambda x: abs(x["z_score"]), reverse=True)
```

## Report Checklist

- [ ] Data sources identified and access granted
- [ ] ETL pipeline tested with full dataset
- [ ] Metric definitions agreed with business owners
- [ ] Report delivered to correct stakeholders
- [ ] Anomaly alerts configured
- [ ] Historical baseline established (min 4 weeks)
- [ ] Data quality checks prevent garbage metrics from being sent

## Key Metrics by Function

| Function | Primary KPIs |
|----------|-------------|
| Revenue | MRR, ARR, Churn MRR, Net Revenue Retention |
| Sales | New pipeline, Win rate, Average deal size, Sales cycle length |
| Marketing | CAC, MQLs, SQL conversion rate, Paid vs. organic breakdown |
| Product | DAU/MAU, Feature adoption, Churn rate, NPS |
| CS | CSAT, Renewal rate, Time-to-value, Tickets per customer |
