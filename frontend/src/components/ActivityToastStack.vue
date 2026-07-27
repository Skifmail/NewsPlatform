<template>
  <div class="toast-stack" aria-live="polite">
    <TransitionGroup name="toast-item">
      <article
        v-for="item in store.items"
        :key="item.id"
        class="activity-toast"
        :class="[phaseClass(item.phase), { 'toast-expandable': canExpand(item) }]"
        :role="canExpand(item) ? 'button' : undefined"
        :tabindex="canExpand(item) ? 0 : undefined"
        @click="onToastClick(item)"
        @keydown.enter.prevent="onToastClick(item)"
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
            <div class="toast-title-row">
              <p class="toast-title">{{ item.title }}</p>
              <span v-if="item.eventCount > 0" class="toast-steps-badge">{{ item.eventCount }} шагов</span>
            </div>
            <p class="toast-detail">{{ item.detail }}</p>
            <p v-if="latestStepLine(item)" class="toast-step-line">
              <span class="toast-step-arrow">→</span>
              {{ latestStepLine(item) }}
            </p>
            <p v-if="canExpand(item)" class="toast-hint">Нажмите для детальной схемы пайплайна</p>
          </div>
        </div>
        <div class="progress-track">
          <div class="progress-fill" :style="{ width: `${item.displayProgress}%` }" />
        </div>
      </article>
    </TransitionGroup>
  </div>
</template>

<script setup>
import { useActivityStore } from '../stores/activityStore'
import { usePipelineStore } from '../stores/pipelineStore'

const store = useActivityStore()
const pipelineStore = usePipelineStore()

function phaseClass(phase) {
  if (phase === 'done') return 'toast-done'
  if (phase === 'error') return 'toast-error'
  if (phase === 'queued') return 'toast-queued'
  return 'toast-running'
}

function canExpand(item) {
  return item.kind === 'job' && Boolean(item.celeryTaskId)
}

function latestStepLine(item) {
  const ev = item.latestEvent
  if (!ev) return ''
  if (ev.response_summary) return ev.response_summary
  if (ev.request_summary) return ev.request_summary
  return ev.label || ''
}

function onToastClick(item) {
  if (!canExpand(item)) return
  pipelineStore.openFor({
    celeryTaskId: item.celeryTaskId,
    title: item.title,
    progress: item.displayProgress ?? item.progress,
    detail: item.detail,
  })
}
</script>

<style scoped>
.toast-stack {
  @apply fixed bottom-6 right-6 z-50 flex w-[min(100%,26rem)] flex-col gap-3 pointer-events-none;
}

.activity-toast {
  @apply pointer-events-auto rounded-panel border bg-panel-elevated px-4 py-3 shadow-panel backdrop-blur-md;
  transition: border-color 0.3s ease, box-shadow 0.3s ease, transform 0.2s ease;
}

.toast-expandable {
  @apply cursor-pointer;
}

.toast-expandable:hover {
  @apply border-accent/50 -translate-y-0.5;
  box-shadow: 0 0 28px rgba(45, 212, 191, 0.14);
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

.toast-title-row {
  @apply flex items-start justify-between gap-2;
}

.toast-title {
  @apply text-sm font-semibold leading-snug text-[var(--text-primary)];
}

.toast-steps-badge {
  @apply shrink-0 rounded-full bg-accent/10 px-2 py-0.5 font-mono text-[10px] text-accent;
}

.toast-detail {
  @apply mt-0.5 text-xs leading-relaxed text-[var(--text-secondary)];
}

.toast-step-line {
  @apply mt-1.5 line-clamp-2 font-mono text-[11px] leading-relaxed text-accent/90;
}

.toast-step-arrow {
  @apply mr-1 opacity-70;
}

.toast-hint {
  @apply mt-1.5 text-[10px] uppercase tracking-wide text-[var(--text-secondary)] opacity-70;
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
