#!/bin/bash
# ============================================
# 🤖 Programmer's Multi-LLM Chatbot - Launcher
# ============================================

# Get the directory where this script lives
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 Starting Programmer's Multi-LLM Chatbot..."
echo "📂 Project: $SCRIPT_DIR"
echo ""

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "⚠️  Virtual environment not found. Creating one..."
    python3 -m venv venv
    source venv/bin/activate
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

echo "✅ Virtual environment activated: $(python3 --version)"
echo "🌐 Launching app..."
echo ""

python3 app.py
