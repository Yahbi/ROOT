---
name: Report Generation
description: Automated report creation with template engines, chart embedding, scheduling, and multi-channel distribution
version: "1.0.0"
author: ROOT
tags: [automation, reports, templates, scheduling, visualization]
platforms: [all]
---

# Report Generation

Build automated reporting pipelines that produce professional, data-driven reports on schedule with minimal human intervention.

## Template Engine Design

- **Separation of concerns**: Data layer (queries/APIs) then processing layer then presentation layer (templates)
- **Jinja2 (Python)**: Industry standard; supports conditionals, loops, filters, template inheritance
- **Template inheritance**: Base template (header, footer, branding) extends to section and report-specific templates
- **Parameterization**: Report date range, entity filters, comparison periods passed as template variables
- **Conditional sections**: Show alert sections only when metric exceeds threshold; hide empty sections
- **Version control**: Store templates in git; track changes and enable rollback
- **Preview mode**: Render with sample data before scheduling; catch formatting errors early

## Chart and Visualization Embedding

### Static Charts
- **Matplotlib/Seaborn**: Generate PNG/SVG; embed as base64 data URI in HTML reports
- **Plotly static**: Export as PNG via pio.write_image(); Kaleido renderer; high-quality vector output
- **Chart sizing**: Standard widths: 600px single column, 1200px full width; consistent across reports

### Interactive Charts (HTML Reports)
- **Plotly.js**: Embed interactive charts with zoom, hover, pan; self-contained HTML
- **Altair/Vega-Lite**: Declarative grammar; JSON spec embeds cleanly; great for dashboards
- **Chart type selection**: Time series = line; comparison = bar; distribution = histogram; scatter = relationship

### Table Formatting
- **Conditional formatting**: Red/green for negative/positive values; bold for thresholds breached
- **Sparklines**: Inline micro-charts in table cells showing trend (7-day, 30-day)
- **Export support**: Include CSV download link for raw data underlying each table
- **Color palette**: Consistent brand colors; colorblind-safe palette (Okabe-Ito or Tableau 10)

## Scheduling and Orchestration

| Report Type | Frequency | Delivery Time | Tolerance |
|------------|-----------|---------------|-----------|
| Daily digest | Every trading day | 7:00 AM local | +30min |
| Weekly summary | Monday | 9:00 AM local | +1hr |
| Monthly review | 1st business day | 10:00 AM local | +2hr |
| Ad-hoc / triggered | On event | ASAP | Immediate |

- **Cron / APScheduler**: Simple time-based scheduling; reliable for fixed schedules
- **DAG-based (Airflow/Prefect)**: For reports with complex data dependencies; retry logic built in
- **Event-triggered**: Report generated when data arrives (webhook, file drop, DB change)
- **Idempotency**: Re-running report for same date produces identical output; essential for debugging
- **Dependency checks**: Verify all data sources are fresh before generating; fail gracefully if data missing

## Distribution Methods

- **Email**: HTML body for quick view + PDF/Excel attachment for archival; use SendGrid/SES
- **Telegram/Discord**: Push key metrics with chart images; link to full report
- **Web dashboard**: Host HTML reports on internal server; searchable archive
- **Cloud storage**: Upload PDF/HTML to S3/GCS; share pre-signed URLs with expiration
- **API endpoint**: Serve report data as JSON; consumers build their own views

## Report Quality Assurance

- **Data validation**: Assert row counts, date ranges, null percentages before rendering; abort on anomalies
- **Metric bounds**: Alert if any KPI deviates more than 3 sigma from historical range
- **Test suite**: Unit tests for calculations; integration tests for template rendering
- **Feedback loop**: Track which reports are opened/forwarded; low engagement signals retirement candidate

## Risk Management

- **Data freshness**: Timestamp all data sources in report footer; readers must know data recency
- **PII handling**: Mask or aggregate personal data; reports often forwarded beyond intended audience
- **Version mismatch**: Lock template version with data schema version; schema changes break reports
- **Storage costs**: Archive reports for compliance (7 years typical); use cold storage for old reports
- **Delivery failures**: Monitor bounce rates and API errors; retry with backoff; alert below 95% delivery
