# AI Content Platform

Платформа автоматизированного сбора, AI-переработки (DeepSeek) и публикации контента в Telegram и VK/MAX каналы.

## Быстрый старт

### Docker (рекомендуется)

```bash
cp .env.example .env
# Заполните DEEPSEEK_API_KEY, ADMIN_USERNAME/ADMIN_PASSWORD, TELEGRAM_BOT_TOKEN и др.

docker compose up -d --build
docker compose exec backend alembic upgrade head
docker compose exec backend python scripts/seed_data.py
```

- Панель: http://localhost:3000 (или http://localhost через nginx)
- API docs: http://localhost:8000/docs
- Вход в панель: логин/пароль из `ADMIN_USERNAME` и `ADMIN_PASSWORD` в `.env`

### Локально без Docker

```bash
cp .env.example .env
./scripts/dev-local.sh
```

Панель: http://127.0.0.1:5173 · API: http://127.0.0.1:8000/docs

Подробнее: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md#локальная-разработка)

## Стек

- Backend: Python 3.12, FastAPI, SQLAlchemy 2 async, Celery, Redis, PostgreSQL
- Frontend: Vue 3, Vite, Pinia, Tailwind
- AI: DeepSeek API

## Документация

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/API.md](docs/API.md)
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
- [docs/DOKPLOY.md](docs/DOKPLOY.md) — деплой на VPS через Dokploy
