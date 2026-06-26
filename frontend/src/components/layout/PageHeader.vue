<template>
  <header class="page-header">
    <div>
      <h1 class="page-title">{{ title }}</h1>
      <p v-if="subtitle" class="page-subtitle">{{ subtitle }}</p>
    </div>
    <div class="page-header-right">
      <div v-if="$slots.actions" class="page-actions">
        <slot name="actions" />
      </div>
      <ThemeToggle />
    </div>
  </header>
</template>

<script setup>
import ThemeToggle from './ThemeToggle.vue'

defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
})
</script>

<style scoped>
.page-header {
  @apply mb-6 flex flex-wrap items-start justify-between gap-4;
}

.page-title {
  @apply text-xl font-semibold tracking-tight text-[var(--text-primary)];
}

.page-subtitle {
  @apply mt-1 text-sm text-[var(--text-secondary)];
}

.page-header-right {
  @apply flex flex-wrap items-center gap-2;
}

.page-actions {
  @apply flex flex-wrap items-center gap-2;
}
</style>
