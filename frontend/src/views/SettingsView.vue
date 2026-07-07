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

      <div v-else-if="aiUsage" class="ai-usage-grid">
        <article class="ai-usage-card">
          <h3 class="ai-usage-card-title">DeepSeek</h3>
          <p class="ai-usage-card-sub">Классификация, рерайт, статьи</p>
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
          </template>
        </article>

        <article class="ai-usage-card">
          <h3 class="ai-usage-card-title">Tavily</h3>
          <p class="ai-usage-card-sub">Веб-поиск для статей</p>
          <template v-if="!aiUsage.tavily.configured">
            <p class="ai-usage-muted">TAVILY_API_KEY не задан</p>
          </template>
          <template v-else-if="aiUsage.tavily.error">
            <p class="ai-usage-error-inline">{{ aiUsage.tavily.error }}</p>
          </template>
          <template v-else>
            <p class="ai-usage-balance">
              {{ aiUsage.tavily.remaining ?? '—' }}
              <span class="ai-usage-currency">из {{ aiUsage.tavily.plan_limit ?? '—' }} кред.</span>
            </p>
            <p class="ai-usage-muted">План: {{ aiUsage.tavily.current_plan || '—' }}</p>
            <div v-if="tavilyUsagePercent != null" class="ai-usage-progress-wrap">
              <div class="ai-usage-progress">
                <div class="ai-usage-progress-bar" :style="{ width: `${tavilyUsagePercent}%` }" />
              </div>
              <p class="ai-usage-muted">
                Использовано {{ aiUsage.tavily.plan_usage }} · Search: {{ aiUsage.tavily.search_usage ?? 0 }}
              </p>
            </div>
          </template>
        </article>

        <article class="ai-usage-card">
          <h3 class="ai-usage-card-title">Qwen Image</h3>
          <p class="ai-usage-card-sub">Обложки (DashScope)</p>
          <template v-if="!aiUsage.qwen_image.configured">
            <p class="ai-usage-muted">QWEN_IMAGE_API_KEY не задан</p>
          </template>
          <template v-else>
            <p class="ai-usage-muted">{{ aiUsage.qwen_image.note }}</p>
            <p v-if="aiUsage.qwen_image.exhausted_count" class="ai-usage-error-inline">
              Временно пропущено моделей: {{ aiUsage.qwen_image.exhausted_count }}
            </p>
            <div v-if="aiUsage.qwen_image.generate_chain?.length" class="ai-usage-chain">
              <p class="ai-usage-chain-label">Text-to-image</p>
              <ul>
                <li v-for="item in aiUsage.qwen_image.generate_chain" :key="'u-gen-' + item.model">
                  <span class="font-mono">{{ item.model }}</span>
                  <span v-if="item.status === 'next'" class="badge-accent">Следующая</span>
                  <span v-else-if="item.status === 'available'" class="badge-muted">В очереди</span>
                  <span v-else class="badge-danger">Квота ~{{ formatTtl(item.ttl_seconds) }}</span>
                </li>
              </ul>
            </div>
            <div v-if="aiUsage.qwen_image.edit_chain?.length" class="ai-usage-chain">
              <p class="ai-usage-chain-label">Image-edit</p>
              <ul>
                <li v-for="item in aiUsage.qwen_image.edit_chain" :key="'u-edit-' + item.model">
                  <span class="font-mono">{{ item.model }}</span>
                  <span v-if="item.status === 'next'" class="badge-accent">Следующая</span>
                  <span v-else-if="item.status === 'available'" class="badge-muted">В очереди</span>
                  <span v-else class="badge-danger">Квота ~{{ formatTtl(item.ttl_seconds) }}</span>
                </li>
              </ul>
            </div>
          </template>
        </article>

        <article class="ai-usage-card">
          <h3 class="ai-usage-card-title">OpenAI</h3>
          <p class="ai-usage-card-sub">Fallback DALL-E</p>
          <p class="ai-usage-muted">{{ aiUsage.openai.note }}</p>
          <p class="ai-usage-muted">
            <span :class="aiUsage.openai.configured ? 'badge-accent' : 'badge-muted'">
              {{ aiUsage.openai.configured ? 'Ключ задан' : 'Не используется' }}
            </span>
          </p>
        </article>

        <article class="ai-usage-card ai-usage-card-wide">
          <h3 class="ai-usage-card-title">Активность платформы</h3>
          <p class="ai-usage-card-sub">Локальный счётчик задач (не квоты провайдеров)</p>
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
                  <td class="setting-desc">Посты с наступившим scheduled_at уходят в каналы</td>
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
          Работает только для каналов с режимом «Статьи». Нужны TAVILY_API_KEY и QWEN_IMAGE_API_KEY (обложки).
        </p>
        <div v-if="articleStatus.length" class="category-meta space-y-1">
          <p v-for="line in articleStatus" :key="line">{{ line }}</p>
        </div>
        <div class="prompt-grid">
          <div>
            <label class="field-label">Промпт выбора темы</label>
            <textarea
              v-model="articleIdeationPrompt"
              rows="6"
              class="input w-full mt-1 font-mono text-xs"
            />
          </div>
          <div>
            <label class="field-label">Промпт написания статьи</label>
            <textarea
              v-model="articleWritingPrompt"
              rows="6"
              class="input w-full mt-1 font-mono text-xs"
            />
          </div>
        </div>
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
          <div class="category-meta mt-3 space-y-3">
            <p class="field-hint !leading-relaxed">
              DashScope не отдаёт остаток квоты в панель. Здесь видно только цепочку моделей и те,
              что временно пропущены после ошибки квоты (кэш ~6 ч). Обновляется при загрузке страницы.
            </p>
            <div v-if="qwenGenerateChainStatus.length">
              <p class="text-xs font-medium text-[var(--text-primary)] mb-1.5">Text-to-image</p>
              <ul class="space-y-1.5">
                <li
                  v-for="item in qwenGenerateChainStatus"
                  :key="'gen-' + item.model"
                  class="flex flex-wrap items-center gap-2"
                >
                  <span class="font-mono text-[var(--text-primary)]">{{ item.model }}</span>
                  <span v-if="item.status === 'next'" class="badge-accent">Следующая при генерации</span>
                  <span v-else-if="item.status === 'available'" class="badge-muted">В очереди</span>
                  <span v-else class="badge-danger">Квота — повтор через ~{{ formatTtl(item.ttlSeconds) }}</span>
                </li>
              </ul>
            </div>
            <div v-if="qwenEditChainStatus.length">
              <p class="text-xs font-medium text-[var(--text-primary)] mb-1.5">Image-edit</p>
              <ul class="space-y-1.5">
                <li
                  v-for="item in qwenEditChainStatus"
                  :key="'edit-' + item.model"
                  class="flex flex-wrap items-center gap-2"
                >
                  <span class="font-mono text-[var(--text-primary)]">{{ item.model }}</span>
                  <span v-if="item.status === 'next'" class="badge-accent">Следующая при генерации</span>
                  <span v-else-if="item.status === 'available'" class="badge-muted">В очереди</span>
                  <span v-else class="badge-danger">Квота — повтор через ~{{ formatTtl(item.ttlSeconds) }}</span>
                </li>
              </ul>
            </div>
            <p v-if="!qwenExhaustedModels.length && (qwenGenerateChainStatus.length || qwenEditChainStatus.length)">
              Сейчас все модели в цепочке доступны — блок «Квота» появится после отказа API.
            </p>
            <p v-else-if="qwenExhaustedModels.length" class="text-[var(--text-secondary)]">
              Пропущено моделей: {{ qwenExhaustedModels.length }}.
            </p>
          </div>
        </section>

        <section class="settings-category panel-card">
          <header class="category-header">
            <h2 class="category-title">AI и классификация</h2>
            <p class="category-subtitle">Промпт определения тематики материала</p>
          </header>
          <label class="field-label">Промпт классификации тематики</label>
          <textarea
            v-model="classificationPrompt"
            rows="12"
            class="input w-full mt-1 font-mono text-xs"
          />
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
const articleIdeationPrompt = ref('')
const articleWritingPrompt = ref('')
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
const classificationPrompt = ref('')
const qwenImageModels = ref('')
const qwenImageEditModels = ref('')
const qwenExhaustedModels = ref([])
const schedulerLastFetch = ref('')
const schedulerLastRetention = ref('')
const saving = ref(false)
const savedSnapshot = ref('')
const aiUsage = ref(null)
const aiUsageLoading = ref(false)
const aiUsageError = ref('')

const tavilyUsagePercent = computed(() => {
  const t = aiUsage.value?.tavily
  if (!t || t.plan_limit == null || t.plan_usage == null || t.plan_limit <= 0) return null
  return Math.min(100, Math.round((t.plan_usage / t.plan_limit) * 100))
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
    article_ideation_prompt: articleIdeationPrompt.value,
    article_writing_prompt: articleWritingPrompt.value,
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
    classification_prompt: classificationPrompt.value,
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
  return `${hours} ч`
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
  } catch (err) {
    aiUsageError.value = err.response?.data?.detail || 'Не удалось загрузить данные AI/API'
  } finally {
    aiUsageLoading.value = false
  }
}

function parseExhaustedModels(raw) {
  if (!raw) return []
  try {
    const data = JSON.parse(raw)
    return Array.isArray(data) ? data : []
  } catch {
    return []
  }
}

function parseModelChain(raw) {
  if (!raw || !String(raw).trim()) return []
  const seen = new Set()
  return String(raw)
    .split(/[,;\n]+/)
    .map((part) => part.trim())
    .filter((name) => {
      if (!name || seen.has(name)) return false
      seen.add(name)
      return true
    })
}

function buildChainStatus(models, exhaustedModels) {
  const exhaustedMap = new Map(
    exhaustedModels.map((item) => [item.model, Number(item.ttl_seconds) || 0]),
  )
  let nextAssigned = false
  return models.map((model) => {
    const ttlSeconds = exhaustedMap.get(model)
    if (ttlSeconds && ttlSeconds > 0) {
      return { model, status: 'exhausted', ttlSeconds }
    }
    if (!nextAssigned) {
      nextAssigned = true
      return { model, status: 'next', ttlSeconds: 0 }
    }
    return { model, status: 'available', ttlSeconds: 0 }
  })
}

const qwenGenerateChainStatus = computed(() =>
  buildChainStatus(parseModelChain(qwenImageModels.value), qwenExhaustedModels.value),
)

const qwenEditChainStatus = computed(() =>
  buildChainStatus(parseModelChain(qwenImageEditModels.value), qwenExhaustedModels.value),
)

async function loadSettings() {
  const { data } = await settingsApi.get()
  const s = data.settings
  scheduleFetch.value = boolFrom(s.schedule_fetch_enabled, true)
  scheduleAi.value = boolFrom(s.schedule_ai_enabled, true)
  schedulePublish.value = boolFrom(s.schedule_publish_enabled, true)
  scheduleRetention.value = boolFrom(s.schedule_retention_enabled, true)
  scheduleArticle.value = boolFrom(s.schedule_article_publish_enabled, false)
  articleIdeationPrompt.value = s.article_ideation_prompt || ''
  articleWritingPrompt.value = s.article_writing_prompt || ''
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
  classificationPrompt.value = s.classification_prompt || ''
  qwenImageModels.value = s.qwen_image_models || ''
  qwenImageEditModels.value = s.qwen_image_edit_models || ''
  qwenExhaustedModels.value = parseExhaustedModels(s.qwen_image_exhausted_models)
  schedulerLastFetch.value = s.scheduler_last_fetch_at || ''
  schedulerLastRetention.value = s.scheduler_last_retention_at || ''
  markSaved()
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
        article_ideation_prompt: articleIdeationPrompt.value,
        article_writing_prompt: articleWritingPrompt.value,
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
        classification_prompt: classificationPrompt.value,
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
  @apply p-5 flex flex-col gap-4 min-w-0;
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

.input-compact {
  @apply inline-block w-24;
}

.input-suffix {
  @apply ml-2 text-sm text-[var(--text-secondary)];
}

.category-meta {
  @apply text-xs text-[var(--text-secondary)] font-mono rounded-lg border border-panel-border bg-panel-elevated px-3 py-2;
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

.ai-usage-currency {
  @apply text-sm font-normal text-[var(--text-secondary)] ml-1;
}

.ai-usage-muted {
  @apply text-xs text-[var(--text-secondary)];
}

.ai-usage-models {
  @apply text-[10px] font-mono text-[var(--text-secondary)] break-all;
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

.ai-usage-chain ul {
  @apply space-y-1 mt-1;
}

.ai-usage-chain li {
  @apply flex flex-wrap items-center gap-2 text-xs;
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

.prompt-grid {
  @apply grid gap-4 lg:grid-cols-2;
}

.settings-footer {
  @apply flex justify-end border-t border-panel-border pt-4;
}
</style>
