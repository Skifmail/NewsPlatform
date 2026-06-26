# AI Content Platform — Техническое задание

## Обзор проекта

Создай веб-платформу для автоматизированного сбора, AI-переработки и публикации контента в Telegram и Макс (VK) каналы.

**Суть системы:** платформа каждые 30 минут парсит новости из RSS-лент, Telegram-каналов и веб-сайтов по трём тематикам (IT, Автомобили, Новости России), сохраняет сырые посты в БД, обрабатывает их через DeepSeek API (рерайт под стиль канала + генерация картинки), показывает владельцу очередь готовых постов в веб-панели для одобрения/редактирования, и публикует одобренные посты в нужные каналы по расписанию.

---

## Стек технологий

### Backend
- **Python 3.12**
- **FastAPI** — REST API + WebSocket для realtime обновлений в панели
- **SQLAlchemy 2.0** (async) + **asyncpg** — ORM и драйвер PostgreSQL
- **Alembic** — миграции БД
- **Celery 5** + **Redis** — очереди фоновых задач (парсинг, AI-обработка, публикация)
- **APScheduler** — планировщик запуска парсеров по расписанию
- **Pydantic v2** — валидация данных и схемы

### Парсинг
- **feedparser** — RSS/Atom ленты (Яндекс Новости, Google News, RBC, TJ, Habr, Дром и др.)
- **Telethon** — чтение Telegram-каналов как userbot (MTProto)
- **httpx** + **BeautifulSoup4** — scraping сайтов без RSS
- **lxml** — быстрый парсинг HTML/XML

### AI-обработка
- **Anthropic Python SDK** — Claude API (claude-sonnet-4-20250514) для рерайта и классификации
- **openai** SDK — DALL-E 3 для генерации картинок (опционально)
- **Pillow** — обработка и ресайз изображений перед публикацией

### Публикация
- **aiogram 3** — публикация в Telegram-каналы через Bot API
- **aiohttp** — VK API / Макс API для публикации во ВКонтакте/Макс

### Frontend
- **Vue 3** + **Vite** — SPA веб-панель
- **Pinia** — state management
- **Tailwind CSS** — стилизация
- **Axios** — HTTP-запросы к API

### Инфраструктура
- **PostgreSQL 16** — основная БД
- **Redis 7** — брокер Celery + кэш
- **Docker Compose** — оркестрация всех сервисов
- **Nginx** — reverse proxy
- **Gunicorn** + **Uvicorn workers** — ASGI сервер
- **Loguru** — логирование
- **python-dotenv** — конфигурация через `.env`

---

## Архитектура БД

### Таблица `sources` — источники контента
```sql
CREATE TABLE sources (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,           -- "Хабр", "TJ", "Telegram: @autoru"
    type        VARCHAR(50) NOT NULL,            -- 'rss' | 'telegram' | 'web'
    url         TEXT NOT NULL,                   -- URL ленты или ссылка на канал
    topic       VARCHAR(50) NOT NULL,            -- 'it' | 'auto' | 'russia'
    is_active   BOOLEAN DEFAULT TRUE,
    fetch_interval_minutes INT DEFAULT 30,
    last_fetched_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

### Таблица `raw_posts` — сырые спарсенные посты
```sql
CREATE TABLE raw_posts (
    id              SERIAL PRIMARY KEY,
    source_id       INT REFERENCES sources(id) ON DELETE CASCADE,
    external_id     VARCHAR(512),                -- уникальный ID поста в источнике (guid, message_id)
    title           TEXT,
    content         TEXT NOT NULL,              -- исходный текст
    url             TEXT,                       -- ссылка на оригинал
    image_url       TEXT,                       -- картинка из оригинала
    topic           VARCHAR(50) NOT NULL,
    published_at    TIMESTAMPTZ,                -- дата публикации в источнике
    fetched_at      TIMESTAMPTZ DEFAULT NOW(),
    is_processed    BOOLEAN DEFAULT FALSE,
    UNIQUE(source_id, external_id)
);
```

### Таблица `channels` — каналы публикации
```sql
CREATE TABLE channels (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,       -- "IT канал Telegram"
    platform        VARCHAR(50) NOT NULL,        -- 'telegram' | 'vk' | 'max'
    platform_id     VARCHAR(255) NOT NULL,       -- @channel_username или -100xxxxxxxxxx
    topic           VARCHAR(50) NOT NULL,        -- 'it' | 'auto' | 'russia'
    style_prompt    TEXT,                        -- системный промпт для рерайта под этот канал
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### Таблица `processed_posts` — обработанные AI посты (очередь модерации)
```sql
CREATE TABLE processed_posts (
    id              SERIAL PRIMARY KEY,
    raw_post_id     INT REFERENCES raw_posts(id) ON DELETE CASCADE,
    channel_id      INT REFERENCES channels(id) ON DELETE CASCADE,
    rewritten_text  TEXT NOT NULL,              -- текст после рерайта
    generated_image_url TEXT,                   -- URL сгенерированной/выбранной картинки
    image_source    VARCHAR(50),                -- 'original' | 'generated' | 'none'
    ai_model        VARCHAR(100),               -- какая модель использовалась
    status          VARCHAR(50) DEFAULT 'pending', -- 'pending' | 'approved' | 'rejected' | 'published' | 'failed'
    scheduled_at    TIMESTAMPTZ,               -- время запланированной публикации
    published_at    TIMESTAMPTZ,
    rejection_reason TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### Таблица `publish_log` — лог публикаций
```sql
CREATE TABLE publish_log (
    id                  SERIAL PRIMARY KEY,
    processed_post_id   INT REFERENCES processed_posts(id),
    channel_id          INT REFERENCES channels(id),
    platform_post_id    VARCHAR(255),           -- ID поста на платформе после публикации
    status              VARCHAR(50) NOT NULL,   -- 'success' | 'failed'
    error_message       TEXT,
    published_at        TIMESTAMPTZ DEFAULT NOW()
);
```

### Таблица `settings` — глобальные настройки платформы
```sql
CREATE TABLE settings (
    key     VARCHAR(255) PRIMARY KEY,
    value   TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
-- Примеры: auto_approve=false, posts_per_day=10, rewrite_language=ru
```

---

## Структура проекта

```
news-platform/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app, роутеры
│   │   ├── config.py                # Pydantic Settings из .env
│   │   ├── database.py              # async engine, session factory
│   │   ├── models/                  # SQLAlchemy модели
│   │   │   ├── source.py
│   │   │   ├── raw_post.py
│   │   │   ├── channel.py
│   │   │   ├── processed_post.py
│   │   │   └── publish_log.py
│   │   ├── schemas/                 # Pydantic схемы (request/response)
│   │   ├── routers/                 # FastAPI роутеры
│   │   │   ├── sources.py           # CRUD источников
│   │   │   ├── channels.py          # CRUD каналов
│   │   │   ├── posts.py             # очередь постов, одобрение/отклонение
│   │   │   ├── publish.py           # ручная и плановая публикация
│   │   │   └── settings.py
│   │   ├── services/
│   │   │   ├── parsers/
│   │   │   │   ├── base.py          # базовый класс парсера
│   │   │   │   ├── rss_parser.py    # feedparser
│   │   │   │   ├── telegram_parser.py # Telethon
│   │   │   │   └── web_parser.py    # httpx + BS4
│   │   │   ├── ai/
│   │   │   │   ├── rewriter.py      # Claude API рерайт
│   │   │   │   ├── classifier.py    # классификация по тематике
│   │   │   │   └── image_gen.py     # DALL-E 3 / обработка оригинала
│   │   │   └── publisher/
│   │   │       ├── telegram.py      # aiogram 3
│   │   │       └── vk.py            # VK/Макс API
│   │   └── tasks/                   # Celery задачи
│   │       ├── celery_app.py
│   │       ├── fetch_tasks.py       # задачи парсинга
│   │       ├── ai_tasks.py          # задачи AI-обработки
│   │       └── publish_tasks.py     # задачи публикации
│   ├── alembic/
│   │   └── versions/
│   ├── alembic.ini
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── views/
│   │   │   ├── QueueView.vue        # очередь постов — главная страница
│   │   │   ├── SourcesView.vue      # управление источниками
│   │   │   ├── ChannelsView.vue     # управление каналами
│   │   │   ├── HistoryView.vue      # история публикаций
│   │   │   └── SettingsView.vue
│   │   ├── components/
│   │   │   ├── PostCard.vue         # карточка поста с превью
│   │   │   ├── PostEditor.vue       # редактор текста поста
│   │   │   └── ImagePicker.vue      # выбор/замена картинки
│   │   ├── stores/
│   │   │   └── postsStore.js
│   │   └── api/
│   │       └── index.js
│   ├── package.json
│   └── vite.config.js
├── docker-compose.yml
├── nginx.conf
└── .env.example
```

---

## Ключевые API-эндпоинты

```
GET    /api/posts/queue              — список постов со статусом 'pending'
GET    /api/posts/{id}               — детальный просмотр поста
PATCH  /api/posts/{id}/approve       — одобрить (+ опционально изменить текст/картинку)
PATCH  /api/posts/{id}/reject        — отклонить с причиной
POST   /api/posts/{id}/publish_now   — опубликовать немедленно
PATCH  /api/posts/{id}/schedule      — поставить в расписание

GET    /api/sources                  — список источников
POST   /api/sources                  — добавить источник
PATCH  /api/sources/{id}             — редактировать
DELETE /api/sources/{id}             — удалить
POST   /api/sources/{id}/fetch_now   — запустить парсинг сейчас

GET    /api/channels                 — список каналов
POST   /api/channels                 — добавить канал
PATCH  /api/channels/{id}            — редактировать (включая style_prompt)

GET    /api/history                  — история опубликованных постов
GET    /api/settings                 — получить все настройки
PATCH  /api/settings                 — обновить настройки

WS     /ws/updates                   — WebSocket для realtime уведомлений о новых постах
```

---

## Бизнес-логика и воркфлоу

### Цикл парсинга (каждые 30 мин, Celery beat)
1. Для каждого активного `source` запускается задача `fetch_source(source_id)`
2. Парсер тянет новые посты, фильтрует уже существующие по `external_id`
3. Новые посты сохраняются в `raw_posts` с `is_processed=False`
4. Автоматически ставится задача `process_post(raw_post_id)` в очередь AI

### Цикл AI-обработки
1. Задача `process_post` берёт сырой пост
2. Классификатор проверяет тематику (если источник мультитематический)
3. Для каждого активного `channel` с соответствующим `topic`:
   - DeepSeek API делает рерайт с использованием `channel.style_prompt`
   - Определяется картинка: оригинальная / сгенерированная / без картинки
4. Создаётся запись `processed_post` со статусом `pending`
5. Владельцу приходит уведомление в Telegram (алерт-бот) о новых постах

### Цикл публикации
1. Владелец в веб-панели просматривает посты, редактирует если нужно, нажимает «Одобрить»
2. Можно одобрить с немедленной публикацией или поставить время
3. Задача `publish_post(processed_post_id)` публикует пост через нужный publisher
4. Статус меняется на `published`, создаётся запись в `publish_log`

### Режим автоодобрения
- Если в настройках `auto_approve=true` — посты публикуются без ручной проверки
- Можно настроить лимит: не более N постов в день на канал

---

## Промпты для DeepSeek API

### Системный промпт рерайтера (шаблон)
```
Ты — редактор Telegram-канала "{channel_name}" с тематикой "{topic}".
Стиль канала: {style_prompt}

Твоя задача — переписать новость для публикации в канале.
Правила:
- Объём: 3-5 предложений, не более 1000 символов
- Без вводных слов типа "Итак", "Таким образом"
- Без хэштегов в тексте (добавятся отдельно)
- Сохрани суть новости, но перепиши своими словами
- Адаптируй под аудиторию канала
- Заканчивай призывом к обсуждению или интересным вопросом
- Отвечай ТОЛЬКО переписанным текстом, без пояснений

Оригинальная новость:
{original_text}
```

### Промпт классификации тематики
```
Определи тематику новости. Ответь ТОЛЬКО одним словом: it, auto или russia.
- it: технологии, программирование, гаджеты, интернет, AI
- auto: автомобили, мотоциклы, ПДД, дороги, транспорт
- russia: политика, экономика, общество, события в России

Новость: {text}
```

---

## Docker Compose

```yaml
version: '3.9'
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: content_platform
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  backend:
    build: ./backend
    command: gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
    env_file: .env
    depends_on:
      - postgres
      - redis
    ports:
      - "8000:8000"

  celery_worker:
    build: ./backend
    command: celery -A app.tasks.celery_app worker --loglevel=info --concurrency=4
    env_file: .env
    depends_on:
      - postgres
      - redis

  celery_beat:
    build: ./backend
    command: celery -A app.tasks.celery_app beat --loglevel=info
    env_file: .env
    depends_on:
      - postgres
      - redis

  frontend:
    build: ./frontend
    ports:
      - "3000:80"

  nginx:
    image: nginx:alpine
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    ports:
      - "80:80"
    depends_on:
      - backend
      - frontend

volumes:
  postgres_data:
```

---

## .env.example

```env
# Database
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=postgres
DB_PORT=5432
DB_NAME=content_platform
DATABASE_URL=postgresql+asyncpg://postgres:your_password@postgres:5432/content_platform

# Redis
REDIS_URL=redis://redis:6379/0

# Claude API
DEEPSEEK_API_KEY=sk-ant-...

# OpenAI (опционально, для DALL-E)
OPENAI_API_KEY=sk-...

# Telegram Bot (для публикации)
TELEGRAM_BOT_TOKEN=...

# Telegram Userbot (Telethon, для парсинга)
TELEGRAM_API_ID=...
TELEGRAM_API_HASH=...
TELEGRAM_PHONE=+7...

# VK / Макс API
VK_ACCESS_TOKEN=...

# Алерт-бот (уведомления владельцу о новых постах)
ALERT_BOT_TOKEN=...
ALERT_CHAT_ID=...

# App
SECRET_KEY=your_secret_key
DEBUG=false
```

---

## Требования к реализации

1. **Async everywhere** — все I/O операции асинхронные (httpx, asyncpg, aiogram)
2. **Дедупликация** — никогда не публиковать один и тот же пост дважды (проверка по `external_id` и хешу текста)
3. **Rate limiting** — не более 1 запроса в секунду к Deepseek API, соблюдать лимиты Telegram Bot API
4. **Retry логика** — Celery retry с экспоненциальным backoff для всех внешних запросов
5. **Loguru** для всех логов, отдельные файлы по уровням
6. **Миграции через Alembic** — никакого `create_all()` в продакшне
7. **Типизация** — type hints везде, совместимо с mypy
8. **Документация API** — автогенерация через FastAPI `/docs`
9. **CORS** — настроить для фронтенда на этапе разработки
10. **Graceful shutdown** — корректное завершение задач Celery при остановке контейнера

---

## С чего начать (порядок реализации)

1. Docker Compose + PostgreSQL + Redis — поднять инфраструктуру
2. Alembic + SQLAlchemy модели — создать схему БД
3. FastAPI skeleton — базовое приложение, health check
4. RSS парсер + Celery задача — первый рабочий парсинг
5. Сохранение в `raw_posts` — персистентность данных
6. Deepseek API рерайт — создание `processed_posts`
7. FastAPI CRUD эндпоинты для очереди постов
8. Vue 3 панель — список постов, кнопки одобрить/отклонить
9. Telegram publisher через aiogram 3
10. VK/Макс publisher
11. Telethon парсер Telegram-каналов
12. WebSocket уведомления о новых постах
13. Настройки, история, расписание

---
*В платформе должна быть возможность редактировать системный промт рерайтера для каждого из каналов и DeepSeek должен будет уже по новому промту переделывать новости. Так же должна быть возможность редактирования промта для классификации тематики. Должна быть возможность добавлять новые каналы ТГ и MAX с новой тематикой.*
*Платформа разрабатывается для личного использования одним владельцем. Авторизация — опциональна на MVP этапе (можно захардкодить или использовать простой API-ключ в заголовке).*
