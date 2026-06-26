import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { authApi, clearToken, getToken, setToken } from '../api/index.js'

export const useAuthStore = defineStore('auth', () => {
  const username = ref('')
  const loading = ref(false)
  const error = ref(null)
  const token = ref(getToken())

  const isAuthenticated = computed(() => Boolean(token.value))

  async function login(user, password) {
    loading.value = true
    error.value = null
    try {
      const { data } = await authApi.login(user, password)
      setToken(data.access_token)
      token.value = data.access_token
      username.value = user
      return true
    } catch (e) {
      const detail = e.response?.data?.detail
      error.value = Array.isArray(detail)
        ? detail.map((d) => d.msg).join(', ')
        : detail || e.message || 'Ошибка входа'
      clearToken()
      token.value = ''
      return false
    } finally {
      loading.value = false
    }
  }

  async function fetchMe() {
    if (!token.value) return false
    try {
      const { data } = await authApi.me()
      username.value = data.username
      return true
    } catch {
      clearToken()
      token.value = ''
      username.value = ''
      return false
    }
  }

  function logout() {
    clearToken()
    token.value = ''
    username.value = ''
    error.value = null
  }

  return {
    username,
    loading,
    error,
    isAuthenticated,
    login,
    fetchMe,
    logout,
  }
})
