# API

Базовый URL: `/api`

## Авторизация панели

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/auth/login` | Тело: `{"username","password"}` → `access_token` |
| GET | `/auth/me` | Текущий пользователь (нужен токен) |

Для остальных эндпоинтов: заголовок `Authorization: Bearer <token>`

Логин и пароль задаются в `.env`: `ADMIN_USERNAME`, `ADMIN_PASSWORD`.

## Сырые материалы (до AI)

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/raw-posts/summary` | Сводка по источникам (всего / ждут AI) |
| GET | `/raw-posts` | Список (`source_id`, `topic`, `is_processed`, `limit`, `offset`) |
| POST | `/raw-posts/{id}/process` | Вручную поставить на AI-обработку |
| POST | `/raw-posts/process-batch` | Пакетно: тело `{"raw_post_ids": [1,2]}` |

## Посты

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/posts/queue` | Очередь pending (после AI) |
| GET | `/posts/approved` | Очередь публикации: `approved` и `failed` (с `last_publish_error`) |
| GET | `/posts/approved/summary` | Счётчик очереди (approved + failed) |
| GET | `/posts/{id}` | Детали |
| PATCH | `/posts/{id}` | Редактирование текста, картинки, `scheduled_at` |
| DELETE | `/posts/{id}` | Удаление (не для published) |
| PATCH | `/posts/{id}/approve` | Одобрить (авто-расписание по каналу, если не `publish_immediately`) |
| PATCH | `/posts/{id}/reject` | Отклонить |
| POST | `/posts/{id}/publish_now` | Опубликовать |
| PATCH | `/posts/{id}/schedule` | Расписание |
| POST | `/posts/{id}/refresh-image` | Подтянуть картинку из RSS/страницы источника |

## История публикаций

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/history` | Все попытки из `publish_log` (успех и ошибка), `channel_id`, `limit`, `offset` |

## Фоновые задачи

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/jobs` | История задач; перед ответом синхронизирует статусы с Celery |
| GET | `/jobs/active` | Активные задачи с `progress` и текстом для уведомлений |
| GET | `/jobs/summary` | Счётчики по статусам (с той же синхронизацией) |
| POST | `/jobs/retry-process/{raw_post_id}` | Повтор AI для необработанного raw_post |

`POST /sources/{id}/fetch_now` возвращает `celery_task_id` и `job_id` — задача в Redis/Celery.

## Источники

| Метод | Путь | Описание |
|-------|------|----------|
| GET/POST | `/sources` | Список / создание |
| PATCH/DELETE | `/sources/{id}` | Изменение / удаление |
| POST | `/sources/{id}/fetch_now` | Парсинг сейчас |

## Каналы

| Метод | Путь | Описание |
|-------|------|----------|
| GET/POST | `/channels` | Список / создание (`content_mode`: `news` \| `article`) |
| PATCH | `/channels/{id}` | Название, `platform_id`, `content_mode`, промпт, расписание |
| DELETE | `/channels/{id}` | Удаление канала и связанных постов |
| POST | `/channels/{id}/recalculate-schedule` | Пересчёт `scheduled_at` для одобренных постов канала |
| POST | `/channels/{id}/generate-article` | Ручной запуск генерации статьи (только `content_mode=article`) |

## Настройки

| Метод | Путь | Описание |
|-------|------|----------|
| GET/PATCH | `/settings` | Автоматика, ручные действия, интервалы, промпты (см. ниже) |
| GET | `/ai-usage` | Баланс DeepSeek, кредиты Tavily (в т.ч. список ключей), цепочка Qwen, локальная статистика (`?refresh=true` — без кэша) |

Ключи (строки `true`/`false` или числа):

| Ключ | Назначение |
|------|------------|
| `schedule_fetch_enabled` | Автопарсинг всех активных источников |
| `schedule_ai_enabled` | AI после автопарсинга |
| `schedule_publish_enabled` | Публикация по `scheduled_at` |
| `schedule_retention_enabled` | Ежедневная очистка (`RETENTION_DAYS` в `.env` + `raw_posts_retention_days` для необработанных материалов) |
| `schedule_curated_publish_enabled` | AI выбирает 1 лучшую новость на тему каждые `fetch_interval_minutes` → рерайт → немедленная публикация (без `scheduled_at`) |
| `schedule_article_publish_enabled` | Автогенерация статей для каналов с `content_mode=article` |
| `article_ideation_prompt` | Промпт выбора темы статьи (`{channel_name}`, `{channel_niche}`, `{recent_topics}`) |
| `article_writing_prompt` | Промпт написания статьи (`{research_context}`, `{topic}`, `{angle}` и др.) |
| `article_teaser_max_length` | Лимит анонса в Telegram (по умолчанию 900) |
| `article_body_max_length` | Лимит тела статьи для Telegraph (по умолчанию 12000) |
| `curated_pick_prompt` | Промпт выбора лучшего материала (`{topic_label}`, `{candidates}`); ответ — JSON `{"id", "reason"}` |
| `curated_pick_history` | Журнал последних выборов (read-only, JSON-массив до 30 записей) |
| `manual_fetch_enabled` | `POST /sources/{id}/fetch_now` |
| `manual_ai_enabled` | AI из «Материалов» и `/jobs/retry-process` |
| `manual_publish_enabled` | `publish_now`, одобрение с немедленной публикацией |
| `auto_ai_after_manual_fetch` | AI после ручного парсинга |
| `fetch_interval_minutes` | Интервал автопарсинга (5–1440) |
| `fetch_max_age_days` | Окно свежести материалов (UTC) |
| `retention_hour_utc` / `retention_minute_utc` | Время запуска очистки |
| `raw_posts_retention_days` | Срок хранения необработанных материалов (по умолчанию 3 дня) |
| `qwen_image_models` / `qwen_image_edit_models` | Цепочки моделей обложек |
| `tavily_api_keys` | JSON-массив доп. ключей Tavily `[{id,label,key}]` (в GET ключи замаскированы) |
| `tavily_active_key_id` | Id активного ключа (`env` = ключ из `.env`, либо id из `tavily_api_keys`) |
| `tavily_auto_switch` | Автопереключение на следующий ключ при исчерпании лимита (`true`/`false`) |
| `auto_approve`, `posts_per_day`, `classification_prompt` | Как раньше |
| `scheduler_last_fetch_at`, `scheduler_last_retention_at` | Только чтение (статус планировщика) |

При отключённом действии API возвращает **403** с пояснением.

## Аналитика каналов

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/analytics/summary` | Сводка по всем каналам |
| GET | `/analytics/channels` | Сводки по каналам |
| GET | `/analytics/channels/{id}` | Детальная сводка канала |
| GET | `/analytics/channels/{id}/growth` | График: `period=today\|week\|month\|all`, `metric=subscribers\|views` |
| GET | `/analytics/channels/{id}/posts` | Метрики постов |
| POST | `/analytics/channels/{id}/refresh` | Сбор статистики канала |
| POST | `/analytics/refresh-all` | Сбор по всем каналам |

Ключевые поля сводки канала:

- `views_24h` / `views_48h` / `views_72h` — **новые** просмотры за скользящее окно (прирост `total_views` между снимками)
- `engagement_rate` — ER за 24ч: `views_24h / subscribers × 100`
- `avg_views` / `total_views` — накопленный итог по постам (не «за сутки»)
- `subscribers_today` / `subscribers_week` — прирост подписчиков за календарный день / 7 дней
- `avg_reach` — только если платформа отдаёт охват (VK); у MAX/Telegram обычно `null`

## WebSocket

`WS /ws/updates?token=<JWT>` — события `activity` (парсинг, AI, публикация, новые посты)

Полная схема: `/docs` (Swagger)
