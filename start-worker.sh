#!/bin/bash
set -e

echo "=== CELERY WORKER STARTUP ==="
echo "REDIS_URL=$REDIS_URL"
echo "Python: $(python --version)"

exec celery -A app.core.celery_app worker \
    --loglevel=info \
    --concurrency=3 \
    --queues=celery \
    -n worker@%h
