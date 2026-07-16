#!/bin/bash
# Start Celery worker in background
celery -A echo worker --loglevel=info --concurrency=1 &

# Start Celery beat in background
celery -A echo beat --loglevel=info &

# Start Gunicorn in foreground
exec gunicorn echo.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120
