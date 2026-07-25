# Graph Report - .  (2026-07-25)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 3281 nodes · 6890 edges · 185 communities (170 shown, 15 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 387 edges (avg confidence: 0.51)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `112a739b`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9
- Community 10
- Community 11
- Community 12
- Community 13
- Community 14
- Community 15
- Community 16
- Community 17
- Community 18
- Community 19
- Community 20
- Community 21
- Community 22
- Community 23
- Community 24
- Community 25
- Community 26
- Community 27
- Community 28
- Community 29
- Community 30
- Community 31
- Community 32
- Community 33
- Community 34
- Community 35
- Community 36
- Community 37
- Community 38
- Community 39
- Community 40
- Community 41
- Community 42
- Community 43
- Community 44
- Community 45
- Community 46
- Community 47
- Community 48
- Community 49
- Community 50
- Community 51
- Community 52
- Community 53
- Community 54
- Community 55
- Community 56
- Community 57
- Community 58
- Community 59
- Community 60
- Community 61
- Community 62
- Community 63
- Community 64
- Community 65
- Community 66
- Community 67
- Community 68
- Community 69
- Community 70
- Community 71
- Community 72
- Community 73
- Community 74
- Community 75
- Community 76
- Community 77
- Community 78
- Community 79
- Community 80
- Community 81
- Community 82
- Community 83
- Community 84
- Community 85
- Community 86
- Community 87
- Community 88
- Community 89
- Community 90
- Community 91
- Community 92
- Community 93
- Community 94
- Community 95
- Community 96
- Community 97
- Community 98
- Community 99
- Community 100
- Community 101
- Community 102
- Community 103
- Community 104
- Community 105
- Community 106
- Community 107
- Community 108
- Community 109
- Community 111
- Community 112
- Community 113
- Community 114
- Community 115
- Community 116
- Community 117
- Community 118
- Community 119
- Community 120
- Community 121
- Community 122
- Community 123
- Community 124
- Community 125
- Community 126
- Community 127
- Community 128
- Community 129
- Community 154
- Community 155
- Community 156
- Community 158
- Community 159
- Community 160
- Community 161
- Community 162
- Community 163
- Community 164
- Community 165
- Community 166

## God Nodes (most connected - your core abstractions)
1. `Channel` - 114 edges
2. `get_settings()` - 112 edges
3. `ProcessedPost` - 82 edges
4. `ProcessedPostRepository` - 58 edges
5. `OrmSchema` - 53 edges
6. `ChannelStatsSnapshot` - 50 edges
7. `PlatformSettingsService` - 50 edges
8. `ChannelRepository` - 48 edges
9. `ChannelAnalyticsService` - 45 edges
10. `JobTracker` - 44 edges

## Surprising Connections (you probably didn't know these)
- `_TokenBody` --uses--> `SettingRepository`  [INFERRED]
  backend/app/api/routers/vk_oauth.py → backend/app/repositories/setting_repository.py
- `GrowthPoint` --uses--> `ChannelResponse`  [INFERRED]
  backend/app/api/schemas/analytics.py → backend/app/api/schemas/channel.py
- `GrowthPoint` --uses--> `OrmSchema`  [INFERRED]
  backend/app/api/schemas/analytics.py → backend/app/api/schemas/common.py
- `ChartGrowthPoint` --uses--> `ChannelResponse`  [INFERRED]
  backend/app/api/schemas/analytics.py → backend/app/api/schemas/channel.py
- `ChartGrowthPoint` --uses--> `OrmSchema`  [INFERRED]
  backend/app/api/schemas/analytics.py → backend/app/api/schemas/common.py

## Import Cycles
- None detected.

## Communities (185 total, 15 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (50): ContentMode, ImageSource, Platform, PostStatus, Доменные перечисления платформы., Платформа публикации., Статус обработанного поста., Источник изображения поста. (+42 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (53): Alembic environment для синхронных миграций., get_settings(), Конфигурация приложения из переменных окружения., Возвращает кэшированный экземпляр настроек.      Returns:         Settings: наст, Настройка структурированного логирования loguru., Асинхронное подключение к PostgreSQL., _emit_to_db(), _get_engine() (+45 more)

### Community 2 - "Community 2"
Cohesion: 0.07
Nodes (53): get_ai_usage(), AuthDep, DbSession, Роутер сводки по AI-провайдерам., Баланс DeepSeek, кредиты Tavily, цепочка Qwen и локальная статистика., AiUsageResponse, BalancePoint, DeepSeekUsage (+45 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (41): PublishStatus, Статус записи в логе публикации., PublishPermanentError, RuntimeError, Ошибка публикации, повтор Celery-задачи не исправит ситуацию., Модель обработанного AI поста., PublishLog, Модель лога публикаций. (+33 more)

### Community 4 - "Community 4"
Cohesion: 0.07
Nodes (44): Проверки флагов настроек для ручных действий API., Запрещает ручную публикацию, если выключена в настройках.      Args:         ses, require_manual_publish(), approve_post(), bulk_queue_action(), delete_post(), get_approved(), get_approved_summary() (+36 more)

### Community 5 - "Community 5"
Cohesion: 0.04
Nodes (36): adForm, adSaving, adStatusLabels, channelId, chartComparisonText, chartMetric, chartMetricOptions, chartTitle (+28 more)

### Community 6 - "Community 6"
Cohesion: 0.07
Nodes (39): exhausted_models_json(), is_invalid_size_error(), is_model_exhausted(), is_quota_exhausted(), list_exhausted_models(), mark_model_exhausted(), parse_model_chain(), Redis (+31 more)

### Community 7 - "Community 7"
Cohesion: 0.06
Nodes (32): ImagePromptBuilder, Собирает финальный промпт Qwen из шаблона канала., Промпт обложки новости из шаблона канала., Подставляет плейсхолдеры в промпт обложек из настроек канала.          Returns:, Убирает кириллицу — Qwen рисует её как надпись на картинке., Переводит тему новости в визуальную сцену на английском., Извлекает короткое имя из заголовка., Очищает описание сцены от абстрактных клише. (+24 more)

### Community 8 - "Community 8"
Cohesion: 0.08
Nodes (35): MaxPublisher, Any, ClientSession, Публикует статью целиком в MAX без Telegraph.          Args:             post: п, Публикует анонс статьи со ссылкой на Telegraph.          Args:             post:, Собирает заголовок авторизации MAX API.          Args:             token: токен, Извлекает slug канала из ссылки или @username.          Args:             platfo, Определяет числовой chat_id канала.          Args:             session: HTTP-сес (+27 more)

### Community 9 - "Community 9"
Cohesion: 0.09
Nodes (41): bulk_delete_raw_posts(), list_raw_posts(), process_raw_post(), process_raw_posts_batch(), AuthDep, DbSession, Роутер сырых постов (материалы до AI)., Массовое удаление сырых постов (материалов). (+33 more)

### Community 10 - "Community 10"
Cohesion: 0.04
Nodes (42): aiUsage, aiUsageError, aiUsageLoading, articleIdeationPrompt, articleStatus, articleWritingPrompt, autoAiAfterManualFetch, autoApprove (+34 more)

### Community 11 - "Community 11"
Cohesion: 0.04
Nodes (24): ProcessedPostRepository, AsyncSession, Количество постов в очереди публикации.          Returns:             int: счётч, Количество постов с указанным статусом.          Args:             status: стату, CRUD для processed_posts., Одобренные посты канала по порядку создания.          Args:             channel_, Удаляет processed_post.          Args:             post_id: ID поста.          R, Пост с связями.          Args:             post_id: ID.          Returns: (+16 more)

### Community 12 - "Community 12"
Cohesion: 0.07
Nodes (41): _distinctive_words(), extract_concepts(), is_topic_too_similar(), merge_topic_lists(), _normalize(), Дедупликация тем статей: семантические маркеры и проверка похожести., Извлекает канонические id концепций из названия темы или заголовка.      Args:, Проверяет, слишком ли похожа тема на недавние.      Сравнивает семантические кон (+33 more)

### Community 13 - "Community 13"
Cohesion: 0.07
Nodes (31): aiUsageApi, api, authApi, channelsApi, clearToken(), getToken(), jobsApi, rawPostsApi (+23 more)

### Community 14 - "Community 14"
Cohesion: 0.10
Nodes (31): Написание длинных познавательных статей., Сборка промптов для генерации обложек., Выбор и генерация изображений для постов., Подбирает обложку для статьи.          Args:             channel: канал публикац, Проверяет, что URL похож на изображение, а не на PDF/документ.          Args:, is_paragraph_article_channel(), paragraph_writing_instructions(), Форматирование Telegram-анонса для познавательного канала «Параграф». (+23 more)

### Community 15 - "Community 15"
Cohesion: 0.09
Nodes (33): Публикация в Telegram через aiogram и Telethon (userbot)., Публикует в Telegram-канал., TelegramPublisher, RuntimeError, Публикация в Telegram через Telethon (userbot, MTProto).  Позволяет подписи к ме, Сессия Telethon не настроена или не авторизована., Ошибка публикации через MTProto., Публикует пост от имени userbot-аккаунта (длинные подписи к медиа). (+25 more)

### Community 16 - "Community 16"
Cohesion: 0.08
Nodes (38): RuntimeError, Клиент Tavily Search API., Выполняет один поисковый запрос конкретным ключом.          Args:             en, Исчерпание кредитов Tavily для текущего ключа., Один результат поиска Tavily., Выполняет поиск по запросу с failover по ключам.          Args:             quer, _TavilyQuotaError, TavilySearchResult (+30 more)

### Community 17 - "Community 17"
Cohesion: 0.09
Nodes (34): _normalize_publish_times_optional(), _normalize_publish_times_required(), Нормализует строку времён «HH:MM,HH:MM» (МСК); пусто → ошибка., Нормализация для Update: None → не менять, иначе как в required., article_scheduler_key(), Ключ БД для времени последней генерации статьи канала.      Args:         channe, due_slot(), format_publish_times() (+26 more)

### Community 18 - "Community 18"
Cohesion: 0.08
Nodes (27): HealthVerdict, Итог оценки: статус и человекочитаемая причина., AppErrorLog, Модель записи об ошибке приложения (для окна логов в панели)., Единая запись ошибки/предупреждения из любого процесса (backend, worker)., AppErrorLogRepository, AsyncSession, Репозиторий логов ошибок приложения (для панели диагностики). (+19 more)

### Community 19 - "Community 19"
Cohesion: 0.09
Nodes (30): MaxMember, Модель участника MAX-канала.  MAX Bot API (эндпоинт ``GET /chats/{id}/members``), Участник MAX-канала со всей доступной от API информацией., MemberDTO, Участник канала со всей доступной от платформы информацией.      Заполняется пла, _apply_dto(), _dto_to_model(), MaxMemberRepository (+22 more)

### Community 20 - "Community 20"
Cohesion: 0.05
Nodes (33): barCount, bars, barTrend(), barTrendClass(), baseY, bounds, chartHeight, chartStyle (+25 more)

### Community 21 - "Community 21"
Cohesion: 0.08
Nodes (27): create_channel(), delete_channel(), generate_article(), list_channels(), AuthDep, DbSession, Редактирует канал (включая style_prompt)., Ставит в очередь генерацию статьи для article-канала. (+19 more)

### Community 22 - "Community 22"
Cohesion: 0.10
Nodes (35): get_settings(), _invalidate_ai_usage_cache(), _public_settings(), AuthDep, DbSession, Сбрасывает кэш /ai-usage после смены ключей Tavily., Готовит настройки для панели: маскирует секреты Tavily.      Args:         merge, Все настройки платформы (дефолты + БД, включая статус планировщика).      Возвра (+27 more)

### Community 23 - "Community 23"
Cohesion: 0.07
Nodes (24): Topic, curated_scheduler_key(), Ключ БД для времени последнего curated-запуска по теме.      Args:         topic, Выбирает один raw_post для рерайта и публикации., TopicPicker, AsyncSession, Число постов по фильтрам.          Args:             source_id: фильтр по источн, Счётчик постов для массового удаления.          Returns:             tuple[int, (+16 more)

### Community 24 - "Community 24"
Cohesion: 0.08
Nodes (36): _is_raster_image_url(), URL ведёт на растровое изображение, пригодное для Pillow/Telegram.      Args:, build_vk_message(), Собирает текст поста для VK.      Для статей (article_body есть) публикуем полны, _abs_pair(), parse_broadcast_stats(), _percent(), Достаёт (current, previous) из StatsAbsValueAndPrev.      Args:         value: о (+28 more)

### Community 25 - "Community 25"
Cohesion: 0.08
Nodes (30): _devtools_ideation_extra(), Инструкции идеации для канала GitHub-находок.      Args:         candidate_repos, GitHubTrendingClient, _parse_item(), AsyncClient, datetime, Клиент живого GitHub Trending через официальный Search API.  GitHub не отдаёт «t, Возвращает объединённый список трендовых репозиториев.          Args: (+22 more)

### Community 26 - "Community 26"
Cohesion: 0.12
Nodes (37): ChannelStatsSnapshot, Точка времени для графиков роста подписчиков и охвата., _aggregate_subscribers_buckets(), _aggregate_views_buckets(), bucket_start(), build_chart_history(), ChartHistoryResult, _delta_percent() (+29 more)

### Community 27 - "Community 27"
Cohesion: 0.06
Nodes (27): adForm, ads, adSaving, adStatusLabels, autoEnabled, channels, defaultPlacedAt(), error (+19 more)

### Community 28 - "Community 28"
Cohesion: 0.11
Nodes (36): delete_ad_integration(), get_analytics_summary(), get_channel_analytics(), get_channel_growth(), get_channel_member_analytics(), get_channel_telegram_stats(), get_refresh_progress(), list_ad_integrations() (+28 more)

### Community 29 - "Community 29"
Cohesion: 0.08
Nodes (29): _parse_bool(), _parse_int(), PlatformSettings, Ключи и значения по умолчанию настроек платформы в БД., Типизированный снимок настроек платформы из БД., Собирает настройки из словаря (дефолты + БД).          Args:             merged:, Нужно ли ставить новые raw_posts на AI после парсинга.          Args:, Парсит строковое значение настройки в bool. (+21 more)

### Community 30 - "Community 30"
Cohesion: 0.09
Nodes (25): ChannelProgress, _key(), _now_iso(), Any, Отслеживание прогресса сбора статистики каналов через Redis.  Прогресс пишется с, Находит запись канала по id., Помечает канал как опрашиваемый сейчас., Помечает канал как завершённый (успех/ошибка) и пишет метрики. (+17 more)

### Community 31 - "Community 31"
Cohesion: 0.08
Nodes (29): allOnPageSelected, buildFiltersPayload(), clearSelection(), deleteByFilters(), deleteSelected(), deleting, dialog, error (+21 more)

### Community 32 - "Community 32"
Cohesion: 0.10
Nodes (25): FastAPI dependencies., Проверяет JWT в заголовке Authorization: Bearer.      Args:         authorizatio, verify_token(), Роутер входа в панель управления., Роутер истории публикаций., Роутер окна диагностики: логи ошибок и здоровье конвейера., Роутер обзорной панели (главная страница)., WebSocket для realtime обновлений. (+17 more)

### Community 33 - "Community 33"
Cohesion: 0.10
Nodes (21): BaseStatsCollector, ChannelStatsDTO, ABC, DTO и базовый класс сборщиков статистики., Агрегированная статистика канала с платформы., Интерфейс сборщика статистики для одной платформы., Собирает статистику канала и постов.          Args:             channel: канал п, get_stats_collector() (+13 more)

### Community 34 - "Community 34"
Cohesion: 0.09
Nodes (26): buildFiltersPayload(), bulkBusy, bulkDeleteFiltered(), bulkDeleteSelected(), bulkMessage, bulkRejectFiltered(), bulkRejectSelected(), channelOptions (+18 more)

### Community 35 - "Community 35"
Cohesion: 0.09
Nodes (19): create_ad_integration(), Создаёт рекламную интеграцию., Обновляет рекламную интеграцию., update_ad_integration(), AdIntegration, Ручной учёт рекламных интеграций., Рекламная интеграция в канале (учёт вручную)., AdIntegrationRepository (+11 more)

### Community 36 - "Community 36"
Cohesion: 0.10
Nodes (28): build_devtools_teaser(), devtools_writing_instructions(), extract_devtools_hook(), extract_github_url(), is_banned_hook_opening(), is_devtools_article_channel(), _normalize_features(), _normalize_language() (+20 more)

### Community 37 - "Community 37"
Cohesion: 0.09
Nodes (22): BasePublisher, ABC, Базовый интерфейс публикатора., Абстрактный публикатор на платформу., Публикует пост.          Args:             post: обработанный пост., Публикация в каналы MAX через Bot API., get_publisher(), Фабрика публикаторов. (+14 more)

### Community 38 - "Community 38"
Cohesion: 0.07
Nodes (28): autoprefixer, axios, dependencies, axios, pinia, vue, vue-router, devDependencies (+20 more)

### Community 39 - "Community 39"
Cohesion: 0.09
Nodes (28): _extract_message_id(), _ms_to_dt(), parse_max_chat_info(), parse_max_member(), parse_max_message_metrics(), _parse_published_at(), Any, datetime (+20 more)

### Community 40 - "Community 40"
Cohesion: 0.09
Nodes (28): _downsample_daily(), Оставляет последний снимок каждого календарного дня.      Args:         snapshot, Суммирует отписки по падениям между соседними снимками.      Telegram не отдаёт, _sum_unsubscribes(), channel(), mock_session(), Тесты ChannelAnalyticsService с мок-коллектором., Сжатие истории оставляет один снимок на календарный день. (+20 more)

### Community 41 - "Community 41"
Cohesion: 0.10
Nodes (20): postsApi, confirmButtonClass, dialog, dialog, emit, imageUrl, props, publish() (+12 more)

### Community 42 - "Community 42"
Cohesion: 0.08
Nodes (23): areaPoints, bounds, clamp(), cleanSeries, containerRef, hasData, hoveredIndex, hoveredPoint (+15 more)

### Community 43 - "Community 43"
Cohesion: 0.08
Nodes (27): attemptAt, hasImage, isFailed, previewOpen, previewText, processedAt, processedAtTitle, props (+19 more)

### Community 44 - "Community 44"
Cohesion: 0.14
Nodes (25): AdIntegrationResponse, MaxMemberResponse, Ответ рекламной интеграции., Участник MAX-канала для API., Нативная статистика Telegram-канала (stats.getBroadcastStats)., TelegramBroadcastStatsResponse, ChannelResponse, OrmSchema (+17 more)

### Community 45 - "Community 45"
Cohesion: 0.09
Nodes (16): Источник: RSS, Telegram или веб., Source, Загружает новые посты из источника.          Args:             source: модель ис, Загружает последние сообщения канала.          Args:             source: источни, AsyncSession, Репозиторий источников., CRUD для таблицы sources., Список всех источников.          Returns:             list[Source]: источники. (+8 more)

### Community 46 - "Community 46"
Cohesion: 0.11
Nodes (25): PostMetricDTO, Метрики одного поста с платформы., parse_vk_group_members(), parse_vk_post_reach(), parse_vk_wall_post(), Any, datetime, Сбор статистики VK-сообществ через API. (+17 more)

### Community 47 - "Community 47"
Cohesion: 0.11
Nodes (25): build_article_read_more_html(), clamp_rewrite_length(), _expand_blockquote(), _expand_blockquote_tags(), pick_article_read_more_label(), Утилиты форматирования текста постов., Собирает заметную CTA-ссылку на полную статью.      Telegram не поддерживает нас, Обрезает текст поста до допустимой длины.      Args:         text: итоговый текс (+17 more)

### Community 48 - "Community 48"
Cohesion: 0.11
Nodes (21): FetchResult, Результат парсинга источника., Краткий итог для панели «Задачи».          Returns:             str: описание ре, Итог одного запуска парсера.      Args:         created_ids: ID новых raw_posts., FetchService, Сервис сбора контента из источников., Оркестрация парсинга и сохранения raw_posts.      Отбор на этапе парсинга: дубли, Парсит источник и сохраняет новые посты.          Args:             source_id: I (+13 more)

### Community 49 - "Community 49"
Cohesion: 0.09
Nodes (18): activityStore, buildEditForm(), channels, create(), dialog, editForms, expandedId, form (+10 more)

### Community 50 - "Community 50"
Cohesion: 0.18
Nodes (19): Доменные сущности (без зависимостей от ORM)., DTO сырого поста от парсера.      Args:         external_id: уникальный ID в ист, RawPostDTO, Модель источника контента., BaseParser, ABC, Базовый интерфейс парсера., Абстрактный парсер источника. (+11 more)

### Community 51 - "Community 51"
Cohesion: 0.10
Nodes (15): Base, Базовый класс SQLAlchemy моделей., Модель глобальных настроек key-value., Setting, AsyncSession, Репозиторий настроек., Все настройки как словарь.          Returns:             dict[str, str]: key ->, Значение настройки.          Args:             key: ключ.             default: з (+7 more)

### Community 52 - "Community 52"
Cohesion: 0.09
Nodes (25): Bot, Публикует статью: полный текст в TG (long-form) или анонс + Telegraph., Публикует статью целиком в Telegram без Telegraph (Github, Параграф)., Публикует анонс статьи со ссылкой на Telegraph (прочие article-каналы)., Отправляет фото и/или текст; при необходимости через userbot.          Args:, Преобразует ошибки Telegram API в типы для политики retry., Отправляет фото и/или текст через Bot API., Отправляет сообщение в канал.          Args:             post: пост. (+17 more)

### Community 53 - "Community 53"
Cohesion: 0.11
Nodes (18): sourcesApi, hasImage, previewOpen, previewText, processedAt, processedAtTitle, props, topicLabel (+10 more)

### Community 54 - "Community 54"
Cohesion: 0.15
Nodes (23): Запрещает ручную AI-обработку, если выключена в настройках.      Args:         s, require_manual_ai(), jobs_summary(), list_active_jobs(), list_jobs(), AuthDep, DbSession, Роутер мониторинга фоновых задач. (+15 more)

### Community 55 - "Community 55"
Cohesion: 0.12
Nodes (19): MaxStatsCollector, normalize_max_chat_link(), ClientSession, Извлекает slug канала из ссылки или @username.      Args:         platform_id: c, Статистика MAX: подписчики, число сообщений и просмотры постов., Собирает participants_count, messages_count и просмотры постов.          Args:, Собирает всех участников канала с пагинацией по ``marker``.          Требует у б, Собирает просмотры известных постов через GET /messages.          Запрашивает по (+11 more)

### Community 56 - "Community 56"
Cohesion: 0.10
Nodes (18): OverviewService, AsyncSession, datetime, Суммарный прирост подписчиков за сегодня по всем каналам., Последние попытки публикации., Топ-5 каналов по числу подписчиков., Формирует список элементов, требующих внимания., Обрезает HTML/текст для превью в виджетах.      Args:         text: исходный тек (+10 more)

### Community 57 - "Community 57"
Cohesion: 0.11
Nodes (16): PostMetric, Метрики отдельного поста на платформе., Просмотры, реакции и охват поста на соцплатформе., PostMetricsRepository, AsyncSession, Репозиторий метрик постов., Средние и суммарные метрики по каналу.          Args:             channel_id: ID, CRUD для post_metrics. (+8 more)

### Community 58 - "Community 58"
Cohesion: 0.12
Nodes (15): JobTracker, _on_task_failure(), _on_task_running(), Регистрирует задачу генерации статьи.          Args:             celery_task_id:, Отправляет WebSocket-событие о задаче.          Args:             job: запись ba, Обновляет текущий этап running-задачи для toast и панели.          Args:, Создание и обновление записей о фоновых задачах., Переводит задачу в статус running.          Args:             celery_task_id: ID (+7 more)

### Community 59 - "Community 59"
Cohesion: 0.12
Nodes (22): captionLimit, channelInitial, channelName, hasImageUrl, imageFailed, imageUrl, longFormChannel, mockTime (+14 more)

### Community 60 - "Community 60"
Cohesion: 0.12
Nodes (22): AdIntegrationCreate, AdIntegrationUpdate, AnalyticsSummaryResponse, ChannelRefreshProgress, ChartGrowthPoint, GrowthHistoryResponse, GrowthPoint, MaxMemberAnalyticsResponse (+14 more)

### Community 61 - "Community 61"
Cohesion: 0.11
Nodes (20): ChannelAnalyticsOverview, _endpoints_delta(), _engagement_rate_from_views(), _growth_since(), datetime, Сервис сбора и агрегации аналитики каналов., ER = просмотры за период / подписчики × 100.      Args:         views: просмотры, Разница значения метрики между первым и последним снимком.      Args:         sn (+12 more)

### Community 62 - "Community 62"
Cohesion: 0.14
Nodes (21): dedupe_teaser_hook_from_body(), _extract_teaser_hook(), _is_structure_label(), _normalize_compare_text(), _normalize_label(), Удаление служебных меток структуры из текста статей., Извлекает текст крючка из HTML-анонса (без заголовка)., Убирает из тела первый абзац, если он дублирует крючок из анонса.      Args: (+13 more)

### Community 63 - "Community 63"
Cohesion: 0.14
Nodes (17): ArticleTopicPlan, План темы и поисковых запросов., _format_recent_topics(), Один запрос к модели за темой статьи.          Args:             channel: канал, Извлекает план темы из ответа модели.          Args:             result: сырой о, Форматирует список недавних тем для промпта.      Args:         topics: темы от, Придумывает тему и поисковые запросы для статьи., Генерирует план темы статьи с проверкой на повторы.          Args:             c (+9 more)

### Community 64 - "Community 64"
Cohesion: 0.12
Nodes (13): Результат выбора материала моделью., TopicPickResult, Выбор лучшего материала для публикации по тематике., Собирает результат выбора из raw_post.          Args:             post: выбранны, Извлекает id и reason из ответа модели.          Args:             result: сырой, Собирает возможные JSON-фрагменты из ответа.          Args:             text: сы, Парсит один JSON-объект с полями id и reason.          Args:             blob: J, Извлекает id и reason regex-ом без полного JSON.          Args:             text (+5 more)

### Community 65 - "Community 65"
Cohesion: 0.14
Nodes (18): JobStatus, JobType, Тип фоновой задачи Celery., Статус фоновой задачи., Модель фоновой задачи Celery для панели., Репозиторий фоновых задач., Выполнение Celery-задач с обновлением статуса в БД., Формирует итог по типу задачи и результату Celery.      Args:         job: запис (+10 more)

### Community 66 - "Community 66"
Cohesion: 0.14
Nodes (18): Подтягивает og:image / первую картинку со страницы статьи.          Args:, Возвращает URL изображения и источник.          Args:             raw_post: сыро, extract_image_from_html(), extract_image_from_rss_entry(), _img_src_from_tag(), is_social_preview_image(), _is_usable_image_url(), normalize_image_url() (+10 more)

### Community 67 - "Community 67"
Cohesion: 0.11
Nodes (13): BackgroundJob, Запись о задаче парсинга, AI или публикации., BackgroundJobRepository, AsyncSession, Число задач в очереди или в работе.          Returns:             int: количеств, CRUD для background_jobs., Находит задачу по ID Celery.          Args:             celery_task_id: идентифи, Создаёт запись задачи.          Args:             job: модель.          Returns: (+5 more)

### Community 68 - "Community 68"
Cohesion: 0.12
Nodes (15): Снимок нативной статистики Telegram-канала (stats.getBroadcastStats)., Скалярные показатели статистики канала на момент замера.      Наполняется только, TelegramBroadcastStats, BroadcastStatsDTO, Нативная статистика Telegram-канала (stats.getBroadcastStats).      Доступна тол, AsyncSession, Репозиторий снимков нативной статистики Telegram-каналов., Хранение и выборка снимков stats.getBroadcastStats. (+7 more)

### Community 69 - "Community 69"
Cohesion: 0.13
Nodes (12): GitHubRepoLogoFetcher, Скачивает README репозитория через GitHub API.          Args:             owner:, Возвращает ветку по умолчанию репозитория.          Args:             owner: вла, Собирает кандидатов на логотип из README.          Args:             readme: mar, Выбирает лучший URL логотипа по score.          Args:             candidates: сп, Превращает относительный путь из README в абсолютный URL.          Args:, Проверяет, что URL похож на картинку.          Args:             url: ссылка., Отсекает бейджи CI, stars shields и прочий шум.          Args:             url: (+4 more)

### Community 70 - "Community 70"
Cohesion: 0.11
Nodes (13): historyApi, theme, app, pinia, router, routes, useThemeStore, stripHtmlForPreview() (+5 more)

### Community 71 - "Community 71"
Cohesion: 0.17
Nodes (19): AsyncSession, Запрещает ручной парсинг, если выключен в настройках.      Args:         session, require_manual_fetch(), create_source(), delete_source(), fetch_now(), list_sources(), AuthDep (+11 more)

### Community 72 - "Community 72"
Cohesion: 0.15
Nodes (20): get_overview(), AuthDep, DbSession, Агрегированные данные для главной страницы «Обзор»., AttentionItem, OverviewKpis, OverviewResponse, OverviewTrendPoint (+12 more)

### Community 73 - "Community 73"
Cohesion: 0.13
Nodes (13): ArticleDraft, Черновик статьи от модели., ArticleWriter, Генерирует длинную статью по результатам исследования., Пишет статью по собранному контексту.          Args:             channel: канал, Один запрос к модели и парсинг ответа.          Args:             channel: канал, Парсит JSON-ответ модели.          Args:             result: сырой ответ., Пытается распарсить JSON-объект из ответа модели.          Args:             res (+5 more)

### Community 74 - "Community 74"
Cohesion: 0.13
Nodes (15): ContentRewriter, Рерайт новостей через DeepSeek., Переписывает пост под канал.          Args:             raw_post: сырой пост., Нормализует сырой ответ модели в текст поста.          Args:             raw: от, Рерайтер контента под стиль канала., Выбирает шаблон промпта и доп. стиль канала.          Если в ``style_prompt`` ес, Очищает ответ рерайтера от рассуждений модели.      Args:         text: сырой от, sanitize_rewrite_output() (+7 more)

### Community 75 - "Community 75"
Cohesion: 0.11
Nodes (12): Снимок агрегированной статистики канала., ChannelStatsRepository, AsyncSession, datetime, Репозиторий снимков статистики каналов., Последний снимок с известным числом подписчиков., CRUD для channel_stats_snapshots., Предыдущий снимок с подписчиками до указанного момента. (+4 more)

### Community 76 - "Community 76"
Cohesion: 0.16
Nodes (20): append_cross_promote_footer(), build_cross_promote_link_label(), build_source_link_html(), cross_promote_footer_length(), long_form_body_limit(), Собирает текст ссылки с опциональным анимированным эмодзи Telegram.      Args:, Добавляет в конец поста ссылку на другую площадку (перелив аудитории).      Args, Длина кросс-промо футера, добавляемого в конец поста.      Нужна, чтобы зарезерв (+12 more)

### Community 77 - "Community 77"
Cohesion: 0.22
Nodes (18): compute_spend(), datetime, Расчёт расходов провайдера из истории снимков баланса.  Провайдер отдаёт только, Сводка расходов провайдера по окнам., Сумма падений баланса среди пар, где поздняя точка не раньше ``since``., Сумма ростов баланса среди пар, где поздняя точка не раньше ``since``., Считает расходы за 24ч/7д/30д и пополнение за 30д.      Args:         series: сн, SpendSummary (+10 more)

### Community 78 - "Community 78"
Cohesion: 0.14
Nodes (17): decode_stage(), encode_stage(), Кодирование текущего этапа фоновой задачи для UI., Разбирает result_summary running-задачи.      Args:         raw: значение из БД., Формирует значение result_summary для running-задачи.      Args:         progres, detail_for_job(), notify_job(), phase_for_status() (+9 more)

### Community 79 - "Community 79"
Cohesion: 0.14
Nodes (14): logsApi, autoRefresh, expanded, health, level, levelOptions, loadHealth(), loading (+6 more)

### Community 80 - "Community 80"
Cohesion: 0.11
Nodes (17): overviewApi, activityItems, activityStore, chartSeries, clockLabel, data, error, failedTodaySub (+9 more)

### Community 81 - "Community 81"
Cohesion: 0.12
Nodes (17): canClose, channels, completed, detailFor(), elapsedLabel, emit, failedCount, formatNum() (+9 more)

### Community 82 - "Community 82"
Cohesion: 0.20
Nodes (17): period_bounds(), Возвращает границы периода и шаг агрегации.      Args:         period: today | w, datetime, Тесты агрегации графиков аналитики., Окна 24/48/72ч считают только приросты внутри окна., Просмотры за сегодня — прирост по 30-минутным корзинам, не накопительный итог., За неделю — столбцы по дням, итог = сумма приростов., Дельта просмотров сравнивается с прошлым периодом. (+9 more)

### Community 83 - "Community 83"
Cohesion: 0.12
Nodes (10): decodeStage(), error, jobResultText(), jobs, load(), loading, statusLabels, summary (+2 more)

### Community 84 - "Community 84"
Cohesion: 0.19
Nodes (15): assess_pipeline(), _hours_between(), datetime, Оценка здоровья конвейера публикаций (чистая логика, без БД).  Главная цель — ло, Часы между моментами (>=0)., Оценивает состояние конвейера публикаций.      Args:         now: текущий момент, Тесты оценки здоровья конвейера публикаций., Ключевой кейс: парсинг свежий, а публикаций давно нет → critical. (+7 more)

### Community 85 - "Community 85"
Cohesion: 0.16
Nodes (11): AiBalanceSnapshot, Снимок баланса AI-провайдера для истории расходов.  Провайдеры (DeepSeek) отдают, Точка баланса провайдера во времени., AiBalanceSnapshotRepository, AsyncSession, datetime, Репозиторий снимков баланса AI-провайдеров., Хранение и выборка истории баланса провайдеров. (+3 more)

### Community 86 - "Community 86"
Cohesion: 0.17
Nodes (12): article_topic_history_key(), parse_topic_history(), Доменные модели и ключи для режима статей., Ключ БД для истории тем канала.      Args:         channel_id: ID канала.      R, Парсит JSON-список недавних тем.      Args:         raw: значение из settings., Сериализует историю тем в JSON.      Args:         topics: темы от новых к стары, Сериализует источники исследования в JSON.      Args:         sources: найденные, serialize_research_sources() (+4 more)

### Community 87 - "Community 87"
Cohesion: 0.17
Nodes (7): DeepSeekClient, Вызов chat/completions с причиной завершения генерации.          Args:, Асинхронный клиент DeepSeek (OpenAI-compatible API)., Извлекает текст ответа из message (content или reasoning_content).          Args, Ищет JSON-объект с указанным полем в тексте.          Args:             text: co, Ограничение: не чаще 1 запроса в секунду., Вызов chat/completions.          Args:             system_prompt: системный пром

### Community 88 - "Community 88"
Cohesion: 0.19
Nodes (9): Any, Обновляет имя автора на существующей странице Telegraph.          Args:, Сериализует nodes для form-data Telegraph API.          Args:             nodes:, Создаёт страницы на telegra.ph через HTTP API., Конвертирует упрощённый HTML в nodes Telegraph.          Args:             body_, Парсит inline-разметку одного абзаца.          Args:             fragment: HTML-, Возвращает access_token, создавая аккаунт при необходимости.          Порядок: а, Публикует HTML-статью на Telegraph.          Args:             title: заголовок (+1 more)

### Community 89 - "Community 89"
Cohesion: 0.16
Nodes (15): settingsApi, boolFrom(), curatedHistory, curatedPickPrompt, curatedStatus, fetchIntervalMinutes, formatPickTime(), load() (+7 more)

### Community 90 - "Community 90"
Cohesion: 0.18
Nodes (14): list_logs(), pipeline_health(), AuthDep, DbSession, Последние ошибки/предупреждения из всех процессов.      Args:         level: фил, Здоровье конвейера публикаций (ловит «тихий» сбой).      Returns:         Pipeli, AppErrorLogResponse, ChannelPublishHealthResponse (+6 more)

### Community 91 - "Community 91"
Cohesion: 0.18
Nodes (11): CuratedPickRecord, parse_curated_pick_history(), datetime, Запись о выборе лучшей новости для умной публикации., Сериализует журнал выборов в JSON для settings.      Args:         records: запи, Элемент журнала умной публикации для панели., Собирает запись журнала из результата выбора.          Args:             topic:, Парсит журнал выборов из JSON в settings.      Args:         raw: значение ключа (+3 more)

### Community 92 - "Community 92"
Cohesion: 0.24
Nodes (9): ClientSession, Статистика VK через wall и stats API., Собирает подписчиков и метрики постов VK.          Args:             channel: ка, Запрашивает members_count сообщества., Собирает метрики известных постов и последних записей стены., Метрики одного поста wall.getById., Охват поста stats.getPostReach. Возвращает (reach_total, reach_subscribers)., Последние посты со стены. (+1 more)

### Community 93 - "Community 93"
Cohesion: 0.18
Nodes (13): login(), me(), AuthDep, Проверяет логин/пароль и выдаёт JWT.      Args:         data: учётные данные., Возвращает текущего пользователя по токену.      Args:         username: логин и, LoginRequest, BaseModel, Схемы авторизации панели. (+5 more)

### Community 94 - "Community 94"
Cohesion: 0.19
Nodes (13): _build_html_text(), _build_plain_text(), _is_too_long_error(), main(), _probe_max(), Bot, Эмпирическая проверка лимитов Telegram Bot API для канала.  Бинарным поиском нах, Запускает все пробы и печатает отчёт. (+5 more)

### Community 95 - "Community 95"
Cohesion: 0.24
Nodes (12): _enter_2fa_password(), _login_via_code(), _login_via_qr(), main(), _print_qr(), TelegramClient, Авторизация Telethon userbot-сессии по QR-коду.  Запускать в интерактивном терми, Резервный вход по коду подтверждения.      Args:         client: подключённый кл (+4 more)

### Community 96 - "Community 96"
Cohesion: 0.23
Nodes (8): ConnectionManager, Any, Менеджер WebSocket-подключений., Принимает подключение., Рассылает сообщение всем клиентам., WebSocket /ws/updates — события activity (задачи, посты, публикации).      Args:, websocket_updates(), WebSocket

### Community 97 - "Community 97"
Cohesion: 0.26
Nodes (10): is_ai_tool(), Определение категории dev-инструмента (AI/LLM или нет).  Нужно, чтобы канал нахо, True, если текст описывает AI/LLM-инструмент.      Args:         text: заголовок, Тесты классификатора AI/LLM-инструментов (правило ≤1 AI из 3 подряд)., Реальные заголовки, из-за которых канал скатился в AI-поток., test_empty(), test_english_ai_descriptions(), test_no_false_positive_on_substrings() (+2 more)

### Community 98 - "Community 98"
Cohesion: 0.18
Nodes (8): animated, deltaClass, deltaText, formattedValue, props, router, valueClass, useCountUp()

### Community 99 - "Community 99"
Cohesion: 0.25
Nodes (8): Источник из веб-поиска., ResearchSource, Асинхронный клиент Tavily для веб-исследования., TavilyClient, Веб-исследование через Tavily., Собирает контекст из интернета для написания статьи., Выполняет поиск и формирует текстовый контекст.          Args:             queri, WebResearchService

### Community 100 - "Community 100"
Cohesion: 0.25
Nodes (10): analyticsApi, pollRefreshProgress(), sleep(), startRefreshAll(), startRefreshChannel(), loadGrowth(), refresh(), refreshAll() (+2 more)

### Community 101 - "Community 101"
Cohesion: 0.22
Nodes (6): Создаёт сервис с цепочками моделей из настроек платформы., Проверяет, настроена ли хотя бы одна модель генерации изображений.          Retu, notify_simple(), Публикует разовое событие (пост, публикация и т.д.).      Args:         activity, Заполняет generated_image_url из оригинала.          Args:             post_id:, Обрабатывает сырой пост через DeepSeek.          Args:             raw_post_id:

### Community 102 - "Community 102"
Cohesion: 0.22
Nodes (7): AsyncSession, Удаляет данные старше заданного срока хранения., Удаляет записи по срокам хранения.          Сначала — необработанные материалы (, RetentionService, Тесты RetentionService., Сначала удаляются необработанные материалы, затем общая очистка., test_cleanup_expired_deletes_unprocessed_and_expired_raw_posts()

### Community 103 - "Community 103"
Cohesion: 0.31
Nodes (7): close(), emit, error, props, reason, submit(), REJECT_REASON_PRESETS

### Community 104 - "Community 104"
Cohesion: 0.22
Nodes (9): ads, defaultPlacedAt(), load(), loadMembers(), loadPosts(), loadTelegramStats(), removeAd(), submitAd() (+1 more)

### Community 105 - "Community 105"
Cohesion: 0.29
Nodes (4): formatDelta(), formatNum(), platformLabels, router

### Community 106 - "Community 106"
Cohesion: 0.38
Nodes (6): BaseModel, VK OAuth — получение user token через классический implicit flow., _TokenBody, vk_oauth_save(), vk_oauth_start(), HTMLResponse

### Community 107 - "Community 107"
Cohesion: 0.29
Nodes (5): Пустая строка в .env трактуется как «не задано»., Заменяет устаревшие имена моделей DeepSeek на актуальные.          DeepSeek удал, Настройки платформы контента.      Args:         Нет — значения читаются из окру, Settings, BaseSettings

### Community 108 - "Community 108"
Cohesion: 0.33
Nodes (5): DeepSeekAuthError, RuntimeError, Ошибки интеграции с AI-провайдерами., Неверный или отсутствующий ключ DeepSeek API., Клиент DeepSeek API с rate limiting.

### Community 109 - "Community 109"
Cohesion: 0.29
Nodes (7): build_paragraph_teaser(), _normalize_quote(), Any, Укорачивает анонс, сохраняя структуру.      Args:         lines: блоки HTML., Собирает HTML-анонс в стиле канала «Параграф».      Args:         data: поля из, Убирает лишние кавычки из цитаты.      Args:         raw: цитата от модели., _truncate_teaser()

### Community 111 - "Community 111"
Cohesion: 0.29
Nodes (7): activateTavilyKey(), addTavilyKey(), dbTavilyKeysPayload(), loadAiUsage(), patchTavilySettings(), removeTavilyKey(), saveTavilyAutoSwitch()

### Community 112 - "Community 112"
Cohesion: 0.29
Nodes (5): DATABASE_URL, DATABASE_URL_SYNC, DB_HOST, REDIS_URL, dev-local.sh script

### Community 113 - "Community 113"
Cohesion: 0.33
Nodes (3): Снимает флаг обработки (для повторного AI).          Args:             post_id:, Помечает пост обработанным.          Args:             post_id: ID поста., Пост по ID.          Args:             post_id: идентификатор.          Returns:

### Community 114 - "Community 114"
Cohesion: 0.33
Nodes (6): clamp(), eventClientX(), onPointerMove(), pickNearestIndex(), setHover(), updateTooltipPosition()

### Community 115 - "Community 115"
Cohesion: 0.33
Nodes (6): boolFrom(), getFormSnapshot(), loadSettings(), markSaved(), parseTavilyResolved(), save()

### Community 116 - "Community 116"
Cohesion: 0.40
Nodes (3): _CallbackHandler, _exchange_code(), main()

### Community 117 - "Community 117"
Cohesion: 0.40
Nodes (4): downgrade(), Добавляет поля интервала и окна публикации на канал., Удаляет поля расписания., upgrade()

### Community 118 - "Community 118"
Cohesion: 0.40
Nodes (4): downgrade(), Добавляет sport в промпт классификации для существующих инсталляций., Откат не восстанавливает старый промпт — правка вручную при необходимости., upgrade()

### Community 119 - "Community 119"
Cohesion: 0.50
Nodes (3): AsyncClient, Скрапит одну или список страниц.          Args:             source: источник с u, Парсит одну страницу.          Args:             client: HTTP-клиент.

### Community 120 - "Community 120"
Cohesion: 0.40
Nodes (5): _count_reactions(), _message_published_at(), Суммирует реакции сообщения.      Args:         message: объект Telethon Message, Возвращает дату публикации сообщения в UTC.      Args:         message: объект T, Message

### Community 125 - "Community 125"
Cohesion: 0.50
Nodes (4): get_history(), AuthDep, DbSession, История попыток публикации (успешные и с ошибкой).

### Community 126 - "Community 126"
Cohesion: 0.50
Nodes (3): publish_event(), Redis pub/sub для WebSocket broadcast., Публикует событие в Redis.      Args:         event_type: тип события.         p

### Community 127 - "Community 127"
Cohesion: 0.50
Nodes (3): Уведомления владельцу через Telegram alert-бот., Отправляет уведомление владельцу.      Args:         message: текст уведомления., send_alert()

### Community 128 - "Community 128"
Cohesion: 0.50
Nodes (4): _as_int(), _fetch_tavily_key_usage(), Any, Запрашивает /usage для одного ключа Tavily.      Returns:         tuple: plan, k

### Community 129 - "Community 129"
Cohesion: 0.50
Nodes (3): Сид начальных RSS-источников., Добавляет источники если их ещё нет.      Returns:         None, seed()

### Community 154 - "Community 154"
Cohesion: 0.67
Nodes (3): get_db_session(), AsyncSession, Dependency: сессия БД с автоматическим закрытием.      Yields:         AsyncSess

## Knowledge Gaps
- **352 isolated node(s):** `docker-entrypoint.sh script`, `name`, `private`, `version`, `type` (+347 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **15 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_settings()` connect `Community 1` to `Community 0`, `Community 2`, `Community 6`, `Community 7`, `Community 8`, `Community 12`, `Community 14`, `Community 15`, `Community 16`, `Community 22`, `Community 25`, `Community 30`, `Community 32`, `Community 33`, `Community 37`, `Community 39`, `Community 45`, `Community 46`, `Community 47`, `Community 48`, `Community 50`, `Community 52`, `Community 55`, `Community 63`, `Community 64`, `Community 73`, `Community 74`, `Community 86`, `Community 87`, `Community 88`, `Community 92`, `Community 93`, `Community 94`, `Community 95`, `Community 101`, `Community 107`, `Community 108`, `Community 126`, `Community 127`?**
  _High betweenness centrality (0.106) - this node is a cross-community bridge._
- **Why does `Channel` connect `Community 14` to `Community 0`, `Community 1`, `Community 7`, `Community 8`, `Community 12`, `Community 15`, `Community 17`, `Community 18`, `Community 21`, `Community 24`, `Community 29`, `Community 30`, `Community 33`, `Community 37`, `Community 39`, `Community 40`, `Community 46`, `Community 47`, `Community 51`, `Community 52`, `Community 55`, `Community 56`, `Community 61`, `Community 63`, `Community 66`, `Community 73`, `Community 74`, `Community 86`, `Community 92`?**
  _High betweenness centrality (0.072) - this node is a cross-community bridge._
- **Why does `ProcessedPost` connect `Community 4` to `Community 0`, `Community 1`, `Community 2`, `Community 3`, `Community 8`, `Community 9`, `Community 11`, `Community 14`, `Community 15`, `Community 18`, `Community 23`, `Community 24`, `Community 37`, `Community 44`, `Community 51`, `Community 52`, `Community 86`, `Community 101`, `Community 102`?**
  _High betweenness centrality (0.062) - this node is a cross-community bridge._
- **Are the 21 inferred relationships involving `ProcessedPost` (e.g. with `Base` and `BasePublisher`) actually correct?**
  _`ProcessedPost` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `ProcessedPostRepository` (e.g. with `ContentMode` and `PostStatus`) actually correct?**
  _`ProcessedPostRepository` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 44 inferred relationships involving `OrmSchema` (e.g. with `AdIntegrationCreate` and `AdIntegrationResponse`) actually correct?**
  _`OrmSchema` has 44 INFERRED edges - model-reasoned connections that need verification._
- **What connects `docker-entrypoint.sh script`, `name`, `private` to the rest of the system?**
  _352 weakly-connected nodes found - possible documentation gaps or missing edges._