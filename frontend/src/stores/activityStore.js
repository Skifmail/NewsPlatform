import { defineStore } from 'pinia'
import { ref } from 'vue'
import { jobsApi } from '../api/index.js'

const MAX_VISIBLE = 4
const DONE_TTL_MS = 4500
const TICK_MS = 180

const LEGACY_MAP = {
  new_pending_post: (p) => ({
    id: `post-${p.processed_post_id}`,
    kind: 'post',
    phase: 'done',
    title: 'Новый пост в очереди модерации',
    detail: 'Готов к проверке',
    progress: 100,
    raw_post_id: p.raw_post_id ?? null,
  }),
  post_published: (p) => ({
    id: `publish-${p.processed_post_id}`,
    kind: 'publish',
    phase: 'done',
    title: 'Пост опубликован',
    detail: 'Отправлен в канал',
    progress: 100,
  }),
}

function normalizeActivity(raw) {
  const phase = raw.phase || 'running'
  const target = Math.min(100, Math.max(0, Number(raw.progress) || 0))
  const latest = raw.latest_event || null
  return {
    id: raw.id || `act-${Date.now()}`,
    kind: raw.kind || 'system',
    phase,
    title: raw.title || 'Выполняется задача',
    detail: raw.detail || '',
    progress: target,
    displayProgress: target,
    jobId: raw.job_id ?? null,
    celeryTaskId: raw.celery_task_id ?? null,
    jobType: raw.job_type ?? null,
    rawPostId: raw.raw_post_id ?? null,
    eventCount: raw.event_count ?? 0,
    latestEvent: latest,
    hideAt: phase === 'done' || phase === 'error' ? Date.now() + DONE_TTL_MS : null,
  }
}

function phaseFromStatus(status) {
  if (status === 'success') return 'done'
  if (status === 'failed') return 'error'
  if (status === 'running') return 'running'
  return 'queued'
}

const STAGE_SEPARATOR = '|'

function decodeStage(raw) {
  if (!raw) return { progress: null, text: null }
  const idx = raw.indexOf(STAGE_SEPARATOR)
  if (idx <= 0) return { progress: null, text: raw }
  const head = raw.slice(0, idx)
  const tail = raw.slice(idx + 1)
  if (/^\d+$/.test(head) && tail) {
    return { progress: Number(head), text: tail }
  }
  return { progress: null, text: raw }
}

function detailFromJob(job) {
  if (job.detail) return job.detail
  if (job.status === 'success') return job.result_summary || 'Успешно завершено'
  if (job.status === 'failed') return job.error_message || 'Ошибка выполнения'
  if (job.status === 'running') {
    const { text } = decodeStage(job.result_summary)
    if (text) return text
    if (job.job_type === 'fetch') return 'Загрузка новых материалов с источника…'
    if (job.job_type === 'process') return 'Рерайт через AI и подготовка постов…'
    if (job.job_type === 'publish') return 'Отправка сообщения в канал…'
    if (job.job_type === 'article') return 'Подготовка к генерации статьи…'
    return 'Выполняется…'
  }
  if (job.result_summary) {
    const { text } = decodeStage(job.result_summary)
    if (text) return text
  }
  return 'В очереди Celery, ожидание worker…'
}

function progressFromJob(job) {
  if (job.progress != null) return job.progress
  if (job.status === 'running') {
    const { progress } = decodeStage(job.result_summary)
    if (progress != null) return progress
  }
  if (job.status === 'success' || job.status === 'failed') return 100
  if (job.status === 'queued') return 12
  return 40
}

function mergeActivity(prev, entry) {
  if (!prev) return entry
  return {
    ...entry,
    displayProgress:
      entry.phase === 'done' || entry.phase === 'error'
        ? 100
        : Math.max(prev.displayProgress, entry.progress),
    celeryTaskId: entry.celeryTaskId || prev.celeryTaskId,
    eventCount: Math.max(entry.eventCount || 0, prev.eventCount || 0),
    latestEvent: entry.latestEvent || prev.latestEvent,
    hideAt:
      entry.phase === 'done' || entry.phase === 'error'
        ? Date.now() + DONE_TTL_MS
        : prev.hideAt,
  }
}

export const useActivityStore = defineStore('activity', () => {
  const items = ref([])
  let tickTimer = null
  let pollTimer = null

  function upsert(raw) {
    const entry = normalizeActivity(raw)
    const idx = items.value.findIndex((a) => a.id === entry.id)
    if (idx >= 0) {
      items.value[idx] = mergeActivity(items.value[idx], entry)
    } else {
      items.value.unshift(entry)
      if (items.value.length > MAX_VISIBLE) {
        items.value = items.value.slice(0, MAX_VISIBLE)
      }
    }
    ensureTick()
    if (entry.phase === 'queued' || entry.phase === 'running') {
      startPolling()
    }
  }

  function applyPipelineUpdate(payload) {
    if (!payload?.celery_task_id) return
    const idx = items.value.findIndex((a) => a.celeryTaskId === payload.celery_task_id)
    if (idx < 0) return
    const prev = items.value[idx]
    items.value[idx] = {
      ...prev,
      detail: payload.current_detail || prev.detail,
      progress: payload.progress ?? prev.progress,
      eventCount: payload.event_count ?? prev.eventCount,
      latestEvent: payload.latest_event || prev.latestEvent,
    }
  }

  function handleWebSocketMessage(msg) {
    if (msg.type === 'activity' && msg.payload) {
      upsert(msg.payload)
      return
    }
    if (msg.type === 'pipeline' && msg.payload) {
      applyPipelineUpdate(msg.payload)
      return
    }
    const mapper = LEGACY_MAP[msg.type]
    if (mapper) upsert(mapper(msg.payload || {}))
  }

  function upsertFromJob(job) {
    const phase = job.phase || phaseFromStatus(job.status)
    upsert({
      id: `job-${job.id}`,
      kind: 'job',
      job_id: job.id,
      celery_task_id: job.celery_task_id,
      job_type: job.job_type,
      raw_post_id: job.raw_post_id ?? null,
      phase,
      title: job.label,
      detail: job.detail || detailFromJob(job),
      progress: progressFromJob(job),
    })
  }

  async function reconcileStaleJobs(activeJobs) {
    const activeIds = new Set(activeJobs.map((j) => j.id))
    const stale = items.value.filter(
      (i) =>
        i.kind === 'job' &&
        i.jobId &&
        (i.phase === 'running' || i.phase === 'queued') &&
        !activeIds.has(i.jobId)
    )
    if (!stale.length) return

    try {
      const { data: recent } = await jobsApi.list({ limit: 100 })
      const byId = new Map(recent.map((j) => [j.id, j]))
      for (const item of stale) {
        const job = byId.get(item.jobId)
        if (!job) {
          upsert({
            id: item.id,
            kind: 'job',
            job_id: item.jobId,
            raw_post_id: item.rawPostId,
            phase: 'done',
            title: item.title,
            detail: 'Завершено',
            progress: 100,
          })
          continue
        }
        if (job.status === 'success' || job.status === 'failed') {
          upsertFromJob({
            ...job,
            phase: phaseFromStatus(job.status),
            progress: 100,
            detail: detailFromJob(job),
          })
        }
      }
    } catch {
      /* ignore */
    }
  }

  async function syncActiveJobs() {
    try {
      const { data } = await jobsApi.active()
      for (const job of data) {
        upsertFromJob(job)
      }
      await reconcileStaleJobs(data)
      const hasRunning = items.value.some(
        (i) => i.phase === 'running' || i.phase === 'queued'
      )
      if (!data.length && !hasRunning) {
        stopPolling()
      }
    } catch {
      /* ignore */
    }
  }

  function pruneExpired() {
    const now = Date.now()
    items.value = items.value.filter((a) => !a.hideAt || a.hideAt > now)
  }

  function ensureTick() {
    if (tickTimer) return
    tickTimer = setInterval(() => {
      pruneExpired()
      for (const a of items.value) {
        if (a.phase === 'running' || a.phase === 'queued') {
          const cap = Math.min(92, (a.progress || 30) + 50)
          if (a.displayProgress < cap) {
            a.displayProgress = Math.min(cap, a.displayProgress + 1.5)
          }
        } else if (a.displayProgress < 100) {
          a.displayProgress = Math.min(100, a.displayProgress + 6)
        }
      }
      if (!items.value.length) {
        clearInterval(tickTimer)
        tickTimer = null
      }
    }, TICK_MS)
  }

  function startPolling() {
    if (pollTimer) return
    syncActiveJobs()
    pollTimer = setInterval(syncActiveJobs, 2000)
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  function reset() {
    stopPolling()
    if (tickTimer) {
      clearInterval(tickTimer)
      tickTimer = null
    }
    items.value = []
  }

  return {
    items,
    upsert,
    handleWebSocketMessage,
    applyPipelineUpdate,
    syncActiveJobs,
    startPolling,
    reset,
    stopPolling,
  }
})
