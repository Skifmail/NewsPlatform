import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getToken, postsApi } from '../api/index.js'

export const usePostsStore = defineStore('posts', () => {
  const queue = ref([])
  const approved = ref([])
  const approvedCount = ref(0)
  const loading = ref(false)
  const approvedLoading = ref(false)
  const error = ref(null)
  const approvedError = ref(null)
  let ws = null
  let reconnectTimer = null
  let messageHandler = null
  const wsConnected = ref(false)

  async function loadQueue() {
    loading.value = true
    error.value = null
    try {
      const { data } = await postsApi.queue()
      queue.value = data
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function loadApproved() {
    approvedLoading.value = true
    approvedError.value = null
    try {
      const { data } = await postsApi.approved()
      approved.value = data
      approvedCount.value = data.length
    } catch (e) {
      approvedError.value = e.message
    } finally {
      approvedLoading.value = false
    }
  }

  async function loadApprovedSummary() {
    try {
      const { data } = await postsApi.approvedSummary()
      approvedCount.value = data.total
    } catch {
      /* ignore */
    }
  }

  async function approve(id, payload) {
    await postsApi.approve(id, payload)
    await Promise.all([loadQueue(), loadApprovedSummary()])
  }

  async function reject(id, reason) {
    await postsApi.reject(id, { reason })
    queue.value = queue.value.filter((p) => p.id !== id)
    await loadQueue()
  }

  async function bulkQueueAction(payload) {
    const { data } = await postsApi.bulkQueue(payload)
    await loadQueue()
    return data
  }

  async function publishNow(id) {
    await postsApi.publishNow(id)
    await Promise.all([loadQueue(), loadApproved(), loadApprovedSummary()])
  }

  async function schedule(id, scheduledAt) {
    await postsApi.schedule(id, { scheduled_at: scheduledAt })
    await Promise.all([loadQueue(), loadApproved(), loadApprovedSummary()])
  }

  async function updatePost(id, payload) {
    const { data } = await postsApi.update(id, payload)
    const idx = approved.value.findIndex((p) => p.id === id)
    if (idx >= 0) approved.value[idx] = data
    return data
  }

  async function deletePost(id) {
    await postsApi.remove(id)
    approved.value = approved.value.filter((p) => p.id !== id)
    approvedCount.value = approved.value.length
    await loadApprovedSummary()
  }

  function disconnectWebSocket() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (ws) {
      ws.onclose = null
      ws.close()
      ws = null
    }
    messageHandler = null
    wsConnected.value = false
  }

  function connectWebSocket(onMessage) {
    const token = getToken()
    if (!token) {
      return
    }
    disconnectWebSocket()
    messageHandler = onMessage

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const url = `${protocol}//${host}/ws/updates?token=${encodeURIComponent(token)}`
    ws = new WebSocket(url)

    ws.onopen = () => {
      wsConnected.value = true
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        messageHandler?.(msg)
      } catch {
        /* ignore */
      }
    }
    ws.onclose = () => {
      ws = null
      wsConnected.value = false
      if (!getToken() || !messageHandler) {
        return
      }
      reconnectTimer = setTimeout(() => {
        connectWebSocket(messageHandler)
      }, 5000)
    }
  }

  return {
    queue,
    approved,
    approvedCount,
    loading,
    approvedLoading,
    error,
    approvedError,
    wsConnected,
    loadQueue,
    loadApproved,
    loadApprovedSummary,
    approve,
    reject,
    bulkQueueAction,
    publishNow,
    schedule,
    updatePost,
    deletePost,
    connectWebSocket,
    disconnectWebSocket,
  }
})
