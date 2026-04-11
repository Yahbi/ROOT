---
name: Data Visualization
description: Chart selection, dashboard design, and storytelling with data
version: "1.0.0"
author: ROOT
tags: [data-analysis, visualization, dashboards, charts, storytelling]
platforms: [all]
---

# Data Visualization

Choose the right charts and design dashboards that drive understanding and action.

## Chart Selection Guide

| Question You're Answering | Best Chart Type | Alternatives |
|--------------------------|----------------|--------------|
| How does X change over time? | Line chart | Area chart, sparkline |
| How do categories compare? | Bar chart (horizontal) | Dot plot, lollipop |
| What is the composition? | Stacked bar (few periods), treemap (many items) | Pie (< 5 slices only) |
| How are values distributed? | Histogram | Box plot, violin plot |
| Is there a relationship? | Scatter plot | Bubble chart (3 variables) |
| What is the geographic pattern? | Choropleth map | Dot density map |
| What is the flow/process? | Sankey diagram | Funnel chart |
| What is the ranking? | Sorted bar chart | Bump chart (ranking over time) |

## Dashboard Design

### Layout Principles
- **Top row**: KPIs and summary metrics (the "so what?" at a glance)
- **Middle**: Detailed charts supporting the KPIs (the "why?")
- **Bottom**: Tables and drill-down data (the "show me the details")
- Read order: left-to-right, top-to-bottom (most important = top-left)

### Dashboard Rules
1. One dashboard = one question or decision it supports
2. Maximum 6-8 visualizations per dashboard (more = cognitive overload)
3. Consistent time range across all charts on the same dashboard
4. Use consistent color coding (red = bad, green = good, throughout)
5. Include comparison: show current vs previous period, vs target, vs benchmark

### Interactivity
- Filters: date range, segment, geography (top of dashboard)
- Drill-down: click a bar to see the breakdown
- Tooltips: hover for precise values (reduce label clutter)
- Cross-filtering: clicking one chart filters all others on the dashboard

## Data Storytelling

### Narrative Structure
1. **Setup**: Here's where we are (current state, metric value)
2. **Conflict**: Here's the problem (trend going wrong, gap vs target)
3. **Resolution**: Here's what we should do (recommendation backed by data)

### Annotation Best Practices
- Annotate the specific insight, not just the data
- Bad annotation: "Q3 2025" / Good annotation: "Launch drove 40% spike in signups"
- Use callout boxes for key numbers
- Highlight the most important data point (different color, larger size)

## Common Visualization Mistakes

- **Truncated y-axis on bar charts**: Makes small differences look huge
- **Pie charts with > 5 slices**: Unreadable — use horizontal bar instead
- **Too many colors**: Max 6-7 distinct colors per chart
- **3D charts**: Never — they distort perception of values
- **Dual y-axes**: Confusing and easily misleading — use two separate charts
- **Missing context**: Always show comparison (vs last period, vs target)
- **Chartjunk**: Remove gridlines, borders, legends unless necessary
