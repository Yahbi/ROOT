---
name: Data Storytelling
description: Chart selection, narrative arc, audience adaptation, executive summaries
version: "1.0.0"
author: ROOT
tags: [communication, data-storytelling, visualization, charts, executive-summary]
platforms: [all]
---

# Data Storytelling

Transform data analysis into compelling narratives that drive decisions and action.

## Chart Selection

### Choose by Data Relationship
| Relationship | Chart Type | Example |
|-------------|-----------|---------|
| Comparison | Bar chart (vertical/horizontal) | Revenue by product, team velocity |
| Trend over time | Line chart | Monthly active users, error rates |
| Part-to-whole | Stacked bar, treemap (not pie charts) | Budget allocation, traffic sources |
| Distribution | Histogram, box plot | Response time distribution, salary ranges |
| Correlation | Scatter plot | Ad spend vs revenue, test coverage vs bug count |
| Ranking | Horizontal bar (sorted) | Top 10 customers, feature usage frequency |
| Geographic | Choropleth map | Users by country, regional sales |

### Anti-Patterns
- **Pie charts**: Hard to compare similar-sized slices. Use horizontal bar instead
- **3D charts**: Distort perception. Always use 2D
- **Dual y-axes**: Misleading. Use two separate charts or normalize the scales
- **Too many colors**: Limit to 5-7 categories. Group the rest as "Other"
- **Truncated axes**: Starting y-axis at non-zero exaggerates differences (label clearly if needed)

### Design Principles
- Title states the insight, not the data: "Revenue grew 40% in Q4" not "Q4 Revenue"
- Label directly on data (not in a legend that requires eye-tracking back and forth)
- Highlight the key data point with color contrast; gray out supporting data
- Remove chartjunk: grid lines, borders, backgrounds that add no information

## Narrative Arc

### The Three-Act Structure for Data
```
Act 1: Setup (What is the situation?)
  "Our API latency has been increasing over the past 6 months."
  [Show: trend line of P99 latency over time]

Act 2: Conflict (Why does it matter?)
  "This is causing a 12% increase in user drop-off on the checkout page."
  [Show: correlation between latency spikes and conversion drops]

Act 3: Resolution (What should we do?)
  "By adding a caching layer, we can reduce P99 latency by 60% within 2 weeks."
  [Show: projected improvement based on load testing data]
```

### Story Framework
1. **Context**: What is the background? What does the audience already know?
2. **Insight**: What did the data reveal? What is surprising or important?
3. **Impact**: So what? Why should the audience care? Quantify in their terms
4. **Action**: What should happen next? Be specific and concrete

## Audience Adaptation

### Tailoring Depth by Audience
| Audience | They Care About | Presentation Style |
|----------|----------------|-------------------|
| Executive | Business impact, ROI, risk | 3-5 slides, headline + key number, recommendation |
| Technical lead | Architecture, trade-offs, evidence | Detailed charts, methodology, confidence intervals |
| Product manager | User impact, timeline, scope | User metrics, feature implications, roadmap |
| Board/investors | Growth, market position, financials | Trend lines, benchmarks, forward projections |

### Executive Summary Formula
```
[Metric] [changed by] [amount] [over period], [driven by] [cause].
This [impacts] [business outcome] by [quantified amount].
We recommend [specific action] which will [expected result] by [date].

Example:
"API error rate increased 300% over 2 weeks, driven by a third-party
payment provider outage. This is causing an estimated $15K/day in lost
transactions. We recommend implementing a backup payment provider, which
will reduce single-point-of-failure risk by next Friday."
```

### The "So What?" Test
After every slide or data point, ask: "So what does this mean for the audience?"
- "Our test coverage is 72%" → so what?
- "72% coverage means 28% of code paths are untested, concentrated in the payment module" → so what?
- "This creates a 3x higher risk of payment bugs reaching production, costing an average of $5K per incident" → actionable

## Presentation Structure

### For Data-Heavy Presentations
1. **Lead with the conclusion** (executives read the ending first anyway)
2. **Support with 2-3 key charts** (not 20 charts — pick the most compelling)
3. **Anticipate objections** (prepare backup slides for "but what about...")
4. **End with a clear ask** (decision needed, budget approved, action taken)

### The Appendix Strategy
- Main deck: 5-8 slides with key insights and recommendations
- Appendix: 20+ slides with detailed methodology, data tables, edge cases
- Present the main deck. Reference appendix only when asked
- Sends the message: "I did rigorous analysis but I respect your time"

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Showing all the data | Curate: show only what supports the insight |
| Leading with methodology | Lead with the conclusion, methodology in appendix |
| Using technical jargon | Translate to business impact (latency → user drop-off → revenue) |
| No clear recommendation | Every data presentation should end with "we should do X" |
| Death by bullet points | Replace bullets with a chart or a single bold statement |
| Correlation presented as causation | Explicitly state: "correlated with" not "caused by" |
