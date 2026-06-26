<template>
  <div>
    <PageHeader
      title="Настройки"
      subtitle="Управление автоматикой и ручными действиями платформы"
    />

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
                    Ежедневно в {{ retentionHourUtc }}:{{ String(retentionMinuteUtc).padStart(2, '0') }} UTC
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
          <div v-if="qwenExhaustedModels.length" class="category-meta mt-3 space-y-1">
            <p class="font-medium text-[var(--text-primary)]">Временно пропущены (квота):</p>
            <p v-for="item in qwenExhaustedModels" :key="item.model">
              {{ item.model }} — повтор через ~{{ formatTtl(item.ttl_seconds) }}
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
import { settingsApi } from '../api/index.js'
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
const postsPerDay = ref(10)
const classificationPrompt = ref('')
const qwenImageModels = ref('')
const qwenImageEditModels = ref('')
const qwenExhaustedModels = ref([])
const schedulerLastFetch = ref('')
const schedulerLastRetention = ref('')
const saving = ref(false)
const savedSnapshot = ref('')

const isDirty = computed(() => getFormSnapshot() !== savedSnapshot.value)

onMounted(() => {
  loadSettings()
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

function parseExhaustedModels(raw) {
  if (!raw) return []
  try {
    const data = JSON.parse(raw)
    return Array.isArray(data) ? data : []
  } catch {
    return []
  }
}

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

.prompt-grid {
  @apply grid gap-4 lg:grid-cols-2;
}

.settings-footer {
  @apply flex justify-end border-t border-panel-border pt-4;
}
</style>
