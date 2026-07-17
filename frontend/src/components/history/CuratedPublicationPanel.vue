<template>
  <div class="curated-panel">
    <section class="settings-category panel-card">
      <header class="category-header">
        <h2 class="category-title">Умная публикация</h2>
        <p class="category-subtitle">
          Каждые N минут AI выбирает 1 лучшую новость по теме и сразу публикует в канал
        </p>
      </header>

      <div class="setting-card">
        <div class="setting-card-text">
          <p class="setting-card-title">Автоматически выбирать и публиковать</p>
          <p class="setting-card-desc">
            AI берёт один материал по теме, переписывает и отправляет в канал без очереди.
          </p>
        </div>
        <button
          type="button"
          class="toggle shrink-0"
          :class="{ 'toggle-on': scheduleCurated }"
          role="switch"
          :aria-checked="scheduleCurated"
          @click="scheduleCurated = !scheduleCurated"
        >
          <span class="toggle-thumb" />
        </button>
      </div>

      <p class="field-hint">
        Интервал совпадает с автопарсингом (сейчас {{ fetchIntervalMinutes }} мин).
        При включении автоматически выключаются «AI после автопарсинга» и «Публикация по слотам» —
        иначе материалы пойдут на рерайт всей пачкой и накопятся в «Одобренных».
        Окно публикации каналов (UTC) по-прежнему учитывается: ночью посты не выходят.
      </p>

      <div v-if="curatedStatus.length" class="category-meta">
        <p v-for="line in curatedStatus" :key="line">{{ line }}</p>
      </div>

      <label class="field-label">Промпт выбора лучшей новости</label>
      <textarea
        v-model="curatedPickPrompt"
        rows="6"
        class="input prompt-input"
      />

      <footer class="panel-footer">
        <span v-if="savedNote" class="saved-note">{{ savedNote }}</span>
        <button type="button" class="btn-primary btn-sm" :disabled="saving" @click="save">
          {{ saving ? 'Сохранение…' : 'Сохранить' }}
        </button>
      </footer>
    </section>

    <section class="settings-category panel-card">
      <header class="category-header">
        <h2 class="category-title">История умного выбора</h2>
        <p class="category-subtitle">Какие новости выбрал AI и почему</p>
      </header>

      <div v-if="loading" class="empty-state">Загрузка…</div>
      <div v-else-if="!curatedHistory.length" class="empty-state">
        Журнал выборов появится после первой умной публикации.
      </div>
      <div v-else class="history-list">
        <article
          v-for="entry in curatedHistory"
          :key="`${entry.picked_at}-${entry.raw_post_id}`"
          class="history-item"
        >
          <div class="history-item-head">
            <span class="topic-pill">{{ entry.topic_label }}</span>
            <time class="history-item-time">{{ formatPickTime(entry.picked_at) }}</time>
          </div>
          <p class="history-item-title">{{ entry.title || 'Без заголовка' }}</p>
          <p class="history-item-source">
            {{ entry.source_name || 'Источник не указан' }} · #{{ entry.raw_post_id }}
          </p>
          <div class="history-item-reason">
            <span class="history-item-reason-label">Почему выбрано</span>
            <p>{{ entry.reason || 'Причина не сохранена' }}</p>
            <small v-if="entry.candidates_count > 1">
              Выбрано из {{ entry.candidates_count }} материалов
            </small>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { settingsApi } from '../../api/index.js'
import { TOPIC_OPTIONS } from '../../constants/topics.js'
import { formatUtcDateTime } from '../../utils/datetime.js'

const scheduleCurated = ref(false)
const curatedPickPrompt = ref('')
const fetchIntervalMinutes = ref(30)
const curatedStatus = ref([])
const curatedHistory = ref([])
const loading = ref(false)
const saving = ref(false)
const savedNote = ref('')

function boolFrom(value, fallback = false) {
  if (value === undefined || value === null || value === '') return fallback
  return value === 'true' || value === '1'
}

function parseCuratedHistory(raw) {
  if (!raw) return []
  try {
    const data = JSON.parse(raw)
    return Array.isArray(data) ? data.slice(0, 30) : []
  } catch {
    return []
  }
}

function formatPickTime(iso) {
  if (!iso) return '—'
  return formatUtcDateTime(iso)
}

async function load() {
  loading.value = true
  try {
    const { data } = await settingsApi.get()
    const s = data.settings || {}
    scheduleCurated.value = boolFrom(s.schedule_curated_publish_enabled, true)
    curatedPickPrompt.value = s.curated_pick_prompt || ''
    fetchIntervalMinutes.value = Number.parseInt(s.fetch_interval_minutes || '30', 10) || 30
    curatedStatus.value = TOPIC_OPTIONS.map(({ value, label }) => {
      const key = `scheduler_last_curated_${value}`
      return s[key] ? `${label} (UTC): ${s[key]}` : null
    }).filter(Boolean)
    curatedHistory.value = parseCuratedHistory(s.curated_pick_history)
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  savedNote.value = ''
  try {
    const settings = {
      schedule_curated_publish_enabled: String(scheduleCurated.value),
      curated_pick_prompt: curatedPickPrompt.value,
    }
    if (scheduleCurated.value) {
      settings.schedule_ai_enabled = 'false'
      settings.schedule_publish_enabled = 'false'
    }
    await settingsApi.update({ settings })
    await load()
    savedNote.value = 'Сохранено'
    setTimeout(() => (savedNote.value = ''), 2500)
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.curated-panel {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  min-width: 0;
  max-width: 100%;
}

.settings-category {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  min-width: 0;
  padding: 1rem;
}

@media (min-width: 640px) {
  .settings-category {
    padding: 1.25rem;
  }
}

.category-header {
  border-bottom: 1px solid rgb(var(--panel-border-rgb));
  padding-bottom: 0.75rem;
}

.category-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.category-subtitle {
  margin-top: 0.25rem;
  font-size: 0.875rem;
  line-height: 1.4;
  color: var(--text-secondary);
}

.setting-card {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  border: 1px solid rgb(var(--panel-border-rgb));
  border-radius: 0.75rem;
  background: rgb(var(--panel-elevated-rgb));
  padding: 1rem;
}

.setting-card-text {
  min-width: 0;
  flex: 1;
}

.setting-card-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary);
}

.setting-card-desc {
  margin-top: 0.25rem;
  font-size: 0.75rem;
  line-height: 1.45;
  color: var(--text-secondary);
}

.shrink-0 {
  flex-shrink: 0;
}

.field-label {
  display: block;
  font-size: 0.75rem;
  font-weight: 500;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--text-secondary);
}

.field-hint {
  font-size: 0.75rem;
  line-height: 1.5;
  color: var(--text-secondary);
}

.category-meta {
  border: 1px solid rgb(var(--panel-border-rgb));
  border-radius: 0.75rem;
  background: rgb(var(--panel-elevated-rgb));
  padding: 0.75rem 1rem;
  font-family: ui-monospace, monospace;
  font-size: 0.7rem;
  line-height: 1.5;
  color: var(--text-secondary);
  overflow-wrap: anywhere;
  word-break: break-word;
}

.prompt-input {
  width: 100%;
  margin-top: 0.25rem;
  font-family: ui-monospace, monospace;
  font-size: 0.75rem;
}

.panel-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.75rem;
  border-top: 1px solid rgb(var(--panel-border-rgb));
  padding-top: 1rem;
}

.saved-note {
  font-size: 0.75rem;
  color: rgb(var(--accent-rgb));
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  min-width: 0;
}

.history-item {
  border: 1px solid rgb(var(--panel-border-rgb));
  border-radius: 0.75rem;
  background: rgb(var(--panel-elevated-rgb));
  padding: 1rem;
  min-width: 0;
}

.history-item-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.topic-pill {
  display: inline-flex;
  border-radius: 0.375rem;
  background: rgb(var(--accent-rgb) / 0.15);
  padding: 0.125rem 0.5rem;
  font-size: 0.75rem;
  font-weight: 500;
  color: rgb(var(--accent-rgb));
}

.history-item-time {
  font-family: ui-monospace, monospace;
  font-size: 0.65rem;
  color: var(--text-secondary);
}

.history-item-title {
  margin-top: 0.75rem;
  font-size: 0.875rem;
  font-weight: 500;
  line-height: 1.35;
  color: var(--text-primary);
  overflow-wrap: anywhere;
}

.history-item-source {
  margin-top: 0.25rem;
  font-size: 0.75rem;
  color: var(--text-secondary);
  overflow-wrap: anywhere;
}

.history-item-reason {
  margin-top: 0.75rem;
  border-top: 1px solid rgb(var(--panel-border-rgb));
  padding-top: 0.75rem;
}

.history-item-reason-label {
  display: block;
  font-size: 0.65rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--text-secondary);
}

.history-item-reason p {
  margin-top: 0.25rem;
  font-size: 0.75rem;
  line-height: 1.45;
  color: var(--text-primary);
  overflow-wrap: anywhere;
}

.history-item-reason small {
  display: block;
  margin-top: 0.25rem;
  font-size: 0.65rem;
  color: var(--text-secondary);
}
</style>
