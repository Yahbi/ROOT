---
name: NLP Techniques
description: Tokenization, NER, sentiment analysis, summarization, and text processing
version: "1.0.0"
author: ROOT
tags: [machine-learning, NLP, text-processing, sentiment, summarization]
platforms: [all]
---

# NLP Techniques

Core natural language processing methods for extracting meaning from text data.

## Text Preprocessing Pipeline

### Standard Steps
1. **Normalize**: lowercase, Unicode normalization (NFKC), fix encoding issues
2. **Tokenize**: split text into tokens (words, subwords, or characters)
3. **Clean**: remove HTML tags, URLs, special characters (task-dependent)
4. **Stopword removal**: remove common words (only for bag-of-words methods, never for LLMs)
5. **Stemming/Lemmatization**: reduce words to root form (only for traditional ML)

### Tokenization Methods
| Method | Use Case | Example |
|--------|---------|---------|
| Whitespace | Quick baseline | "New York" → ["New", "York"] |
| WordPiece | BERT-family models | "playing" → ["play", "##ing"] |
| BPE | GPT-family, LLaMA | "lowest" → ["low", "est"] |
| SentencePiece | Multilingual models | Language-agnostic subword |

## Named Entity Recognition (NER)

### Entity Types
- **PER**: Person names
- **ORG**: Organizations, companies
- **LOC**: Locations, addresses
- **DATE/TIME**: Temporal expressions
- **MONEY**: Monetary values
- **Custom**: Domain-specific (drug names, stock tickers, product codes)

### Approaches
- **SpaCy**: Fast, rule-based + statistical, good for production
- **Hugging Face transformers**: BERT-based NER, best accuracy
- **LLM extraction**: Prompt-based, no training needed, flexible but slower
- **Regex + rules**: For structured entities (email, phone, dates)

## Sentiment Analysis

### Methods (by complexity)
1. **Lexicon-based**: VADER, TextBlob — fast, no training, moderate accuracy
2. **Fine-tuned classifier**: BERT/RoBERTa fine-tuned on labeled sentiment data
3. **LLM zero-shot**: Prompt GPT/Claude with rating instructions — flexible, expensive
4. **Aspect-based**: Extract sentiment per aspect ("food was great, service was slow")

### Financial Sentiment
- Use FinBERT or domain-adapted models — general sentiment models miss financial context
- "Revenue missed expectations" is bearish — general NLP might rate "revenue" as neutral
- Always calibrate on domain-specific labeled data before production use

## Text Summarization

### Extractive Summarization
- Select the most important sentences from the original text
- Methods: TextRank (graph-based), TF-IDF scoring, BERT sentence scoring
- Pro: no hallucination, fast. Con: may not flow naturally

### Abstractive Summarization
- Generate new text that captures the key points
- Methods: BART, T5, Pegasus, or LLM prompting
- Pro: more natural and concise. Con: can hallucinate details
- Always verify factual claims in summaries against source

### Map-Reduce for Long Documents
1. Split document into chunks (1000-2000 tokens each)
2. Summarize each chunk independently (map step)
3. Concatenate chunk summaries and summarize again (reduce step)
4. Repeat reduce if still too long

## Practical Tips

- Always evaluate NLP models on domain-specific test sets (not just benchmarks)
- Preprocessing that helps traditional ML (stemming, stopwords) often hurts transformer models
- For production: batch inference is 5-10x cheaper per item than real-time
- Multilingual: use multilingual models (XLM-R, mBERT) rather than translating to English first
