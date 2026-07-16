#!/bin/bash

# Run database migrations
python manage.py migrate --noinput

# Start Celery worker in the background (concurrency=1 to limit RAM)
celery -A echo worker --loglevel=warning --concurrency=1 &

# Start Gunicorn in the foreground (1 worker to stay under 512MB free tier)
exec gunicorn echo.wsgi:application --bind 0.0.0.0:$PORT --workers 1 --timeout 120
