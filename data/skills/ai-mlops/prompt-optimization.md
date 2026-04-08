---
name: Prompt Optimization for Production
description: Systematically improve LLM prompt quality through evaluation, iteration, and automated testing
version: "1.0.0"
author: ROOT
tags: [mlops, prompt-engineering, LLM, evaluation, optimization, production]
platforms: [all]
difficulty: intermediate
---

# Prompt Optimization for Production

Treat prompts as code: version control them, measure their performance,
and improve them through systematic iteration rather than intuition.

## Prompt Evaluation Framework

### Define Metrics First

```python
# Before optimizing, define what "good" means
EVALUATION_METRICS = {
    "accuracy": "Fraction of responses matching expected output",
    "groundedness": "Response uses only information from provided context",
    "completeness": "All required fields present in structured output",
    "latency": "p95 response time < 5 seconds",
    "cost": "Average tokens per response",
    "format_compliance": "Output matches required schema 100% of the time",
}
```

### Test Dataset

```python
# Create golden dataset of 50-200 representative examples
golden_dataset = [
    {
        "input": {"user_query": "What is the refund policy?", "context": "...docs..."},
        "expected_output": "Refunds are available within 30 days of purchase.",
        "criteria": ["mentions 30 days", "no hallucination", "concise"],
    },
    # ... more examples covering edge cases
]
```

## Automated Evaluation

### LLM-as-Judge

```python
from anthropic import Anthropic

client = Anthropic()

def evaluate_response(
    prompt_template: str,
    test_case: dict,
    judge_model: str = "claude-opus-4-5"
) -> dict:
    # Run the prompt
    actual_output = run_prompt(prompt_template, test_case["input"])

    # Judge the response
    judge_prompt = f"""
Evaluate this AI response on a scale of 1-10 for each criterion.
Return JSON with scores and brief reasoning.

Criteria: {test_case['criteria']}

User Input: {test_case['input']}
Expected: {test_case['expected_output']}
Actual: {actual_output}

Return: {{"scores": {{"criterion": score}}, "overall": score, "issues": ["..."]}}
"""
    judgment = client.messages.create(
        model=judge_model, max_tokens=500,
        messages=[{"role": "user", "content": judge_prompt}]
    )
    return json.loads(judgment.content[0].text)
```

### Exact Match and Regex Testing

```python
def evaluate_structured_output(response: str, expected_schema: dict) -> dict:
    """For JSON/structured outputs — deterministic evaluation."""
    try:
        parsed = json.loads(response)
        missing_fields = set(expected_schema.keys()) - set(parsed.keys())
        type_errors = {k: f"Expected {expected_schema[k]}, got {type(parsed.get(k)).__name__}"
                       for k in expected_schema if k in parsed
                       and not isinstance(parsed[k], expected_schema[k])}
        return {
            "valid_json": True,
            "missing_fields": list(missing_fields),
            "type_errors": type_errors,
            "score": 1.0 - (len(missing_fields) + len(type_errors)) / len(expected_schema)
        }
    except json.JSONDecodeError:
        return {"valid_json": False, "score": 0.0}
```

## Prompt Versioning

```python
# Store prompts in a registry with version history
PROMPT_REGISTRY = {
    "customer_support_v1": {
        "template": "You are a helpful support agent...",
        "version": "1.0.0",
        "created": "2026-03-01",
        "eval_score": 0.72,
        "status": "archived"
    },
    "customer_support_v2": {
        "template": "You are an expert customer success agent...",
        "version": "2.0.0",
        "created": "2026-04-01",
        "eval_score": 0.89,
        "status": "production"
    }
}

# Always version prompts with git — treat as source code
# Store in prompts/ directory, include version in filename
# e.g., prompts/customer_support_v2.txt
```

## Systematic Improvement Techniques

### 1. Chain-of-Thought (CoT) for Reasoning Tasks

```
Before CoT:
  "Classify this transaction as fraud or legitimate: {transaction}"

After CoT:
  "Analyze this transaction step by step:
   1. Check: Is the amount unusual for this user? {avg_spend}
   2. Check: Is the location consistent with history? {location_history}
   3. Check: Is the merchant category expected? {merchant_categories}
   4. Based on the above analysis, classify as FRAUD or LEGITIMATE.
   Transaction: {transaction}"
```

### 2. Few-Shot Examples

```python
def build_few_shot_prompt(task_description: str, examples: list, query: str) -> str:
    examples_str = "\n\n".join([
        f"Input: {ex['input']}\nOutput: {ex['output']}"
        for ex in examples
    ])
    return f"""{task_description}

Here are some examples:

{examples_str}

Now process this:
Input: {query}
Output:"""
```

### 3. Structured Output Enforcement

```python
# Force JSON output with explicit schema
STRUCTURED_PROMPT = """
Extract the following information from the customer message.
Return ONLY a JSON object matching this exact schema:

{{
  "intent": "question|complaint|request|compliment",
  "urgency": "low|medium|high|critical",
  "topics": ["list", "of", "topics"],
  "sentiment_score": 0.0-1.0,
  "requires_human": true|false
}}

Customer message: {message}

JSON:"""
```

### 4. Persona and Context Priming

```python
EFFECTIVE_SYSTEM_PROMPT = """You are ROOT, an expert financial analyst with 15 years of
experience in equity research and quantitative trading.

Your responses:
- Are precise and use specific numbers when available
- Cite relevant financial metrics (P/E, EV/EBITDA, etc.)
- Acknowledge uncertainty explicitly ("based on available data...")
- Do NOT give personalized investment advice
- Are structured with clear headers for complex analyses

Format: Use markdown tables for comparisons, code blocks for formulas."""
```

## A/B Testing Prompts

```python
import hashlib
import random

def select_prompt_variant(user_id: str, experiment_name: str) -> str:
    """Deterministic prompt variant assignment for A/B testing."""
    hash_val = int(hashlib.md5(f"{user_id}:{experiment_name}".encode()).hexdigest(), 16)
    bucket = hash_val % 100

    if bucket < 50:
        return "prompt_variant_A"
    else:
        return "prompt_variant_B"

# Track results per variant
def log_prompt_result(variant: str, success: bool, latency_ms: int):
    metrics_store.increment(f"prompt_ab/{variant}/attempts")
    if success:
        metrics_store.increment(f"prompt_ab/{variant}/successes")
    metrics_store.record(f"prompt_ab/{variant}/latency", latency_ms)
```

## Cost Optimization

```python
# Estimate and monitor prompt cost
COST_PER_1K_TOKENS = {
    "claude-haiku": {"input": 0.00025, "output": 0.00125},
    "claude-sonnet-4-6": {"input": 0.003, "output": 0.015},
    "claude-opus-4-5": {"input": 0.015, "output": 0.075},
}

def estimate_monthly_cost(
    model: str,
    avg_input_tokens: int,
    avg_output_tokens: int,
    requests_per_day: int
) -> dict:
    costs = COST_PER_1K_TOKENS[model]
    daily_cost = requests_per_day * (
        avg_input_tokens / 1000 * costs["input"] +
        avg_output_tokens / 1000 * costs["output"]
    )
    return {"daily_cost": daily_cost, "monthly_cost": daily_cost * 30}

# Optimization strategies:
# 1. Use Haiku for simple classification → Opus only for complex reasoning
# 2. Cache repeated prompt+response pairs (Redis, 1h TTL)
# 3. Batch similar requests when latency allows
# 4. Compress context with extractive summarization
```

## Evaluation Scorecard Template

```
Prompt: customer_support_v2
Date: 2026-04-08
Evaluator: automated + human spot-check (n=20)

Metrics:
  Overall score:      8.9 / 10
  Format compliance:  100% (50/50 valid JSON)
  Accuracy:           92% (46/50 correct)
  Groundedness:       94% (no hallucinations in 47/50)
  Latency (p95):      3.2 seconds
  Cost (per request): $0.0042

Issues found:
  - 3 cases where urgency = "low" when should be "medium"
  - 1 case where topics list was empty for ambiguous query

Next iteration:
  - Add example showing urgency escalation for shipping delays
  - Add fallback instruction for ambiguous queries
```
