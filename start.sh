#!/bin/bash
cd /Users/yohan/Desktop/ROOT
source .venv/bin/activate
exec uvicorn backend.main:app --host 127.0.0.1 --port 9000
