<template>
  <div class="countdown" :class="urgencyClass">
    <span class="countdown-label">{{ label }}</span>
    <span class="countdown-value">{{ display }}</span>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'

const props = defineProps({
  scheduledAt: { type: String, default: null },
})

const now = ref(Date.now())
let timer = null

onMounted(() => {
  timer = setInterval(() => {
    now.value = Date.now()
  }, 1000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

const targetMs = computed(() => {
  if (!props.scheduledAt) return null
  const t = new Date(props.scheduledAt).getTime()
  return Number.isNaN(t) ? null : t
})

const remainingMs = computed(() => {
  if (targetMs.value == null) return null
  return targetMs.value - now.value
})

const label = computed(() => {
  if (!props.scheduledAt) return 'Публикация'
  if (remainingMs.value == null) return 'Публикация'
  if (remainingMs.value <= 0) return 'Публикуется'
  return 'До публикации'
})

const display = computed(() => {
  if (!props.scheduledAt) return 'не запланировано'
  if (remainingMs.value == null) return '—'
  if (remainingMs.value <= 0) return 'сейчас'
  const sec = Math.floor(remainingMs.value / 1000)
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = sec % 60
  if (h > 0) return `${h}ч ${String(m).padStart(2, '0')}м ${String(s).padStart(2, '0')}с`
  if (m > 0) return `${m}м ${String(s).padStart(2, '0')}с`
  return `${s}с`
})

const urgencyClass = computed(() => {
  if (remainingMs.value == null) return 'countdown-muted'
  if (remainingMs.value <= 0) return 'countdown-now'
  if (remainingMs.value < 5 * 60 * 1000) return 'countdown-soon'
  return 'countdown-ok'
})
</script>

<style scoped>
.countdown {
  @apply flex items-center justify-between gap-2 rounded-lg border px-3 py-2 text-sm;
}

.countdown-label {
  @apply text-xs uppercase tracking-wider text-[var(--text-secondary)];
}

.countdown-value {
  @apply font-mono font-semibold tabular-nums;
}

.countdown-ok {
  @apply border-accent/30 bg-accent-muted text-accent;
}

.countdown-soon {
  @apply border-amber-500/40 bg-amber-500/10 text-amber-400;
}

.countdown-now {
  @apply border-accent/50 bg-accent/20 text-accent animate-pulse;
}

.countdown-muted {
  @apply border-panel-border bg-panel-bg text-[var(--text-secondary)];
}
</style>
