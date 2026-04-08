---
name: Tool Use Patterns
description: Designing tool-using LLM agents with robust schema design, error handling, and chaining
version: "1.0.0"
author: ROOT
tags: [ai-engineering, tools, agents, function-calling, chaining]
platforms: [all]
---

# Tool Use Patterns

Design reliable tool-using agents that can plan, execute, and recover from failures.

## Tool Schema Design

### Principles
- **Descriptive names**: `search_documents` not `search` — the model selects tools by name
- **Rich descriptions**: explain when to use the tool, not just what it does
- **Typed parameters**: use enums for constrained choices, required vs optional fields
- **Minimal surface area**: fewer tools with clear purposes beat many overlapping tools

### Parameter Design
- Default values for optional params reduce hallucinated arguments
- Use string enums over free-text when options are known (`sort: "asc" | "desc"`)
- Include `reason` parameter to force the model to justify tool selection
- Limit parameter count to 5-7 — more causes selection errors

## Execution Patterns

### ReAct (Reason + Act)
1. Model reasons about what tool to call and why
2. Tool executes and returns result
3. Model observes result and decides next action or final answer
4. Loop until task complete or max iterations reached

### Plan-then-Execute
1. Model generates full plan (ordered list of tool calls)
2. Execute plan sequentially, feeding each result to next step
3. If any step fails, re-plan from current state
4. Best for multi-step tasks with predictable structure

### Parallel Tool Calls
- When tools are independent, call them simultaneously
- Merge results before next reasoning step
- Example: search three databases in parallel, then synthesize

## Error Handling

### Graceful Degradation
- Return structured error messages: `{"error": "rate_limited", "retry_after": 30}`
- Model should retry with backoff on transient errors
- Provide fallback tools: if API search fails, fall back to local search
- Set max retries per tool (3) and max total tool calls per request (15)

### Validation Layer
- Validate tool arguments before execution (type check, range check)
- Validate tool outputs before returning to model (schema conformance)
- Log all tool calls for debugging and audit

## Tool Chaining Patterns

| Pattern | Description | Example |
|---------|-------------|---------|
| Sequential | Output of tool A feeds into tool B | Search → Fetch → Summarize |
| Conditional | Tool choice depends on prior result | Check cache → if miss → query API |
| Iterative | Repeat tool until condition met | Refine search until >3 relevant results |
| Fan-out/merge | Parallel calls, merge results | Query 3 sources → combine |

## Testing Tool-Using Agents

1. Unit test each tool independently with known inputs/outputs
2. Test tool selection: given a prompt, does the model pick the right tool?
3. Test error recovery: inject failures, verify graceful degradation
4. Test chain completion: end-to-end scenarios with multiple tools
5. Monitor token cost per tool chain — optimize verbose tool outputs
