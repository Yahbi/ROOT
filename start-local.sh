#!/bin/bash
# ROOT Quick Start — run this on your local machine
# Usage: bash start-root.sh

set -e

echo "🚀 Starting ROOT v1.0.0..."

# Clone if not already cloned
if [ ! -d "ROOT" ]; then
    echo "📥 Cloning from GitHub..."
    git clone https://github.com/Yahbi/ROOT.git
    cd ROOT
    git checkout claude/diagnose-system-issues-3XA1e
else
    cd ROOT
    git pull origin claude/diagnose-system-issues-3XA1e
fi

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt 2>/dev/null || pip3 install -r requirements.txt

# Copy env if missing
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "⚠️  Created .env from template — edit it to add your API keys"
fi

# Start Ollama if available
if command -v ollama &>/dev/null; then
    ollama serve &>/dev/null &
    sleep 2
    ollama pull gemma3:4b 2>/dev/null || true
    echo "✅ Ollama running with Gemma 3 4B"
fi

# Start ROOT
echo ""
echo "============================================"
echo "  ROOT v1.0.0 — ASTRA Intelligence"
echo "  Opening: http://localhost:9000"
echo "============================================"
echo ""

# Open browser automatically
if command -v open &>/dev/null; then
    (sleep 5 && open http://localhost:9000) &
elif command -v xdg-open &>/dev/null; then
    (sleep 5 && xdg-open http://localhost:9000) &
fi

python -m backend.main || python3 -m backend.main
