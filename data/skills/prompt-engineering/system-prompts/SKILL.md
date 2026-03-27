---
name: system-prompts
description: Design effective system prompts for LLM interactions
version: 1.0.0
author: ROOT
tags: [prompts, llm, engineering, ai]
platforms: [darwin, linux, win32]
---

# System Prompt Engineering

## When to Use
When ROOT needs to craft prompts for LLM calls (reflection, extraction, generation).

## Prompt Anatomy
- ROLE: Tell the LLM who it is and what it does
- CONTEXT: Provide all relevant background information
- TASK: What to do
- FORMAT: Exact output structure (JSON, markdown, bullet points)
- CONSTRAINTS: Length limits, style, things to avoid

## Best Practices
- Be specific about output format (especially JSON)
- Include "Return empty array [] if nothing" for extraction tasks
- Use "thinking" tier for complex analysis, "fast" for simple extraction
- Keep system prompts under 2000 tokens for efficiency
