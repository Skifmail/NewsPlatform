<template>
  <div class="overview">
    <section class="hero panel-card">
      <div class="hero-glow hero-glow-a" aria-hidden="true" />
      <div class="hero-glow hero-glow-b" aria-hidden="true" />
      <div class="hero-content">
        <div>
          <p class="hero-greeting">{{ greeting }}</p>
          <h1 class="hero-title">Командный центр</h1>
          <p class="hero-sub">{{ clockLabel }}</p>
        </div>
        <div class="hero-status">
          <span class="status-pill" :class="wsConnected ? 'status-live' : 'status-off'">
            <span class="status-dot" />
            WebSocket
          </span>
          <span class="status-pill" :class="platformStatus.schedule_fetch_enabled ? 'status-on' : 'status-off'">
            Парсинг {{ platformStatus.schedule_fetch_enabled ? 'вкл' : 'выкл' }}
          </span>
          <span class="status-pill" :class="platformStatus.schedule_ai_enabled ? 'status-on' : 'status-off'">
            AI {{ platformStatus.schedule_ai_enabled ? 'вкл' : 'выкл' }}
          </span>
          <span class="status-pill" :class="platformStatus.schedule_publish_enabled ? 'status-on' : 'status-off'">
            Публикация {{ platformStatus.schedule_publish_enabled ? 'вкл' : 'выкл' }}
          </span>
        </div>
      </div>
    </section>

    <p v-if="loading && !data" class="empty-state">Загрузка обзора…</p>
    <p v-else-if="error" class="empty-state text-danger">{{ error }}</p>

    <template v-else-if="data">
      <div class="kpi-row">
        <KpiCard
          label="Подписчиков"
          :value="data.kpis.subscribers_total"
          :delta="data.kpis.subscribers_delta_today"
          accent
          to="/analytics"
          :delay="0"
        />
        <KpiCard
          label="Публикаций сегодня"
          :value="data.kpis.publications_today_success"
          :sub="failedTodaySub"
          to="/history"
          :delay="80"
        />
        <KpiCard
          label="Просмотры"
          :value="data.kpis.total_views || 0"
          format="compact"
          to="/analytics"
          :delay="160"
        />
        <KpiCard
          label="На модерации"
          :value="data.kpis.queue_pending"
          to="/queue"
          :delay="240"
        />
        <KpiCard
          label="Активные задачи"
          :value="data.kpis.active_jobs"
          to="/jobs"
          :delay="320"
        />
      </div>

      <div class="main-grid">
        <section class="chart-section panel-card">
          <header class="chart-head">
            <h2 class="chart-title">Рост аудитории</h2>
            <div class="period-tabs">
              <button
                v-for="p in periods"
                :key="p.value"
                type="button"
                class="period-tab"
                :class="{ 'period-tab-active': trendPeriod === p.value }"
                @click="setPeriod(p.value)"
              >
                {{ p.label }}
              </button>
            </div>
          </header>
          <BarLineChart
            :series="chartSeries"
            :key="trendPeriod"
            :animate="true"
            class="overview-chart"
          />
        </section>
        <AttentionPanel :items="data.attention" />
      </div>

      <div class="secondary-grid">
        <LiveActivityFeed :items="activityItems" :connected="wsConnected" />
        <TopChannels :items="data.top_channels" />
      </div>

      <div class="secondary-grid">
        <RecentPublications :items="data.recent_publications" />
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import BarLineChart from '../components/analytics/BarLineChart.vue'
import AttentionPanel from '../components/overview/AttentionPanel.vue'
import KpiCard from '../components/overview/KpiCard.vue'
import LiveActivityFeed from '../components/overview/LiveActivityFeed.vue'
import RecentPublications from '../components/overview/RecentPublications.vue'
import TopChannels from '../components/overview/TopChannels.vue'
import { overviewApi } from '../api/index.js'
import { useActivityStore } from '../stores/activityStore'
import { usePostsStore } from '../stores/postsStore'

const activityStore = useActivityStore()
const postsStore = usePostsStore()
const { wsConnected } = storeToRefs(postsStore)

const data = ref(null)
const loading = ref(false)
const error = ref(null)
const trendPeriod = ref('week')
const clockLabel = ref('')
let refreshTimer = null
let clockTimer = null
let activityRefreshTimer = null

const periods = [
  { value: 'today', label: 'Сегодня' },
  { value: 'week', label: 'Неделя' },
  { value: 'month', label: 'Месяц' },
]

const platformStatus = computed(
  () =>
    data.value?.platform_status || {
      schedule_fetch_enabled: false,
      schedule_ai_enabled: false,
      schedule_publish_enabled: false,
    },
)

const activityItems = computed(() => activityStore.items)

const failedTodaySub = computed(() => {
  const failed = data.value?.kpis?.publications_today_failed
  if (!failed) return ''
  return `${failed} с ошибкой`
})

const chartSeries = computed(() =>
  (data.value?.trend || []).map((point) => ({
    value: point.value,
    label: point.label,
    fullLabel: new Date(point.captured_at).toLocaleString('ru-RU'),
  })),
)

const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 6) return 'Доброй ночи'
  if (hour < 12) return 'Доброе утро'
  if (hour < 18) return 'Добрый день'
  return 'Добрый вечер'
})

function updateClock() {
  clockLabel.value = new Date().toLocaleString('ru-RU', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    hour: '2-digit',
    minute: '2-digit',
  })
}

async function load() {
  loading.value = true
  error.value = null
  try {
    const { data: payload } = await overviewApi.get({ trend_period: trendPeriod.value })
    data.value = payload
  } catch (e) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}

function setPeriod(period) {
  if (trendPeriod.value === period) return
  trendPeriod.value = period
  load()
}

watch(
  () => activityStore.items.map((item) => `${item.id}:${item.phase}`).join('|'),
  () => {
    if (activityRefreshTimer) clearTimeout(activityRefreshTimer)
    activityRefreshTimer = setTimeout(() => {
      if (!loading.value) load()
    }, 2000)
  },
)

onMounted(() => {
  updateClock()
  clockTimer = setInterval(updateClock, 30_000)
  load()
  refreshTimer = setInterval(load, 30_000)
  activityStore.syncActiveJobs()
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
  if (clockTimer) clearInterval(clockTimer)
  if (activityRefreshTimer) clearTimeout(activityRefreshTimer)
})
</script>

<style scoped>
.overview {
  @apply flex flex-col gap-6;
}

.hero {
  @apply relative overflow-hidden p-6;
}

.hero-glow {
  @apply pointer-events-none absolute rounded-full blur-3xl;
  animation: hero-drift 8s ease-in-out infinite alternate;
}

.hero-glow-a {
  @apply -left-10 -top-10 h-40 w-40;
  background: rgb(var(--accent-rgb) / 0.18);
}

.hero-glow-b {
  @apply -bottom-12 right-0 h-48 w-48;
  background: rgb(var(--info-rgb) / 0.12);
  animation-delay: -3s;
}

.hero-content {
  @apply relative z-10 flex flex-wrap items-start justify-between gap-4;
}

.hero-greeting {
  @apply text-xs font-semibold uppercase tracking-widest text-accent;
}

.hero-title {
  @apply mt-1 text-2xl font-semibold tracking-tight text-[var(--text-primary)];
}

.hero-sub {
  @apply mt-1 text-sm capitalize text-[var(--text-secondary)];
}

.hero-status {
  @apply flex flex-wrap gap-2;
}

.status-pill {
  @apply inline-flex items-center gap-1.5 rounded-pill border px-3 py-1.5 text-xs font-medium;
}

.status-live,
.status-on {
  @apply border-accent/35 bg-accent-muted text-accent;
}

.status-off {
  @apply border-panel-border bg-panel-bg text-[var(--text-secondary)];
}

.status-dot {
  @apply h-1.5 w-1.5 rounded-full bg-current;
}

.status-live .status-dot {
  animation: live-pulse 1.6s ease-in-out infinite;
}

.kpi-row {
  @apply grid gap-4 grid-cols-2 md:grid-cols-3 xl:grid-cols-5;
}

.main-grid {
  @apply grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)];
}

.chart-section {
  @apply p-4;
}

.chart-head {
  @apply mb-4 flex flex-wrap items-center justify-between gap-3;
}

.chart-title {
  @apply text-sm font-semibold text-[var(--text-primary)];
}

.period-tabs {
  @apply flex flex-wrap gap-1 rounded-pill border border-panel-border bg-panel-bg p-1;
}

.period-tab {
  @apply rounded-pill px-3 py-1 text-xs font-medium text-[var(--text-secondary)]
    transition-colors hover:text-[var(--text-primary)];
}

.period-tab-active {
  @apply bg-accent text-white shadow-glow;
}

.overview-chart {
  @apply min-h-[260px];
}

@media (max-width: 640px) {
  .overview-chart {
    min-height: 240px;
  }

  .chart-section {
    @apply overflow-visible;
  }
}

.secondary-grid {
  @apply grid gap-4 md:grid-cols-2;
}

@keyframes hero-drift {
  from {
    transform: translate(0, 0) scale(1);
  }
  to {
    transform: translate(12px, 8px) scale(1.08);
  }
}

@keyframes live-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
}

@media (prefers-reduced-motion: reduce) {
  .hero-glow {
    animation: none;
  }

  .status-live .status-dot {
    animation: none;
  }
}
</style>
