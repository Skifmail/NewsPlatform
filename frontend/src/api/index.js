import axios from 'axios'

const TOKEN_STORAGE = 'content_platform_token'

export function getToken() {
  return localStorage.getItem(TOKEN_STORAGE) || ''
}

export function setToken(token) {
  localStorage.setItem(TOKEN_STORAGE, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_STORAGE)
}

const api = axios.create({
  baseURL: '/api',
})

api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && !error.config?.url?.includes('/auth/login')) {
      clearToken()
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default api

export const authApi = {
  login: (username, password) =>
    api.post('/auth/login', { username, password }),
  me: () => api.get('/auth/me'),
}

export const postsApi = {
  queue: () => api.get('/posts/queue'),
  approved: () => api.get('/posts/approved'),
  approvedSummary: () => api.get('/posts/approved/summary'),
  get: (id) => api.get(`/posts/${id}`),
  update: (id, data) => api.patch(`/posts/${id}`, data),
  remove: (id) => api.delete(`/posts/${id}`),
  approve: (id, data) => api.patch(`/posts/${id}/approve`, data),
  reject: (id, data) => api.patch(`/posts/${id}/reject`, data),
  publishNow: (id) => api.post(`/posts/${id}/publish_now`),
  refreshImage: (id) => api.post(`/posts/${id}/refresh-image`),
  bulkQueue: (data) => api.post('/posts/queue/bulk', data),
}

export const sourcesApi = {
  list: () => api.get('/sources'),
  create: (data) => api.post('/sources', data),
  update: (id, data) => api.patch(`/sources/${id}`, data),
  remove: (id) => api.delete(`/sources/${id}`),
  fetchNow: (id) => api.post(`/sources/${id}/fetch_now`),
}

export const channelsApi = {
  list: () => api.get('/channels'),
  create: (data) => api.post('/channels', data),
  update: (id, data) => api.patch(`/channels/${id}`, data),
  remove: (id) => api.delete(`/channels/${id}`),
  generateArticle: (id) => api.post(`/channels/${id}/generate-article`),
}

export const settingsApi = {
  get: () => api.get('/settings'),
  update: (data) => api.patch('/settings', data),
}

export const aiUsageApi = {
  get: (params) => api.get('/ai-usage', { params }),
}

export const historyApi = {
  list: (params) => api.get('/history', { params }),
}

export const overviewApi = {
  get: (params) => api.get('/overview', { params }),
}

export const analyticsApi = {
  summary: () => api.get('/analytics/summary'),
  channels: () => api.get('/analytics/channels'),
  channel: (id) => api.get(`/analytics/channels/${id}`),
  channelGrowth: (id, params) => api.get(`/analytics/channels/${id}/growth`, { params }),
  channelPosts: (id, params) => api.get(`/analytics/channels/${id}/posts`, { params }),
  channelMembers: (id) => api.get(`/analytics/channels/${id}/members`),
  channelTelegramStats: (id) => api.get(`/analytics/channels/${id}/telegram-stats`),
  refreshChannel: (id) => api.post(`/analytics/channels/${id}/refresh`),
  refreshAll: () => api.post('/analytics/refresh-all'),
  refreshProgress: (jobId) => api.get(`/analytics/refresh-progress/${jobId}`),
  ads: (params) => api.get('/analytics/ads', { params }),
  createAd: (data) => api.post('/analytics/ads', data),
  updateAd: (id, data) => api.patch(`/analytics/ads/${id}`, data),
  removeAd: (id) => api.delete(`/analytics/ads/${id}`),
}

export const jobsApi = {
  list: (params) => api.get('/jobs', { params }),
  active: () => api.get('/jobs/active'),
  summary: () => api.get('/jobs/summary'),
}

export const rawPostsApi = {
  summary: () => api.get('/raw-posts/summary'),
  list: (params) => api.get('/raw-posts', { params }),
  process: (id) => api.post(`/raw-posts/${id}/process`),
  processBatch: (rawPostIds) =>
    api.post('/raw-posts/process-batch', { raw_post_ids: rawPostIds }),
  bulkDelete: (data) => api.post('/raw-posts/bulk-delete', data),
}
