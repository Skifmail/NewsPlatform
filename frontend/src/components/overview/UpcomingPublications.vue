<template>
  <section class="upcoming panel-card">
    <header class="upcoming-head">
      <h2 class="upcoming-title">Ближайшие публикации</h2>
      <RouterLink to="/approved" class="upcoming-link">Все →</RouterLink>
    </header>

    <p v-if="!items.length" class="upcoming-empty">Запланированных публикаций нет.</p>

    <ul v-else class="upcoming-list">
      <li v-for="item in items" :key="item.id" class="upcoming-item">
        <div class="upcoming-meta">
          <span class="upcoming-channel">{{ item.channel_name }}</span>
          <PublishCountdown :scheduled-at="item.scheduled_at" />
        </div>
        <p v-if="item.preview" class="upcoming-preview">{{ item.preview }}</p>
      </li>
    </ul>
  </section>
</template>

<script setup>
import PublishCountdown from '../PublishCountdown.vue'

defineProps({
  items: { type: Array, default: () => [] },
})
</script>

<style scoped>
.upcoming {
  @apply p-4 h-full;
}

.upcoming-head {
  @apply mb-4 flex items-center justify-between gap-2;
}

.upcoming-title {
  @apply text-sm font-semibold text-[var(--text-primary)];
}

.upcoming-link {
  @apply text-xs font-medium text-accent hover:underline;
}

.upcoming-empty {
  @apply text-sm text-[var(--text-secondary)];
}

.upcoming-list {
  @apply flex flex-col gap-3;
}

.upcoming-item {
  @apply rounded-lg border border-panel-border bg-panel-bg/50 p-3;
}

.upcoming-meta {
  @apply mb-2 flex flex-wrap items-center justify-between gap-2;
}

.upcoming-channel {
  @apply text-sm font-medium text-[var(--text-primary)];
}

.upcoming-preview {
  @apply text-xs text-[var(--text-secondary)] line-clamp-2;
}
</style>
