---
name: ML Infrastructure Scaling
description: Scale ML training and inference infrastructure using GPUs, distributed training, and cloud auto-scaling
version: "1.0.0"
author: ROOT
tags: [mlops, infrastructure, GPU, distributed-training, scaling, kubernetes]
platforms: [all]
difficulty: advanced
---

# ML Infrastructure Scaling

Scale ML systems from a single GPU to distributed clusters without sacrificing
training efficiency or inference latency.

## Training Scaling Strategies

### Single GPU Optimization (Start Here)
```python
# Mixed precision training — 2x speedup, 50% memory reduction
from torch.cuda.amp import autocast, GradScaler

scaler = GradScaler()

for batch in dataloader:
    with autocast():  # Auto float16 for eligible ops
        outputs = model(batch)
        loss = criterion(outputs, labels)

    scaler.scale(loss).backward()
    scaler.step(optimizer)
    scaler.update()

# Gradient checkpointing — trade compute for memory
model.gradient_checkpointing_enable()
# Allows training 3-4x larger models at cost of ~30% slower training
```

### Data Parallelism (Multiple GPUs, Same Node)
```python
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP

# Initialize process group
dist.init_process_group(backend="nccl")

model = DDP(model, device_ids=[local_rank])  # Each GPU gets a full model copy
# Gradients synchronized automatically across all GPUs

# Launch: torchrun --nproc_per_node=8 train.py
```

### Tensor Parallelism (Very Large Models > 70B)
```python
# DeepSpeed + Megatron-LM for sharding a single model across GPUs
import deepspeed

ds_config = {
    "zero_optimization": {
        "stage": 3,  # ZeRO-3: shard params + gradients + optimizer states
        "overlap_comm": True,
        "contiguous_gradients": True,
    },
    "bf16": {"enabled": True},
    "train_micro_batch_size_per_gpu": 1,
    "gradient_accumulation_steps": 32,
}

model_engine, optimizer, _, _ = deepspeed.initialize(
    model=model, config=ds_config
)
```

## Inference Scaling

### Batching for Throughput
```python
# Dynamic batching — collect requests, process in batch
import asyncio
from collections import defaultdict

class BatchInferenceServer:
    def __init__(self, model, max_batch_size=32, max_wait_ms=50):
        self.model = model
        self.max_batch_size = max_batch_size
        self.max_wait_ms = max_wait_ms
        self.queue = asyncio.Queue()

    async def predict(self, input_data):
        future = asyncio.Future()
        await self.queue.put((input_data, future))
        return await future

    async def batch_processor(self):
        while True:
            batch, futures = [], []
            # Collect up to max_batch_size items or wait max_wait_ms
            deadline = asyncio.get_event_loop().time() + self.max_wait_ms / 1000
            while len(batch) < self.max_batch_size:
                try:
                    timeout = max(0, deadline - asyncio.get_event_loop().time())
                    input_data, future = await asyncio.wait_for(self.queue.get(), timeout=timeout)
                    batch.append(input_data)
                    futures.append(future)
                except asyncio.TimeoutError:
                    break

            if batch:
                results = self.model.predict_batch(batch)
                for future, result in zip(futures, results):
                    future.set_result(result)
```

### Model Quantization for Inference
```python
import torch

# INT8 quantization — 4x smaller model, 2-4x faster inference
from torch.quantization import quantize_dynamic

quantized_model = quantize_dynamic(
    model,
    {torch.nn.Linear},  # Quantize linear layers
    dtype=torch.qint8
)
quantized_model.save("model_int8.pt")

# ONNX export for framework-independent serving
torch.onnx.export(
    model,
    sample_input,
    "model.onnx",
    opset_version=17,
    dynamic_axes={"input": {0: "batch_size"}}  # Variable batch size
)
```

## Kubernetes ML Cluster Configuration

```yaml
# GPU node pool for training jobs
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ml-training-worker
spec:
  replicas: 4
  template:
    spec:
      containers:
      - name: trainer
        image: ml-training:v1.2.0
        resources:
          requests:
            nvidia.com/gpu: "1"
            memory: "32Gi"
            cpu: "8"
          limits:
            nvidia.com/gpu: "1"
            memory: "64Gi"
      nodeSelector:
        cloud.google.com/gke-accelerator: nvidia-tesla-a100
      tolerations:
      - key: nvidia.com/gpu
        operator: Exists
        effect: NoSchedule
```

```yaml
# Horizontal Pod Autoscaler for inference
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: inference-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ml-inference
  minReplicas: 2
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: External
    external:
      metric:
        name: inference_queue_depth
      target:
        type: Value
        value: "100"  # Scale up when queue > 100 requests
```

## Cost Optimization

### Spot/Preemptible Instances for Training
```python
# Checkpointing for fault-tolerant training on spot instances
class CheckpointCallback:
    def __init__(self, checkpoint_dir: str, frequency: int = 500):
        self.checkpoint_dir = checkpoint_dir
        self.frequency = frequency

    def on_step_end(self, step: int, model, optimizer, scheduler):
        if step % self.frequency == 0:
            torch.save({
                "step": step,
                "model_state": model.state_dict(),
                "optimizer_state": optimizer.state_dict(),
                "scheduler_state": scheduler.state_dict(),
            }, f"{self.checkpoint_dir}/checkpoint_{step}.pt")
            print(f"Checkpoint saved at step {step}")
```

### Cost Tracking per Job
```python
INSTANCE_COSTS = {
    "p3.2xlarge": 3.06,     # $/hour, 1x V100
    "p3.8xlarge": 12.24,    # $/hour, 4x V100
    "p4d.24xlarge": 32.77,  # $/hour, 8x A100
}

def estimate_training_cost(instance_type: str, training_hours: float) -> dict:
    hourly = INSTANCE_COSTS.get(instance_type, 0)
    return {
        "estimated_cost": hourly * training_hours,
        "cost_per_epoch": hourly * training_hours / n_epochs,
    }
```

## GPU Utilization Monitoring

```bash
# Real-time GPU monitoring
watch -n 1 nvidia-smi

# Python GPU monitoring in training loop
import pynvml

pynvml.nvmlInit()
handle = pynvml.nvmlDeviceGetHandleByIndex(0)

def log_gpu_metrics():
    mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
    utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
    return {
        "gpu_utilization": utilization.gpu,
        "memory_used_gb": mem_info.used / 1e9,
        "memory_free_gb": mem_info.free / 1e9,
    }

# Target: GPU utilization > 80% during training
# Low GPU utilization signals data loading bottleneck — fix DataLoader workers
```

## Scaling Decision Matrix

| Model Size | Training Hardware | Inference Hardware |
|-----------|-------------------|-------------------|
| < 100M params | Single A10G (24GB) | CPU or T4 (16GB) |
| 1-7B params | Single A100 (80GB) | A10G (24GB) |
| 7-70B params | 4-8x A100 with DDP | 2-4x A100 |
| 70B+ params | 8-64x A100 with FSDP | 4-8x H100 |
