# Echo

**Echo** is a Django 5 application for audio upload, transcription (Faster-Whisper),
AI summarisation (Anthropic Claude), and real-time chat over WebSockets.

---

## Quick Start (3 commands)

```bash
# 1. Clone the repository
git clone https://github.com/your-org/echo.git && cd echo

# 2. Copy and configure the environment file
cp .env.example .env
# ↳ Edit .env and set SECRET_KEY and ANTHROPIC_API_KEY at minimum

# 3. Start all services
docker compose up --build
```

The app will be available at **http://localhost:8000**  
Health check: **http://localhost:8000/health/** → `{"status": "ok"}`

---

## Services

| Service        | Port | Description                        |
|----------------|------|------------------------------------|
| `web`          | 8000 | Django 5 development server        |
| `postgres`     | 5432 | PostgreSQL 16 database             |
| `redis`        | 6379 | Redis 7 (Celery broker + channels) |
| `celery-worker`| —    | Celery async task worker           |

---

## Project Structure

```
echo/
├── apps/
│   ├── core/           # Health endpoint, shared utilities
│   ├── uploads/        # File upload handling
│   ├── transcription/  # Faster-Whisper transcription tasks
│   ├── summarisation/  # Claude summarisation tasks
│   ├── chat/           # Real-time chat (Channels/WebSocket)
│   └── sessions/       # User session management
├── echo/
│   ├── settings/
│   │   ├── base.py        # Shared settings
│   │   ├── development.py # SQLite, DEBUG=True
│   │   └── production.py  # PostgreSQL, Redis, security hardening
│   ├── asgi.py
│   ├── celery.py
│   ├── urls.py
│   └── wsgi.py
├── docker-compose.yml
├── Dockerfile
├── manage.py
└── requirements.txt
```

---

## Environment Variables

| Variable            | Required | Description                        |
|---------------------|----------|------------------------------------|
| `SECRET_KEY`        | ✅       | Django secret key                  |
| `DEBUG`             | ✅       | `True` for development             |
| `DATABASE_URL`      | ✅       | Postgres DSN (production)          |
| `REDIS_URL`         | ✅       | Redis DSN for Celery + Channels    |
| `ANTHROPIC_API_KEY` | ✅       | Claude API key                     |
| `ALLOWED_HOSTS`     | Prod     | Comma-separated allowed hostnames  |

---

## Development Without Docker

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

---

## Running Tests

```bash
docker compose exec web python manage.py test
```

---

## Deploying ECHO to Render

**Prerequisites:** GitHub account, Render account (free at render.com)

**Steps:**
1. Push your code to a GitHub repository
2. Go to render.com → New → Blueprint → connect your repo
   Render reads `render.yaml` and creates all services automatically
3. In the Render dashboard, add `SECRET_KEY` and `ANTHROPIC_API_KEY` to the `echo-web` service environment variables
4. Trigger a manual deploy on `echo-web`
5. Your app is live at `https://echo-web.onrender.com`

That's it. Render handles HTTPS, deploys on every git push, and restarts crashed services automatically.

To check it's working: visit `https://your-app.onrender.com/health/`
Should return: `{"status": "ok", "db": "ok", "redis": "ok", "version": "1.0.0"}`

**Estimated monthly cost on Render:**
- echo-web (Starter): $7/mo
- echo-celery (Starter): $7/mo
- echo-celery-beat (Starter): $7/mo
- Postgres (free tier): $0
- Redis (free tier): $0
- Disk 10GB: $1.25/mo

**Total: ~$22/mo** while building. Scale down celery-beat to free tier if budget is tight — cleanup just won't run automatically.
