<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="open"
        class="modal-backdrop"
        role="presentation"
        @click.self="onBackdrop"
      >
        <div
          class="modal-panel"
          role="dialog"
          aria-modal="true"
          aria-labelledby="refresh-progress-title"
        >
          <div class="modal-header">
            <div>
              <h2 id="refresh-progress-title" class="modal-title">
                Обновление статистики
              </h2>
              <p class="modal-sub">{{ statusLine }}</p>
            </div>
            <button
              type="button"
              class="btn-ghost btn-sm"
              aria-label="Закрыть"
              :disabled="!canClose"
              @click="emit('close')"
            >
              <svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div class="overall">
            <div class="overall-head">
              <span class="overall-count">{{ completed }} / {{ total || '—' }} каналов</span>
              <span class="overall-elapsed">{{ elapsedLabel }}</span>
            </div>
            <div class="progress-track">
              <div
                class="progress-fill"
                :class="{ 'progress-fill-error': isError }"
                :style="{ width: `${overallPercent}%` }"
              />
            </div>
          </div>

          <ul class="channel-list">
            <li
              v-for="ch in channels"
              :key="ch.id"
              class="channel-row"
              :class="`channel-row--${ch.status}`"
            >
              <span class="status-icon" :class="`status-icon--${ch.status}`">
                <svg v-if="ch.status === 'success'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                </svg>
                <svg v-else-if="ch.status === 'failed'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
                <span v-else-if="ch.status === 'running'" class="spinner" />
                <span v-else class="dot" />
              </span>

              <div class="channel-main">
                <div class="channel-top">
                  <span class="channel-name">{{ ch.name }}</span>
                  <span class="badge-muted channel-platform">{{ platformLabel(ch.platform) }}</span>
                </div>
                <p class="channel-detail" :class="{ 'channel-detail--error': ch.status === 'failed' }">
                  {{ detailFor(ch) }}
                </p>
              </div>
            </li>
          </ul>

          <div class="modal-actions">
            <button
              type="button"
              class="btn-secondary btn-sm"
              :disabled="!canClose"
              @click="emit('close')"
            >
              {{ canClose ? 'Закрыть' : 'Идёт сбор…' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  progress: { type: Object, default: null },
})

const emit = defineEmits(['close'])

const platformLabels = { telegram: 'Telegram', vk: 'VK', max: 'MAX' }
function platformLabel(p) {
  return platformLabels[p] || p
}

const now = ref(Date.now())
let timer = null

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      now.value = Date.now()
      if (!timer) timer = setInterval(() => (now.value = Date.now()), 1000)
    } else if (timer) {
      clearInterval(timer)
      timer = null
    }
  },
)

const channels = computed(() => props.progress?.channels || [])
const total = computed(() => props.progress?.total ?? channels.value.length)
const completed = computed(() => props.progress?.completed ?? 0)
const isDone = computed(() => props.progress?.status === 'done')
const isError = computed(() => props.progress?.status === 'error')
const canClose = computed(() => !props.progress || isDone.value || isError.value)

const overallPercent = computed(() => {
  if (!total.value) return isDone.value ? 100 : 8
  return Math.round((completed.value / total.value) * 100)
})

const failedCount = computed(
  () => channels.value.filter((c) => c.status === 'failed').length,
)

const statusLine = computed(() => {
  if (!props.progress) return 'Запуск задачи…'
  if (isDone.value) {
    const ok = total.value - failedCount.value
    return failedCount.value
      ? `Готово: успешно ${ok}, с ошибками ${failedCount.value}`
      : `Готово: обновлено ${ok} каналов`
  }
  if (isError.value) return 'Задача завершилась с ошибкой'
  const running = channels.value.find((c) => c.status === 'running')
  if (running) return `Опрашиваю канал «${running.name}»…`
  return 'Сбор статистики в процессе…'
})

const elapsedLabel = computed(() => {
  const started = props.progress?.started_at
  if (!started) return ''
  const end = props.progress?.finished_at
    ? new Date(props.progress.finished_at).getTime()
    : now.value
  const sec = Math.max(0, Math.round((end - new Date(started).getTime()) / 1000))
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return m ? `${m} мин ${s} с` : `${s} с`
})

function formatNum(n) {
  if (n == null) return '—'
  return new Intl.NumberFormat('ru-RU').format(n)
}

function detailFor(ch) {
  if (ch.status === 'pending') return 'Ожидание очереди'
  if (ch.status === 'running') return 'Опрос платформы…'
  if (ch.status === 'failed') return ch.error || 'Ошибка сбора'
  const parts = []
  if (ch.subscribers != null) parts.push(`${formatNum(ch.subscribers)} подписчиков`)
  if (ch.posts != null) parts.push(`${formatNum(ch.posts)} постов`)
  if (ch.total_views != null) parts.push(`${formatNum(ch.total_views)} просмотров`)
  return parts.length ? parts.join(' · ') : 'Данные получены'
}

function onBackdrop() {
  if (canClose.value) emit('close')
}
</script>

<style scoped>
.modal-backdrop {
  @apply fixed inset-0 z-[65] flex items-center justify-center bg-[var(--overlay-bg)] p-4 backdrop-blur-sm;
}

.modal-panel {
  @apply panel-card-elevated flex max-h-[85vh] w-full max-w-lg flex-col p-6 shadow-panel;
}

.modal-header {
  @apply mb-4 flex items-start justify-between gap-4;
}

.modal-title {
  @apply text-lg font-semibold text-[var(--text-primary)];
}

.modal-sub {
  @apply mt-1 text-sm text-[var(--text-secondary)];
}

.overall {
  @apply mb-4;
}

.overall-head {
  @apply mb-1.5 flex items-center justify-between text-xs text-[var(--text-secondary)];
}

.overall-count {
  @apply font-medium text-[var(--text-primary)];
}

.progress-track {
  @apply h-2 w-full overflow-hidden rounded-pill bg-panel-border;
}

.progress-fill {
  @apply h-full rounded-pill bg-accent transition-all duration-500 ease-out;
}

.progress-fill-error {
  @apply bg-danger;
}

.channel-list {
  @apply -mr-2 flex-1 space-y-1.5 overflow-y-auto pr-2;
}

.channel-row {
  @apply flex items-start gap-3 rounded-lg border border-transparent px-2 py-2 transition-colors;
}

.channel-row--running {
  @apply border-accent/30 bg-accent-muted;
}

.status-icon {
  @apply mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full;
}

.status-icon svg {
  @apply h-3.5 w-3.5;
}

.status-icon--success {
  @apply bg-accent-muted text-accent;
}

.status-icon--failed {
  @apply text-danger;
}

.dot {
  @apply h-2 w-2 rounded-full bg-panel-border;
}

.spinner {
  @apply h-3.5 w-3.5 rounded-full border-2 border-accent/30 border-t-accent;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.channel-main {
  @apply min-w-0 flex-1;
}

.channel-top {
  @apply flex items-center gap-2;
}

.channel-name {
  @apply truncate text-sm font-medium text-[var(--text-primary)];
}

.channel-platform {
  @apply shrink-0 text-[10px];
}

.channel-detail {
  @apply mt-0.5 truncate text-xs text-[var(--text-secondary)];
}

.channel-detail--error {
  @apply text-danger;
}

.modal-actions {
  @apply mt-4 flex justify-end border-t border-panel-border pt-4;
}

.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-active .modal-panel,
.modal-leave-active .modal-panel {
  transition: transform 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .modal-panel,
.modal-leave-to .modal-panel {
  transform: scale(0.96) translateY(8px);
}
</style>
