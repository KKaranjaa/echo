#!/bin/bash
# Start Celery worker in the background
celery -A echo worker --loglevel=info --concurrency=1 &

# Start Celery beat in the background
celery -A echo beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler &

# Start Gunicorn in the foreground
exec gunicorn echo.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120
