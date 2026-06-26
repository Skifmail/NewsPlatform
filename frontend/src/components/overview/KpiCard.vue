<template>
  <article
    class="kpi-card panel-card"
    :class="{ 'kpi-card-clickable': to }"
    :style="{ animationDelay: `${delay}ms` }"
    role="button"
    :tabindex="to ? 0 : undefined"
    @click="navigate"
    @keydown.enter="navigate"
  >
    <div class="kpi-glow" aria-hidden="true" />
    <span class="kpi-label">{{ label }}</span>
    <span class="kpi-value" :class="valueClass">
      {{ formattedValue }}
      <span v-if="delta != null" class="kpi-delta" :class="deltaClass">{{ deltaText }}</span>
    </span>
    <span v-if="sub" class="kpi-sub">{{ sub }}</span>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useCountUp } from '../../composables/useCountUp.js'

const props = defineProps({
  label: { type: String, required: true },
  value: { type: Number, default: 0 },
  format: { type: String, default: 'number' },
  delta: { type: Number, default: null },
  sub: { type: String, default: '' },
  accent: { type: Boolean, default: false },
  to: { type: String, default: '' },
  delay: { type: Number, default: 0 },
})

const router = useRouter()
const animated = useCountUp(() => props.value)

const formattedValue = computed(() => {
  if (props.format === 'compact') {
    return new Intl.NumberFormat('ru-RU', {
      notation: 'compact',
      maximumFractionDigits: 1,
    }).format(animated.value)
  }
  return new Intl.NumberFormat('ru-RU').format(animated.value)
})

const valueClass = computed(() => (props.accent ? 'text-accent' : ''))

const deltaText = computed(() => {
  if (props.delta == null) return ''
  if (props.delta === 0) return '0'
  return props.delta > 0 ? `+${props.delta}` : String(props.delta)
})

const deltaClass = computed(() => {
  if (props.delta > 0) return 'text-accent'
  if (props.delta < 0) return 'text-danger'
  return 'text-[var(--text-secondary)]'
})

function navigate() {
  if (props.to) router.push(props.to)
}
</script>

<style scoped>
.kpi-card {
  @apply relative overflow-hidden p-4 flex flex-col gap-1 min-w-0;
  animation: kpi-enter 0.55s cubic-bezier(0.22, 1, 0.36, 1) both;
  transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;
}

.kpi-card-clickable {
  @apply cursor-pointer;
}

.kpi-card-clickable:hover {
  @apply -translate-y-0.5 shadow-glow border-accent/35;
}

.kpi-glow {
  @apply pointer-events-none absolute -right-6 -top-6 h-24 w-24 rounded-full opacity-0 transition-opacity duration-300;
  background: radial-gradient(circle, rgb(var(--accent-rgb) / 0.22), transparent 70%);
}

.kpi-card:hover .kpi-glow {
  @apply opacity-100;
}

.kpi-label {
  @apply text-xs uppercase tracking-wide text-[var(--text-secondary)];
}

.kpi-value {
  @apply text-2xl font-semibold tabular-nums text-[var(--text-primary)];
}

.kpi-delta {
  @apply ml-2 text-sm font-medium;
}

.kpi-sub {
  @apply text-xs text-[var(--text-secondary)];
}

@keyframes kpi-enter {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .kpi-card {
    animation: none;
  }
}
</style>
