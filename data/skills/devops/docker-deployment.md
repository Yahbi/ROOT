---
name: Docker Deployment
description: Multi-stage builds, Docker Compose, health checks, and volume management
version: "1.0.0"
author: ROOT
tags: [devops, docker, deployment, containers, compose]
platforms: [all]
---

# Docker Deployment

Containerize applications with production-ready Docker practices.

## Multi-Stage Builds

### Pattern
```dockerfile
# Stage 1: Build
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime
FROM python:3.12-slim
COPY --from=builder /install /usr/local
COPY . /app
WORKDIR /app
USER nonroot
CMD ["python", "-m", "backend.main"]
```

### Benefits
- Final image contains only runtime dependencies (smaller, more secure)
- Build tools and dev dependencies excluded from production image
- Typical 2-5x image size reduction

### Best Practices
- Pin base image versions: `python:3.12.3-slim` not `python:3.12`
- Use `.dockerignore` to exclude `.git`, `__pycache__`, `.env`, `tests/`
- Run as non-root user in production (create with `useradd`)
- Order layers by change frequency: deps first, code last (cache optimization)

## Docker Compose

### Production Compose Structure
```yaml
services:
  app:
    build: .
    ports: ["9000:9000"]
    environment:
      - DATABASE_URL=sqlite:///data/app.db
    volumes:
      - app-data:/app/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: "1.0"
```

## Health Checks

### Application-Level
- `/health`: Returns 200 + version + basic status (lightweight, < 100ms)
- `/ready`: Returns 200 only when app can serve traffic (DB connected, models loaded)
- Orchestrators (Docker, K8s) use these to route traffic and restart unhealthy containers

### Health Check Design
- Check database connectivity (simple query like `SELECT 1`)
- Check external API reachability if critical
- Set reasonable timeouts (10s) — a slow health check is worse than a failed one
- Return structured JSON: `{"status": "healthy", "version": "1.0.0", "uptime": 3600}`

## Volume Management

### Data Persistence
- Use named volumes for data that must survive container restarts
- Mount specific directories, not the entire container filesystem
- SQLite databases: volume mount the data directory, set WAL mode

### Backup Strategy
1. Stop or pause writes to the container
2. Copy volume data: `docker cp container:/app/data ./backup/`
3. Or use volume backup tools: `docker run --rm -v app-data:/data -v $(pwd):/backup alpine tar czf /backup/data.tar.gz /data`
4. Schedule daily backups via cron or CI/CD pipeline

## Security Checklist

- [ ] Non-root user in Dockerfile
- [ ] No secrets in image layers (use runtime environment variables or secrets)
- [ ] Base image scanned for CVEs (Trivy, Snyk)
- [ ] Read-only filesystem where possible (`read_only: true` in compose)
- [ ] Network isolation: only expose necessary ports
- [ ] Resource limits set (memory, CPU) to prevent noisy neighbor
