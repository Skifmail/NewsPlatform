<template>
  <div
    class="theme-toggle"
    role="group"
    aria-label="Переключение темы"
  >
    <button
      type="button"
      class="theme-toggle-btn"
      :class="{ 'theme-toggle-btn-active': theme.isLight }"
      :aria-pressed="theme.isLight"
      title="Светлая тема"
      @click="theme.setTheme('light')"
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
        <circle cx="12" cy="12" r="4" />
        <path
          stroke-linecap="round"
          d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"
        />
      </svg>
    </button>
    <button
      type="button"
      class="theme-toggle-btn"
      :class="{ 'theme-toggle-btn-active': theme.isDark }"
      :aria-pressed="theme.isDark"
      title="Тёмная тема"
      @click="theme.setTheme('dark')"
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"
        />
      </svg>
    </button>
  </div>
</template>

<script setup>
import { useThemeStore } from '../../stores/themeStore'

const theme = useThemeStore()
</script>

<style scoped>
.theme-toggle {
  @apply inline-flex items-center gap-0.5 rounded-pill border border-panel-border bg-panel-surface p-0.5 shadow-sm;
}

.theme-toggle-btn {
  @apply flex h-8 w-8 items-center justify-center rounded-pill text-[var(--text-secondary)]
    transition-all duration-200 hover:text-[var(--text-primary)];
}

.theme-toggle-btn svg {
  @apply h-4 w-4;
}

.theme-toggle-btn-active {
  @apply bg-accent text-white shadow-sm hover:text-white;
}
</style>
