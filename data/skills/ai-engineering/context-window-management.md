---
name: Context Window Management
description: Techniques for managing long contexts in LLM applications
version: "1.0.0"
author: ROOT
tags: [ai-engineering, context, compression, chunking, summarization]
platforms: [all]
---

# Context Window Management

Maximize LLM effectiveness by intelligently managing what fits in the context window.

## Context Budget Planning

### Token Allocation Strategy
- **System prompt**: 10-15% of window (instructions, persona, constraints)
- **Retrieved context**: 40-50% (RAG results, documents, code)
- **Conversation history**: 20-30% (recent turns, compressed older turns)
- **Output buffer**: 15-20% (reserve for model response)

### Monitoring Utilization
- Track token count per request using tiktoken or model-specific tokenizer
- Set compression trigger at 80-85% utilization
- Alert when context exceeds 90% — quality degrades near the limit

## Compression Techniques

### Summarization-Based Compression
1. Summarize older conversation turns into 2-3 sentence recaps
2. Replace full documents with extracted key points and quotes
3. Use hierarchical summarization for very long documents (chunk → summarize → merge)

### Sliding Window with Anchors
- Keep first message (system prompt) and last N turns always present
- Compress middle turns progressively — most recent = full, older = summary
- Pin critical facts as "anchor memories" that never get compressed

### Semantic Chunking
- Split documents at semantic boundaries (paragraphs, sections, topics)
- Score each chunk by relevance to the current query (cosine similarity)
- Include only top-K most relevant chunks, ordered by document position

## Strategies by Use Case

| Use Case | Strategy | Key Technique |
|----------|----------|---------------|
| Long conversations | Rolling summary | Compress turns older than 10 messages |
| Document Q&A | Selective retrieval | Embed + retrieve top 5-8 chunks |
| Code analysis | AST-aware chunking | Include function signatures + relevant bodies |
| Multi-document | Map-reduce | Summarize each doc, then synthesize |

## Implementation Checklist

1. Measure baseline token usage across typical requests
2. Implement token counting before each LLM call
3. Build compression pipeline: detect threshold → select strategy → compress → verify
4. Test that compression preserves critical information (run eval suite)
5. Monitor compression ratio and response quality correlation
6. Set up fallback: if context still too large after compression, truncate oldest non-essential content

## Common Pitfalls

- Compressing too aggressively — losing critical details that change the answer
- Not accounting for output tokens in the budget
- Treating all context as equally important (system prompt > recent turns > old history)
- Ignoring that models attend less to middle content ("lost in the middle" effect)
- Placing the most important retrieved context at the beginning or end, not the middle
