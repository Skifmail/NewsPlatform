<template>
  <div class="curated-panel">
    <section class="settings-category panel-card">
      <header class="category-header">
        <h2 class="category-title">Умная публикация</h2>
        <p class="category-subtitle">Экономия токенов — выбор лучшей новости по теме</p>
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
              <td class="setting-name">Лучшая новость → рерайт → канал</td>
              <td class="setting-desc">
                AI выбирает 1 материал на тему (it/auto/russia/sport), рерайтит и публикует по расписанию каналов
              </td>
              <td class="col-toggle">
                <button
                  type="button"
                  class="toggle mx-auto"
                  :class="{ 'toggle-on': scheduleCurated }"
                  role="switch"
                  :aria-checked="scheduleCurated"
                  @click="scheduleCurated = !scheduleCurated"
                >
                  <span class="toggle-thumb" />
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <p class="field-hint">
        Рекомендуется выключить «AI после автопарсинга» — иначе все материалы пойдут на рерайт.
        Расписание слотов берётся из настроек каналов (интервал и окно UTC).
      </p>

      <div v-if="curatedStatus.length" class="category-meta space-y-1">
        <p v-for="line in curatedStatus" :key="line">{{ line }}</p>
      </div>

      <label class="field-label">Промпт выбора лучшей новости</label>
      <textarea
        v-model="curatedPickPrompt"
        rows="6"
        class="input w-full mt-1 font-mono text-xs"
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
      <div v-else class="table-wrap overflow-x-auto">
        <table class="table-panel curated-table">
          <thead>
            <tr>
              <th>Дата</th>
              <th>Тема</th>
              <th>Номер</th>
              <th>Источник</th>
              <th>Новость</th>
              <th>Причина</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="entry in curatedHistory"
              :key="`${entry.picked_at}-${entry.raw_post_id}`"
            >
              <td class="whitespace-nowrap font-mono text-xs text-[var(--text-secondary)]">
                {{ formatPickTime(entry.picked_at) }}
              </td>
              <td class="whitespace-nowrap">
                <span class="curated-history-topic">{{ entry.topic_label }}</span>
              </td>
              <td class="whitespace-nowrap font-mono text-xs">#{{ entry.raw_post_id }}</td>
              <td class="whitespace-nowrap">{{ entry.source_name || '—' }}</td>
              <td class="cell-title">{{ entry.title }}</td>
              <td class="cell-reason">
                {{ entry.reason }}
                <span v-if="entry.candidates_count > 1" class="cell-candidates">
                  (из {{ entry.candidates_count }} кандидатов)
                </span>
              </td>
            </tr>
          </tbody>
        </table>
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
    scheduleCurated.value = boolFrom(s.schedule_curated_publish_enabled, false)
    curatedPickPrompt.value = s.curated_pick_prompt || ''
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
    await settingsApi.update({
      settings: {
        schedule_curated_publish_enabled: String(scheduleCurated.value),
        curated_pick_prompt: curatedPickPrompt.value,
      },
    })
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
  @apply space-y-6;
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

.field-label {
  @apply block text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)];
}

.field-hint {
  @apply text-xs text-[var(--text-secondary)];
}

.category-meta {
  @apply text-xs text-[var(--text-secondary)] font-mono rounded-lg border border-panel-border bg-panel-elevated px-3 py-2;
}

.panel-footer {
  @apply flex items-center justify-end gap-3 border-t border-panel-border pt-4;
}

.saved-note {
  @apply text-xs text-accent;
}

.curated-history-topic {
  @apply inline-flex rounded bg-accent/15 px-2 py-0.5 text-xs font-medium text-accent;
}

.curated-table td {
  @apply align-top;
}

.cell-title {
  @apply min-w-[220px] text-sm font-medium text-[var(--text-primary)];
}

.cell-reason {
  @apply min-w-[260px] text-sm text-[var(--text-secondary)];
}

.cell-candidates {
  @apply text-xs text-[var(--text-tertiary)];
}
</style>
