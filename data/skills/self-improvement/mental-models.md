---
name: Mental Models
description: First principles, inversion, second-order thinking, and decision-making models
version: "1.0.0"
author: ROOT
tags: [self-improvement, mental-models, first-principles, inversion, thinking]
platforms: [all]
---

# Mental Models

A toolkit of thinking frameworks for better reasoning and decision-making.

## First Principles Thinking

### What It Is
- Break problems down to their fundamental truths (physics-style reasoning)
- Reason up from fundamentals instead of reasoning by analogy ("that's how it's always been done")
- Strip away assumptions to see the core problem clearly

### How to Apply
1. State the problem or belief
2. List all assumptions baked into the current approach
3. For each assumption, ask: "Is this fundamentally true, or just convention?"
4. Build a solution from only the truths that survive scrutiny

### Example
- Assumption: "Building a SaaS product requires a large engineering team"
- First principles: What do you actually need? A solution that runs, charges money, and serves users
- Fundamental truth: You need code, hosting, and a payment processor
- Insight: One person can ship a SaaS product using existing tools (Vercel, Stripe, GPT API)

## Inversion

### What It Is
- Instead of asking "How do I succeed?", ask "How would I guarantee failure?"
- Avoid the failure modes, and success becomes more likely
- Charlie Munger: "All I want to know is where I'm going to die, so I'll never go there"

### Application
| Forward Question | Inverted Question |
|-----------------|-------------------|
| How do we grow revenue? | How would we destroy revenue? (ignore customers, stop marketing, break the product) |
| How do we ship fast? | How would we guarantee slow delivery? (no priorities, scope creep, no tests) |
| How do we build a great team? | How would we ensure everyone quits? (micromanage, no growth, unclear direction) |

## Second-Order Thinking

### What It Is
- First-order: What happens if I do X?
- Second-order: What happens after that? What are the consequences of the consequences?
- Most people stop at first-order — second-order is where competitive advantage lives

### Examples
| Decision | First-Order Effect | Second-Order Effect |
|----------|-------------------|---------------------|
| Cut prices 50% | More customers | Attracts price-sensitive users who churn, devalues brand |
| Hire fast to meet deadline | Team gets bigger | Onboarding overhead, communication costs increase, velocity may drop |
| Add every requested feature | Users get what they want | Product becomes complex, onboarding suffers, maintenance burden grows |

## Other Essential Models

### Pareto Principle (80/20)
- 80% of results come from 20% of efforts
- Identify the vital few activities that drive most of the outcome
- Apply ruthlessly: what 20% of features serve 80% of users?

### Circle of Competence
- Know what you know well, and operate primarily within that area
- At the edges: proceed with caution, seek expert input
- Outside: don't pretend expertise — delegate or learn before acting
- Expanding your circle is valuable, but be honest about its current boundaries

### Map Is Not the Territory
- Models, metrics, and plans are abstractions — they simplify reality
- The dashboard says "system healthy" but users are complaining — trust reality
- All models are wrong, some are useful — use them with awareness of their limitations

### Occam's Razor
- The simplest explanation that fits the facts is usually correct
- Don't build complex theories when a simple one explains the evidence
- In engineering: the simplest architecture that meets requirements is best

### Margin of Safety
- Build in buffer for the unexpected (time estimates, financial projections, system capacity)
- If your plan only works under perfect conditions, it's a fragile plan
- The bigger the consequences of failure, the larger the margin should be

## Using Mental Models

### Building Your Toolkit
1. Learn 2-3 models deeply (first principles, inversion, second-order)
2. Practice applying them to daily decisions for 30 days
3. Gradually add new models (one per month)
4. Cross-reference: use multiple models on the same problem for richer analysis
5. The goal: pattern-match to the right model quickly, then think rigorously within it
