---
name: LLM Fine-Tuning
description: Fine-tune large language models using LoRA, QLoRA, and instruction tuning for domain-specific tasks
version: "1.0.0"
author: ROOT
tags: [mlops, llm, fine-tuning, LoRA, QLoRA, instruction-tuning, PEFT]
platforms: [all]
difficulty: advanced
---

# LLM Fine-Tuning

Adapt pre-trained LLMs to specific tasks or domains efficiently using parameter-efficient
fine-tuning (PEFT) techniques that avoid full model retraining.

## When to Fine-Tune vs. Prompt Engineer

| Scenario | Approach |
|----------|---------|
| General task, GPT-4 works well | Use prompting — skip fine-tuning |
| Need specific style/format consistently | Few-shot prompting or fine-tune |
| Domain-specific knowledge not in base model | Fine-tune on domain data |
| Latency requirement < 200ms | Fine-tune smaller model |
| Cost reduction needed (10-50x cheaper inference) | Fine-tune smaller model |
| Task requires > 10k examples to be reliable | Fine-tune |
| Safety/alignment requirement | RLHF or DPO fine-tune |

## Data Preparation

### Instruction Dataset Format (Alpaca-style)
```json
[
  {
    "instruction": "Classify this customer message as positive, negative, or neutral.",
    "input": "The product arrived 3 days late and the packaging was damaged.",
    "output": "Negative"
  },
  {
    "instruction": "Summarize this financial report in 2 sentences.",
    "input": "Q3 2026 revenue increased 23%...",
    "output": "Revenue grew 23% year-over-year driven by cloud segment..."
  }
]
```

### Dataset Quality Requirements
- Minimum 100 examples for task fine-tuning (1000+ recommended)
- Diverse coverage of edge cases and variations
- Consistent format and quality — garbage in, garbage out
- Held-out validation set (10-20% of data) for evaluation
- No train/test leakage (deduplicate across splits)

### Data Augmentation
```python
# Paraphrase existing examples to expand dataset
def augment_example(example: dict, llm) -> list:
    return [
        {**example, "instruction": paraphrase(example["instruction"], llm)},
        {**example, "input": paraphrase(example["input"], llm) if example["input"] else ""},
    ]
```

## LoRA (Low-Rank Adaptation)

Fine-tune only a small fraction of parameters (typically 0.1-1% of total).

```python
from peft import LoraConfig, get_peft_model, TaskType
from transformers import AutoModelForCausalLM

base_model = AutoModelForCausalLM.from_pretrained("meta-llama/Llama-3-8B")

lora_config = LoraConfig(
    task_type=TaskType.CAUSAL_LM,
    r=16,               # Rank — higher = more parameters, more capacity
    lora_alpha=32,      # Scaling factor (alpha/r = actual learning rate scale)
    lora_dropout=0.1,
    target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],  # Which layers to adapt
    bias="none"
)

model = get_peft_model(base_model, lora_config)
model.print_trainable_parameters()
# Trainable params: 8,388,608 (0.64% of total) — 155x fewer than full fine-tune
```

## QLoRA (4-bit Quantized LoRA)

Train on consumer GPUs by quantizing the base model to 4-bit.

```python
from transformers import BitsAndBytesConfig
import torch

quantization_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4"  # Normal float 4-bit quantization
)

model = AutoModelForCausalLM.from_pretrained(
    "meta-llama/Llama-3-8B",
    quantization_config=quantization_config,
    device_map="auto"
)
# Llama 3 8B: normally 16GB VRAM → 5GB with QLoRA (fits on 8GB GPU)
```

## Training Configuration

```python
from transformers import TrainingArguments
from trl import SFTTrainer

training_args = TrainingArguments(
    output_dir="./fine-tuned-model",
    num_train_epochs=3,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,  # Effective batch = 16
    warmup_steps=100,
    learning_rate=2e-4,             # Higher than full fine-tune for LoRA
    fp16=True,
    logging_steps=50,
    evaluation_strategy="steps",
    eval_steps=200,
    save_steps=500,
    load_best_model_at_end=True,
    metric_for_best_model="eval_loss"
)

trainer = SFTTrainer(
    model=model,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset,
    peft_config=lora_config,
    dataset_text_field="text",      # Column with formatted prompt+response
    max_seq_length=2048,
    args=training_args,
)
trainer.train()
```

## DPO (Direct Preference Optimization)

Fine-tune from human preferences without RLHF complexity.

```json
// DPO dataset format: preferred vs. rejected pairs
{
  "prompt": "Explain quantum entanglement simply.",
  "chosen": "Quantum entanglement is like having two magic coins...",
  "rejected": "Quantum entanglement refers to a phenomenon whereby..."
}
```

```python
from trl import DPOTrainer

dpo_trainer = DPOTrainer(
    model=model,
    ref_model=ref_model,  # The original pre-fine-tuned model
    beta=0.1,             # Controls deviation from reference model
    train_dataset=dpo_dataset,
    processing_class=tokenizer,
    args=training_args
)
dpo_trainer.train()
```

## Evaluation

```python
# Task-specific metrics
from evaluate import load

# For classification tasks
accuracy_metric = load("accuracy")
f1_metric = load("f1")

# For generation tasks
rouge = load("rouge")  # Summarization
bleu = load("bleu")    # Translation

# For LLM alignment
from openai import OpenAI
def llm_as_judge(prompt: str, response: str, reference: str) -> float:
    """Use GPT-4 to score response quality 1-10"""
    ...
```

## Deployment After Fine-Tuning

1. **Merge LoRA adapters** into base model for cleaner deployment:
   ```python
   merged_model = model.merge_and_unload()
   merged_model.save_pretrained("./final-model")
   ```

2. **Quantize for inference**: Convert to GGUF (llama.cpp) or GPTQ for fast serving
3. **Benchmark latency**: Confirm it meets SLA (test with Locust or k6)
4. **A/B test against baseline** before full rollout

## Compute Requirements

| Model Size | LoRA GPU | QLoRA GPU | Training Time (1k examples) |
|------------|----------|-----------|----------------------------|
| 7B params | 16GB | 8GB | ~30 min |
| 13B params | 32GB | 16GB | ~60 min |
| 70B params | 2x80GB | 40GB | ~6 hours |
| 405B params | 8x80GB | 4x80GB | ~48 hours |
