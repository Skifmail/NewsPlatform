<template>
  <div>
    <PageHeader
      title="Настройки"
      subtitle="Управление автоматикой и ручными действиями платформы"
    />

    <section class="settings-category panel-card ai-usage-section">
      <header class="category-header ai-usage-header">
        <div>
          <h2 class="category-title">AI и API</h2>
          <p class="category-subtitle">
            Балансы и кредиты провайдеров
            <span v-if="aiUsage?.fetched_at">
              · обновлено {{ formatAiUsageTime(aiUsage.fetched_at) }}
              <span v-if="aiUsage.from_cache"> (кэш ~{{ Math.round(aiUsage.cache_ttl_seconds / 60) }} мин)</span>
            </span>
          </p>
        </div>
        <button
          type="button"
          class="btn-secondary btn-compact"
          :disabled="aiUsageLoading"
          @click="loadAiUsage(true)"
        >
          {{ aiUsageLoading ? 'Обновление…' : 'Обновить' }}
        </button>
      </header>

      <p v-if="aiUsageError" class="ai-usage-error">{{ aiUsageError }}</p>

      <div v-if="aiUsageLoading && !aiUsage" class="ai-usage-loading">Загрузка данных провайдеров…</div>

      <div v-else-if="aiUsage" class="provider-list">
        <!-- DeepSeek -->
        <article class="provider-row" :class="{ 'is-open': expandedProvider === 'deepseek' }">
          <button type="button" class="provider-header" @click="toggleProvider('deepseek')">
            <div class="provider-header-main">
              <span class="chevron" :class="{ open: expandedProvider === 'deepseek' }">▸</span>
              <div class="provider-title-block">
                <span class="provider-title">DeepSeek</span>
                <span class="provider-sub">Классификация, рерайт, статьи</span>
              </div>
            </div>
            <div class="provider-metrics">
              <div class="provider-metric">
                <span class="provider-metric-val">{{ providerSummaries.deepseek.balance }}</span>
                <span class="provider-metric-label">баланс</span>
              </div>
              <div class="provider-metric">
                <span class="provider-metric-val">{{ providerSummaries.deepseek.spend }}</span>
                <span class="provider-metric-label">расход 30д</span>
              </div>
              <div class="provider-metric">
                <span class="provider-metric-val" :class="providerSummaries.deepseek.statusClass">{{ providerSummaries.deepseek.limit }}</span>
                <span class="provider-metric-label">статус</span>
              </div>
            </div>
          </button>
          <transition name="expand" @enter="startExpand" @after-enter="endExpand" @before-leave="startCollapse" @leave="doCollapse">
            <div v-if="expandedProvider === 'deepseek'" class="expand-body provider-body">
              <template v-if="!aiUsage.deepseek.configured">
                <p class="ai-usage-muted">DEEPSEEK_API_KEY не задан</p>
              </template>
              <template v-else-if="aiUsage.deepseek.error">
                <p class="ai-usage-error-inline">{{ aiUsage.deepseek.error }}</p>
              </template>
              <template v-else>
                <p class="ai-usage-balance">
                  {{ aiUsage.deepseek.total_balance }}
                  <span class="ai-usage-currency">{{ aiUsage.deepseek.currency }}</span>
                </p>
                <p class="ai-usage-muted">
                  Подарочный: {{ aiUsage.deepseek.granted_balance || '0' }}
                  · Пополнение: {{ aiUsage.deepseek.topped_up_balance || '0' }}
                </p>
                <p class="ai-usage-muted">
                  <span
                    class="badge-accent"
                    :class="{ 'badge-danger': aiUsage.deepseek.is_available === false }"
                  >
                    {{ aiUsage.deepseek.is_available === false ? 'Недостаточно средств' : 'Доступен' }}
                  </span>
                </p>
                <p v-if="aiUsage.deepseek.models?.length" class="ai-usage-models">
                  {{ aiUsage.deepseek.models.join(', ') }}
                </p>
                <div v-if="aiUsage.deepseek.history" class="ai-spend">
                  <p class="ai-spend-title">Расходы</p>
                  <div class="ai-spend-row">
                    <span class="ai-spend-item">
                      <span class="ai-spend-val">{{ fmtSpend(aiUsage.deepseek.history.spent_24h) }}</span>
                      <span class="ai-spend-label">24 ч</span>
                    </span>
                    <span class="ai-spend-item">
                      <span class="ai-spend-val">{{ fmtSpend(aiUsage.deepseek.history.spent_7d) }}</span>
                      <span class="ai-spend-label">7 дней</span>
                    </span>
                    <span class="ai-spend-item">
                      <span class="ai-spend-val">{{ fmtSpend(aiUsage.deepseek.history.spent_30d) }}</span>
                      <span class="ai-spend-label">30 дней</span>
                    </span>
                  </div>
                  <p
                    v-if="aiUsage.deepseek.history.topped_up_30d > 0"
                    class="ai-usage-muted"
                  >
                    Пополнено за 30 дней: +{{ fmtSpend(aiUsage.deepseek.history.topped_up_30d) }} {{ aiUsage.deepseek.currency }}
                  </p>
                  <Sparkline
                    v-if="deepseekSpark.length > 1"
                    :points="deepseekSpark"
                    class="ai-spend-spark"
                  />
                  <p v-else class="ai-usage-muted ai-spend-hint">
                    История копится с каждым замером баланса (примерно раз в час) — точки появятся позже.
                  </p>
                </div>
              </template>
            </div>
          </transition>
        </article>

        <!-- Tavily -->
        <article class="provider-row" :class="{ 'is-open': expandedProvider === 'tavily' }">
          <button type="button" class="provider-header" @click="toggleProvider('tavily')">
            <div class="provider-header-main">
              <span class="chevron" :class="{ open: expandedProvider === 'tavily' }">▸</span>
              <div class="provider-title-block">
                <span class="provider-title">Tavily</span>
                <span class="provider-sub">Веб-поиск для статей</span>
              </div>
            </div>
            <div class="provider-metrics">
              <div class="provider-metric">
                <span class="provider-metric-val">{{ providerSummaries.tavily.balance }}</span>
                <span class="provider-metric-label">остаток</span>
              </div>
              <div class="provider-metric">
                <span class="provider-metric-val">{{ providerSummaries.tavily.spend }}</span>
                <span class="provider-metric-label">расход</span>
              </div>
              <div class="provider-metric">
                <span class="provider-metric-val">{{ providerSummaries.tavily.limit }}</span>
                <span class="provider-metric-label">лимит / мес</span>
              </div>
            </div>
          </button>
          <transition name="expand" @enter="startExpand" @after-enter="endExpand" @before-leave="startCollapse" @leave="doCollapse">
            <div v-if="expandedProvider === 'tavily'" class="expand-body provider-body">
              <template v-if="!aiUsage.tavily.configured && !tavilyKeys.length">
                <p class="ai-usage-muted">Ключ не задан — добавьте ниже или TAVILY_API_KEY в .env</p>
              </template>
              <template v-else-if="aiUsage.tavily.error && !aiUsage.tavily.keys?.length">
                <p class="ai-usage-error-inline">{{ aiUsage.tavily.error }}</p>
              </template>
              <template v-else>
                <p class="ai-usage-kpi-label">Осталось у текущего ключа</p>
                <p class="ai-usage-balance">
                  {{ aiUsage.tavily.remaining ?? '—' }}
                  <span class="ai-usage-currency">кредитов</span>
                </p>
                <p class="ai-usage-muted">
                  Лимит плана «{{ aiUsage.tavily.current_plan || '—' }}»:
                  {{ aiUsage.tavily.plan_limit ?? '—' }} / мес.
                </p>
                <div v-if="tavilyUsagePercent != null" class="ai-usage-progress-wrap">
                  <div class="ai-usage-progress">
                    <div class="ai-usage-progress-bar" :style="{ width: `${tavilyUsagePercent}%` }" />
                  </div>
                  <p class="ai-usage-muted">
                    Потрачено {{ aiUsage.tavily.plan_usage }} из {{ aiUsage.tavily.plan_limit }}
                    ({{ tavilyUsagePercent }}%)
                  </p>
                  <p class="ai-usage-muted">
                    Из них Search: {{ aiUsage.tavily.search_usage ?? 0 }} — поиск при генерации статей
                  </p>
                </div>
              </template>

              <div class="tavily-keys-block">
                <p class="ai-usage-kpi-label">Ключи</p>
                <p class="ai-usage-muted ai-usage-explainer">
                  Выберите активный ключ. При автопереключении система уйдёт на следующий,
                  если у текущего кончатся кредиты (до конца месяца).
                </p>
                <label class="tavily-auto-switch">
                  <input v-model="tavilyAutoSwitch" type="checkbox" @change="saveTavilyAutoSwitch" />
                  Автопереключение при исчерпании лимита
                </label>
                <ul v-if="tavilyKeysDisplay.length" class="tavily-keys-list">
                  <li v-for="item in tavilyKeysDisplay" :key="item.id" class="tavily-key-row">
                    <label class="tavily-key-select">
                      <input
                        type="radio"
                        name="tavily-active"
                        :value="item.id"
                        :checked="tavilyActiveKeyId === item.id"
                        @change="activateTavilyKey(item.id)"
                      />
                      <span class="tavily-key-meta">
                        <span class="tavily-key-label">{{ item.label }}</span>
                        <span class="font-mono tavily-key-masked">{{ item.masked_key || item.key }}</span>
                      </span>
                    </label>
                    <span v-if="item.status === 'next'" class="badge-accent">Сейчас эта</span>
                    <span v-else-if="item.status === 'exhausted'" class="badge-danger">
                      Лимит{{ item.ttl_seconds ? ` · ~${formatTtl(item.ttl_seconds)}` : '' }}
                    </span>
                    <span v-else-if="tavilyActiveKeyId === item.id" class="badge-muted">Выбрана</span>
                    <span v-if="item.remaining != null" class="tavily-key-remaining">
                      {{ item.remaining }} кр.
                    </span>
                    <button
                      v-if="item.source !== 'env'"
                      type="button"
                      class="btn-secondary btn-compact tavily-key-remove"
                      :disabled="tavilyKeysSaving"
                      @click="removeTavilyKey(item.id)"
                    >
                      Удалить
                    </button>
                  </li>
                </ul>
                <p v-else class="ai-usage-muted">Пока нет ключей</p>
                <div class="tavily-add-form">
                  <input
                    v-model="tavilyNewLabel"
                    type="text"
                    class="input input-compact-wide"
                    placeholder="Подпись (например, Аккаунт 2)"
                  />
                  <input
                    v-model="tavilyNewKey"
                    type="password"
                    class="input input-compact-wide"
                    placeholder="tvly-…"
                    autocomplete="off"
                  />
                  <button
                    type="button"
                    class="btn-secondary btn-compact"
                    :disabled="tavilyKeysSaving || !tavilyNewKey.trim()"
                    @click="addTavilyKey"
                  >
                    {{ tavilyKeysSaving ? '…' : 'Добавить' }}
                  </button>
                </div>
                <p v-if="tavilyKeysError" class="ai-usage-error-inline">{{ tavilyKeysError }}</p>
              </div>
            </div>
          </transition>
        </article>

        <!-- Qwen -->
        <article class="provider-row" :class="{ 'is-open': expandedProvider === 'qwen' }">
          <button type="button" class="provider-header" @click="toggleProvider('qwen')">
            <div class="provider-header-main">
              <span class="chevron" :class="{ open: expandedProvider === 'qwen' }">▸</span>
              <div class="provider-title-block">
                <span class="provider-title">Qwen Image</span>
                <span class="provider-sub">Обложки (DashScope)</span>
              </div>
            </div>
            <div class="provider-metrics">
              <div class="provider-metric">
                <span class="provider-metric-val">{{ providerSummaries.qwen.balance }}</span>
                <span class="provider-metric-label">активная</span>
              </div>
              <div class="provider-metric">
                <span class="provider-metric-val">{{ providerSummaries.qwen.spend }}</span>
                <span class="provider-metric-label">в цепочке</span>
              </div>
              <div class="provider-metric">
                <span class="provider-metric-val" :class="providerSummaries.qwen.statusClass">{{ providerSummaries.qwen.limit }}</span>
                <span class="provider-metric-label">квота</span>
              </div>
            </div>
          </button>
          <transition name="expand" @enter="startExpand" @after-enter="endExpand" @before-leave="startCollapse" @leave="doCollapse">
            <div v-if="expandedProvider === 'qwen'" class="expand-body provider-body">
              <template v-if="!aiUsage.qwen_image.configured">
                <p class="ai-usage-muted">QWEN_IMAGE_API_KEY не задан</p>
              </template>
              <template v-else>
                <p class="ai-usage-kpi-label">Статус цепочки, не баланс</p>
                <p class="ai-usage-muted ai-usage-explainer">
                  DashScope не отдаёт «осталось N картинок». Платформа пробует модели сверху вниз;
                  если API вернёт ошибку квоты — модель пропускается ~6&nbsp;ч, берётся следующая.
                </p>
                <p v-if="!aiUsage.qwen_image.exhausted_count" class="ai-usage-muted">
                  <span class="badge-accent">Все модели доступны</span>
                </p>
                <p v-else class="ai-usage-error-inline">
                  Временно пропущено из‑за квоты: {{ aiUsage.qwen_image.exhausted_count }}
                </p>
                <div v-if="aiUsage.qwen_image.generate_chain?.length" class="ai-usage-chain">
                  <p class="ai-usage-chain-label">Новые обложки</p>
                  <p class="ai-usage-chain-hint">Text-to-image · при каждой генерации обложки поста</p>
                  <ol class="ai-usage-chain-list">
                    <li
                      v-for="(item, index) in aiUsage.qwen_image.generate_chain"
                      :key="'u-gen-' + item.model"
                    >
                      <span class="ai-usage-chain-rank">{{ index + 1 }}</span>
                      <span class="font-mono">{{ item.model }}</span>
                      <span v-if="item.status === 'next'" class="badge-accent">Сейчас эта</span>
                      <span v-else-if="item.status === 'available'" class="badge-muted">Запасная</span>
                      <span v-else class="badge-danger">Квота · ~{{ formatTtl(item.ttl_seconds) }}</span>
                    </li>
                  </ol>
                </div>
                <div v-if="aiUsage.qwen_image.edit_chain?.length" class="ai-usage-chain">
                  <p class="ai-usage-chain-label">Правка картинок</p>
                  <p class="ai-usage-chain-hint">Image-edit · логотипы GitHub и доработка обложек</p>
                  <ol class="ai-usage-chain-list">
                    <li
                      v-for="(item, index) in aiUsage.qwen_image.edit_chain"
                      :key="'u-edit-' + item.model"
                    >
                      <span class="ai-usage-chain-rank">{{ index + 1 }}</span>
                      <span class="font-mono">{{ item.model }}</span>
                      <span v-if="item.status === 'next'" class="badge-accent">Сейчас эта</span>
                      <span v-else-if="item.status === 'available'" class="badge-muted">Запасная</span>
                      <span v-else class="badge-danger">Квота · ~{{ formatTtl(item.ttl_seconds) }}</span>
                    </li>
                  </ol>
                </div>
              </template>
            </div>
          </transition>
        </article>

        <!-- OpenAI -->
        <article class="provider-row" :class="{ 'is-open': expandedProvider === 'openai' }">
          <button type="button" class="provider-header" @click="toggleProvider('openai')">
            <div class="provider-header-main">
              <span class="chevron" :class="{ open: expandedProvider === 'openai' }">▸</span>
              <div class="provider-title-block">
                <span class="provider-title">OpenAI</span>
                <span class="provider-sub">GPT Image 2 · обложки</span>
              </div>
            </div>
            <div class="provider-metrics">
              <div class="provider-metric">
                <span class="provider-metric-val">{{ providerSummaries.openai.balance }}</span>
                <span class="provider-metric-label">ключи</span>
              </div>
              <div class="provider-metric">
                <span class="provider-metric-val">{{ providerSummaries.openai.spend }}</span>
                <span class="provider-metric-label">расход 30д</span>
              </div>
              <div class="provider-metric">
                <span class="provider-metric-val" :class="providerSummaries.openai.statusClass">{{ providerSummaries.openai.limit }}</span>
                <span class="provider-metric-label">статус</span>
              </div>
            </div>
          </button>
          <transition name="expand" @enter="startExpand" @after-enter="endExpand" @before-leave="startCollapse" @leave="doCollapse">
            <div v-if="expandedProvider === 'openai'" class="expand-body provider-body">
              <template v-if="aiUsage.openai.error">
                <p class="ai-usage-error-inline">{{ aiUsage.openai.error }}</p>
              </template>
              <template v-else-if="aiUsage.openai.total_spent_30d != null">
                <p class="ai-usage-balance">
                  {{ aiUsage.openai.total_spent_30d.toFixed(2) }}
                  <span class="ai-usage-currency">{{ aiUsage.openai.currency || 'USD' }}</span>
                  <span class="ai-usage-muted" style="margin-left:.4em">за 30 дней</span>
                </p>
              </template>
              <template v-else>
                <p class="ai-usage-muted">
                  <span :class="(aiUsage.openai.configured || openaiKeys.length) ? 'badge-accent' : 'badge-muted'">
                    {{ (aiUsage.openai.configured || openaiKeys.length) ? 'Ключ задан' : 'Не используется' }}
                  </span>
                  <span v-if="aiUsage.openai.configured" class="ai-usage-muted" style="margin-left:.5em">
                    (.env)
                  </span>
                </p>
              </template>
              <p v-if="aiUsage.openai.note" class="ai-usage-muted">{{ aiUsage.openai.note }}</p>

              <div class="tavily-keys-block">
                <p class="ai-usage-kpi-label">Ключи из панели</p>
                <p class="ai-usage-muted ai-usage-explainer">
                  Первый включённый ключ используется для генерации GPT Image 2.
                  Переключайте тумблером — выключенные ключи не расходуются.
                </p>
                <ul v-if="openaiKeys.length" class="tavily-keys-list">
                  <li v-for="item in openaiKeys" :key="item.id" class="tavily-key-row">
                    <label class="tavily-key-select openai-key-select">
                      <input
                        type="checkbox"
                        :checked="item.enabled"
                        @change="toggleOpenaiKey(item.id, $event.target.checked)"
                      />
                      <span class="tavily-key-meta">
                        <span class="tavily-key-label">{{ item.label }}</span>
                        <span v-if="item.note" class="openai-key-note">{{ item.note }}</span>
                        <span class="font-mono tavily-key-masked">{{ item.key }}</span>
                      </span>
                    </label>
                    <span v-if="item.enabled" class="badge-accent">Вкл</span>
                    <span v-else class="badge-muted">Выкл</span>
                    <button
                      type="button"
                      class="btn-secondary btn-compact tavily-key-remove"
                      :disabled="openaiKeysSaving"
                      @click="removeOpenaiKey(item.id)"
                    >
                      Удалить
                    </button>
                  </li>
                </ul>
                <p v-else class="ai-usage-muted">Пока нет ключей</p>
                <div class="tavily-add-form openai-add-form">
                  <input
                    v-model="openaiNewLabel"
                    type="text"
                    class="input input-compact-wide"
                    placeholder="Название (напр. Prod ключ)"
                  />
                  <input
                    v-model="openaiNewNote"
                    type="text"
                    class="input input-compact-wide"
                    placeholder="Заметка (напр. для канала Открытки)"
                  />
                  <input
                    v-model="openaiNewKey"
                    type="password"
                    class="input input-compact-wide"
                    placeholder="sk-…"
                    autocomplete="off"
                  />
                  <button
                    type="button"
                    class="btn-secondary btn-compact"
                    :disabled="openaiKeysSaving || !openaiNewKey.trim()"
                    @click="addOpenaiKey"
                  >
                    {{ openaiKeysSaving ? '…' : 'Добавить' }}
                  </button>
                </div>
                <p v-if="openaiKeysError" class="ai-usage-error-inline">{{ openaiKeysError }}</p>
              </div>
            </div>
          </transition>
        </article>

        <!-- OpenRouter -->
        <article class="provider-row" :class="{ 'is-open': expandedProvider === 'openrouter' }">
          <button type="button" class="provider-header" @click="toggleProvider('openrouter')">
            <div class="provider-header-main">
              <span class="chevron" :class="{ open: expandedProvider === 'openrouter' }">▸</span>
              <div class="provider-title-block">
                <span class="provider-title">OpenRouter</span>
                <span class="provider-sub">Grok Imagine Video · анимация</span>
              </div>
            </div>
            <div class="provider-metrics">
              <div class="provider-metric">
                <span class="provider-metric-val">{{ providerSummaries.openrouter.balance }}</span>
                <span class="provider-metric-label">остаток</span>
              </div>
              <div class="provider-metric">
                <span class="provider-metric-val">{{ providerSummaries.openrouter.spend }}</span>
                <span class="provider-metric-label">расход</span>
              </div>
              <div class="provider-metric">
                <span class="provider-metric-val">{{ providerSummaries.openrouter.limit }}</span>
                <span class="provider-metric-label">куплено</span>
              </div>
            </div>
          </button>
          <transition name="expand" @enter="startExpand" @after-enter="endExpand" @before-leave="startCollapse" @leave="doCollapse">
            <div v-if="expandedProvider === 'openrouter'" class="expand-body provider-body">
              <template v-if="!aiUsage.openrouter?.configured">
                <p class="ai-usage-muted">{{ aiUsage.openrouter?.note || 'Ключ OpenRouter не задан' }}</p>
              </template>
              <template v-else-if="aiUsage.openrouter.error">
                <p class="ai-usage-error-inline">{{ aiUsage.openrouter.error }}</p>
              </template>
              <template v-else>
                <p v-if="aiUsage.openrouter.remaining != null" class="ai-usage-balance">
                  {{ fmtSpend(aiUsage.openrouter.remaining) }}
                  <span class="ai-usage-currency">USD</span>
                  <span class="ai-usage-muted" style="margin-left:.4em">остаток</span>
                </p>
                <p v-else class="ai-usage-balance">
                  {{ fmtSpend(aiUsage.openrouter.key_usage) }}
                  <span class="ai-usage-currency">USD</span>
                  <span class="ai-usage-muted" style="margin-left:.4em">потрачено ключом</span>
                </p>
                <p class="ai-usage-muted">
                  <template v-if="aiUsage.openrouter.total_credits != null">
                    Куплено: {{ fmtSpend(aiUsage.openrouter.total_credits) }}
                    · Потрачено: {{ fmtSpend(aiUsage.openrouter.total_usage) }}
                  </template>
                  <template v-else>
                    Ключ сегодня: {{ fmtSpend(aiUsage.openrouter.key_usage_daily) }}
                    · месяц: {{ fmtSpend(aiUsage.openrouter.key_usage_monthly) }}
                    <template v-if="aiUsage.openrouter.limit != null">
                      · лимит ключа: {{ fmtSpend(aiUsage.openrouter.limit_remaining) }} / {{ fmtSpend(aiUsage.openrouter.limit) }}
                    </template>
                  </template>
                </p>
                <p v-if="aiUsage.openrouter.key_label" class="ai-usage-muted">
                  Активный ключ: {{ aiUsage.openrouter.key_label }}
                </p>
                <p v-if="aiUsage.openrouter.note" class="ai-usage-muted">{{ aiUsage.openrouter.note }}</p>
              </template>

              <p class="field-hint mt-3">
                Ключ с <a href="https://openrouter.ai/keys" target="_blank" rel="noopener">openrouter.ai</a>.
                Модель по умолчанию: <span class="font-mono">x-ai/grok-imagine-video</span>.
              </p>

              <div class="tavily-keys-block mt-3">
                <p class="ai-usage-kpi-label">Ключи из панели</p>
                <p class="ai-usage-muted ai-usage-explainer">
                  Первый включённый ключ используется для анимации обложек.
                </p>
                <ul v-if="openrouterKeys.length" class="tavily-keys-list">
                  <li v-for="item in openrouterKeys" :key="item.id" class="tavily-key-row">
                    <label class="tavily-key-select openai-key-select">
                      <input
                        type="checkbox"
                        :checked="item.enabled"
                        @change="toggleOpenrouterKey(item.id, $event.target.checked)"
                      />
                      <span class="tavily-key-meta">
                        <span class="tavily-key-label">{{ item.label }}</span>
                        <span v-if="item.note" class="openai-key-note">{{ item.note }}</span>
                        <span class="font-mono tavily-key-masked">{{ item.key }}</span>
                      </span>
                    </label>
                    <span v-if="item.enabled" class="badge-accent">Вкл</span>
                    <span v-else class="badge-muted">Выкл</span>
                    <button
                      type="button"
                      class="btn-secondary btn-compact tavily-key-remove"
                      :disabled="openrouterKeysSaving"
                      @click="removeOpenrouterKey(item.id)"
                    >
                      Удалить
                    </button>
                  </li>
                </ul>
                <p v-else class="ai-usage-muted">Пока нет ключей</p>
                <div class="tavily-add-form openai-add-form">
                  <input
                    v-model="openrouterNewLabel"
                    type="text"
                    class="input input-compact-wide"
                    placeholder="Название (напр. Prod OpenRouter)"
                  />
                  <input
                    v-model="openrouterNewNote"
                    type="text"
                    class="input input-compact-wide"
                    placeholder="Заметка (напр. анимация обложек)"
                  />
                  <input
                    v-model="openrouterNewKey"
                    type="password"
                    class="input input-compact-wide"
                    placeholder="sk-or-v1-…"
                    autocomplete="off"
                  />
                  <button
                    type="button"
                    class="btn-secondary btn-compact"
                    :disabled="openrouterKeysSaving || !openrouterNewKey.trim()"
                    @click="addOpenrouterKey"
                  >
                    {{ openrouterKeysSaving ? '…' : 'Сохранить ключ' }}
                  </button>
                </div>
                <p v-if="openrouterKeysError" class="ai-usage-error-inline">{{ openrouterKeysError }}</p>
              </div>

              <label class="field-label mt-4" for="openrouter-video-model">Модель видео</label>
              <input
                id="openrouter-video-model"
                v-model="openrouterVideoModel"
                type="text"
                class="input w-full mt-1 font-mono text-xs"
                placeholder="x-ai/grok-imagine-video"
              />
              <label class="field-label mt-3" for="postcard-animation-duration">
                Длительность анимации (сек)
              </label>
              <input
                id="postcard-animation-duration"
                v-model.number="postcardAnimationDuration"
                type="number"
                min="1"
                max="15"
                step="1"
                class="input w-full mt-1 font-mono text-xs"
              />
              <p class="field-hint mt-1">
                Короткий GIF-эффект: 1–2 сек. Диапазон модели Grok: 1–15 сек.
              </p>
              <label class="active-toggle mt-4 block">
                <input v-model="postcardAnimationEnabled" type="checkbox" class="active-checkbox" />
                <span>Анимация обложек включена глобально</span>
              </label>
              <p class="field-hint mt-2">
                Если выключено — все каналы получают только статичные картинки.
                На каждом канале со статьями можно включить анимацию отдельно.
              </p>
              <button
                type="button"
                class="btn-secondary btn-compact mt-4"
                :disabled="openrouterParamsSaving"
                @click="saveOpenrouterParams"
              >
                {{ openrouterParamsSaving ? 'Сохранение…' : 'Сохранить параметры' }}
              </button>
            </div>
          </transition>
        </article>

        <!-- Platform activity -->
        <article class="provider-row" :class="{ 'is-open': expandedProvider === 'local' }">
          <button type="button" class="provider-header" @click="toggleProvider('local')">
            <div class="provider-header-main">
              <span class="chevron" :class="{ open: expandedProvider === 'local' }">▸</span>
              <div class="provider-title-block">
                <span class="provider-title">Активность платформы</span>
                <span class="provider-sub">Локальный счётчик задач</span>
              </div>
            </div>
            <div class="provider-metrics">
              <div class="provider-metric">
                <span class="provider-metric-val">{{ aiUsage.local.deepseek_jobs_24h }}</span>
                <span class="provider-metric-label">AI 24ч</span>
              </div>
              <div class="provider-metric">
                <span class="provider-metric-val">{{ aiUsage.local.articles_24h }}</span>
                <span class="provider-metric-label">статьи 24ч</span>
              </div>
              <div class="provider-metric">
                <span class="provider-metric-val">{{ aiUsage.local.generated_images_30d }}</span>
                <span class="provider-metric-label">обложки 30д</span>
              </div>
            </div>
          </button>
          <transition name="expand" @enter="startExpand" @after-enter="endExpand" @before-leave="startCollapse" @leave="doCollapse">
            <div v-if="expandedProvider === 'local'" class="expand-body provider-body">
              <div class="ai-usage-stats">
                <div>
                  <p class="ai-usage-stat-value">{{ aiUsage.local.deepseek_jobs_24h }}</p>
                  <p class="ai-usage-stat-label">AI-задач за 24 ч</p>
                </div>
                <div>
                  <p class="ai-usage-stat-value">{{ aiUsage.local.deepseek_jobs_30d }}</p>
                  <p class="ai-usage-stat-label">AI-задач за 30 дн.</p>
                </div>
                <div>
                  <p class="ai-usage-stat-value">{{ aiUsage.local.articles_24h }}</p>
                  <p class="ai-usage-stat-label">Статей за 24 ч</p>
                </div>
                <div>
                  <p class="ai-usage-stat-value">{{ aiUsage.local.generated_images_30d }}</p>
                  <p class="ai-usage-stat-label">Обложек за 30 дн.</p>
                </div>
              </div>
            </div>
          </transition>
        </article>
      </div>
    </section>

    <form class="settings-form" @submit.prevent="save">
      <div class="settings-grid">
        <section class="settings-category panel-card">
          <header class="category-header">
            <h2 class="category-title">Автоматика</h2>
            <p class="category-subtitle">Задачи по расписанию Celery Beat</p>
          </header>
          <div class="table-wrap overflow-hidden">
            <table class="table-panel settings-table">
              <thead>
                <tr>
                  <th>Параметр</th>
                  <th>Описание</th>
                  <th class="col-toggle">Вкл.</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td class="setting-name">Автопарсинг источников</td>
                  <td class="setting-desc">Интервал: {{ fetchInterval }} мин (ниже в «Интервалы»)</td>
                  <td class="col-toggle">
                    <SettingToggle v-model="scheduleFetch" />
                  </td>
                </tr>
                <tr>
                  <td class="setting-name">AI после автопарсинга</td>
                  <td class="setting-desc">Новые материалы сразу ставятся в очередь DeepSeek</td>
                  <td class="col-toggle">
                    <SettingToggle v-model="scheduleAi" />
                  </td>
                </tr>
                <tr>
                  <td class="setting-name">Публикация по расписанию</td>
                  <td class="setting-desc">Публикация одобренных постов по расписанию канала (publish_times, МСК)</td>
                  <td class="col-toggle">
                    <SettingToggle v-model="schedulePublish" />
                  </td>
                </tr>
                <tr>
                  <td class="setting-name">Очистка старых записей</td>
                  <td class="setting-desc">
                    Ежедневно в {{ retentionHourUtc }}:{{ String(retentionMinuteUtc).padStart(2, '0') }} UTC.
                    Материалы без AI старше {{ rawPostsRetentionDays }} дн. удаляются автоматически.
                  </td>
                  <td class="col-toggle">
                    <SettingToggle v-model="scheduleRetention" />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="schedulerLastFetch || schedulerLastRetention" class="category-meta">
            <p v-if="schedulerLastFetch">Последний автопарсинг (UTC): {{ schedulerLastFetch }}</p>
            <p v-if="schedulerLastRetention">Последняя очистка (UTC): {{ schedulerLastRetention }}</p>
          </div>
        </section>

        <section class="settings-category panel-card">
          <header class="category-header">
            <h2 class="category-title">Ручное управление</h2>
            <p class="category-subtitle">Кнопки и действия из панели</p>
          </header>
          <div class="table-wrap overflow-hidden">
            <table class="table-panel settings-table">
              <thead>
                <tr>
                  <th>Параметр</th>
                  <th>Описание</th>
                  <th class="col-toggle">Вкл.</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td class="setting-name">Кнопка «Парсить»</td>
                  <td class="setting-desc">Ручной запуск парсинга одного источника</td>
                  <td class="col-toggle">
                    <SettingToggle v-model="manualFetch" />
                  </td>
                </tr>
                <tr>
                  <td class="setting-name">AI из «Материалы»</td>
                  <td class="setting-desc">Кнопки «На AI» и пакетная обработка</td>
                  <td class="col-toggle">
                    <SettingToggle v-model="manualAi" />
                  </td>
                </tr>
                <tr>
                  <td class="setting-name">AI после ручного парсинга</td>
                  <td class="setting-desc">Автоматически обрабатывать новые материалы после «Парсить»</td>
                  <td class="col-toggle">
                    <SettingToggle v-model="autoAiAfterManualFetch" />
                  </td>
                </tr>
                <tr>
                  <td class="setting-name">Ручная публикация</td>
                  <td class="setting-desc">«Опубликовать сейчас» и «Одобрить и опубликовать»</td>
                  <td class="col-toggle">
                    <SettingToggle v-model="manualPublish" />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="settings-category panel-card">
          <header class="category-header">
            <h2 class="category-title">Интервалы и парсинг</h2>
            <p class="category-subtitle">Тайминги и окно свежести ленты</p>
          </header>
          <div class="table-wrap overflow-hidden">
            <table class="table-panel settings-table">
              <thead>
                <tr>
                  <th>Параметр</th>
                  <th>Значение</th>
                  <th>Примечание</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td class="setting-name">Интервал автопарсинга</td>
                  <td>
                    <input
                      v-model.number="fetchInterval"
                      type="number"
                      min="5"
                      max="1440"
                      class="input input-compact"
                    />
                    <span class="input-suffix">мин</span>
                  </td>
                  <td class="setting-desc">От 5 до 1440</td>
                </tr>
                <tr>
                  <td class="setting-name">Окно свежести</td>
                  <td>
                    <input
                      v-model.number="fetchMaxAgeDays"
                      type="number"
                      min="1"
                      max="30"
                      class="input input-compact"
                    />
                    <span class="input-suffix">дн.</span>
                  </td>
                  <td class="setting-desc">1 = только вчера и сегодня по дате в ленте</td>
                </tr>
                <tr>
                  <td class="setting-name">Час очистки</td>
                  <td>
                    <input
                      v-model.number="retentionHourUtc"
                      type="number"
                      min="0"
                      max="23"
                      class="input input-compact"
                    />
                    <span class="input-suffix">UTC</span>
                  </td>
                  <td class="setting-desc">0–23</td>
                </tr>
                <tr>
                  <td class="setting-name">Минута очистки</td>
                  <td>
                    <input
                      v-model.number="retentionMinuteUtc"
                      type="number"
                      min="0"
                      max="59"
                      class="input input-compact"
                    />
                    <span class="input-suffix">UTC</span>
                  </td>
                  <td class="setting-desc">0–59</td>
                </tr>
                <tr>
                  <td class="setting-name">Хранение материалов без AI</td>
                  <td>
                    <input
                      v-model.number="rawPostsRetentionDays"
                      type="number"
                      min="1"
                      max="90"
                      class="input input-compact"
                    />
                    <span class="input-suffix">дн.</span>
                  </td>
                  <td class="setting-desc">Необработанные записи в «Материалы» старше этого срока удаляются при очистке</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="settings-category panel-card">
          <header class="category-header">
            <h2 class="category-title">Модерация и лимиты</h2>
            <p class="category-subtitle">Одобрение и дневные квоты</p>
          </header>
          <div class="table-wrap overflow-hidden">
            <table class="table-panel settings-table">
              <thead>
                <tr>
                  <th>Параметр</th>
                  <th>Описание / значение</th>
                  <th class="col-toggle">Вкл.</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td class="setting-name">Автоодобрение</td>
                  <td class="setting-desc">
                    После AI — approved и публикация в каналы (не зависит от «Ручная публикация»)
                  </td>
                  <td class="col-toggle">
                    <SettingToggle v-model="autoApprove" />
                  </td>
                </tr>
                <tr>
                  <td class="setting-name">Постов в день на канал</td>
                  <td colspan="2">
                    <input v-model.number="postsPerDay" type="number" min="1" class="input input-compact" />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <section class="settings-category panel-card">
        <header class="category-header">
          <h2 class="category-title">Автогенерация статей</h2>
          <p class="category-subtitle">Длинные статьи с поиском в интернете и Telegraph</p>
        </header>
        <div class="table-wrap overflow-hidden">
          <table class="table-panel settings-table">
            <thead>
              <tr>
                <th>Параметр</th>
                <th>Описание</th>
                <th class="col-toggle">Вкл.</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td class="setting-name">Статьи по расписанию</td>
                <td class="setting-desc">
                  AI придумывает тему, ищет в интернете (Tavily), пишет статью и публикует анонс + Telegraph
                </td>
                <td class="col-toggle">
                  <SettingToggle v-model="scheduleArticle" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="field-hint">
          Работает только для каналов с режимом «Статьи». Нужен ключ Tavily
          (в блоке «AI и API» выше или TAVILY_API_KEY) и QWEN_IMAGE_API_KEY (обложки).
        </p>
        <div v-if="articleStatus.length" class="category-meta space-y-1">
          <p v-for="line in articleStatus" :key="line">{{ line }}</p>
        </div>
        <p class="field-hint">
          Промпты выбора темы и написания статьи редактируются в разделе
          <RouterLink to="/prompts" class="text-accent underline">«Промпты»</RouterLink>.
        </p>
      </section>

      <div class="settings-grid">
        <section class="settings-category panel-card">
          <header class="category-header">
            <h2 class="category-title">Генерация обложек</h2>
            <p class="category-subtitle">Модели Qwen text-to-image и image-edit</p>
          </header>
          <p class="field-hint">
            Порядок моделей сверху вниз. При исчерпании квоты платформа автоматически
            переключается на следующую (кэш ~6 ч). WAN/video-модели сюда не добавляйте —
            только text-to-image из вкладки Vision.
          </p>
          <label class="field-label">Модели text-to-image</label>
          <textarea
            v-model="qwenImageModels"
            rows="4"
            class="input w-full mt-1 font-mono text-xs"
            placeholder="qwen-image-plus,qwen-image-max,qwen-image"
          />
          <label class="field-label mt-3">Модели image-edit (логотипы GitHub)</label>
          <textarea
            v-model="qwenImageEditModels"
            rows="3"
            class="input w-full mt-1 font-mono text-xs"
            placeholder="qwen-image-edit-plus,qwen-image-edit-max"
          />
          <p class="field-hint mt-3">
            Статус моделей (какая активна, какие пропущены по квоте) — в блоке
            <strong>«AI и API»</strong> вверху страницы.
          </p>
        </section>

        <section class="settings-category panel-card">
          <header class="category-header">
            <h2 class="category-title">AI и классификация</h2>
            <p class="category-subtitle">Промпт определения тематики материала</p>
          </header>
          <p class="field-hint">
            Промпт классификации и остальные AI-промпты редактируются в разделе
            <RouterLink to="/prompts" class="text-accent underline">«Промпты»</RouterLink>.
          </p>
        </section>
      </div>

      <footer class="settings-footer">
        <button type="submit" class="btn-primary" :disabled="saving">
          {{ saving ? 'Сохранение…' : 'Сохранить' }}
        </button>
      </footer>
    </form>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, defineComponent, h } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import PageHeader from '../components/layout/PageHeader.vue'
import Sparkline from '../components/analytics/Sparkline.vue'
import { settingsApi, aiUsageApi } from '../api/index.js'
import { useDialogStore } from '../stores/dialogStore'

const dialog = useDialogStore()

const SettingToggle = defineComponent({
  name: 'SettingToggle',
  props: {
    modelValue: { type: Boolean, required: true },
  },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    return () =>
      h(
        'button',
        {
          type: 'button',
          class: ['toggle', 'mx-auto', props.modelValue ? 'toggle-on' : ''],
          role: 'switch',
          'aria-checked': props.modelValue,
          onClick: () => emit('update:modelValue', !props.modelValue),
        },
        [h('span', { class: 'toggle-thumb' })],
      )
  },
})

function boolFrom(s, fallback = false) {
  if (s === undefined || s === null || s === '') return fallback
  return s === 'true' || s === '1'
}

const scheduleFetch = ref(true)
const scheduleAi = ref(true)
const schedulePublish = ref(true)
const scheduleRetention = ref(true)
const scheduleArticle = ref(false)
const articleStatus = ref([])
const manualFetch = ref(true)
const manualAi = ref(true)
const manualPublish = ref(true)
const autoAiAfterManualFetch = ref(true)
const autoApprove = ref(false)
const fetchInterval = ref(30)
const fetchMaxAgeDays = ref(1)
const retentionHourUtc = ref(3)
const retentionMinuteUtc = ref(30)
const rawPostsRetentionDays = ref(3)
const postsPerDay = ref(10)
const qwenImageModels = ref('')
const qwenImageEditModels = ref('')
const schedulerLastFetch = ref('')
const schedulerLastRetention = ref('')
const saving = ref(false)
const savedSnapshot = ref('')
const aiUsage = ref(null)
const aiUsageLoading = ref(false)
const aiUsageError = ref('')
const expandedProvider = ref(null)

function toggleProvider(id) {
  expandedProvider.value = expandedProvider.value === id ? null : id
}

function startExpand(el) {
  el.style.height = '0'
  el.style.overflow = 'hidden'
  void el.offsetHeight
  el.style.height = `${el.scrollHeight}px`
}
function endExpand(el) {
  el.style.height = ''
  el.style.overflow = ''
}
function startCollapse(el) {
  el.style.height = `${el.scrollHeight}px`
  el.style.overflow = 'hidden'
  void el.offsetHeight
}
function doCollapse(el) {
  el.style.height = '0'
}

function fmtSpend(n) {
  if (n == null) return '—'
  const num = Number(n)
  if (Number.isNaN(num)) return '—'
  if (num === 0) return '0'
  return num < 0.01 ? num.toFixed(4) : num.toFixed(2)
}

const providerSummaries = computed(() => {
  const u = aiUsage.value
  const ds = u?.deepseek
  const tv = u?.tavily
  const qw = u?.qwen_image
  const oa = u?.openai
  const or_ = u?.openrouter

  const qwenNext = (qw?.generate_chain || []).find((m) => m.status === 'next')
  const qwenCount = (qw?.generate_chain || []).length

  return {
    deepseek: {
      balance: ds?.configured && !ds.error ? `${ds.total_balance || '—'} ${ds.currency || ''}`.trim() : '—',
      spend: ds?.history ? fmtSpend(ds.history.spent_30d) : '—',
      limit: !ds?.configured ? 'нет ключа' : ds.error ? 'ошибка' : ds.is_available === false ? 'нет средств' : 'OK',
      statusClass: ds?.is_available === false || ds?.error ? 'is-bad' : '',
    },
    tavily: {
      balance: tv?.remaining != null ? String(tv.remaining) : '—',
      spend: tv?.plan_usage != null ? String(tv.plan_usage) : '—',
      limit: tv?.plan_limit != null ? String(tv.plan_limit) : '—',
      statusClass: '',
    },
    qwen: {
      balance: !qw?.configured ? '—' : qwenNext ? qwenNext.model.replace(/^.*\//, '').slice(0, 18) : '—',
      spend: qw?.configured ? String(qwenCount) : '—',
      limit: !qw?.configured ? 'нет ключа' : qw.exhausted_count ? `${qw.exhausted_count} skip` : 'OK',
      statusClass: qw?.exhausted_count ? 'is-bad' : '',
    },
    openai: {
      balance: String(openaiKeys.value.filter((k) => k.enabled).length || (oa?.configured ? 1 : 0)),
      spend: oa?.total_spent_30d != null ? fmtSpend(oa.total_spent_30d) : '—',
      limit: oa?.error ? 'ошибка' : oa?.configured || openaiKeys.value.length ? 'OK' : 'нет ключа',
      statusClass: oa?.error ? 'is-bad' : '',
    },
    openrouter: {
      balance: or_?.remaining != null ? fmtSpend(or_.remaining) : or_?.configured ? fmtSpend(or_.key_usage) : '—',
      spend: or_?.total_usage != null ? fmtSpend(or_.total_usage) : or_?.key_usage_monthly != null ? fmtSpend(or_.key_usage_monthly) : '—',
      limit: or_?.total_credits != null ? fmtSpend(or_.total_credits) : or_?.limit != null ? fmtSpend(or_.limit) : or_?.configured ? '∞' : '—',
      statusClass: or_?.error ? 'is-bad' : '',
    },
  }
})

const deepseekSpark = computed(() => {
  const pts = aiUsage.value?.deepseek?.history?.points || []
  return pts.map((p) => Number(p.balance)).filter((n) => !Number.isNaN(n))
})

const tavilyKeys = ref([])
const tavilyActiveKeyId = ref('')
const tavilyAutoSwitch = ref(true)
const tavilyNewLabel = ref('')
const tavilyNewKey = ref('')
const tavilyKeysSaving = ref(false)
const tavilyKeysError = ref('')

const openaiKeys = ref([])
const openaiNewLabel = ref('')
const openaiNewNote = ref('')
const openaiNewKey = ref('')
const openaiKeysSaving = ref(false)
const openaiKeysError = ref('')

const openrouterKeys = ref([])
const openrouterNewLabel = ref('')
const openrouterNewNote = ref('')
const openrouterNewKey = ref('')
const openrouterKeysSaving = ref(false)
const openrouterKeysError = ref('')
const openrouterParamsSaving = ref(false)
const openrouterVideoModel = ref('x-ai/grok-imagine-video')
const postcardAnimationEnabled = ref(true)
const postcardAnimationDuration = ref(2)

const tavilyUsagePercent = computed(() => {
  const t = aiUsage.value?.tavily
  if (!t || t.plan_limit == null || t.plan_usage == null || t.plan_limit <= 0) return null
  return Math.min(100, Math.round((t.plan_usage / t.plan_limit) * 100))
})

const tavilyKeysDisplay = computed(() => {
  const usageKeys = aiUsage.value?.tavily?.keys
  if (usageKeys?.length) {
    return usageKeys.map((item) => ({
      id: item.id,
      label: item.label,
      masked_key: item.masked_key,
      source: item.source,
      status: item.status,
      ttl_seconds: item.ttl_seconds,
      remaining: item.remaining,
    }))
  }
  return tavilyKeys.value.map((item) => ({
    id: item.id,
    label: item.label,
    masked_key: item.key,
    source: item.source || 'db',
    status: tavilyActiveKeyId.value === item.id ? 'next' : 'available',
    ttl_seconds: null,
    remaining: null,
  }))
})

const isDirty = computed(() => getFormSnapshot() !== savedSnapshot.value)

onMounted(() => {
  loadSettings()
  loadAiUsage(false)
  window.addEventListener('beforeunload', onBeforeUnload)
})

onUnmounted(() => {
  window.removeEventListener('beforeunload', onBeforeUnload)
})

onBeforeRouteLeave(async (_to, _from, next) => {
  if (!isDirty.value) {
    next()
    return
  }

  const choice = await dialog.unsavedChanges({
    message: 'Вы изменили настройки, но не сохранили их. Что сделать?',
  })

  if (choice === 'stay') {
    next(false)
    return
  }

  if (choice === 'discard') {
    next()
    return
  }

  try {
    await save({ silent: true })
    next()
  } catch {
    next(false)
  }
})

function onBeforeUnload(event) {
  if (!isDirty.value) return
  event.preventDefault()
  event.returnValue = ''
}

function getFormSnapshot() {
  return JSON.stringify({
    schedule_fetch_enabled: scheduleFetch.value,
    schedule_ai_enabled: scheduleAi.value,
    schedule_publish_enabled: schedulePublish.value,
    schedule_retention_enabled: scheduleRetention.value,
    schedule_article_publish_enabled: scheduleArticle.value,
    manual_fetch_enabled: manualFetch.value,
    manual_ai_enabled: manualAi.value,
    manual_publish_enabled: manualPublish.value,
    auto_ai_after_manual_fetch: autoAiAfterManualFetch.value,
    auto_approve: autoApprove.value,
    fetch_interval_minutes: fetchInterval.value,
    fetch_max_age_days: fetchMaxAgeDays.value,
    retention_hour_utc: retentionHourUtc.value,
    retention_minute_utc: retentionMinuteUtc.value,
    raw_posts_retention_days: rawPostsRetentionDays.value,
    posts_per_day: postsPerDay.value,
    qwen_image_models: qwenImageModels.value,
    qwen_image_edit_models: qwenImageEditModels.value,
  })
}

function markSaved() {
  savedSnapshot.value = getFormSnapshot()
}

function formatTtl(seconds) {
  const mins = Math.max(1, Math.round(Number(seconds) / 60))
  if (mins < 60) return `${mins} мин`
  const hours = Math.round(mins / 60)
  if (hours < 48) return `${hours} ч`
  const days = Math.round(hours / 24)
  return `${days} дн.`
}

function formatAiUsageTime(iso) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString('ru-RU', { timeZone: 'UTC', timeZoneName: 'short' })
  } catch {
    return iso
  }
}

async function loadAiUsage(refresh = false) {
  aiUsageLoading.value = true
  aiUsageError.value = ''
  try {
    const { data } = await aiUsageApi.get(refresh ? { refresh: true } : {})
    aiUsage.value = data
    if (data?.tavily) {
      tavilyAutoSwitch.value = data.tavily.auto_switch !== false
      if (data.tavily.active_key_id) {
        tavilyActiveKeyId.value = data.tavily.active_key_id
      }
    }
  } catch (err) {
    aiUsageError.value = err.response?.data?.detail || 'Не удалось загрузить данные AI/API'
  } finally {
    aiUsageLoading.value = false
  }
}

function parseTavilyResolved(raw) {
  try {
    const parsed = JSON.parse(raw || '[]')
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function parseOpenaiKeys(raw) {
  try {
    const parsed = JSON.parse(raw || '[]')
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function parseOpenrouterKeys(raw) {
  return parseOpenaiKeys(raw)
}

async function loadSettings() {
  const { data } = await settingsApi.get()
  const s = data.settings
  scheduleFetch.value = boolFrom(s.schedule_fetch_enabled, true)
  scheduleAi.value = boolFrom(s.schedule_ai_enabled, true)
  schedulePublish.value = boolFrom(s.schedule_publish_enabled, true)
  scheduleRetention.value = boolFrom(s.schedule_retention_enabled, true)
  scheduleArticle.value = boolFrom(s.schedule_article_publish_enabled, false)
  articleStatus.value = Object.entries(s)
    .filter(([key]) => key.startsWith('scheduler_last_article_'))
    .map(([key, value]) => {
      const id = key.replace('scheduler_last_article_', '')
      return `Канал #${id} (UTC): ${value}`
    })
  manualFetch.value = boolFrom(s.manual_fetch_enabled, true)
  manualAi.value = boolFrom(s.manual_ai_enabled, true)
  manualPublish.value = boolFrom(s.manual_publish_enabled, true)
  autoAiAfterManualFetch.value = boolFrom(s.auto_ai_after_manual_fetch, true)
  autoApprove.value = boolFrom(s.auto_approve, false)
  fetchInterval.value = parseInt(s.fetch_interval_minutes || '30', 10)
  fetchMaxAgeDays.value = parseInt(s.fetch_max_age_days || '1', 10)
  retentionHourUtc.value = parseInt(s.retention_hour_utc || '3', 10)
  retentionMinuteUtc.value = parseInt(s.retention_minute_utc || '30', 10)
  rawPostsRetentionDays.value = parseInt(s.raw_posts_retention_days || '3', 10)
  postsPerDay.value = parseInt(s.posts_per_day || '10', 10)
  qwenImageModels.value = s.qwen_image_models || ''
  qwenImageEditModels.value = s.qwen_image_edit_models || ''
  openrouterKeys.value = parseOpenrouterKeys(s.openrouter_api_keys)
  openrouterVideoModel.value = s.openrouter_video_model || 'x-ai/grok-imagine-video'
  postcardAnimationEnabled.value = boolFrom(s.postcard_animation_enabled, true)
  postcardAnimationDuration.value = parseInt(s.postcard_animation_duration || '2', 10) || 2
  schedulerLastFetch.value = s.scheduler_last_fetch_at || ''
  schedulerLastRetention.value = s.scheduler_last_retention_at || ''
  tavilyKeys.value = parseTavilyResolved(s.tavily_keys_resolved)
  tavilyActiveKeyId.value = s.tavily_active_key_id || tavilyKeys.value[0]?.id || ''
  tavilyAutoSwitch.value = boolFrom(s.tavily_auto_switch, true)
  openaiKeys.value = parseOpenaiKeys(s.openai_api_keys)
  markSaved()
}

function dbTavilyKeysPayload(extra = null) {
  const fromSettings = tavilyKeys.value.filter((item) => item.source !== 'env')
  const list = extra ? [...fromSettings, extra] : fromSettings
  return JSON.stringify(
    list.map((item) => ({
      id: item.id,
      label: item.label,
      key: item.key,
    })),
  )
}

async function patchTavilySettings(partial) {
  tavilyKeysSaving.value = true
  tavilyKeysError.value = ''
  try {
    const { data } = await settingsApi.update({ settings: partial })
    const s = data.settings
    tavilyKeys.value = parseTavilyResolved(s.tavily_keys_resolved)
    tavilyActiveKeyId.value =
      s.tavily_active_key_id || tavilyKeys.value[0]?.id || ''
    tavilyAutoSwitch.value = boolFrom(s.tavily_auto_switch, true)
    await loadAiUsage(true)
  } catch (err) {
    tavilyKeysError.value =
      err.response?.data?.detail || 'Не удалось сохранить ключи Tavily'
    throw err
  } finally {
    tavilyKeysSaving.value = false
  }
}

async function addTavilyKey() {
  const key = tavilyNewKey.value.trim()
  if (!key) return
  if (key.length > 200 || /[^\x20-\x7E]/.test(key) || /\s/.test(key)) {
    tavilyKeysError.value =
      'Ключ должен быть коротким ASCII (tvly-…), без пробелов и эмодзи. Не вставляйте лог деплоя.'
    return
  }
  const label = tavilyNewLabel.value.trim() || `Ключ ${tavilyKeys.value.length + 1}`
  const id =
    typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : `k-${Date.now()}`
  try {
    await patchTavilySettings({
      tavily_api_keys: dbTavilyKeysPayload({ id, label, key }),
      tavily_active_key_id: tavilyActiveKeyId.value || id,
      tavily_auto_switch: String(tavilyAutoSwitch.value),
    })
    if (!tavilyActiveKeyId.value) {
      tavilyActiveKeyId.value = id
    }
    tavilyNewKey.value = ''
    tavilyNewLabel.value = ''
  } catch {
    /* ошибка уже в tavilyKeysError */
  }
}

async function removeTavilyKey(keyId) {
  const ok = await dialog.confirm({
    title: 'Удалить ключ Tavily?',
    message: 'Ключ будет удалён из панели. Ключ из .env удалить нельзя.',
  })
  if (!ok) return
  const remaining = tavilyKeys.value.filter(
    (item) => item.source !== 'env' && item.id !== keyId,
  )
  const nextActive =
    tavilyActiveKeyId.value === keyId
      ? tavilyKeys.value.find((item) => item.id !== keyId)?.id || ''
      : tavilyActiveKeyId.value
  try {
    await patchTavilySettings({
      tavily_api_keys: JSON.stringify(
        remaining.map((item) => ({
          id: item.id,
          label: item.label,
          key: item.key,
        })),
      ),
      tavily_active_key_id: nextActive,
    })
  } catch {
    /* ошибка уже в tavilyKeysError */
  }
}

async function activateTavilyKey(keyId) {
  tavilyActiveKeyId.value = keyId
  try {
    await patchTavilySettings({ tavily_active_key_id: keyId })
  } catch {
    /* ошибка уже в tavilyKeysError */
  }
}

async function saveTavilyAutoSwitch() {
  try {
    await patchTavilySettings({
      tavily_auto_switch: String(tavilyAutoSwitch.value),
    })
  } catch {
    /* ошибка уже в tavilyKeysError */
  }
}

function dbOpenaiKeysPayload(extra = null) {
  const list = extra ? [...openaiKeys.value, extra] : [...openaiKeys.value]
  return JSON.stringify(
    list.map((item) => ({
      id: item.id,
      label: item.label,
      note: item.note,
      key: item.key,
      enabled: item.enabled,
    })),
  )
}

async function patchOpenaiSettings(partial) {
  openaiKeysSaving.value = true
  openaiKeysError.value = ''
  try {
    const { data } = await settingsApi.update({ settings: partial })
    openaiKeys.value = parseOpenaiKeys(data.settings.openai_api_keys)
    await loadAiUsage(true)
  } catch (err) {
    openaiKeysError.value =
      err.response?.data?.detail || 'Не удалось сохранить ключи OpenAI'
    throw err
  } finally {
    openaiKeysSaving.value = false
  }
}

async function addOpenaiKey() {
  const key = openaiNewKey.value.trim()
  if (!key) return
  if (key.length > 200 || /[^\x20-\x7E]/.test(key) || /\s/.test(key)) {
    openaiKeysError.value =
      'Ключ должен быть коротким ASCII (sk-…), без пробелов и эмодзи.'
    return
  }
  const label = openaiNewLabel.value.trim() || `Ключ ${openaiKeys.value.length + 1}`
  const note = openaiNewNote.value.trim()
  const id =
    typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : `k-${Date.now()}`
  try {
    await patchOpenaiSettings({
      openai_api_keys: dbOpenaiKeysPayload({ id, label, note, key, enabled: true }),
    })
    openaiNewKey.value = ''
    openaiNewLabel.value = ''
    openaiNewNote.value = ''
  } catch {
    /* ошибка уже в openaiKeysError */
  }
}

async function removeOpenaiKey(keyId) {
  const ok = await dialog.confirm({
    title: 'Удалить ключ OpenAI?',
    message: 'Ключ будет удалён из панели.',
  })
  if (!ok) return
  const remaining = openaiKeys.value.filter((item) => item.id !== keyId)
  try {
    await patchOpenaiSettings({
      openai_api_keys: JSON.stringify(
        remaining.map((item) => ({
          id: item.id,
          label: item.label,
          note: item.note,
          key: item.key,
          enabled: item.enabled,
        })),
      ),
    })
  } catch {
    /* ошибка уже в openaiKeysError */
  }
}

async function toggleOpenaiKey(keyId, enabled) {
  const updated = openaiKeys.value.map((item) =>
    item.id === keyId ? { ...item, enabled } : item,
  )
  try {
    await patchOpenaiSettings({
      openai_api_keys: JSON.stringify(
        updated.map((item) => ({
          id: item.id,
          label: item.label,
          note: item.note,
          key: item.key,
          enabled: item.enabled,
        })),
      ),
    })
  } catch {
    /* ошибка уже в openaiKeysError */
  }
}

function dbOpenrouterKeysPayload(extra = null) {
  const list = extra ? [...openrouterKeys.value, extra] : [...openrouterKeys.value]
  return JSON.stringify(
    list.map((item) => ({
      id: item.id,
      label: item.label,
      note: item.note,
      key: item.key,
      enabled: item.enabled,
    })),
  )
}

async function patchOpenrouterSettings(partial) {
  openrouterKeysSaving.value = true
  openrouterKeysError.value = ''
  try {
    const { data } = await settingsApi.update({ settings: partial })
    openrouterKeys.value = parseOpenrouterKeys(data.settings.openrouter_api_keys)
  } catch (err) {
    openrouterKeysError.value =
      err.response?.data?.detail || 'Не удалось сохранить ключи OpenRouter'
    throw err
  } finally {
    openrouterKeysSaving.value = false
  }
}

async function addOpenrouterKey() {
  const key = openrouterNewKey.value.trim()
  if (!key) return
  if (key.length > 200 || /[^\x20-\x7E]/.test(key) || /\s/.test(key)) {
    openrouterKeysError.value =
      'Ключ должен быть коротким ASCII (sk-or-…), без пробелов и эмодзи.'
    return
  }
  const label = openrouterNewLabel.value.trim() || `Ключ ${openrouterKeys.value.length + 1}`
  const note = openrouterNewNote.value.trim()
  const id =
    typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : `or-${Date.now()}`
  try {
    await patchOpenrouterSettings({
      openrouter_api_keys: dbOpenrouterKeysPayload({ id, label, note, key, enabled: true }),
    })
    openrouterNewKey.value = ''
    openrouterNewLabel.value = ''
    openrouterNewNote.value = ''
  } catch {
    /* ошибка уже в openrouterKeysError */
  }
}

async function removeOpenrouterKey(keyId) {
  const ok = await dialog.confirm({
    title: 'Удалить ключ OpenRouter?',
    message: 'Ключ будет удалён из панели.',
  })
  if (!ok) return
  const remaining = openrouterKeys.value.filter((item) => item.id !== keyId)
  try {
    await patchOpenrouterSettings({
      openrouter_api_keys: JSON.stringify(
        remaining.map((item) => ({
          id: item.id,
          label: item.label,
          note: item.note,
          key: item.key,
          enabled: item.enabled,
        })),
      ),
    })
  } catch {
    /* ошибка уже в openrouterKeysError */
  }
}

async function toggleOpenrouterKey(keyId, enabled) {
  const updated = openrouterKeys.value.map((item) =>
    item.id === keyId ? { ...item, enabled } : item,
  )
  try {
    await patchOpenrouterSettings({
      openrouter_api_keys: JSON.stringify(
        updated.map((item) => ({
          id: item.id,
          label: item.label,
          note: item.note,
          key: item.key,
          enabled: item.enabled,
        })),
      ),
    })
  } catch {
    /* ошибка уже в openrouterKeysError */
  }
}

async function saveOpenrouterParams() {
  openrouterParamsSaving.value = true
  openrouterKeysError.value = ''
  try {
    await settingsApi.update({
      settings: {
        openrouter_video_model: openrouterVideoModel.value.trim(),
        postcard_animation_enabled: String(postcardAnimationEnabled.value),
        postcard_animation_duration: String(
          Math.min(15, Math.max(1, Number(postcardAnimationDuration.value) || 2)),
        ),
      },
    })
    await dialog.alert({
      title: 'OpenRouter',
      message: 'Параметры анимации сохранены.',
    })
  } catch (err) {
    openrouterKeysError.value =
      err.response?.data?.detail || 'Не удалось сохранить параметры OpenRouter'
  } finally {
    openrouterParamsSaving.value = false
  }
}


async function save({ silent = false } = {}) {
  saving.value = true
  try {
    await settingsApi.update({
      settings: {
        schedule_fetch_enabled: String(scheduleFetch.value),
        schedule_ai_enabled: String(scheduleAi.value),
        schedule_publish_enabled: String(schedulePublish.value),
        schedule_retention_enabled: String(scheduleRetention.value),
        schedule_article_publish_enabled: String(scheduleArticle.value),
        manual_fetch_enabled: String(manualFetch.value),
        manual_ai_enabled: String(manualAi.value),
        manual_publish_enabled: String(manualPublish.value),
        auto_ai_after_manual_fetch: String(autoAiAfterManualFetch.value),
        auto_approve: String(autoApprove.value),
        fetch_interval_minutes: String(fetchInterval.value),
        fetch_max_age_days: String(fetchMaxAgeDays.value),
        retention_hour_utc: String(retentionHourUtc.value),
        retention_minute_utc: String(retentionMinuteUtc.value),
        raw_posts_retention_days: String(rawPostsRetentionDays.value),
        posts_per_day: String(postsPerDay.value),
        qwen_image_models: qwenImageModels.value,
        qwen_image_edit_models: qwenImageEditModels.value,
      },
    })
    await loadSettings()
    if (!silent) {
      await dialog.alert({
        title: 'Настройки',
        message: 'Сохранено. Изменения расписания применяются без перезапуска Beat.',
      })
    }
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.settings-form {
  @apply space-y-6;
}

.settings-grid {
  @apply grid gap-6 xl:grid-cols-2;
}

.settings-category {
  @apply flex flex-col gap-4 p-4 min-w-0 sm:p-5;
}

.table-wrap {
  @apply max-w-full overflow-x-auto;
}

.category-header {
  @apply border-b border-panel-border pb-3;
}

.category-title {
  @apply text-base font-semibold text-[var(--text-primary)];
}

.category-subtitle {
  @apply text-sm text-[var(--text-secondary)] mt-0.5;
}

.settings-table .setting-name {
  @apply font-medium text-[var(--text-primary)] align-top whitespace-nowrap;
}

.settings-table .setting-desc {
  @apply text-sm text-[var(--text-secondary)] align-top;
}

.settings-table .col-toggle {
  @apply w-20 text-center align-middle;
}

.settings-table th.col-toggle {
  @apply text-center;
}

/* На мобильных таблицы настроек не влезают по ширине — раскладываем строки в столбик. */
@media (max-width: 767px) {
  .settings-table,
  .settings-table tbody,
  .settings-table tr,
  .settings-table td {
    display: block;
    width: 100%;
  }

  .settings-table thead {
    display: none;
  }

  .settings-table tr {
    border: 1px solid rgb(var(--panel-border-rgb));
    border-radius: 0.75rem;
    background: rgb(var(--panel-elevated-rgb));
    padding: 0.875rem 1rem;
    margin-bottom: 0.75rem;
  }

  .settings-table tr:last-child {
    margin-bottom: 0;
  }

  .settings-table td {
    padding: 0;
    border: 0;
  }

  .settings-table .setting-name {
    white-space: normal;
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--text-primary);
  }

  .settings-table .setting-desc {
    margin-top: 0.375rem;
    font-size: 0.75rem;
    line-height: 1.45;
  }

  .settings-table .col-toggle {
    width: 100%;
    text-align: left;
    margin-top: 0.75rem;
  }

  /* Тумблер: слева, а не по центру колонки. */
  .settings-table .col-toggle :deep(.toggle) {
    margin-left: 0;
    margin-right: 0;
  }

  .settings-table td[colspan] {
    margin-top: 0.75rem;
  }

  .input-compact {
    @apply w-full;
  }
}

.input-compact {
  @apply inline-block w-24;
}

.input-suffix {
  @apply ml-2 text-sm text-[var(--text-secondary)];
}

.category-meta {
  @apply text-xs text-[var(--text-secondary)] font-mono rounded-lg border border-panel-border bg-panel-elevated px-3 py-2;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.field-label {
  @apply block text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)];
}

.field-hint {
  @apply text-xs text-[var(--text-secondary)];
}

.ai-usage-section {
  @apply mb-6;
}

.ai-usage-header {
  @apply flex flex-wrap items-start justify-between gap-3 border-b-0 pb-0;
}

.btn-compact {
  @apply shrink-0 px-3 py-1.5 text-xs;
}

.ai-usage-grid {
  @apply grid gap-4 md:grid-cols-2 xl:grid-cols-3;
}

.provider-list {
  @apply flex flex-col gap-3;
}

.provider-row {
  @apply panel-card overflow-hidden transition-colors;
}

.provider-row.is-open {
  @apply ring-1 ring-accent;
}

.provider-header {
  @apply flex w-full flex-wrap items-center justify-between gap-3 p-4 text-left
         cursor-pointer hover:bg-panel-hover transition-colors;
}

.provider-header-main {
  @apply flex items-center gap-3 min-w-0;
}

.provider-title-block {
  @apply flex min-w-0 flex-col;
}

.provider-title {
  @apply text-sm font-semibold text-[var(--text-primary)] truncate;
}

.provider-sub {
  @apply text-[11px] text-[var(--text-secondary)] truncate;
}

.provider-metrics {
  @apply flex flex-wrap items-center gap-4 sm:gap-6;
}

.provider-metric {
  @apply flex flex-col items-end min-w-[4.5rem];
}

.provider-metric-val {
  @apply text-sm font-semibold tabular-nums text-[var(--text-primary)];
}

.provider-metric-val.is-bad {
  @apply text-red-400;
}

.provider-metric-label {
  @apply text-[10px] uppercase tracking-wide text-[var(--text-secondary)];
}

.chevron {
  @apply inline-block text-[var(--text-secondary)] text-xs transition-transform duration-200;
}

.chevron.open {
  @apply rotate-90;
}

.provider-body {
  @apply px-4 pb-5 pt-1 border-t border-panel-border space-y-2;
}

.expand-enter-active,
.expand-leave-active {
  transition: height 0.28s ease;
  overflow: hidden;
}

.ai-usage-card {
  @apply rounded-xl border border-panel-border bg-panel-elevated p-4 space-y-2;
}

.ai-usage-card-wide {
  @apply md:col-span-2 xl:col-span-3;
}

.ai-usage-card-title {
  @apply text-sm font-semibold text-[var(--text-primary)];
}

.ai-usage-card-sub {
  @apply text-xs text-[var(--text-secondary)];
}

.ai-usage-balance {
  @apply text-2xl font-semibold text-[var(--text-primary)] tabular-nums;
}

.ai-usage-kpi-label {
  @apply text-[10px] font-medium uppercase tracking-wider text-[var(--text-secondary)];
}

.ai-usage-currency {
  @apply text-sm font-normal text-[var(--text-secondary)] ml-1;
}

.ai-usage-muted {
  @apply text-xs text-[var(--text-secondary)];
}

.ai-usage-models {
  @apply text-[10px] font-mono text-[var(--text-secondary)] break-all;
}

.ai-spend {
  @apply mt-3 pt-3 border-t border-panel-border;
}

.ai-spend-title {
  @apply text-[11px] uppercase tracking-wide text-[var(--text-secondary)] mb-1;
}

.ai-spend-row {
  @apply flex gap-4;
}

.ai-spend-item {
  @apply flex flex-col;
}

.ai-spend-val {
  @apply text-sm font-semibold text-accent;
}

.ai-spend-label {
  @apply text-[10px] text-[var(--text-secondary)];
}

.ai-spend-spark {
  @apply mt-2 w-full;
}

.ai-spend-hint {
  @apply mt-2;
}

.ai-usage-error,
.ai-usage-error-inline {
  @apply text-xs text-danger;
}

.ai-usage-loading {
  @apply text-sm text-[var(--text-secondary)];
}

.ai-usage-progress-wrap {
  @apply space-y-1 pt-1;
}

.ai-usage-progress {
  @apply h-2 w-full overflow-hidden rounded-pill bg-panel-border;
}

.ai-usage-progress-bar {
  @apply h-full rounded-pill bg-accent transition-all duration-500;
}

.ai-usage-explainer {
  @apply leading-relaxed;
}

.ai-usage-chain ul,
.ai-usage-chain-list {
  @apply space-y-1.5 mt-1 list-none p-0 m-0;
}

.ai-usage-chain li {
  @apply flex flex-wrap items-center gap-2 text-xs;
  overflow-wrap: anywhere;
}

.ai-usage-chain li .font-mono {
  overflow-wrap: anywhere;
  word-break: break-word;
}

.ai-usage-chain-hint {
  @apply text-[10px] text-[var(--text-secondary)] -mt-1 mb-1;
}

.ai-usage-chain-rank {
  @apply inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full
    bg-panel-hover text-[10px] font-semibold text-[var(--text-secondary)];
}

.ai-usage-chain-label {
  @apply text-[10px] font-medium uppercase tracking-wider text-[var(--text-secondary)] mt-2 first:mt-0;
}

.ai-usage-stats {
  @apply grid grid-cols-2 sm:grid-cols-4 gap-4 pt-2;
}

.ai-usage-stat-value {
  @apply text-xl font-semibold text-[var(--text-primary)] tabular-nums;
}

.ai-usage-stat-label {
  @apply text-xs text-[var(--text-secondary)];
}

.settings-footer {
  @apply flex justify-end border-t border-panel-border pt-4;
}

.ai-usage-card-tavily {
  @apply md:col-span-2 xl:col-span-2;
}

.tavily-keys-block {
  @apply space-y-2 pt-3 mt-2 border-t border-panel-border;
}

.tavily-auto-switch {
  @apply flex items-center gap-2 text-xs text-[var(--text-secondary)] cursor-pointer;
}

.tavily-keys-list {
  @apply space-y-2 list-none p-0 m-0;
}

.tavily-key-row {
  @apply flex flex-wrap items-center gap-2 text-xs rounded-lg border border-panel-border
    bg-panel-bg px-2.5 py-2;
}

.tavily-key-select {
  @apply flex items-start gap-2 flex-1 min-w-[12rem] cursor-pointer;
}

.tavily-key-meta {
  @apply flex flex-col gap-0.5 min-w-0;
}

.tavily-key-label {
  @apply font-medium text-[var(--text-primary)];
}

.tavily-key-masked {
  @apply text-[10px] text-[var(--text-secondary)] break-all;
}

.tavily-key-remaining {
  @apply text-[10px] tabular-nums text-[var(--text-secondary)];
}

.tavily-key-remove {
  @apply ml-auto;
}

.tavily-add-form {
  @apply flex flex-wrap items-center gap-2 pt-1;
}

.input-compact-wide {
  @apply inline-block min-w-[10rem] flex-1;
}

.openai-key-note {
  @apply text-[10px] text-[var(--text-secondary)] italic;
}
</style>
