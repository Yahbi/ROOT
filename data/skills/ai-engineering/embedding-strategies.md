---
name: Embedding Strategies
description: Choosing and optimizing embedding models for search, clustering, and similarity
version: "1.0.0"
author: ROOT
tags: [ai-engineering, embeddings, vector-search, similarity, semantic]
platforms: [all]
---

# Embedding Strategies

Select, optimize, and deploy embedding models for semantic search, clustering, and similarity tasks.

## Model Selection Guide

| Model | Dimensions | Speed | Quality | Best For |
|-------|-----------|-------|---------|----------|
| text-embedding-3-small (OpenAI) | 1536 | Fast | Good | General purpose, cost-sensitive |
| text-embedding-3-large (OpenAI) | 3072 | Medium | Excellent | High-accuracy retrieval |
| BGE-large-en-v1.5 | 1024 | Medium | Very Good | Self-hosted, privacy-sensitive |
| E5-mistral-7b-instruct | 4096 | Slow | Excellent | Best open-source quality |
| all-MiniLM-L6-v2 | 384 | Very Fast | Good | Low-latency, edge deployment |
| Cohere embed-v3 | 1024 | Fast | Excellent | Multilingual, search + classification |

## Optimization Techniques

### Dimensionality Reduction
- **Matryoshka embeddings**: truncate to 256/512 dims with minimal quality loss (supported by text-embedding-3-*)
- **PCA**: reduce dimensions post-hoc, keep 95% variance (typically 256 dims suffices)
- **Trade-off**: lower dims = faster search + less storage, but check retrieval quality

### Quantization
- **Binary quantization**: 32x storage reduction, 95%+ retrieval quality retained
- **Scalar quantization (int8)**: 4x reduction, 99%+ quality retained
- **Use with oversampling**: retrieve 4x candidates, then re-rank with full-precision embeddings

### Instruction-Tuned Embeddings
- Prefix queries with task instruction: "search_query: ..." vs "search_document: ..."
- E5 and BGE models benefit significantly from task-specific prefixes
- Improves retrieval by 5-10% on domain-specific benchmarks

## Indexing Strategies

- **Flat (brute-force)**: exact search, use for <100K vectors
- **IVF (Inverted File)**: partition into clusters, search nearest clusters — good for 100K-10M vectors
- **HNSW**: graph-based approximate search — best quality/speed trade-off for most use cases
- **Tuning nprobe/ef_search**: higher = more accurate but slower, tune on your data

## Evaluation

1. Prepare 100+ query-document relevance pairs from your domain
2. Measure Recall@5, Recall@10, and MRR on this test set
3. Compare 2-3 embedding models head-to-head
4. Factor in latency and cost (API calls, self-hosting compute)
5. Re-evaluate quarterly as new models release frequently

## Common Mistakes

- Using a general-purpose model for highly specialized domain without evaluation
- Not normalizing embeddings before cosine similarity (most models output normalized, but verify)
- Embedding very long documents without chunking (information gets diluted)
- Mixing different embedding models in the same vector store index
