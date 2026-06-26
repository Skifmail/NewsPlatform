<template>
  <section class="live-feed panel-card">
    <header class="feed-head">
      <h2 class="feed-title">Живая активность</h2>
      <span class="live-pill" :class="connected ? 'live-on' : 'live-off'">
        <span class="live-dot" />
        {{ connected ? 'Online' : 'Offline' }}
      </span>
    </header>

    <p v-if="!items.length" class="feed-empty">Фоновых задач сейчас нет.</p>

    <ul v-else class="feed-list">
      <li v-for="item in items" :key="item.id" class="feed-item" :class="phaseClass(item.phase)">
        <div class="feed-item-head">
          <span class="feed-title-text">{{ item.title }}</span>
          <span class="feed-phase">{{ phaseLabel(item.phase) }}</span>
        </div>
        <p class="feed-detail">{{ item.detail }}</p>
        <div class="feed-progress">
          <div class="feed-progress-fill" :style="{ width: `${item.displayProgress}%` }" />
        </div>
      </li>
    </ul>
  </section>
</template>

<script setup>
defineProps({
  items: { type: Array, default: () => [] },
  connected: { type: Boolean, default: false },
})

function phaseClass(phase) {
  if (phase === 'done') return 'feed-done'
  if (phase === 'error') return 'feed-error'
  return 'feed-running'
}

function phaseLabel(phase) {
  if (phase === 'done') return 'Готово'
  if (phase === 'error') return 'Ошибка'
  if (phase === 'queued') return 'В очереди'
  return 'В работе'
}
</script>

<style scoped>
.live-feed {
  @apply p-4 h-full;
}

.feed-head {
  @apply mb-4 flex items-center justify-between gap-2;
}

.feed-title {
  @apply text-sm font-semibold text-[var(--text-primary)];
}

.live-pill {
  @apply inline-flex items-center gap-1.5 rounded-pill px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider;
}

.live-on {
  @apply bg-accent-muted text-accent;
}

.live-off {
  @apply bg-panel-hover text-[var(--text-secondary)];
}

.live-dot {
  @apply h-1.5 w-1.5 rounded-full bg-current;
}

.live-on .live-dot {
  animation: live-pulse 1.6s ease-in-out infinite;
}

.feed-empty {
  @apply text-sm text-[var(--text-secondary)];
}

.feed-list {
  @apply flex max-h-72 flex-col gap-2 overflow-y-auto;
}

.feed-item {
  @apply rounded-lg border border-panel-border bg-panel-bg/50 px-3 py-2.5;
}

.feed-item-head {
  @apply mb-1 flex items-start justify-between gap-2;
}

.feed-title-text {
  @apply text-sm font-medium text-[var(--text-primary)];
}

.feed-phase {
  @apply shrink-0 text-[10px] uppercase tracking-wide text-[var(--text-secondary)];
}

.feed-detail {
  @apply mb-2 text-xs text-[var(--text-secondary)] line-clamp-2;
}

.feed-progress {
  @apply h-1 overflow-hidden rounded-full bg-panel-border/80;
}

.feed-progress-fill {
  @apply h-full rounded-full bg-accent transition-[width] duration-300 ease-out;
}

.feed-error .feed-progress-fill {
  @apply bg-danger;
}

.feed-done .feed-progress-fill {
  @apply bg-accent;
}

@keyframes live-pulse {
  0%,
  100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.45;
    transform: scale(0.85);
  }
}

@media (prefers-reduced-motion: reduce) {
  .live-on .live-dot {
    animation: none;
  }
}
</style>
