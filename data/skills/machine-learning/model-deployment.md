---
name: ML Model Deployment
description: Serving ML models in production with batch, real-time, and A/B testing patterns
version: "1.0.0"
author: ROOT
tags: [machine-learning, deployment, serving, MLOps, production]
platforms: [all]
---

# ML Model Deployment

Move models from notebooks to production with reliable serving, monitoring, and iteration.

## Serving Patterns

### Batch Prediction
- Run predictions on a schedule (hourly, daily) against a dataset
- Store results in a database or data warehouse for downstream consumption
- Best for: recommendations, risk scores, email targeting, reporting
- Tools: Airflow/Dagster scheduled job, Spark for large datasets

### Real-Time Prediction
- Model serves predictions via REST/gRPC API with < 100ms latency
- Best for: fraud detection, search ranking, content moderation
- Tools: FastAPI + model in memory, TensorFlow Serving, Triton, SageMaker endpoints
- Cache frequent predictions (Redis) to reduce compute cost

### Streaming Prediction
- Model consumes events from Kafka/Kinesis and produces predictions continuously
- Best for: IoT anomaly detection, real-time personalization
- Tools: Flink + embedded model, Kafka Streams

## Model Packaging

### Serialization Formats
| Format | Framework | Size | Loading Speed |
|--------|----------|------|---------------|
| ONNX | Cross-framework | Small | Fast |
| TorchScript | PyTorch | Medium | Fast |
| SavedModel | TensorFlow | Large | Medium |
| Pickle/Joblib | Scikit-learn | Small | Fast |
| MLflow Model | Any | Varies | Medium |

### Containerization
1. Create Dockerfile with pinned dependency versions
2. Include model artifacts (weights, config, preprocessors)
3. Health check endpoint: `/health` returns model version and status
4. Multi-stage build: build dependencies first, copy only runtime artifacts

## A/B Testing in Production

### Implementation
1. Deploy candidate model alongside current champion
2. Route traffic: 90% champion / 10% candidate (or use bandit allocation)
3. Define success metric and minimum sample size before starting
4. Run for statistical significance (typically 1-4 weeks)
5. Promote candidate if it wins, roll back if it loses

### Guardrails
- Set automatic rollback if candidate error rate > champion + 5%
- Monitor latency — candidate should not degrade response time
- Shadow mode first: run candidate in parallel but don't serve its predictions to users

## Monitoring in Production

### Key Metrics
- **Prediction latency**: p50, p95, p99 response times
- **Throughput**: predictions per second
- **Error rate**: failed predictions / total predictions
- **Data drift**: input feature distributions shifting from training data
- **Concept drift**: model accuracy degrading over time

### Drift Detection
- Compare live feature distributions to training set using KS-test or PSI
- Alert when Population Stability Index (PSI) > 0.2 for any feature
- Retrain trigger: when model accuracy drops below baseline - 2% on holdout set

## Deployment Checklist

1. Model artifact versioned and stored in model registry (MLflow, W&B)
2. Preprocessing pipeline packaged with model (avoid training-serving skew)
3. API contract documented: input schema, output schema, error codes
4. Load tested: confirmed latency and throughput meet SLA under peak load
5. Monitoring dashboards: latency, errors, drift, business metrics
6. Rollback plan: one-click revert to previous model version
