<template>
  <div class="logs-view">
    <header class="logs-head">
      <div>
        <h1 class="page-title">Диагностика</h1>
        <p class="page-sub">Здоровье конвейера и все ошибки платформы в одном месте</p>
      </div>
      <div class="head-actions">
        <label class="auto-toggle">
          <input type="checkbox" v-model="autoRefresh" />
          Автообновление
        </label>
        <button type="button" class="btn-ghost btn-sm" :disabled="loading" @click="refreshAll">
          Обновить
        </button>
      </div>
    </header>

    <!-- Health banner -->
    <section v-if="health" class="health-card" :class="`health-${health.status}`">
      <div class="health-main">
        <span class="health-dot" />
        <div>
          <p class="health-reason">{{ health.reason }}</p>
          <p class="health-meta">
            Последняя публикация: <b>{{ fmt(health.last_publish_at) }}</b>
            · Парсинг: {{ fmt(health.last_fetch_at) }}
          </p>
        </div>
      </div>
      <div class="health-stats">
        <div class="stat">
          <span class="stat-num">{{ health.errors_1h }}</span>
          <span class="stat-label">ошибок за час</span>
        </div>
        <div class="stat">
          <span class="stat-num">{{ health.errors_24h }}</span>
          <span class="stat-label">за сутки</span>
        </div>
        <div class="stat">
          <span class="stat-num">{{ health.failed_jobs_24h }}</span>
          <span class="stat-label">упавших задач</span>
        </div>
      </div>
    </section>

    <!-- Per-channel last publish -->
    <section v-if="health && health.channels.length" class="channels-row">
      <div
        v-for="ch in health.channels"
        :key="ch.channel_id"
        class="chan-chip"
        :class="{ 'chan-stale': isStale(ch) }"
        :title="`Последняя публикация: ${fmt(ch.last_published_at)}`"
      >
        <span class="chan-name">{{ ch.name }}</span>
        <span class="chan-ago">{{ agoLabel(ch) }}</span>
      </div>
    </section>

    <!-- Filters -->
    <div class="filters">
      <button
        v-for="opt in levelOptions"
        :key="opt.value"
        type="button"
        class="chip"
        :class="{ 'chip-active': level === opt.value }"
        @click="setLevel(opt.value)"
      >
        {{ opt.label }}
      </button>
      <span class="filters-spacer" />
      <span class="filters-count">{{ logs.length }} записей</span>
    </div>

    <!-- Error table -->
    <section class="log-list">
      <p v-if="!logs.length && !loading" class="empty">Ошибок нет — чисто ✨</p>
      <div
        v-for="row in logs"
        :key="row.id"
        class="log-row"
        :class="`lvl-${row.level.toLowerCase()}`"
        @click="toggle(row.id)"
      >
        <div class="log-line">
          <span class="log-badge" :class="`badge-${row.level.toLowerCase()}`">{{ row.level }}</span>
          <span class="log-service">{{ row.service }}</span>
          <span class="log-time">{{ fmt(row.created_at) }}</span>
          <span class="log-msg">{{ row.message }}</span>
        </div>
        <div class="log-source">{{ row.source }}</div>
        <pre v-if="expanded.has(row.id) && row.context" class="log-context">{{ row.context }}</pre>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { logsApi } from '../api/index.js'

const REFRESH_MS = 15000
const STALE_HOURS = 5

const health = ref(null)
const logs = ref([])
const loading = ref(false)
const level = ref('')
const autoRefresh = ref(true)
const expanded = ref(new Set())
let timer = null

const levelOptions = [
  { value: '', label: 'Все' },
  { value: 'ERROR', label: 'Ошибки' },
  { value: 'WARNING', label: 'Предупреждения' },
  { value: 'CRITICAL', label: 'Критичные' },
]

function fmt(value) {
  if (!value) return '—'
  const d = new Date(value)
  return d.toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' })
}

function agoLabel(ch) {
  if (ch.hours_since == null) return 'нет постов'
  const h = ch.hours_since
  if (h < 1) return `${Math.round(h * 60)} мин назад`
  if (h < 48) return `${Math.round(h)} ч назад`
  return `${Math.round(h / 24)} дн назад`
}

function isStale(ch) {
  return ch.hours_since == null || ch.hours_since >= STALE_HOURS
}

function toggle(id) {
  const next = new Set(expanded.value)
  next.has(id) ? next.delete(id) : next.add(id)
  expanded.value = next
}

function setLevel(value) {
  level.value = value
  loadLogs()
}

async function loadHealth() {
  try {
    const { data } = await logsApi.health()
    health.value = data
  } catch (e) {
    // health не критичен для страницы — молча
  }
}

async function loadLogs() {
  try {
    const params = { limit: 200 }
    if (level.value) params.level = level.value
    const { data } = await logsApi.list(params)
    logs.value = data
  } catch (e) {
    logs.value = []
  }
}

async function refreshAll() {
  loading.value = true
  await Promise.all([loadHealth(), loadLogs()])
  loading.value = false
}

function startTimer() {
  stopTimer()
  timer = setInterval(() => {
    if (autoRefresh.value) refreshAll()
  }, REFRESH_MS)
}

function stopTimer() {
  if (timer) clearInterval(timer)
  timer = null
}

onMounted(() => {
  refreshAll()
  startTimer()
})

onUnmounted(stopTimer)
</script>

<style scoped>
.logs-view {
  @apply flex flex-col gap-4 p-4 md:p-6;
}

.logs-head {
  @apply flex items-start justify-between gap-4 flex-wrap;
}

.page-title {
  @apply text-xl font-semibold text-[var(--text-primary)];
}

.page-sub {
  @apply text-sm text-[var(--text-secondary)] mt-1;
}

.head-actions {
  @apply flex items-center gap-3;
}

.auto-toggle {
  @apply flex items-center gap-2 text-sm text-[var(--text-secondary)] cursor-pointer;
}

/* Health banner */
.health-card {
  @apply flex items-center justify-between gap-4 rounded-panel border p-4 flex-wrap;
}

.health-main {
  @apply flex items-center gap-3;
}

.health-dot {
  @apply h-3 w-3 rounded-full shrink-0;
}

.health-reason {
  @apply text-base font-semibold text-[var(--text-primary)];
}

.health-meta {
  @apply text-xs text-[var(--text-secondary)] mt-0.5;
}

.health-stats {
  @apply flex gap-5;
}

.stat {
  @apply flex flex-col items-center;
}

.stat-num {
  @apply text-lg font-bold text-[var(--text-primary)];
}

.stat-label {
  @apply text-[10px] uppercase tracking-wide text-[var(--text-secondary)];
}

.health-ok {
  @apply border-emerald-500/40 bg-emerald-500/10;
}
.health-ok .health-dot {
  @apply bg-emerald-500;
}
.health-warning {
  @apply border-amber-500/50 bg-amber-500/10;
}
.health-warning .health-dot {
  @apply bg-amber-500;
}
.health-critical {
  @apply border-red-500/50 bg-red-500/10;
}
.health-critical .health-dot {
  @apply bg-red-500 animate-pulse;
}

/* Channels */
.channels-row {
  @apply flex flex-wrap gap-2;
}
.chan-chip {
  @apply flex items-center gap-2 rounded-pill border border-panel-border bg-panel-surface px-3 py-1 text-xs;
}
.chan-name {
  @apply font-medium text-[var(--text-primary)];
}
.chan-ago {
  @apply text-[var(--text-secondary)];
}
.chan-stale {
  @apply border-amber-500/50 bg-amber-500/10;
}
.chan-stale .chan-ago {
  @apply text-amber-600 font-semibold;
}

/* Filters */
.filters {
  @apply flex items-center gap-2 flex-wrap;
}
.chip {
  @apply rounded-pill border border-panel-border px-3 py-1 text-xs text-[var(--text-secondary)];
}
.chip-active {
  @apply bg-accent-muted text-accent border-accent/40;
}
.filters-spacer {
  @apply flex-1;
}
.filters-count {
  @apply text-xs text-[var(--text-secondary)];
}

/* Log list */
.log-list {
  @apply flex flex-col gap-1.5;
}
.empty {
  @apply text-sm text-[var(--text-secondary)] py-8 text-center;
}
.log-row {
  @apply rounded-panel border border-panel-border bg-panel-surface px-3 py-2 cursor-pointer transition-colors;
}
.log-row:hover {
  @apply border-accent/40;
}
.log-line {
  @apply flex items-center gap-2 flex-wrap;
}
.log-badge {
  @apply rounded px-1.5 py-0.5 text-[10px] font-bold;
}
.badge-error, .badge-critical {
  @apply bg-red-500/15 text-red-600;
}
.badge-warning {
  @apply bg-amber-500/15 text-amber-600;
}
.log-service {
  @apply text-[10px] uppercase tracking-wide text-[var(--text-secondary)];
}
.log-time {
  @apply text-xs text-[var(--text-secondary)];
}
.log-msg {
  @apply text-sm text-[var(--text-primary)] flex-1 min-w-0 truncate;
}
.log-source {
  @apply text-[11px] text-[var(--text-secondary)] mt-0.5 truncate;
}
.log-context {
  @apply mt-2 max-h-64 overflow-auto rounded bg-black/40 p-2 text-[11px] text-red-200 whitespace-pre-wrap;
}
.lvl-critical {
  @apply border-l-2 border-l-red-500;
}
</style>
