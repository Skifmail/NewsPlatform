# Развёртывание

## Docker Compose (рекомендуется)

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec backend alembic upgrade head
docker compose exec backend python scripts/seed_data.py
```

Сервисы: `postgres`, `redis`, `backend`, `celery_worker`, `celery_beat`, `frontend`, `nginx`.

## Production (VPS / Dokploy)

```bash
cp .env.production.example .env
# заполните секреты, затем:
docker compose -f docker-compose.prod.yml up -d --build
```

Полная инструкция с переносом БД: [docs/DOKPLOY.md](DOKPLOY.md)

## Переменные окружения

Обязательные для MVP:

- `DATABASE_URL`, `REDIS_URL`
- `DEEPSEEK_API_KEY`
- `ADMIN_USERNAME`, `ADMIN_PASSWORD` — вход в панель
- `TELEGRAM_BOT_TOKEN` — для публикации

Опционально:

- `TELEGRAM_API_ID/HASH/PHONE` — Telethon парсинг
- `VK_ACCESS_TOKEN` — публикация во VK
- `MAX_BOT_TOKEN` — публикация в каналы MAX (см. ниже)
- `ALERT_BOT_TOKEN`, `ALERT_CHAT_ID` — уведомления

## MAX (каналы мессенджера)

После одобрения бота на [business.max.ru](https://business.max.ru):

1. Скопируйте токен бота в `.env`:
   ```env
   MAX_BOT_TOKEN=ваш_токен
   ```
2. Добавьте бота **администратором** в канал с правами «Публикация сообщений».
3. Узнайте `chat_id` канала (один из способов):
   ```bash
   docker compose exec backend python scripts/max_resolve_chat.py my_channel_slug
   ```
   или укажите в панели slug канала / ссылку `https://max.ru/...` — платформа резолвит ID при публикации.
4. В панели **Каналы** создайте канал: платформа **MAX**, ID — числовой `chat_id` или slug.
5. Пересоздайте worker после смены `.env`:
   ```bash
   docker compose up -d --force-recreate celery_worker backend
   ```
6. Одобрите пост в очереди — публикация пойдёт через `POST https://platform-api.max.ru/messages`.

Документация API: [dev.max.ru/docs-api](https://dev.max.ru/docs-api)

## Telethon

Первый запуск userbot требует интерактивной авторизации:

```bash
docker compose exec -it backend python -c "
from telethon import TelegramClient
from app.core.config import get_settings
s = get_settings()
c = TelegramClient('telethon_sessions/session', s.telegram_api_id, s.telegram_api_hash)
import asyncio
asyncio.run(c.start(phone=s.telegram_phone))
"
```

## Локальная разработка

**Важно:** `uvicorn` не завершается — если запустить backend и frontend одной цепочкой команд в одном терминале, фронтенд **никогда не стартует**. Нужны два терминала или скрипт ниже.

### Вариант 1: скрипт (один терминал)

```bash
./scripts/dev-local.sh
```

### Вариант 2: два терминала

Терминал 1 — backend:

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
PYTHONPATH=. .venv/bin/uvicorn app.main:app --reload
```

Терминал 2 — frontend:

```bash
cd frontend && npm install && npm run dev
```

- Панель: http://127.0.0.1:5173
- API docs: http://127.0.0.1:8000/docs
- Вход в панель: `ADMIN_USERNAME` / `ADMIN_PASSWORD` из `.env`

### Ошибки при локальном запуске

| Симптом | Причина | Решение |
|--------|---------|---------|
| `401 Unauthorized` | Не вошли или неверный логин/пароль | Войдите на `/login`; проверьте `ADMIN_USERNAME` и `ADMIN_PASSWORD` в `.env` |
| `attached to a different loop` в celery_worker | Старый пул asyncpg после `asyncio.run` | Пересоберите worker (`docker compose up -d --build celery_worker`); в коде после каждой задачи вызывается `engine.dispose()` |
| AI: «плейсхолдер sk-...» при валидном ключе в `.env` | `docker compose restart` **не** подхватывает новый `.env` | После правки `.env`: `docker compose up -d --force-recreate backend celery_worker celery_beat` |
| Парсинг Telegram: 0 постов | Не заданы `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_PHONE` | Заполните в `.env` или используйте RSS/Web источники |
| `address already in use` на порту 5432 | Локальный PostgreSQL занял 5432 | В Compose Postgres проброшен на **5433** (`5433:5432`). Внутри Docker сервисы по-прежнему ходят на `postgres:5432` |
| `password authentication failed for user "postgres"` | `DB_PASSWORD` не совпадает с PostgreSQL на `:5432` | Задайте в `.env` реальный пароль пользователя `postgres` (локальная БД) или остановите локальный PostgreSQL и запустите `docker compose up -d postgres` |
| Пустая очередь после 500 | Нет миграций | `cd backend && PYTHONPATH=. .venv/bin/alembic upgrade head` |
| Парсинг «без новых» для всех источников | Битый RSS URL или все записи уже в БД | `docker compose exec backend python scripts/fix_source_urls.py`; для Habr это норма после первого прогона (48 постов) |

### Хранение и индексы

- Индексы: `processed_posts(status)`, `raw_posts(source_id, is_processed, fetched_at DESC)`.
- Автоудаление записей старше `RETENTION_DAYS` (по умолчанию 30): Celery Beat каждый день в **03:30 UTC**.
  Удаляются: `raw_posts` (и каскадом `processed_posts`), `background_jobs`, старые `publish_log`.
- После смены `RETENTION_DAYS` в `.env`: `docker compose up -d --force-recreate celery_worker celery_beat`.

### URL источников

```bash
docker compose exec backend python scripts/fix_source_urls.py
```

Исправляет RBC (`/20/` → `/30/`) и метаданные Lenta. Для источника «Drom» с лентой Lenta:

```bash
docker compose exec backend python scripts/fix_misconfigured_sources.py
```

Переименует в **Lenta.ru** (тема `russia`) и добавит **Autostat** для настоящих авто-новостей. **Yandex** как `web` на `https://dzen.ru/` без `parser_config` не парсится — замените на RSS или настройте селекторы.

Создание БД на локальном PostgreSQL (если базы ещё нет):

```bash
sudo -u postgres psql -c "CREATE DATABASE content_platform;"
```
