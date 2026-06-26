<template>
  <div class="toast-stack" aria-live="polite">
    <TransitionGroup name="toast-item">
      <article
        v-for="item in store.items"
        :key="item.id"
        class="activity-toast"
        :class="phaseClass(item.phase)"
      >
        <div class="toast-head">
          <span class="toast-icon" aria-hidden="true">
            <svg
              v-if="item.phase === 'done'"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            >
              <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
            </svg>
            <svg
              v-else-if="item.phase === 'error'"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            >
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
            <span v-else class="toast-spinner" />
          </span>
          <div class="toast-text">
            <p class="toast-title">{{ item.title }}</p>
            <p class="toast-detail">{{ item.detail }}</p>
          </div>
        </div>
        <div class="progress-track">
          <div
            class="progress-fill"
            :style="{ width: `${item.displayProgress}%` }"
          />
        </div>
      </article>
    </TransitionGroup>
  </div>
</template>

<script setup>
import { useActivityStore } from '../stores/activityStore'

const store = useActivityStore()

function phaseClass(phase) {
  if (phase === 'done') return 'toast-done'
  if (phase === 'error') return 'toast-error'
  if (phase === 'queued') return 'toast-queued'
  return 'toast-running'
}
</script>

<style scoped>
.toast-stack {
  @apply fixed bottom-6 right-6 z-50 flex w-[min(100%,22rem)] flex-col gap-3 pointer-events-none;
}

.activity-toast {
  @apply pointer-events-auto rounded-panel border bg-panel-elevated px-4 py-3 shadow-panel backdrop-blur-md;
  transition: border-color 0.3s ease, box-shadow 0.3s ease;
}

.toast-running {
  @apply border-accent/40 shadow-[0_0_24px_rgba(45,212,191,0.12)];
}

.toast-queued {
  @apply border-panel-border;
}

.toast-done {
  @apply border-accent/50;
}

.toast-error {
  @apply border-red-500/40;
}

.toast-head {
  @apply mb-2.5 flex gap-3;
}

.toast-icon {
  @apply mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent-muted text-accent;
}

.toast-icon svg {
  @apply h-4 w-4;
}

.toast-error .toast-icon {
  @apply bg-red-500/15 text-red-400;
}

.toast-spinner {
  @apply h-4 w-4 rounded-full border-2 border-accent/30 border-t-accent animate-spin;
}

.toast-text {
  @apply min-w-0 flex-1;
}

.toast-title {
  @apply text-sm font-semibold leading-snug text-[var(--text-primary)];
}

.toast-detail {
  @apply mt-0.5 text-xs leading-relaxed text-[var(--text-secondary)] line-clamp-2;
}

.progress-track {
  @apply h-1.5 overflow-hidden rounded-full bg-panel-border/80;
}

.progress-fill {
  @apply h-full rounded-full bg-gradient-to-r from-accent/70 to-accent transition-[width] duration-300 ease-out;
}

.toast-error .progress-fill {
  @apply from-red-500/70 to-red-400;
}

.toast-done .progress-fill {
  @apply from-accent to-emerald-400;
}

.toast-item-enter-active,
.toast-item-leave-active {
  transition: all 0.35s cubic-bezier(0.22, 1, 0.36, 1);
}

.toast-item-enter-from,
.toast-item-leave-to {
  opacity: 0;
  transform: translateX(12px) translateY(8px);
}

.toast-item-move {
  transition: transform 0.35s cubic-bezier(0.22, 1, 0.36, 1);
}
</style>
