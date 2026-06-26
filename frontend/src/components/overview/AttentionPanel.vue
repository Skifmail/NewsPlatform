<template>
  <section class="attention panel-card">
    <header class="attention-head">
      <h2 class="attention-title">Требует внимания</h2>
      <span v-if="!items.length" class="badge-accent">Всё спокойно</span>
    </header>

    <p v-if="!items.length" class="attention-empty">
      Нет срочных задач — платформа работает штатно.
    </p>

    <ul v-else class="attention-list">
      <li
        v-for="(item, index) in items"
        :key="item.key"
        class="attention-item"
        :class="`attention-${item.severity}`"
        :style="{ animationDelay: `${index * 60}ms` }"
        role="button"
        tabindex="0"
        @click="go(item.route)"
        @keydown.enter="go(item.route)"
      >
        <span class="attention-count">{{ item.count }}</span>
        <span class="attention-label">{{ item.label }}</span>
        <span class="attention-arrow">→</span>
      </li>
    </ul>
  </section>
</template>

<script setup>
import { useRouter } from 'vue-router'

defineProps({
  items: { type: Array, default: () => [] },
})

const router = useRouter()

function go(route) {
  if (route) router.push(route)
}
</script>

<style scoped>
.attention {
  @apply p-4 h-full;
}

.attention-head {
  @apply mb-4 flex items-center justify-between gap-2;
}

.attention-title {
  @apply text-sm font-semibold text-[var(--text-primary)];
}

.attention-empty {
  @apply text-sm text-[var(--text-secondary)];
}

.attention-list {
  @apply flex flex-col gap-2;
}

.attention-item {
  @apply flex items-center gap-3 rounded-lg border border-panel-border bg-panel-bg/60 px-3 py-2.5
    cursor-pointer transition-all duration-200 hover:border-accent/40 hover:bg-panel-hover/50;
  animation: attention-enter 0.45s cubic-bezier(0.22, 1, 0.36, 1) both;
}

.attention-count {
  @apply flex h-8 min-w-[2rem] items-center justify-center rounded-pill bg-panel-hover
    px-2 text-sm font-semibold tabular-nums;
}

.attention-label {
  @apply flex-1 text-sm text-[var(--text-primary)];
}

.attention-arrow {
  @apply text-xs text-accent opacity-0 transition-opacity;
}

.attention-item:hover .attention-arrow {
  @apply opacity-100;
}

.attention-warning .attention-count {
  @apply bg-amber-500/15 text-amber-400;
}

.attention-danger .attention-count {
  @apply bg-danger/15 text-danger;
}

.attention-info .attention-count {
  @apply bg-info/15 text-info;
}

@keyframes attention-enter {
  from {
    opacity: 0;
    transform: translateX(-8px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .attention-item {
    animation: none;
  }
}
</style>
