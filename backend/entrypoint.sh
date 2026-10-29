#!/bin/sh
set -e

echo "🚀 [RP_ChatBot Backend] Starting container initialization..."

# Run Alembic migrations
echo "📦 [Alembic] Running database migrations..."
alembic upgrade head
echo "✅ [Alembic] Migrations completed successfully."

# Start FastAPI with Uvicorn
echo "🌐 [Uvicorn] Starting FastAPI application on 0.0.0.0:8000..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips="*"

