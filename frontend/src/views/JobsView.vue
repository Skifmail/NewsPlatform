<template>
  <div>
    <PageHeader
      title="Фоновые задачи"
      subtitle="Очередь Celery (Redis): парсинг источников → AI-обработка → очередь модерации"
    >
      <template #actions>
        <button type="button" class="btn-secondary btn-sm" :disabled="loading" @click="load">
          Обновить
        </button>
      </template>
    </PageHeader>

    <div class="stats-row">
      <div class="stat-card">
        <span class="stat-label">В очереди</span>
        <span class="stat-value text-[var(--text-secondary)]">{{ summary.queued }}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">В работе</span>
        <span class="stat-value text-accent">{{ summary.running }}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">Успешно</span>
        <span class="stat-value">{{ summary.success }}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">Ошибки</span>
        <span class="stat-value text-danger">{{ summary.failed }}</span>
      </div>
    </div>

    <p v-if="loading && !jobs.length" class="empty-state">Загрузка…</p>
    <p v-else-if="error" class="empty-state text-danger">{{ error }}</p>
    <p v-else-if="!jobs.length" class="empty-state">
      Задач пока нет. Запустите парсинг в «Источники» или генерацию статьи в «Каналы».
    </p>

    <div v-else class="table-wrap panel-card overflow-hidden">
      <table class="table-panel">
        <thead>
          <tr>
            <th>Время</th>
            <th>Тип</th>
            <th>Статус</th>
            <th>Описание</th>
            <th>Результат</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="job in jobs" :key="job.id">
            <td class="whitespace-nowrap text-xs text-[var(--text-secondary)] font-mono">
              {{ formatTime(job.created_at) }}
            </td>
            <td>
              <span :class="typeBadgeClass(job.job_type)">{{ typeLabel(job.job_type) }}</span>
            </td>
            <td>
              <span :class="statusBadgeClass(job.status)">{{ statusLabel(job.status) }}</span>
            </td>
            <td>
              <p class="text-sm text-[var(--text-primary)]">{{ job.label }}</p>
              <p v-if="job.celery_task_id" class="text-[10px] text-[var(--text-secondary)] font-mono mt-0.5 truncate max-w-md">
                {{ job.celery_task_id }}
              </p>
            </td>
            <td class="text-sm">
              <span v-if="jobResultText(job)" :class="jobResultClass(job)">{{ jobResultText(job) }}</span>
              <span v-else-if="job.status === 'running'" class="text-[var(--text-secondary)]">Выполняется…</span>
              <span v-else-if="job.status === 'queued'" class="text-[var(--text-secondary)]">Ожидает worker</span>
              <span v-else>—</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p class="hint">Обновление каждые 5 с. Убедитесь, что запущен <code class="text-xs">celery_worker</code>.</p>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import PageHeader from '../components/layout/PageHeader.vue'
import { jobsApi } from '../api/index.js'

const jobs = ref([])
const summary = ref({ queued: 0, running: 0, success: 0, failed: 0, active_total: 0 })
const loading = ref(false)
const error = ref(null)
let pollTimer = null

const typeLabels = {
  fetch: 'Парсинг',
  process: 'AI',
  publish: 'Публикация',
  article: 'Статья',
}

const statusLabels = {
  queued: 'В очереди',
  running: 'В работе',
  success: 'Готово',
  failed: 'Ошибка',
}

function typeLabel(t) {
  return typeLabels[t] || t
}

function statusLabel(s) {
  return statusLabels[s] || s
}

function typeBadgeClass(t) {
  if (t === 'fetch') return 'badge-info'
  if (t === 'process') return 'badge-purple'
  if (t === 'article') return 'badge-accent'
  return 'badge-muted'
}

function statusBadgeClass(s) {
  if (s === 'queued') return 'badge-muted'
  if (s === 'running') return 'badge-accent'
  if (s === 'success') return 'badge-accent'
  if (s === 'failed') return 'badge-danger'
  return 'badge-muted'
}

function decodeStage(raw) {
  if (!raw) return null
  const idx = raw.indexOf('|')
  if (idx <= 0) return raw
  const head = raw.slice(0, idx)
  const tail = raw.slice(idx + 1)
  if (/^\d+$/.test(head) && tail) return tail
  return raw
}

function jobResultText(job) {
  if (job.error_message) return job.error_message
  if (job.result_summary) return decodeStage(job.result_summary)
  return null
}

function jobResultClass(job) {
  if (job.error_message) return 'text-danger'
  return 'text-accent'
}

function formatTime(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return iso
  }
}

async function load() {
  loading.value = true
  error.value = null
  try {
    const [jobsRes, sumRes] = await Promise.all([jobsApi.list(), jobsApi.summary()])
    jobs.value = jobsRes.data
    summary.value = sumRes.data
  } catch (e) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  load()
  pollTimer = setInterval(load, 5000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.stats-row {
  @apply mb-6 grid gap-4 grid-cols-2 lg:grid-cols-4;
}

.hint {
  @apply mt-4 text-xs text-[var(--text-secondary)];
}
</style>
