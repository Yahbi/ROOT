---
name: Model Evaluation
description: Evaluating LLM outputs using automated metrics, human evaluation, and A/B testing
version: "1.0.0"
author: ROOT
tags: [ai-engineering, evaluation, metrics, LLM, quality]
platforms: [all]
---

# LLM Output Evaluation

Systematically measure and compare LLM output quality across tasks.

## Automated Metrics

### Text Similarity
- **BLEU**: n-gram precision vs reference — good for translation, weak for open-ended tasks
- **ROUGE-L**: longest common subsequence — better for summarization
- **BERTScore**: semantic similarity via contextual embeddings — correlates better with human judgment
- **Exact Match**: binary correctness — use for factoid QA, code output, classification

### Task-Specific
- **Code**: pass@k (functional correctness on test cases), cyclomatic complexity
- **Summarization**: ROUGE-1/2/L, factual consistency score (NLI-based)
- **Classification**: precision, recall, F1 per class, confusion matrix
- **RAG**: faithfulness (claims supported by context), answer relevance, retrieval recall

## Human Evaluation Framework

1. **Define rubric**: 1-5 scale on each dimension (accuracy, helpfulness, fluency, safety)
2. **Calibrate raters**: have 3+ raters score 20 shared examples, measure inter-rater agreement (Cohen's kappa > 0.6)
3. **Blind evaluation**: raters do not know which model produced which output
4. **Side-by-side comparison**: show outputs from model A and B, ask "which is better and why"
5. **Sample size**: minimum 100 examples for statistical significance at 95% confidence

## A/B Testing in Production

1. **Split traffic** 50/50 between current model and challenger
2. **Track metrics**: user satisfaction (thumbs up/down), task completion rate, follow-up questions (fewer = better)
3. **Run duration**: minimum 1 week or 1000 interactions per variant
4. **Statistical test**: two-proportion z-test for binary metrics, Mann-Whitney U for ratings
5. **Decision**: deploy challenger if p < 0.05 and effect size > minimum meaningful difference

## LLM-as-Judge

- Use a stronger model (e.g., GPT-4/Claude Opus) to evaluate weaker model outputs
- Provide explicit scoring criteria in the judge prompt
- Randomize output order to avoid position bias
- Validate judge accuracy against human ratings on 50+ examples first
- Be aware: LLM judges tend to prefer longer, more verbose outputs

## Evaluation Cadence

- **Pre-deployment**: full eval suite (automated + human) on held-out test set
- **Weekly**: automated metrics on production sample (100+ interactions)
- **Monthly**: human evaluation on stratified sample of edge cases
- **Quarterly**: full benchmark refresh with updated test data
