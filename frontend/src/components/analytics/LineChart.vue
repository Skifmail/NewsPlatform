<template>
  <div
    ref="containerRef"
    class="line-chart"
    @mousemove="onMouseMove"
    @mouseleave="clearHover"
  >
    <div
      v-if="hoveredPoint"
      ref="tooltipRef"
      class="chart-tooltip"
      :class="tooltipPlacement === 'below' ? 'chart-tooltip--below' : 'chart-tooltip--above'"
      :style="tooltipStyle"
      role="tooltip"
    >
      <span class="chart-tooltip-value">{{ formatValue(hoveredPoint.value) }}</span>
      <span v-if="hoveredPoint.fullLabel" class="chart-tooltip-label">
        {{ hoveredPoint.fullLabel }}
      </span>
    </div>

    <svg :viewBox="`0 0 ${width} ${height}`" class="chart-svg" role="img">
      <g v-if="hasData">
        <line
          v-for="(tick, i) in yTicks"
          :key="`grid-${i}`"
          :x1="padding.left"
          :x2="width - padding.right"
          :y1="tick.y"
          :y2="tick.y"
          class="grid-line"
        />

        <text
          v-for="(tick, i) in yTicks"
          :key="`ylabel-${i}`"
          :x="padding.left - 8"
          :y="tick.y + 3"
          text-anchor="end"
          class="axis-label"
        >
          {{ tick.label }}
        </text>

        <polygon :points="areaPoints" class="chart-area" />
        <polyline
          :points="linePoints"
          class="chart-line"
          :class="{ 'chart-line-animate': animate }"
          vector-effect="non-scaling-stroke"
        />

        <g v-for="(pt, i) in points" :key="`pt-${i}`">
          <circle
            :cx="pt.x"
            :cy="pt.y"
            :r="hoveredIndex === i ? 5 : 3"
            class="chart-dot"
            :class="{ 'chart-dot-active': hoveredIndex === i }"
            @mouseenter="setHover(i)"
          />
        </g>

        <text
          v-for="(label, i) in xLabels"
          :key="`xlabel-${i}`"
          :x="label.x"
          :y="height - 6"
          text-anchor="middle"
          class="axis-label"
        >
          {{ label.text }}
        </text>
      </g>

      <text
        v-else
        :x="width / 2"
        :y="height / 2"
        text-anchor="middle"
        class="axis-label"
      >
        Недостаточно данных для графика
      </text>
    </svg>
  </div>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue'

const props = defineProps({
  series: {
    type: Array,
    default: () => [],
  },
  width: { type: Number, default: 640 },
  height: { type: Number, default: 240 },
  animate: { type: Boolean, default: false },
})

const TOOLTIP_EDGE_GAP = 8
const TOOLTIP_POINT_GAP = 12
const TOOLTIP_ESTIMATED_HEIGHT = 48

const padding = { top: 28, right: 20, bottom: 28, left: 48 }

const containerRef = ref(null)
const tooltipRef = ref(null)
const hoveredIndex = ref(null)
const tooltipPos = ref({ x: 0, y: 0 })
const tooltipPlacement = ref('above')

const cleanSeries = computed(() =>
  props.series.filter((p) => p.value != null)
)

const hasData = computed(() => cleanSeries.value.length >= 2)

const bounds = computed(() => {
  const values = cleanSeries.value.map((p) => p.value)
  const min = Math.min(...values)
  const max = Math.max(...values)
  if (min === max) {
    return { min: min - 1, max: max + 1 }
  }
  const pad = (max - min) * 0.1
  return { min: Math.max(0, min - pad), max: max + pad }
})

const plotWidth = computed(() => props.width - padding.left - padding.right)
const plotHeight = computed(() => props.height - padding.top - padding.bottom)

function xFor(index, total) {
  if (total <= 1) return padding.left
  return padding.left + (index / (total - 1)) * plotWidth.value
}

function yFor(value) {
  const { min, max } = bounds.value
  const ratio = (value - min) / (max - min || 1)
  return padding.top + (1 - ratio) * plotHeight.value
}

const points = computed(() =>
  cleanSeries.value.map((p, i) => ({
    x: xFor(i, cleanSeries.value.length),
    y: yFor(p.value),
    value: p.value,
    label: p.label,
    fullLabel: p.fullLabel || p.label,
  }))
)

const hoveredPoint = computed(() => {
  if (hoveredIndex.value == null) return null
  return points.value[hoveredIndex.value] || null
})

const tooltipStyle = computed(() => ({
  left: `${tooltipPos.value.x}px`,
  top: `${tooltipPos.value.y}px`,
}))

const linePoints = computed(() =>
  points.value.map((p) => `${p.x},${p.y}`).join(' ')
)

const areaPoints = computed(() => {
  if (!points.value.length) return ''
  const baseY = padding.top + plotHeight.value
  const first = points.value[0]
  const last = points.value[points.value.length - 1]
  return [
    `${first.x},${baseY}`,
    ...points.value.map((p) => `${p.x},${p.y}`),
    `${last.x},${baseY}`,
  ].join(' ')
})

const yTicks = computed(() => {
  const { min, max } = bounds.value
  const count = 4
  return Array.from({ length: count + 1 }, (_, i) => {
    const value = min + ((max - min) * i) / count
    return {
      y: yFor(value),
      label: formatTick(value),
    }
  })
})

const xLabels = computed(() => {
  const total = points.value.length
  if (!total) return []
  const maxLabels = 6
  const step = Math.max(1, Math.ceil(total / maxLabels))
  const result = []
  for (let i = 0; i < total; i += step) {
    result.push({ x: points.value[i].x, text: points.value[i].label })
  }
  return result
})

function formatTick(value) {
  const rounded = Math.round(value)
  if (Math.abs(rounded) >= 1000) {
    return `${(rounded / 1000).toFixed(1)}k`
  }
  return `${rounded}`
}

function formatValue(value) {
  return new Intl.NumberFormat('ru-RU').format(value)
}

function setHover(index) {
  hoveredIndex.value = index
  updateTooltipPosition(index)
}

function clearHover() {
  hoveredIndex.value = null
  tooltipPlacement.value = 'above'
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

function updateTooltipPosition(index) {
  const container = containerRef.value
  const point = points.value[index]
  if (!container || !point) return

  const svg = container.querySelector('.chart-svg')
  if (!svg) return

  const svgRect = svg.getBoundingClientRect()
  const containerRect = container.getBoundingClientRect()
  const scaleX = svgRect.width / props.width
  const scaleY = svgRect.height / props.height

  const pointX = svgRect.left - containerRect.left + point.x * scaleX
  const pointY = svgRect.top - containerRect.top + point.y * scaleY

  const tooltipHeight =
    tooltipRef.value?.offsetHeight || TOOLTIP_ESTIMATED_HEIGHT
  const tooltipWidth = tooltipRef.value?.offsetWidth || 96
  const placeBelow = pointY - tooltipHeight - TOOLTIP_POINT_GAP < TOOLTIP_EDGE_GAP
  tooltipPlacement.value = placeBelow ? 'below' : 'above'

  const rawY = placeBelow
    ? pointY + TOOLTIP_POINT_GAP
    : pointY - TOOLTIP_POINT_GAP
  const halfWidth = tooltipWidth / 2

  tooltipPos.value = {
    x: clamp(
      pointX,
      halfWidth + TOOLTIP_EDGE_GAP,
      containerRect.width - halfWidth - TOOLTIP_EDGE_GAP,
    ),
    y: clamp(
      rawY,
      TOOLTIP_EDGE_GAP + (placeBelow ? 0 : tooltipHeight),
      containerRect.height - TOOLTIP_EDGE_GAP - (placeBelow ? tooltipHeight : 0),
    ),
  }

  if (!tooltipRef.value) {
    nextTick(() => updateTooltipPosition(index))
  }
}

function onMouseMove(event) {
  if (!hasData.value) return

  const svg = containerRef.value?.querySelector('.chart-svg')
  if (!svg) return

  const rect = svg.getBoundingClientRect()
  const scaleX = props.width / rect.width
  const relativeX = (event.clientX - rect.left) * scaleX

  let nearest = 0
  let minDistance = Infinity
  points.value.forEach((point, index) => {
    const distance = Math.abs(point.x - relativeX)
    if (distance < minDistance) {
      minDistance = distance
      nearest = index
    }
  })

  hoveredIndex.value = nearest
  updateTooltipPosition(nearest)
}
</script>

<style scoped>
.line-chart {
  @apply relative w-full;
}

.chart-svg {
  @apply w-full;
}

.chart-tooltip {
  @apply pointer-events-none absolute z-10 -translate-x-1/2
    rounded-md border border-panel-border bg-panel-surface px-2 py-1 text-center shadow-md;
}

.chart-tooltip--above {
  @apply -translate-y-full;
}

.chart-tooltip--below {
  @apply translate-y-0;
}

.chart-tooltip-value {
  @apply block text-sm font-semibold text-[var(--text-primary)];
}

.chart-tooltip-label {
  @apply block text-[10px] text-[var(--text-secondary)];
}

.grid-line {
  stroke: rgb(var(--panel-border-rgb));
  stroke-width: 1;
  opacity: 0.5;
}

.chart-line {
  fill: none;
  stroke: rgb(var(--accent-rgb));
  stroke-width: 2;
  stroke-linejoin: round;
  stroke-linecap: round;
}

.chart-line-animate {
  stroke-dasharray: 1200;
  stroke-dashoffset: 1200;
  animation: chart-draw 1.4s cubic-bezier(0.22, 1, 0.36, 1) forwards;
}

@keyframes chart-draw {
  to {
    stroke-dashoffset: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .chart-line-animate {
    animation: none;
    stroke-dasharray: none;
    stroke-dashoffset: 0;
  }
}

.chart-area {
  fill: rgb(var(--accent-rgb));
  opacity: 0.12;
}

.chart-dot {
  fill: rgb(var(--accent-rgb));
  cursor: pointer;
}

.chart-dot-active {
  stroke: rgb(var(--accent-rgb));
  stroke-width: 2;
  fill: var(--panel-surface, #fff);
}

.axis-label {
  fill: var(--text-secondary);
  font-size: 10px;
  font-family: ui-monospace, monospace;
}
</style>
