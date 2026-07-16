#!/bin/bash
# Start Celery worker in the background
celery -A echo worker --loglevel=info &

# Start Gunicorn in the foreground
exec gunicorn echo.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120
