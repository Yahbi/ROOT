---
name: model-selection
description: Choose the right LLM model tier for each task
version: 1.0.0
author: ROOT
tags: [llm, models, performance, cost]
platforms: [darwin, linux, win32]
---

# Model Selection Strategy

From ECC performance rules + DeepSeek + llama.cpp knowledge.

## When to Use
- Before every LLM call, select the appropriate tier

## Cloud Tiers (Anthropic)

### Haiku 4.5 — Fast & Cheap
- 90% of Sonnet capability at 3x cost savings
- Use for: lightweight agents, frequent invocations, auto-extraction, classification
- Temperature: 0.2-0.3 for factual, 0.5-0.7 for creative

### Sonnet 4.6 — Best Coding Model
- Main development work, orchestration, complex tasks
- Use for: conversation, code generation, task routing
- Temperature: 0.5-0.7 default

### Opus 4.6 — Deepest Reasoning
- Complex architecture, maximum reasoning, research
- Use for: self-reflection, planning, critical decisions
- Temperature: 0.3-0.5 for analysis, 0.7 for creative

## Local Tiers (No API needed)

### llama.cpp
- Best performance, C/C++, hardware-optimized
- Quantization: 4-bit for speed, 8-bit for quality
- Apple Metal acceleration on M-series

### GPT4All
- Easiest setup, desktop app + Python library
- GGUF format, no GPU required
- Good for: offline operation, privacy-sensitive tasks

### DeepSeek-V3
- 671B params (37B activated), open-source
- Competitive with GPT-4/Claude
- Best for: self-hosted at scale

## Context Window Management
- Avoid last 20% of context for large tasks
- Use context compression at 85% utilization
- Single-file edits tolerate higher utilization
