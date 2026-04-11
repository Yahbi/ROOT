---
name: SEO Optimization
description: Technical SEO, content strategy, keyword research, and link building to drive organic traffic growth
category: business
difficulty: intermediate
version: "1.0.0"
author: ROOT
tags: [business, seo, organic-traffic, keyword-research, content-marketing, technical-seo, link-building]
platforms: [all]
---

# SEO Optimization

Build a systematic SEO program that drives compounding organic traffic growth through technical excellence, content strategy, and authority building.

## SEO Fundamentals

### How Google Ranks Pages
1. **Crawlability**: Can Googlebot access the page? (robots.txt, sitemaps, internal links)
2. **Indexability**: Should this page be indexed? (canonical tags, noindex directives)
3. **Relevance**: Does the content match search intent? (keywords, content depth, structure)
4. **Authority**: Do credible sites link to this page? (backlinks, domain authority)
5. **Experience**: Is the page fast, mobile-friendly, and trustworthy? (Core Web Vitals, HTTPS)

### Search Intent Types
| Intent | Example Query | Content Type |
|--------|-------------|--------------|
| **Informational** | "how to reduce churn" | Blog post, guide |
| **Navigational** | "HubSpot login" | Brand page |
| **Commercial Investigation** | "best CRM software 2024" | Comparison page |
| **Transactional** | "buy Salesforce license" | Product page, pricing |

## Keyword Research

### Process
1. **Seed keywords**: brainstorm core topics your product/service addresses
2. **Expand**: use tools (Ahrefs, Semrush, Google Keyword Planner) to find related terms
3. **Filter by intent**: focus on keywords matching buying-journey stages
4. **Prioritize by opportunity**: sort by (volume × difficulty) where difficulty is inversely weighted

### Keyword Metrics
| Metric | What It Means | Target |
|--------|-------------|--------|
| Monthly Search Volume | How many searches per month | > 200/month for most content |
| Keyword Difficulty (KD) | 0-100 score; harder = more competition | < 40 for new sites; < 70 for established |
| CPC | How much advertisers pay; indicates commercial value | Higher = more valuable keyword |
| SERP Features | Does Google show snippets, maps, shopping? | Target featured snippet opportunities |

### Keyword Classification
```python
keyword_strategy = {
    "bottom_of_funnel": {
        "examples": ["best X for Y", "X pricing", "X vs Y", "X alternatives"],
        "intent": "transactional/commercial",
        "priority": "highest",
        "content_type": "comparison pages, pricing pages",
    },
    "middle_of_funnel": {
        "examples": ["how to solve Z problem", "guide to X", "X best practices"],
        "intent": "informational",
        "priority": "high",
        "content_type": "long-form guides, tutorials",
    },
    "top_of_funnel": {
        "examples": ["what is X", "X explained", "why X matters"],
        "intent": "informational (awareness)",
        "priority": "medium",
        "content_type": "educational blog posts",
    },
}
```

## Technical SEO

### Core Web Vitals (Ranking Signals)
| Metric | What It Measures | Target | Tool |
|--------|-----------------|--------|------|
| LCP (Largest Contentful Paint) | Load speed of main content | < 2.5 seconds | PageSpeed Insights |
| FID (First Input Delay) → INP | Interactivity responsiveness | < 200ms INP | CrUX report |
| CLS (Cumulative Layout Shift) | Visual stability | < 0.1 | PageSpeed Insights |

### Technical SEO Checklist
```bash
# Check crawlability
curl -I https://yoursite.com/robots.txt
# Verify sitemap
curl https://yoursite.com/sitemap.xml

# Check HTTPS redirect
curl -I http://yoursite.com
# Should return 301 → https://yoursite.com

# Check canonical
curl -s https://yoursite.com/page | grep "canonical"
```

### Structured Data (Schema.org)
```html
<!-- Article schema for blog posts -->
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "How to Reduce Customer Churn by 30%",
  "datePublished": "2024-01-15",
  "dateModified": "2024-01-20",
  "author": {"@type": "Person", "name": "Jane Smith"},
  "publisher": {"@type": "Organization", "name": "Acme Inc", "logo": "..."},
  "description": "A step-by-step guide to identifying and reducing churn..."
}
</script>

<!-- FAQ schema for featured snippet potential -->
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "What is customer churn?",
      "acceptedAnswer": {"@type": "Answer", "text": "Customer churn is..."}
    }
  ]
}
</script>
```

### Crawl Budget Optimization
- Block non-SEO pages in `robots.txt`: `Disallow: /search?`, `Disallow: /admin/`
- Eliminate duplicate content with canonical tags
- Fix broken internal links (404s waste crawl budget)
- Flatten site architecture: every page reachable within 3 clicks from homepage
- Submit XML sitemap to Google Search Console

## On-Page SEO

### Content Optimization Framework
```markdown
## Page Optimization Checklist

### Target Keyword Placement
- [ ] Title tag: keyword near the beginning (< 60 characters)
- [ ] Meta description: compelling copy with keyword (< 155 characters)
- [ ] H1: exactly one, contains keyword
- [ ] H2s: use keyword variations and related terms
- [ ] First 100 words: include target keyword naturally
- [ ] URL: short, keyword-inclusive (/churn-reduction-strategies not /blog?id=123)
- [ ] Alt text on images: descriptive, keyword-relevant where natural

### Content Quality
- [ ] Satisfies the search intent (informational, commercial, etc.)
- [ ] Covers topic comprehensively (check what top 3 results include)
- [ ] Includes original data, examples, or unique perspective
- [ ] Readability: Flesch score > 60; short sentences and paragraphs
- [ ] Internal links: 3-5 links to related pages on your site
- [ ] External links: 2-3 authoritative external sources
```

### Title Tag Formulas
- How-to: `How to [Achieve Outcome] in [Timeframe] — [Brand]`
- Listicle: `[Number] [Adjective] [Category] for [Audience] ([Year])`
- Comparison: `[Product A] vs [Product B]: Which Is Better for [Use Case]?`
- Definition: `What Is [Keyword]? Definition, Examples, and [Related Topic]`

## Link Building

### Ethical Link Acquisition Strategies

| Strategy | Effort | Link Quality | Scalability |
|----------|--------|-------------|-------------|
| Digital PR (data studies) | High | Very High | Low |
| Guest posting | Medium | Medium-High | Medium |
| Resource page outreach | Medium | High | Medium |
| Broken link building | Medium | Medium | Medium |
| HARO / journalist outreach | Low-Medium | High | Medium |
| Product integrations | Low | High | Low |
| Community participation | Low | Low-Medium | High |

### Outreach Email Template
```
Subject: Your resource on [topic] — a quick suggestion

Hi [Name],

I found your guide on [specific topic] while researching [their topic].
In the section about [specific section], you link to [resource they link to].

I recently published [your resource], which covers [what makes it better:
more recent data, more depth, different angle]. It might be a good addition
for your readers.

You can check it out here: [URL]

Either way, great work on the [their resource] — [genuine specific compliment].

Best,
[Name]
```

## SEO Analytics

### KPIs to Track
| Metric | Tool | Target/Alert |
|--------|------|-------------|
| Organic sessions | GA4 | +10% MoM growth |
| Keyword rankings (tracked set) | Ahrefs/Semrush | % of keywords in top 3/10 |
| Click-through rate (CTR) | Google Search Console | > 3% average |
| Impressions growth | Search Console | Leading indicator of future traffic |
| Backlinks acquired (30d) | Ahrefs | > 10 new referring domains/month |
| Pages indexed | Search Console | < 5% of submitted pages not indexed |

### Content Audit Process (Quarterly)
1. Export all pages with organic traffic from GA4
2. Identify pages with: ranking drops, thin content, cannibalization issues
3. Prioritize: high-volume pages with declining traffic get updated first
4. Action types: refresh content, consolidate thin pages (301 redirect), expand coverage
5. Track: measure traffic change 90 days after update

### Rank Tracking Setup
```python
# Keywords to track for a SaaS product (example)
tracked_keywords = {
    "brand": ["your_brand_name", "your_brand_name reviews", "your_brand_name pricing"],
    "product": ["crm software", "best crm for startups", "salesforce alternative"],
    "competitor": ["hubspot alternative", "pipedrive vs salesforce"],
    "long_tail": ["how to manage sales pipeline", "crm workflow automation guide"],
}
# Check weekly with Ahrefs Rank Tracker or Semrush Position Tracking
```
