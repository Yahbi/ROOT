#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
echo "ROOT starting on http://127.0.0.1:9000"
exec uvicorn backend.main:app --host 127.0.0.1 --port 9000
