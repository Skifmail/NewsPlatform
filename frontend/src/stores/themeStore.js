import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

const STORAGE_KEY = 'np-theme'

/** @typedef {'dark' | 'light'} ThemeMode */

/**
 * Читает сохранённую тему из localStorage.
 *
 * @returns {ThemeMode}
 */
function readStoredTheme() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    return stored === 'light' ? 'light' : 'dark'
  } catch {
    return 'dark'
  }
}

/**
 * Применяет тему к корневому элементу документа.
 *
 * @param {ThemeMode} mode - Режим темы.
 * @returns {void}
 */
export function applyTheme(mode) {
  document.documentElement.dataset.theme = mode
}

/**
 * Pinia-store для переключения светлой и тёмной темы.
 */
export const useThemeStore = defineStore('theme', () => {
  const mode = ref(readStoredTheme())

  const isDark = computed(() => mode.value === 'dark')
  const isLight = computed(() => mode.value === 'light')

  /**
   * Устанавливает тему и сохраняет выбор.
   *
   * @param {ThemeMode} next - Новый режим темы.
   * @returns {void}
   */
  function setTheme(next) {
    mode.value = next
    applyTheme(next)
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {
      /* ignore */
    }
  }

  /**
   * Переключает тему между светлой и тёмной.
   *
   * @returns {void}
   */
  function toggleTheme() {
    setTheme(mode.value === 'dark' ? 'light' : 'dark')
  }

  /**
   * Инициализирует тему при старте приложения.
   *
   * @returns {void}
   */
  function initTheme() {
    applyTheme(mode.value)
  }

  return {
    mode,
    isDark,
    isLight,
    setTheme,
    toggleTheme,
    initTheme,
  }
})
