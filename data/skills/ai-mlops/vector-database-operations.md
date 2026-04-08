---
name: Vector Database Operations
description: Design, operate, and optimize vector databases for semantic search, RAG, and similarity applications
version: "1.0.0"
author: ROOT
tags: [mlops, vector-database, embeddings, RAG, semantic-search, similarity]
platforms: [all]
difficulty: intermediate
---

# Vector Database Operations

Store and retrieve high-dimensional embeddings at scale for semantic search,
RAG systems, recommendation engines, and similarity applications.

## Core Concepts

- **Embedding**: Dense vector representation of text/image/audio (e.g., 1536-dimensional float array)
- **Similarity search**: Find K nearest neighbors by cosine similarity or Euclidean distance
- **ANN (Approximate Nearest Neighbor)**: Trades perfect accuracy for massive speed gains
- **Index**: Data structure for efficient similarity search (HNSW, IVF, LSH)

## Database Comparison

| Database | Scale | Best For | Latency | Cost |
|----------|-------|---------|---------|------|
| Pinecone | Billions | Production RAG, managed | ~5ms | SaaS |
| Weaviate | Hundreds of millions | GraphQL + vectors | ~10ms | Open/SaaS |
| Qdrant | Hundreds of millions | Rust performance, filtering | ~3ms | Open/SaaS |
| Chroma | Millions | Local development, prototyping | ~1ms | Open source |
| pgvector | Tens of millions | Already using PostgreSQL | ~50ms | Free |
| FAISS | Billions (offline) | Batch similarity, research | <1ms | Open source |
| Milvus | Billions | Kubernetes-native scale | ~5ms | Open source |

## Setting Up Qdrant (Recommended Open-Source)

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import uuid

client = QdrantClient("localhost", port=6333)

# Create collection
client.create_collection(
    collection_name="knowledge_base",
    vectors_config=VectorParams(
        size=1536,                # OpenAI text-embedding-3-small dimension
        distance=Distance.COSINE  # Cosine similarity (best for text)
    )
)

# Index documents
def index_documents(documents: list[dict]):
    embeddings = get_embeddings([d["text"] for d in documents])

    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding.tolist(),
            payload={
                "text": doc["text"],
                "source": doc.get("source"),
                "category": doc.get("category"),
                "created_at": doc.get("created_at")
            }
        )
        for doc, embedding in zip(documents, embeddings)
    ]

    client.upsert(collection_name="knowledge_base", points=points)
```

## Similarity Search

```python
from openai import OpenAI

openai_client = OpenAI()

def semantic_search(query: str, top_k: int = 5, filters: dict = None):
    """Retrieve most semantically similar documents."""
    # Get query embedding
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=query
    )
    query_vector = response.data[0].embedding

    # Build optional filter
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    search_filter = None
    if filters:
        search_filter = Filter(
            must=[FieldCondition(key=k, match=MatchValue(value=v))
                  for k, v in filters.items()]
        )

    # Search
    results = client.search(
        collection_name="knowledge_base",
        query_vector=query_vector,
        limit=top_k,
        query_filter=search_filter,
        with_payload=True
    )

    return [
        {"text": r.payload["text"], "score": r.score, "source": r.payload.get("source")}
        for r in results
    ]
```

## RAG System Implementation

```python
from anthropic import Anthropic

anthropic = Anthropic()

def rag_query(user_question: str, top_k: int = 5) -> str:
    """Retrieval-Augmented Generation pipeline."""
    # 1. Retrieve relevant context
    context_docs = semantic_search(user_question, top_k=top_k)

    # 2. Format context for LLM
    context_str = "\n\n".join([
        f"Source: {doc['source']}\n{doc['text']}"
        for doc in context_docs
    ])

    # 3. Generate grounded response
    response = anthropic.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": f"""Answer the question using ONLY the provided context.
If the answer isn't in the context, say "I don't have information about this."

Context:
{context_str}

Question: {user_question}"""
        }]
    )
    return response.content[0].text
```

## Chunking Strategies

```python
# Fixed-size chunking (simplest)
def chunk_fixed(text: str, size: int = 512, overlap: int = 50) -> list[str]:
    tokens = tokenizer.encode(text)
    chunks = []
    for i in range(0, len(tokens), size - overlap):
        chunk = tokenizer.decode(tokens[i:i + size])
        chunks.append(chunk)
    return chunks

# Semantic chunking (better quality)
def chunk_by_paragraph(text: str, max_tokens: int = 512) -> list[str]:
    paragraphs = text.split("\n\n")
    chunks, current, current_len = [], [], 0
    for para in paragraphs:
        para_len = len(tokenizer.encode(para))
        if current_len + para_len > max_tokens and current:
            chunks.append("\n\n".join(current))
            current, current_len = [], 0
        current.append(para)
        current_len += para_len
    if current:
        chunks.append("\n\n".join(current))
    return chunks
```

## Index Configuration and Performance

### HNSW Parameters (Qdrant/Weaviate)
```python
# Higher ef_construction = better index quality, slower build
# Higher m = more connections per node, better recall, more memory
client.update_collection(
    collection_name="knowledge_base",
    hnsw_config={"m": 16, "ef_construct": 100}  # Standard settings
    # Production: {"m": 32, "ef_construct": 200} for better recall
)
```

### Payload Indexing for Filtered Search
```python
# Create index on frequently filtered fields
client.create_payload_index(
    collection_name="knowledge_base",
    field_name="category",
    field_schema="keyword"   # For exact match filtering
)
client.create_payload_index(
    collection_name="knowledge_base",
    field_name="created_at",
    field_schema="datetime"  # For range queries
)
```

## Maintenance Operations

```python
# Delete outdated documents
client.delete(
    collection_name="knowledge_base",
    points_selector=Filter(
        must=[FieldCondition(key="source", match=MatchValue(value="old_docs_v1"))]
    )
)

# Update existing document (upsert by ID)
client.upsert(
    collection_name="knowledge_base",
    points=[PointStruct(id=existing_id, vector=new_embedding, payload=new_payload)]
)

# Monitor collection health
info = client.get_collection("knowledge_base")
print(f"Vectors: {info.vectors_count}, Indexed: {info.indexed_vectors_count}")
```

## Quality Evaluation

```python
# Retrieval quality metrics
def evaluate_retrieval(test_queries: list, ground_truth: list, k: int = 5):
    results = []
    for query, relevant_doc_ids in zip(test_queries, ground_truth):
        retrieved = semantic_search(query, top_k=k)
        retrieved_ids = [r["id"] for r in retrieved]

        # Recall@K: what fraction of relevant docs were retrieved
        recall_at_k = len(set(retrieved_ids) & set(relevant_doc_ids)) / len(relevant_doc_ids)
        # MRR: position of first relevant result
        mrr = next((1/(i+1) for i, id in enumerate(retrieved_ids) if id in relevant_doc_ids), 0)
        results.append({"recall@k": recall_at_k, "mrr": mrr})

    return pd.DataFrame(results).mean().to_dict()
```
