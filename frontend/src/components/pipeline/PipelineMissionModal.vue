<template>
  <Teleport to="body">
    <Transition name="mission">
      <div
        v-if="store.open"
        class="mission-backdrop"
        role="presentation"
        @click.self="store.close()"
      >
        <div class="mission-panel" role="dialog" aria-modal="true" aria-labelledby="mission-title">
          <div class="mission-scan" aria-hidden="true" />
          <div class="mission-grid" aria-hidden="true" />

          <header class="mission-header">
            <div>
              <p class="mission-kicker">Pipeline Mission Control</p>
              <h2 id="mission-title" class="mission-title">{{ store.title }}</h2>
              <p class="mission-sub">{{ store.currentDetail || 'Ожидание данных…' }}</p>
            </div>
            <div class="mission-header-actions">
              <span class="mission-status" :class="`mission-status--${store.status}`">
                {{ statusLabel }}
              </span>
              <button type="button" class="btn-ghost btn-sm" aria-label="Закрыть" @click="store.close()">
                ✕
              </button>
            </div>
          </header>

          <div class="mission-progress">
            <div class="mission-progress-meta">
              <span>{{ store.progress }}%</span>
              <span>{{ store.events.length }} шагов</span>
            </div>
            <div class="mission-progress-track">
              <div class="mission-progress-fill" :style="{ width: `${store.progress}%` }" />
            </div>
          </div>

          <div class="mission-body">
            <section class="mission-graph" aria-label="Схема обмена данными">
              <svg viewBox="0 0 100 100" class="mission-svg" preserveAspectRatio="xMidYMid meet">
                <defs>
                  <filter id="glow">
                    <feGaussianBlur stdDeviation="1.2" result="blur" />
                    <feMerge>
                      <feMergeNode in="blur" />
                      <feMergeNode in="SourceGraphic" />
                    </feMerge>
                  </filter>
                </defs>

                <g v-for="edge in edges" :key="edge.key">
                  <line
                    :x1="edge.x1"
                    :y1="edge.y1"
                    :x2="edge.x2"
                    :y2="edge.y2"
                    class="mission-edge"
                    :class="{ 'mission-edge--live': edge.live }"
                  />
                  <circle v-if="edge.live" r="1.2" :fill="edge.color" class="mission-packet">
                    <animateMotion
                      dur="1.4s"
                      repeatCount="indefinite"
                      :path="`M ${edge.x1} ${edge.y1} L ${edge.x2} ${edge.y2}`"
                    />
                  </circle>
                </g>

                <g
                  v-for="node in graphNodes"
                  :key="node.id"
                  :transform="`translate(${node.x}, ${node.y})`"
                  class="mission-node"
                  :class="{
                    'mission-node--active': store.activeNodes.has(node.id),
                    'mission-node--pulse': pulseNode === node.id,
                  }"
                >
                  <circle r="5.5" :fill="node.color" fill-opacity="0.15" stroke="currentColor" stroke-width="0.35" />
                  <circle r="2.2" :fill="node.color" filter="url(#glow)" />
                  <text y="-7" text-anchor="middle" class="mission-node-label">{{ node.short }}</text>
                </g>
              </svg>
              <p class="mission-graph-hint">Клик по шагу справа — детали запроса и ответа</p>
            </section>

            <section class="mission-log" aria-label="Журнал шагов">
              <div v-if="store.loading && !store.events.length" class="mission-log-empty">
                Загрузка телеметрии…
              </div>
              <div v-else-if="store.error && !store.events.length" class="mission-log-empty mission-log-empty--error">
                {{ store.error }}
              </div>
              <ul v-else class="mission-events">
                <li
                  v-for="(ev, idx) in store.events"
                  :key="ev.id"
                  class="mission-event"
                  :class="[
                    `mission-event--${ev.status}`,
                    { 'mission-event--selected': selectedId === ev.id },
                  ]"
                  :style="{ '--delay': `${idx * 40}ms` }"
                  @click="selectedId = selectedId === ev.id ? null : ev.id"
                >
                  <div class="mission-event-head">
                    <span class="mission-event-dot" />
                    <div class="mission-event-main">
                      <p class="mission-event-label">{{ ev.label }}</p>
                      <p class="mission-event-meta">
                        <span v-if="ev.provider">{{ ev.provider }}</span>
                        <span v-if="ev.model"> · {{ ev.model }}</span>
                        <span v-if="ev.duration_ms"> · {{ ev.duration_ms }} ms</span>
                      </p>
                    </div>
                    <span class="mission-event-arrow">{{ flowArrow(ev) }}</span>
                  </div>

                  <Transition name="detail-expand">
                    <div v-if="selectedId === ev.id" class="mission-event-detail">
                      <div v-if="ev.request_summary" class="mission-payload">
                        <span class="mission-payload-tag">→ запрос</span>
                        <p>{{ ev.request_summary }}</p>
                      </div>
                      <div v-if="ev.response_summary" class="mission-payload mission-payload--in">
                        <span class="mission-payload-tag">← ответ</span>
                        <p>{{ ev.response_summary }}</p>
                      </div>
                      <div v-if="ev.error" class="mission-payload mission-payload--err">
                        <span class="mission-payload-tag">✕ ошибка</span>
                        <p>{{ ev.error }}</p>
                      </div>
                    </div>
                  </Transition>
                </li>
              </ul>
            </section>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { nodeMeta, usePipelineStore } from '../../stores/pipelineStore'

const store = usePipelineStore()
const selectedId = ref(null)

const LAYOUT = {
  platform: { x: 50, y: 52 },
  deepseek: { x: 22, y: 28 },
  tavily: { x: 78, y: 28 },
  openai: { x: 18, y: 78 },
  qwen: { x: 82, y: 78 },
  openrouter: { x: 50, y: 16 },
  github: { x: 30, y: 88 },
  storage: { x: 70, y: 88 },
}

const statusLabel = computed(() => {
  if (store.status === 'done') return 'Завершено'
  if (store.status === 'error') return 'Ошибка'
  return 'В процессе'
})

const pulseNode = computed(() => store.activeEdge?.to ?? null)

const graphNodes = computed(() =>
  Object.entries(LAYOUT).map(([id, pos]) => ({
    id,
    ...pos,
    ...nodeMeta(id),
  }))
)

const edges = computed(() => {
  const seen = new Set()
  const list = []
  for (const ev of store.events) {
    if (ev.direction === 'internal') continue
    const from = LAYOUT[ev.from_node] || LAYOUT.platform
    const to = LAYOUT[ev.to_node] || LAYOUT.platform
    const key = `${ev.from_node}-${ev.to_node}-${ev.id}`
    if (seen.has(key)) continue
    seen.add(key)
    list.push({
      key,
      x1: from.x,
      y1: from.y,
      x2: to.x,
      y2: to.y,
      live: store.activeEdge?.id === ev.id && ev.status === 'running',
      color: nodeMeta(ev.to_node).color,
    })
  }
  return list
})

function flowArrow(ev) {
  if (ev.direction === 'inbound') return '←'
  if (ev.direction === 'outbound') return '→'
  return '•'
}

watch(
  () => store.open,
  (isOpen) => {
    if (!isOpen) selectedId.value = null
  }
)
</script>

<style scoped>
.mission-backdrop {
  @apply fixed inset-0 z-[100] flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm;
}

.mission-panel {
  @apply relative flex max-h-[min(92vh,880px)] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-accent/25 bg-[#0a0f14] shadow-[0_0_60px_rgba(45,212,191,0.15)];
}

.mission-grid {
  @apply pointer-events-none absolute inset-0 opacity-30;
  background-image:
    linear-gradient(rgba(45, 212, 191, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(45, 212, 191, 0.08) 1px, transparent 1px);
  background-size: 24px 24px;
  animation: grid-drift 20s linear infinite;
}

.mission-scan {
  @apply pointer-events-none absolute inset-x-0 top-0 h-24 opacity-40;
  background: linear-gradient(180deg, rgba(45, 212, 191, 0.25), transparent);
  animation: scan 3.5s ease-in-out infinite;
}

.mission-header {
  @apply relative z-10 flex items-start justify-between gap-4 border-b border-white/10 px-5 py-4 md:px-6;
}

.mission-kicker {
  @apply font-mono text-[10px] uppercase tracking-[0.2em] text-accent/80;
}

.mission-title {
  @apply mt-1 text-lg font-semibold text-white md:text-xl;
}

.mission-sub {
  @apply mt-1 text-sm text-slate-400;
}

.mission-header-actions {
  @apply flex shrink-0 items-center gap-2;
}

.mission-status {
  @apply rounded-full border px-2.5 py-0.5 font-mono text-xs;
}

.mission-status--running {
  @apply border-accent/40 text-accent;
}

.mission-status--done {
  @apply border-emerald-500/40 text-emerald-400;
}

.mission-status--error {
  @apply border-red-500/40 text-red-400;
}

.mission-progress {
  @apply relative z-10 border-b border-white/10 px-5 py-3 md:px-6;
}

.mission-progress-meta {
  @apply mb-1.5 flex justify-between font-mono text-xs text-slate-400;
}

.mission-progress-track {
  @apply h-1.5 overflow-hidden rounded-full bg-white/10;
}

.mission-progress-fill {
  @apply h-full rounded-full bg-gradient-to-r from-accent/60 to-accent transition-[width] duration-500;
  box-shadow: 0 0 12px rgba(45, 212, 191, 0.5);
}

.mission-body {
  @apply relative z-10 grid min-h-0 flex-1 grid-cols-1 gap-0 lg:grid-cols-[1.1fr_0.9fr];
}

.mission-graph {
  @apply relative border-b border-white/10 p-4 lg:border-b-0 lg:border-r lg:p-5;
  min-height: 280px;
}

.mission-svg {
  @apply h-full w-full min-h-[240px];
  color: rgba(148, 163, 184, 0.6);
}

.mission-edge {
  stroke: rgba(148, 163, 184, 0.25);
  stroke-width: 0.35;
  stroke-dasharray: 1.5 1.5;
}

.mission-edge--live {
  stroke: rgba(45, 212, 191, 0.85);
  stroke-width: 0.5;
  animation: dash-flow 1s linear infinite;
}

.mission-node-label {
  @apply fill-slate-400 font-mono text-[3px];
}

.mission-node--active {
  color: rgba(45, 212, 191, 0.9);
}

.mission-node--pulse circle:first-child {
  animation: node-pulse 1.2s ease-in-out infinite;
}

.mission-graph-hint {
  @apply mt-2 text-center text-xs text-slate-500;
}

.mission-log {
  @apply min-h-0 overflow-y-auto p-4 md:p-5;
  max-height: min(52vh, 420px);
}

.mission-log-empty {
  @apply py-12 text-center text-sm text-slate-500;
}

.mission-log-empty--error {
  @apply text-red-400;
}

.mission-events {
  @apply space-y-2;
}

.mission-event {
  @apply cursor-pointer rounded-lg border border-white/5 bg-white/[0.03] px-3 py-2.5 transition-all duration-300;
  animation: event-in 0.4s ease backwards;
  animation-delay: var(--delay, 0ms);
}

.mission-event:hover {
  @apply border-accent/25 bg-white/[0.06];
}

.mission-event--selected {
  @apply border-accent/40 bg-accent/5;
}

.mission-event--running {
  @apply border-accent/30 shadow-[0_0_20px_rgba(45,212,191,0.08)];
}

.mission-event--failed {
  @apply border-red-500/30;
}

.mission-event--skipped {
  @apply opacity-70;
}

.mission-event-head {
  @apply flex items-start gap-2;
}

.mission-event-dot {
  @apply mt-1.5 h-2 w-2 shrink-0 rounded-full bg-slate-500;
}

.mission-event--running .mission-event-dot {
  @apply bg-accent animate-pulse;
}

.mission-event--success .mission-event-dot {
  @apply bg-emerald-400;
}

.mission-event--failed .mission-event-dot {
  @apply bg-red-400;
}

.mission-event-main {
  @apply min-w-0 flex-1;
}

.mission-event-label {
  @apply text-sm font-medium text-slate-100;
}

.mission-event-meta {
  @apply mt-0.5 font-mono text-[11px] text-slate-500;
}

.mission-event-arrow {
  @apply font-mono text-accent/80;
}

.mission-event-detail {
  @apply mt-2 space-y-2 border-t border-white/10 pt-2;
}

.mission-payload {
  @apply rounded-md bg-black/30 p-2 text-xs leading-relaxed text-slate-300;
}

.mission-payload--in {
  @apply border-l-2 border-emerald-500/50;
}

.mission-payload--err {
  @apply border-l-2 border-red-500/50 text-red-300;
}

.mission-payload-tag {
  @apply mb-1 block font-mono text-[10px] uppercase tracking-wider text-slate-500;
}

.detail-expand-enter-active,
.detail-expand-leave-active {
  transition: all 0.25s ease;
}

.detail-expand-enter-from,
.detail-expand-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

.mission-enter-active,
.mission-leave-active {
  transition: opacity 0.3s ease;
}

.mission-enter-active .mission-panel,
.mission-leave-active .mission-panel {
  transition: transform 0.35s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.3s ease;
}

.mission-enter-from,
.mission-leave-to {
  opacity: 0;
}

.mission-enter-from .mission-panel,
.mission-leave-to .mission-panel {
  opacity: 0;
  transform: scale(0.96) translateY(12px);
}

@keyframes grid-drift {
  from { transform: translateY(0); }
  to { transform: translateY(24px); }
}

@keyframes scan {
  0%, 100% { opacity: 0.15; transform: translateY(-100%); }
  50% { opacity: 0.45; transform: translateY(200%); }
}

@keyframes dash-flow {
  to { stroke-dashoffset: -3; }
}

@keyframes node-pulse {
  0%, 100% { r: 5.5; opacity: 0.6; }
  50% { r: 7; opacity: 1; }
}

@keyframes event-in {
  from { opacity: 0; transform: translateX(8px); }
  to { opacity: 1; transform: translateX(0); }
}
</style>
