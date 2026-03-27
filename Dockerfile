FROM python:3.12-slim

# System deps for aiohttp, numpy (vector store), and SQLite
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl sqlite3 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY backend/ backend/
COPY data/ data/
COPY .env* ./

# Create data dir if missing (persisted via volume)
RUN mkdir -p data/skills data/reflections data/hooks

# Health check — ROOT must respond within 10s
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:9000/api/health || exit 1

EXPOSE 9000

# Run with auto-reload disabled for production
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "9000", "--workers", "1"]
