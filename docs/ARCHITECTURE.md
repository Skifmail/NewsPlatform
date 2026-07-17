# Архитектура

## Слои (Clean Architecture Light)

| Слой | Назначение |
|------|------------|
| `domain/` | Enums, DTO без фреймворков |
| `repositories/` | Доступ к данным |
| `services/` | Use-cases: fetch, process, moderate, publish |
| `infrastructure/` | ORM, парсеры, AI, публикаторы, Redis events |
| `api/` | FastAPI роутеры и схемы |
| `tasks/` | Celery workers |

## Поток данных

1. **Celery Beat** каждую минуту → `platform_scheduler_tick` читает настройки из БД (`/settings`):
   - автопарсинг активных источников (интервал `fetch_interval_minutes`, флаг `schedule_fetch_enabled`);
   - AI после парсинга (`schedule_ai_enabled`, по умолчанию выкл. при умной публикации) — рерайтит **все** новые материалы в очередь pending;
   - **умная публикация** (`schedule_curated_publish_enabled`, по умолчанию вкл.): каждые `fetch_interval_minutes` (как автопарсинг) AI выбирает 1 лучший необработанный материал на тему из «Материалов», рерайтит и **сразу публикует** (`curated=True` → без очереди `scheduled_at`). Окно публикации канала (UTC) сохраняется; лимит `posts_per_day` в этом режиме не применяется;
   - **автогенерация статей** (`schedule_article_publish_enabled`): для каналов с `content_mode=article` AI придумывает тему, ищет в интернете (Tavily), пишет длинную статью, публикует на Telegraph и анонс в Telegram;
   - публикация по `scheduled_at` (`schedule_publish_enabled`, по умолчанию выкл.) — для ручной очереди «Одобренных»; при включённой умной публикации новые одобрения без «Опубликовать сейчас» **не** получают автослот;
   - очистка старых записей (`schedule_retention_enabled`, время UTC в настройках).
2. Парсер сохраняет `raw_posts` (окно свежести: `fetch_max_age_days`, по умолчанию вчера+сегодня UTC).
3. Основной автопоток: парсинг → накопление в «Материалах» → умная публикация (1 на тему → сразу в канал). Альтернатива: `process_post` после парсинга (`schedule_ai_enabled`) → `processed_post` (pending) на каждый канал с тем же `topic`.
4. Модерация в Vue-панели → `publish_post` → Telegram / VK / MAX (ручная публикация отключается флагом).
5. Redis pub/sub → WebSocket `/ws/updates`

Все контейнеры (`postgres`, `redis`, `backend`, `celery_worker`, `celery_beat`, `frontend`) обычно работают **локально на машине разработчика** через `docker compose`; внешние API — DeepSeek, Telegram/VK по ключам из `.env`.

## Парсинг (без AI-промпта)

1. Парсер (`rss` / `telegram` / `web`) забирает до 50 последних записей с URL источника.
2. Каждая запись проверяется только на дубликат: пара `(source_id, external_id)` уже в `raw_posts` → пропуск.
3. **Промпт на этапе парсинга не используется.** Сообщение «Новых материалов не найдено» значит либо лента пуста/битый URL, либо все записи уже были сохранены ранее (типично для Habr после первого успешного прогона).

## Редактируемые промпты (только AI)

- `channels.style_prompt` — полный шаблон рерайта (с `{original_text}`, `{source_url}` и др.) или краткое описание стиля
- Публикация в Telegram через Bot API: подпись к фото — макс. **1024** символа (Premium не расширяет лимит бота); длинный текст с картинкой — фото + ответ с полным текстом
- Публикация в MAX через Bot API (`MaxPublisher`, `MAX_BOT_TOKEN`): HTML до **4000** символов, обложка через `POST /uploads?type=image`
- `settings.classification_prompt` — уточнение темы it/auto/russia/sport перед раскладкой по каналам

## Режим «Статьи» (`content_mode=article`)

1. `TopicIdeationService` — выбор темы и поисковых запросов (DeepSeek).
   Антиповтор: заголовки из БД + история в settings, программная проверка `topic_dedup`
   (концепции вроде плацебо/дежавю), до 5 попыток при дубликате.
2. `WebResearchService` — Tavily Search (RU/EN источники).
3. `ArticleWriter` — длинная статья (до `article_body_max_length` символов).
   Для IT-каналов с «GitHub»/«находки» в названии анонс собирается автоматически
   (`devtools_teaser_formatter`): имя репо, hook, «Что умеет», stars/forks, язык, ссылка на GitHub
   (для превью в Telegram) + отдельно «Читать полностью →» на Telegraph.
   Для канала «Параграф» анонс собирается через `paragraph_teaser_formatter`:
   заголовок, крючок с эмодзи, цитата в blockquote, финальная интрига.
   Обложка: если в README репозитория найден логотип — Qwen Image Edit стилизует его;
   иначе — текстовая генерация по метафоре.
4. **Qwen-Image** — обложка по двухэтапному промпту: ArticleWriter описывает метафору → `ImagePromptBuilder` собирает финальный шаблон (на канале — поле `image_prompt_guidelines`). Из промпта вырезается кириллица и триггеры «обложка/постер», чтобы модель не рисовала галлюцинированный текст.
5. `ProcessedPost`: `article_body`, `rewritten_text` = анонс, без `raw_post_id`.
6. Публикация: Telegraph (полный текст) + Telegram (фото + анонс + ссылка).

Требуется `TAVILY_API_KEY` в `.env`; для обложек — `QWEN_IMAGE_API_KEY` (основной) или `OPENAI_API_KEY` (fallback).

## Хранение данных

- `RETENTION_DAYS` (по умолчанию 30): ежедневная задача `cleanup_old_records` удаляет старые
  `raw_posts`, `background_jobs` и `publish_log`.
- Индексы для панели: очередь по `status`, материалы по `(source_id, is_processed, fetched_at)`.

## Аналитика каналов

- Сбор: `ChannelAnalyticsService` → коллекторы Telegram/VK/MAX → снимки `channel_stats_snapshots`
  и актуальные `post_metrics`.
- Подписчики — stock-метрика (уровень на момент замера).
- Просмотры на графике и в окнах 24/48/72ч — flow-метрика: сумма **приростов** `total_views`
  между соседними снимками (не повторный подсчёт абсолютных значений).
- ER в сводке канала: `views_24h / subscribers × 100`.
- MAX/Telegram не отдают охват через Bot API; охват доступен в основном для VK.

## Дедупликация

- `UNIQUE(source_id, external_id)` для сырых постов
- `content_hash` на raw_posts
- `publish_text_hash` на processed_posts per channel
