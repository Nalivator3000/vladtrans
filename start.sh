#!/bin/bash
set -e

echo "=== STARTUP DEBUG ==="
echo "PORT=$PORT"
echo "DATABASE_URL=$DATABASE_URL"
echo "REDIS_URL=$REDIS_URL"
echo "OPENAI_API_KEY=${OPENAI_API_KEY:0:10}..."
echo "Python: $(python --version)"
echo ""

echo "=== TESTING IMPORTS ==="
python -c "
import sys
print('sys.path:', sys.path)

print('Importing FastAPI...')
from fastapi import FastAPI
print('FastAPI OK')

print('Importing config...')
from app.core.config import settings
print('Config OK')

print('Importing app.main...')
from app.main import app
print('app.main OK')
"

echo ""
echo "=== RUNNING DB MIGRATIONS ==="
python scripts/init_db.py

echo ""
echo "=== STARTING UVICORN on port $PORT ==="
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --log-level debug
