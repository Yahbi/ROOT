---
name: Prompt Optimization
description: Techniques for optimizing LLM prompts for accuracy, consistency, and structured output
version: "1.0.0"
author: ROOT
tags: [ai-engineering, prompts, LLM, chain-of-thought, few-shot]
platforms: [all]
---

# Prompt Optimization

Systematically improve LLM prompt quality to maximize accuracy, reduce hallucination, and ensure consistent output format.

## Core Techniques

### Chain-of-Thought (CoT)
- Add "Let's think step by step" or explicit reasoning scaffolds
- Break complex reasoning into numbered sub-problems
- For math/logic: require the model to show intermediate calculations
- **When to use**: Multi-step reasoning, math, code generation, complex analysis

### Few-Shot Examples
- Provide 3-5 input/output examples that cover edge cases
- Order examples from simple to complex
- Include at least one negative/tricky example to calibrate boundaries
- **When to use**: Classification, extraction, format-sensitive tasks

### Structured Output
- Define explicit JSON schema or markdown template in the prompt
- Use delimiters (```json, XML tags) to frame expected output
- Add "Respond ONLY with the JSON object, no explanation" for strict parsing
- Validate output against schema programmatically

## Optimization Process

1. **Baseline**: Write a naive prompt, test on 20+ diverse inputs, measure accuracy
2. **Error analysis**: Categorize failures (hallucination, format errors, missing info, wrong reasoning)
3. **Iterate**: Apply targeted fixes per failure category
4. **A/B test**: Compare original vs optimized on held-out test set
5. **Monitor**: Track production accuracy weekly, re-optimize when drift exceeds 5%

## Anti-Patterns to Avoid

- Vague instructions ("do a good job") instead of specific criteria
- Overloading a single prompt with too many tasks (split into chain)
- Not specifying output format (leads to inconsistent parsing)
- Using examples that are too similar (model overfits to pattern)
- Prompt injection vulnerability: always sanitize user input before embedding

## Temperature and Sampling Guide

| Task | Temperature | Top-p | Notes |
|------|------------|-------|-------|
| Classification | 0.0 | 1.0 | Deterministic, single correct answer |
| Code generation | 0.0-0.2 | 0.95 | Low creativity, high correctness |
| Creative writing | 0.7-1.0 | 0.9 | Higher diversity desired |
| Data extraction | 0.0 | 1.0 | Must be precise and reproducible |
| Brainstorming | 0.8-1.0 | 0.95 | Want divergent ideas |
