<template>
  <div
    ref="containerRef"
    class="bar-line-chart"
    :class="{ 'bar-line-chart--compact': compact, 'bar-line-chart--themed': themed }"
    :style="chartStyle"
    @mousemove="onPointerMove"
    @mouseleave="clearHover"
    @touchstart.passive="onPointerMove"
    @touchmove.passive="onPointerMove"
  >
    <div v-if="themed" class="bar-line-chart-surface" aria-hidden="true" />

    <Teleport to="body">
      <div
        v-if="hoveredPoint && !compact"
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
    </Teleport>

    <svg :viewBox="`0 0 ${width} ${chartHeight}`" class="chart-svg" role="img">
      <g v-if="hasData">
        <line
          :x1="padding.left"
          :x2="width - padding.right"
          :y1="baseY"
          :y2="baseY"
          class="axis-line"
        />
        <line
          :x1="padding.left"
          :x2="padding.left"
          :y1="padding.top"
          :y2="baseY"
          class="axis-line"
        />

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

        <rect
          v-for="(bar, i) in bars"
          :key="`bar-${i}`"
          :x="bar.x"
          :y="bar.y"
          :width="bar.width"
          :height="bar.height"
          class="chart-bar"
          :class="[barTrendClass(i), { 'chart-bar-animate': animate }]"
          :style="barStyle(i)"
          rx="1"
          @mouseenter="setHover(i)"
        />

        <polyline
          v-if="lineVisible"
          :key="lineRenderKey"
          :points="linePoints"
          pathLength="1"
          class="chart-line"
          :class="lineClass"
          vector-effect="non-scaling-stroke"
          @animationend="onLineAnimationEnd"
        />

        <circle
          v-if="lastPoint && endDotVisible"
          :cx="lastPoint.x"
          :cy="lastPoint.y"
          r="3.5"
          class="chart-end-dot"
        />

        <circle
          v-for="(pt, i) in points"
          v-show="!compact"
          :key="`dot-${i}`"
          :cx="pt.x"
          :cy="pt.y"
          :r="hoveredIndex === i ? 4.5 : 0"
          class="chart-dot"
          :class="{ 'chart-dot-active': hoveredIndex === i }"
          @mouseenter="setHover(i)"
        />

        <text
          v-for="(label, i) in xLabels"
          :key="`xlabel-${i}`"
          :x="label.x"
          :y="chartHeight - 6"
          text-anchor="middle"
          class="axis-label"
        >
          {{ label.text }}
        </text>
      </g>

      <text
        v-else
        :x="width / 2"
        :y="chartHeight / 2"
        text-anchor="middle"
        class="axis-label"
      >
        {{ emptyLabel }}
      </text>
    </svg>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

const props = defineProps({
  series: {
    type: Array,
    default: () => [],
  },
  width: { type: Number, default: 640 },
  height: { type: Number, default: null },
  animate: { type: Boolean, default: true },
  compact: { type: Boolean, default: false },
  themed: { type: Boolean, default: true },
  animationBaseDelay: { type: Number, default: 0 },
  emptyLabel: { type: String, default: 'Недостаточно данных для графика' },
})

const BAR_STAGGER_MS = 22
const LINE_AFTER_BARS_MS = 80

const chartHeight = computed(() => props.height ?? (props.compact ? 44 : 280))

const TOOLTIP_EDGE_GAP = 8
const TOOLTIP_POINT_GAP = 14
const TOOLTIP_ESTIMATED_HEIGHT = 52

const padding = computed(() =>
  props.compact
    ? { top: 6, right: 4, bottom: 4, left: 4 }
    : { top: 48, right: 16, bottom: 32, left: 44 },
)

const containerRef = ref(null)
const tooltipRef = ref(null)
const hoveredIndex = ref(null)
const tooltipPos = ref({ x: 0, y: 0 })
const tooltipPlacement = ref('above')
const lineAnimationDone = ref(!props.animate)
const lineVisible = ref(true)
const lineRenderKey = ref(0)
let lineFallbackTimer = null
let measurePass = false

const cleanSeries = computed(() => props.series.filter((p) => p.value != null))
const hasData = computed(() => cleanSeries.value.length >= 2)
const barCount = computed(() => cleanSeries.value.length)

const chartStyle = computed(() => ({
  '--bar-count': barCount.value,
  '--anim-base': `${props.animationBaseDelay}ms`,
}))

const lineClass = computed(() => {
  if (!props.animate || lineAnimationDone.value) return 'chart-line-done'
  return 'chart-line-animate'
})

const endDotVisible = computed(() => !props.animate || lineAnimationDone.value)

const bounds = computed(() => {
  const values = cleanSeries.value.map((p) => p.value)
  const min = Math.min(...values)
  const max = Math.max(...values)
  if (min === max) {
    return { min: min - 1, max: max + 1 }
  }
  // Запас сверху, чтобы пик и тултип не прилипали к краю на узких экранах.
  const span = max - min
  const padTop = Math.max(span * 0.28, 6)
  const padBottom = Math.max(span * 0.1, 1)
  return { min: Math.max(0, min - padBottom), max: max + padTop }
})

const plotWidth = computed(() => props.width - padding.value.left - padding.value.right)
const plotHeight = computed(() => chartHeight.value - padding.value.top - padding.value.bottom)
const baseY = computed(() => padding.value.top + plotHeight.value)

function xCenterFor(index, total) {
  const slot = plotWidth.value / total
  return padding.value.left + index * slot + slot / 2
}

function yFor(value) {
  const { min, max } = bounds.value
  const ratio = (value - min) / (max - min || 1)
  return padding.value.top + (1 - ratio) * plotHeight.value
}

function barTrend(index) {
  if (index === 0) return 'base'
  const prev = cleanSeries.value[index - 1]?.value
  const curr = cleanSeries.value[index]?.value
  if (prev == null || curr == null) return 'base'
  if (curr > prev) return 'up'
  if (curr < prev) return 'down'
  return 'flat'
}

function barTrendClass(index) {
  return `chart-bar--${barTrend(index)}`
}

const points = computed(() =>
  cleanSeries.value.map((p, i) => ({
    x: xCenterFor(i, cleanSeries.value.length),
    y: yFor(p.value),
    value: p.value,
    label: p.label,
    fullLabel: p.fullLabel || p.label,
    trend: barTrend(i),
  })),
)

const bars = computed(() => {
  const total = cleanSeries.value.length
  const slot = plotWidth.value / total
  const barWidth = Math.max(props.compact ? 2 : 3, slot * (props.compact ? 0.72 : 0.58))
  return cleanSeries.value.map((p, i) => {
    const y = yFor(p.value)
    return {
      x: xCenterFor(i, total) - barWidth / 2,
      y,
      width: barWidth,
      height: Math.max(0, baseY.value - y),
    }
  })
})

const lastPoint = computed(() => points.value[points.value.length - 1] || null)

const hoveredPoint = computed(() => {
  if (hoveredIndex.value == null) return null
  return points.value[hoveredIndex.value] || null
})

const tooltipStyle = computed(() => ({
  left: `${tooltipPos.value.x}px`,
  top: `${tooltipPos.value.y}px`,
}))

const linePoints = computed(() => points.value.map((p) => `${p.x},${p.y}`).join(' '))

const yTicks = computed(() => {
  if (props.compact) return []
  const { min, max } = bounds.value
  const count = 4
  return Array.from({ length: count + 1 }, (_, i) => {
    const value = min + ((max - min) * i) / count
    return { y: yFor(value), label: formatTick(value) }
  })
})

const xLabels = computed(() => {
  if (props.compact) return []
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

function barStyle(index) {
  return {
    animationDelay: `${props.animationBaseDelay + index * BAR_STAGGER_MS}ms`,
  }
}

function onLineAnimationEnd() {
  if (lineFallbackTimer) {
    clearTimeout(lineFallbackTimer)
    lineFallbackTimer = null
  }
  lineAnimationDone.value = true
}

function scheduleLineFallback() {
  if (lineFallbackTimer) clearTimeout(lineFallbackTimer)
  if (!props.animate) return
  const delay = props.animationBaseDelay + barCount.value * BAR_STAGGER_MS + LINE_AFTER_BARS_MS + 1200
  lineFallbackTimer = setTimeout(() => {
    lineAnimationDone.value = true
    lineFallbackTimer = null
  }, delay)
}

async function restartLineAnimation() {
  if (lineFallbackTimer) {
    clearTimeout(lineFallbackTimer)
    lineFallbackTimer = null
  }
  lineAnimationDone.value = !props.animate
  lineVisible.value = false
  lineRenderKey.value += 1
  await nextTick()
  lineVisible.value = true
  scheduleLineFallback()
}

watch(
  () => linePoints.value,
  (next, prev) => {
    if (prev == null || prev === next) return
    if (props.animate) restartLineAnimation()
  },
)

watch(
  () => props.animate,
  (value) => {
    lineAnimationDone.value = !value
    if (value) scheduleLineFallback()
  },
)

onMounted(() => {
  if (props.animate) scheduleLineFallback()
})

onUnmounted(() => {
  if (lineFallbackTimer) clearTimeout(lineFallbackTimer)
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
  measurePass = false
  updateTooltipPosition(index)
}

function clearHover() {
  hoveredIndex.value = null
  tooltipPlacement.value = 'above'
  measurePass = false
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

function eventClientX(event) {
  if (event.touches?.[0]) return event.touches[0].clientX
  if (event.changedTouches?.[0]) return event.changedTouches[0].clientX
  return event.clientX
}

function pickNearestIndex(clientX) {
  const svg = containerRef.value?.querySelector('.chart-svg')
  if (!svg || !points.value.length) return null

  const rect = svg.getBoundingClientRect()
  const scaleX = props.width / rect.width
  const relativeX = (clientX - rect.left) * scaleX

  let nearest = 0
  let minDistance = Infinity
  points.value.forEach((point, index) => {
    const distance = Math.abs(point.x - relativeX)
    if (distance < minDistance) {
      minDistance = distance
      nearest = index
    }
  })
  return nearest
}

function updateTooltipPosition(index) {
  const point = points.value[index]
  if (!point) return

  const svg = containerRef.value?.querySelector('.chart-svg')
  if (!svg) return

  const svgRect = svg.getBoundingClientRect()
  const scaleX = svgRect.width / props.width
  const scaleY = svgRect.height / chartHeight.value

  // Viewport-координаты: тултип в Teleport не клипается overflow графика.
  const pointX = svgRect.left + point.x * scaleX
  const pointY = svgRect.top + point.y * scaleY

  const tooltipHeight =
    tooltipRef.value?.offsetHeight || TOOLTIP_ESTIMATED_HEIGHT
  const tooltipWidth = tooltipRef.value?.offsetWidth || 110
  const placeBelow = pointY - tooltipHeight - TOOLTIP_POINT_GAP < TOOLTIP_EDGE_GAP
  tooltipPlacement.value = placeBelow ? 'below' : 'above'

  const rawY = placeBelow
    ? pointY + TOOLTIP_POINT_GAP
    : pointY - TOOLTIP_POINT_GAP
  const halfWidth = tooltipWidth / 2
  const viewportWidth = window.innerWidth
  const viewportHeight = window.innerHeight

  tooltipPos.value = {
    x: clamp(pointX, halfWidth + TOOLTIP_EDGE_GAP, viewportWidth - halfWidth - TOOLTIP_EDGE_GAP),
    y: clamp(
      rawY,
      TOOLTIP_EDGE_GAP + (placeBelow ? 0 : tooltipHeight),
      viewportHeight - TOOLTIP_EDGE_GAP - (placeBelow ? tooltipHeight : 0),
    ),
  }

  if (!props.compact && !measurePass) {
    measurePass = true
    nextTick(() => updateTooltipPosition(index))
  }
}

function onPointerMove(event) {
  if (!hasData.value || props.compact) return
  const clientX = eventClientX(event)
  if (clientX == null) return
  const nearest = pickNearestIndex(clientX)
  if (nearest == null) return
  hoveredIndex.value = nearest
  measurePass = false
  updateTooltipPosition(nearest)
}
</script>

<style scoped>
.bar-line-chart {
  @apply relative w-full overflow-visible rounded-panel;
}

.bar-line-chart-surface {
  @apply pointer-events-none absolute inset-0 overflow-hidden rounded-panel;
  background-color: rgb(var(--panel-bg-rgb));
  background-image:
    linear-gradient(rgb(var(--panel-border-rgb) / 0.45) 1px, transparent 1px),
    linear-gradient(90deg, rgb(var(--panel-border-rgb) / 0.45) 1px, transparent 1px);
  background-size: 10px 10px;
  border: 1px solid rgb(var(--panel-border-rgb));
  box-shadow: inset 0 0 28px rgb(var(--accent-rgb) / 0.04);
}

.bar-line-chart--compact {
  @apply rounded-md;
  min-height: 2.5rem;
}

.bar-line-chart--compact .bar-line-chart-surface {
  @apply rounded-md;
  background-size: 6px 6px;
}

.chart-svg {
  @apply relative z-[1] block w-full;
}

.chart-tooltip {
  position: fixed;
  z-index: 80;
  pointer-events: none;
  transform: translateX(-50%);
  @apply rounded-md border border-panel-border bg-panel-surface px-2.5 py-1.5 text-center shadow-panel;
}

.chart-tooltip--above {
  transform: translate(-50%, -100%);
}

.chart-tooltip--below {
  transform: translate(-50%, 0);
}

.chart-tooltip-value {
  @apply block text-sm font-semibold text-[var(--text-primary)];
}

.chart-tooltip-label {
  @apply block text-[10px] text-[var(--text-secondary)];
}

.axis-line {
  stroke: rgb(var(--panel-border-rgb));
  stroke-width: 1;
}

.grid-line {
  stroke: rgb(var(--panel-border-rgb) / 0.55);
  stroke-width: 1;
}

.chart-bar--base {
  fill: rgb(var(--accent-rgb) / 0.75);
}

.chart-bar--up {
  fill: rgb(var(--accent-rgb) / 0.92);
}

.chart-bar--down {
  fill: rgb(var(--danger-rgb) / 0.88);
}

.chart-bar--flat {
  fill: rgb(var(--accent-rgb) / 0.92);
}

.chart-bar-animate {
  transform-box: fill-box;
  transform-origin: center bottom;
  transform: scaleY(0);
  animation: bar-rise 0.275s cubic-bezier(0.22, 1.15, 0.36, 1) forwards;
}

.chart-line {
  fill: none;
  stroke: rgb(var(--accent-rgb) / 0.9);
  stroke-width: 1.5;
  stroke-linejoin: round;
  stroke-linecap: round;
}

.chart-line-animate {
  opacity: 0;
  stroke-dasharray: 1;
  stroke-dashoffset: 1;
  animation:
    line-fade-in 0.01s linear forwards,
    chart-draw 1.1s cubic-bezier(0.22, 1, 0.36, 1) forwards;
  animation-delay:
    calc(var(--anim-base, 0ms) + var(--bar-count, 8) * 22ms + 80ms),
    calc(var(--anim-base, 0ms) + var(--bar-count, 8) * 22ms + 80ms);
}

.chart-line-done {
  opacity: 1;
  stroke-dasharray: none;
  stroke-dashoffset: 0;
}

.chart-end-dot {
  fill: rgb(var(--accent-rgb));
  animation: dot-fade-in 0.25s ease forwards;
}

.chart-dot {
  fill: rgb(var(--accent-rgb));
  cursor: pointer;
  transition: r 0.15s ease;
}

.chart-dot-active {
  stroke: rgb(var(--accent-rgb));
  stroke-width: 2;
  fill: rgb(var(--panel-surface-rgb));
}

.axis-label {
  fill: var(--text-secondary);
  font-size: 10px;
  font-family: ui-monospace, monospace;
}

@keyframes bar-rise {
  from {
    transform: scaleY(0);
    opacity: 0.4;
  }
  to {
    transform: scaleY(1);
    opacity: 1;
  }
}

@keyframes line-fade-in {
  to {
    opacity: 1;
  }
}

@keyframes chart-draw {
  to {
    stroke-dashoffset: 0;
  }
}

@keyframes dot-fade-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  .chart-bar-animate {
    animation: none;
    transform: scaleY(1);
    opacity: 1;
  }

  .chart-line-animate {
    animation: none;
    opacity: 1;
    stroke-dasharray: none;
    stroke-dashoffset: 0;
  }

  .chart-end-dot {
    animation: none;
    opacity: 1;
  }
}
</style>
