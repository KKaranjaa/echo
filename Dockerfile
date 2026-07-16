FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies for psycopg2, ffmpeg, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Collect static files at build time so WhiteNoise can serve them.
# We use placeholder values so Django can start without real credentials.
RUN DJANGO_SETTINGS_MODULE=echo.settings.production \
    SECRET_KEY=build-only-placeholder \
    DATABASE_URL=sqlite:////tmp/build.db \
    python manage.py collectstatic --noinput

COPY start.sh .
RUN chmod +x start.sh

EXPOSE 8000

CMD ["./start.sh"]
