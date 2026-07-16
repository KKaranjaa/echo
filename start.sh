#!/bin/bash

# Run database migrations
python manage.py migrate --noinput

# Start Celery worker in the background
celery -A echo worker --loglevel=info --concurrency=1 &

# Start Celery beat in the background
celery -A echo beat --loglevel=info &

# Start Gunicorn in the foreground
exec gunicorn echo.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120
