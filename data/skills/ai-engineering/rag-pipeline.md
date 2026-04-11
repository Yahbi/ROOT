---
name: RAG Pipeline
description: Building retrieval-augmented generation pipelines for grounded LLM responses
version: "1.0.0"
author: ROOT
tags: [ai-engineering, RAG, retrieval, embeddings, vector-db]
platforms: [all]
---

# RAG Pipeline Design

Build retrieval-augmented generation systems that ground LLM responses in factual, up-to-date source documents.

## Architecture Components

1. **Document Ingestion** — parse, chunk, embed, and index source documents
2. **Query Processing** — transform user query into effective retrieval query
3. **Retrieval** — find top-k relevant chunks from vector store
4. **Context Assembly** — rank, deduplicate, and format retrieved chunks
5. **Generation** — LLM produces answer grounded in retrieved context
6. **Evaluation** — measure retrieval quality and answer faithfulness

## Chunking Strategies

| Strategy | Chunk Size | Overlap | Best For |
|----------|-----------|---------|----------|
| Fixed-size | 512 tokens | 50 tokens | General purpose, fast |
| Sentence-based | 3-5 sentences | 1 sentence | Conversational content |
| Semantic | Variable | By topic | Technical documents |
| Recursive split | 1000 chars | 200 chars | Code + prose mixed |
| Document-aware | Section-level | Headers retained | Structured docs (manuals, specs) |

## Retrieval Optimization

- **Hybrid search**: combine dense embeddings (semantic) + BM25 (keyword) with reciprocal rank fusion
- **Query expansion**: use LLM to generate 3 paraphrases, retrieve for each, merge results
- **Metadata filtering**: pre-filter by date, source, category before vector search
- **Re-ranking**: use cross-encoder (e.g., ms-marco-MiniLM) to re-score top-50 into top-5
- **MMR (Maximal Marginal Relevance)**: balance relevance with diversity in results

## Common Failure Modes

- **Retrieval miss**: relevant doc exists but is not retrieved — fix chunking or embedding model
- **Context poisoning**: irrelevant chunk confuses the LLM — add re-ranking step
- **Hallucination despite context**: LLM ignores retrieved text — add "Answer ONLY based on the provided context"
- **Stale data**: index not updated — implement incremental indexing pipeline
- **Over-retrieval**: too many chunks dilute signal — reduce k, improve re-ranking

## Evaluation Metrics

- **Retrieval**: Recall@k, MRR, nDCG — does the system find the right chunks?
- **Faithfulness**: Does the answer only contain claims supported by retrieved context?
- **Relevance**: Does the answer actually address the user's question?
- **Latency**: End-to-end time from query to response (target <3s for interactive)
