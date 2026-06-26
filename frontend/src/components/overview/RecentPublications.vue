<template>
  <section class="recent panel-card">
    <header class="recent-head">
      <h2 class="recent-title">Последние публикации</h2>
      <RouterLink to="/history" class="recent-link">История →</RouterLink>
    </header>

    <p v-if="!items.length" class="recent-empty">Публикаций пока нет.</p>

    <ul v-else class="recent-list">
      <li v-for="item in items" :key="item.id" class="recent-item">
        <div class="recent-row">
          <span class="recent-channel">{{ item.channel_name || '—' }}</span>
          <span class="recent-badge" :class="statusClass(item.status)">
            {{ statusLabel(item.status) }}
          </span>
        </div>
        <p v-if="item.preview" class="recent-preview">{{ item.preview }}</p>
        <span class="recent-time">{{ formatDate(item.attempted_at) }}</span>
      </li>
    </ul>
  </section>
</template>

<script setup>
defineProps({
  items: { type: Array, default: () => [] },
})

function statusLabel(status) {
  return status === 'success' ? 'Успех' : 'Ошибка'
}

function statusClass(status) {
  return status === 'success' ? 'recent-success' : 'recent-failed'
}

function formatDate(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}
</script>

<style scoped>
.recent {
  @apply p-4 h-full;
}

.recent-head {
  @apply mb-4 flex items-center justify-between gap-2;
}

.recent-title {
  @apply text-sm font-semibold text-[var(--text-primary)];
}

.recent-link {
  @apply text-xs font-medium text-accent hover:underline;
}

.recent-empty {
  @apply text-sm text-[var(--text-secondary)];
}

.recent-list {
  @apply flex max-h-80 flex-col gap-2 overflow-y-auto;
}

.recent-item {
  @apply rounded-lg border border-panel-border bg-panel-bg/50 px-3 py-2.5;
}

.recent-row {
  @apply mb-1 flex items-center justify-between gap-2;
}

.recent-channel {
  @apply text-sm font-medium text-[var(--text-primary)] truncate;
}

.recent-badge {
  @apply shrink-0 rounded-pill px-2 py-0.5 text-[10px] font-semibold uppercase;
}

.recent-success {
  @apply bg-accent-muted text-accent;
}

.recent-failed {
  @apply bg-danger/15 text-danger;
}

.recent-preview {
  @apply mb-1 text-xs text-[var(--text-secondary)] line-clamp-2;
}

.recent-time {
  @apply text-[10px] font-mono text-[var(--text-secondary)];
}
</style>
