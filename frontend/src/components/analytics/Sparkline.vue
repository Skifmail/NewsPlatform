<template>
  <svg
    :viewBox="`0 0 ${width} ${height}`"
    preserveAspectRatio="none"
    class="sparkline"
    role="img"
    aria-hidden="true"
  >
    <polyline
      v-if="pathPoints"
      :points="pathPoints"
      fill="none"
      stroke="currentColor"
      stroke-width="1.5"
      stroke-linecap="round"
      stroke-linejoin="round"
      vector-effect="non-scaling-stroke"
    />
  </svg>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  points: {
    type: Array,
    default: () => [],
  },
  width: { type: Number, default: 120 },
  height: { type: Number, default: 40 },
})

const pathPoints = computed(() => {
  const values = props.points
    .map((p) => p.subscribers)
    .filter((v) => v != null)
  if (values.length < 2) return ''

  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const stepX = props.width / (values.length - 1)

  return values
    .map((value, index) => {
      const x = index * stepX
      const y = props.height - ((value - min) / range) * (props.height - 4) - 2
      return `${x},${y}`
    })
    .join(' ')
})
</script>

<style scoped>
.sparkline {
  @apply text-accent opacity-80;
}
</style>
