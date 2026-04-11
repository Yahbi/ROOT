---
name: Fine-Tuning
description: When and how to fine-tune LLMs using LoRA, full fine-tuning, and data preparation
version: "1.0.0"
author: ROOT
tags: [ai-engineering, fine-tuning, LoRA, training, data-prep]
platforms: [all]
---

# LLM Fine-Tuning

Determine when fine-tuning is warranted and execute it effectively.

## Decision Framework: When to Fine-Tune

| Scenario | Better Approach |
|----------|----------------|
| Need domain-specific tone/style | Fine-tune |
| Need to follow a specific output format consistently | Fine-tune |
| Need factual knowledge about your domain | RAG (not fine-tuning) |
| Need to reduce latency (shorter prompts) | Fine-tune to internalize instructions |
| Have <100 training examples | Few-shot prompting instead |
| Have 500-10,000 labeled examples | LoRA fine-tuning |
| Have 50,000+ examples + compute budget | Full fine-tuning |

## Data Preparation

1. **Collect examples**: minimum 500 high-quality input/output pairs
2. **Format consistently**: use chat format (system, user, assistant messages)
3. **Deduplicate**: remove near-duplicates (>0.9 cosine similarity)
4. **Balance**: ensure no class represents >50% of examples
5. **Split**: 80% train, 10% validation, 10% held-out test
6. **Quality audit**: manually review 10% of training data for errors
7. **Contamination check**: ensure test examples are not in training set

## LoRA Fine-Tuning (Recommended Default)

- **What**: Low-Rank Adaptation — trains small adapter matrices, freezes base model
- **Rank (r)**: start with r=16, increase to 64 if underfitting
- **Alpha**: set alpha = 2*r as starting point
- **Target modules**: attention layers (q_proj, v_proj) for most tasks; add MLP for complex tasks
- **Learning rate**: 1e-4 to 3e-4 with cosine decay
- **Epochs**: 2-5 (watch validation loss — stop when it plateaus)
- **Tools**: Hugging Face PEFT, Axolotl, unsloth

## Full Fine-Tuning

- Reserve for cases where LoRA underperforms after hyperparameter search
- Learning rate: 1e-5 to 5e-5 (much lower than LoRA)
- Requires significantly more GPU memory (8xA100 for 7B model)
- Use gradient checkpointing + DeepSpeed ZeRO-3 to manage memory
- Risk of catastrophic forgetting — evaluate on general benchmarks too

## Evaluation After Fine-Tuning

- Compare fine-tuned vs base model on held-out test set
- Measure task-specific accuracy AND general capability (ensure no regression)
- Run safety evaluations (fine-tuning can weaken safety training)
- A/B test in production with 10% traffic before full rollout

## Common Pitfalls

- Training on too-few examples (underfits) or too-many epochs (overfits)
- Not validating data quality (garbage in = garbage out)
- Ignoring catastrophic forgetting on general tasks
- Fine-tuning when prompt engineering would suffice
