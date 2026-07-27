import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { jobsApi } from '../api/index.js'

const POLL_MS = 700

export const NODE_META = {
  platform: { label: 'NewsPlatform', short: 'Платформа', color: '#2dd4bf' },
  deepseek: { label: 'DeepSeek', short: 'DeepSeek', color: '#38bdf8' },
  tavily: { label: 'Tavily Search', short: 'Tavily', color: '#818cf8' },
  openai: { label: 'OpenAI Images', short: 'OpenAI', color: '#34d399' },
  qwen: { label: 'Qwen Image', short: 'Qwen', color: '#fb7185' },
  openrouter: { label: 'Grok Video', short: 'Grok', color: '#fbbf24' },
  github: { label: 'GitHub', short: 'GitHub', color: '#94a3b8' },
  storage: { label: 'Хранилище', short: 'Диск', color: '#64748b' },
}

/** @param {string} nodeId */
export function nodeMeta(nodeId) {
  return (
    NODE_META[nodeId] || {
      label: nodeId,
      short: nodeId,
      color: '#64748b',
    }
  )
}

export const usePipelineStore = defineStore('pipeline', () => {
  const open = ref(false)
  const celeryTaskId = ref(null)
  const title = ref('')
  const seedProgress = ref(0)
  const seedDetail = ref('')
  const data = ref(null)
  const loading = ref(false)
  const error = ref(null)
  const waitingTelemetry = ref(false)
  let pollTimer = null

  const events = computed(() => data.value?.events || [])
  const progress = computed(() => data.value?.progress ?? seedProgress.value ?? 0)
  const currentDetail = computed(
    () => data.value?.current_detail || seedDetail.value || 'Ожидание телеметрии…'
  )
  const status = computed(() => data.value?.status || 'running')
  const isTerminal = computed(
    () => status.value === 'done' || status.value === 'error' || status.value === 'cancelled'
  )

  const activeNodes = computed(() => {
    const set = new Set(['platform'])
    for (const ev of events.value) {
      if (ev.from_node) set.add(ev.from_node)
      if (ev.to_node) set.add(ev.to_node)
    }
    return set
  })

  const activeEdge = computed(() => {
    const running = [...events.value].reverse().find((e) => e.status === 'running')
    if (running && running.to_node !== 'platform') {
      return { from: running.from_node || 'platform', to: running.to_node, id: running.id }
    }
    const last = [...events.value].reverse().find(
      (e) => e.to_node && e.to_node !== 'platform' && e.status !== 'skipped'
    )
    if (!last) return null
    return { from: last.from_node || 'platform', to: last.to_node, id: last.id }
  })

  async function fetchOnce() {
    if (!celeryTaskId.value) return
    try {
      const { data: payload } = await jobsApi.pipeline(celeryTaskId.value)
      data.value = payload
      error.value = null
      waitingTelemetry.value = false
      if (payload.progress != null) seedProgress.value = payload.progress
      if (payload.current_detail) seedDetail.value = payload.current_detail
      if (payload.status === 'done' || payload.status === 'error' || payload.status === 'cancelled') {
        stopPolling()
      }
    } catch (err) {
      if (err.response?.status === 404) {
        waitingTelemetry.value = true
      } else {
        error.value = 'Не удалось загрузить детали пайплайна'
      }
    } finally {
      loading.value = false
    }
  }

  function startPolling() {
    if (pollTimer) return
    pollTimer = setInterval(fetchOnce, POLL_MS)
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  /**
   * @param {{
   *   celeryTaskId: string,
   *   title?: string,
   *   progress?: number,
   *   detail?: string,
   * }} item
   */
  async function openFor(item) {
    if (!item?.celeryTaskId) return
    celeryTaskId.value = item.celeryTaskId
    title.value = item.title || 'Пайплайн задачи'
    seedProgress.value = Number(item.progress) || 0
    seedDetail.value = item.detail || ''
    open.value = true
    loading.value = true
    error.value = null
    waitingTelemetry.value = false
    data.value = null
    await fetchOnce()
    if (!isTerminal.value) startPolling()
  }

  function applyWsUpdate(payload) {
    if (!payload?.celery_task_id) return
    if (payload.celery_task_id === celeryTaskId.value) {
      if (payload.progress != null) seedProgress.value = payload.progress
      if (payload.current_detail) seedDetail.value = payload.current_detail
    }
    if (data.value && data.value.celery_task_id === payload.celery_task_id) {
      data.value = {
        ...data.value,
        progress: payload.progress ?? data.value.progress,
        current_detail: payload.current_detail ?? data.value.current_detail,
        status: payload.status ?? data.value.status,
      }
    }
    if (open.value && celeryTaskId.value === payload.celery_task_id) {
      fetchOnce()
    }
  }

  function close() {
    open.value = false
    stopPolling()
    celeryTaskId.value = null
    data.value = null
    error.value = null
    waitingTelemetry.value = false
  }

  function reset() {
    close()
  }

  return {
    open,
    celeryTaskId,
    title,
    seedProgress,
    seedDetail,
    data,
    loading,
    error,
    waitingTelemetry,
    events,
    progress,
    currentDetail,
    status,
    isTerminal,
    activeNodes,
    activeEdge,
    openFor,
    close,
    fetchOnce,
    applyWsUpdate,
    reset,
    stopPolling,
  }
})
