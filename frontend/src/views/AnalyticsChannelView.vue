<template>
  <div>
    <PageHeader
      :title="overview ? overview.channel.name : 'Канал'"
      :subtitle="overview ? `${platformLabel(overview.channel.platform)} · ${overview.channel.topic}` : ''"
    >
      <template #actions>
        <button type="button" class="btn-ghost btn-sm" @click="goBack">← К списку</button>
        <button
          type="button"
          class="btn-secondary btn-sm"
          :disabled="refreshing"
          @click="refresh"
        >
          {{ refreshing ? 'Обновление…' : 'Обновить' }}
        </button>
      </template>
    </PageHeader>

    <p v-if="loading && !overview" class="empty-state">Загрузка…</p>
    <p v-else-if="error" class="empty-state text-danger">{{ error }}</p>

    <template v-else-if="overview">
      <div class="kpi-grid">
        <div class="kpi-card panel-card">
          <span class="kpi-label">Подписчики</span>
          <span class="kpi-value text-accent">{{ formatNum(overview.subscribers) }}</span>
          <span
            v-if="overview.subscribers_today != null"
            :class="deltaClass(overview.subscribers_today)"
            class="kpi-delta"
          >
            {{ formatDelta(overview.subscribers_today) }} сегодня
          </span>
          <span
            v-if="overview.subscribers_week != null"
            :class="deltaClass(overview.subscribers_week)"
            class="kpi-delta"
          >
            {{ formatDelta(overview.subscribers_week) }} за неделю
          </span>
        </div>
        <div class="kpi-card panel-card">
          <span class="kpi-label">Публикаций</span>
          <span class="kpi-value">{{ formatNum(overview.publications_total) }}</span>
          <span class="kpi-delta text-[var(--text-secondary)]">через платформу</span>
        </div>
        <div class="kpi-card panel-card">
          <span class="kpi-label">Просмотры за 24ч</span>
          <span class="kpi-value">{{ formatNum(overview.views_24h) }}</span>
          <span class="kpi-delta text-[var(--text-secondary)]">
            <template v-if="overview.views_48h != null || overview.views_72h != null">
              48ч: {{ formatNum(overview.views_48h) }}
              · 72ч: {{ formatNum(overview.views_72h) }}
            </template>
            <template v-else>новые просмотры по замерам</template>
          </span>
        </div>
        <div class="kpi-card panel-card">
          <span class="kpi-label">ER за 24ч</span>
          <span class="kpi-value">{{ overview.engagement_rate != null ? `${overview.engagement_rate}%` : '—' }}</span>
          <span class="kpi-delta text-[var(--text-secondary)]">просмотры 24ч / подписчики</span>
        </div>
        <div class="kpi-card panel-card">
          <span class="kpi-label">Ср. на пост</span>
          <span class="kpi-value">{{ overview.avg_views ?? '—' }}</span>
          <span class="kpi-delta text-[var(--text-secondary)]">накопленный итог</span>
          <span
            v-if="overview.total_views != null"
            class="kpi-delta text-accent"
          >
            {{ formatNum(overview.total_views) }} всего по постам
          </span>
        </div>
        <div class="kpi-card panel-card">
          <span class="kpi-label">Реклама</span>
          <span class="kpi-value">{{ overview.ad_integrations_count }}</span>
          <span class="kpi-delta text-[var(--text-secondary)]">{{ formatMoney(overview.ad_revenue_total) }}</span>
        </div>
        <div v-if="overview.avg_reach != null" class="kpi-card panel-card">
          <span class="kpi-label">Ср. охват</span>
          <span class="kpi-value">{{ overview.avg_reach }}</span>
          <span class="kpi-delta text-[var(--text-secondary)]">на пост (VK)</span>
        </div>
      </div>

      <p v-if="metricsHint" class="metrics-hint">{{ metricsHint }}</p>

      <section class="chart-section panel-card">
        <div class="section-head">
          <div>
            <h2 class="section-title">{{ chartTitle }}</h2>
            <p v-if="growthHistory?.period_total != null" class="chart-total">
              <template v-if="chartMetric === 'views'">
                Новые просмотры за {{ periodLabel(growthPeriod) }}:
                <strong>{{ formatNum(growthHistory.period_total) }}</strong>
              </template>
              <template v-else>
                Сейчас: <strong>{{ formatNum(growthHistory.period_total) }}</strong> подписчиков
              </template>
            </p>
            <p
              v-if="chartComparisonText"
              :class="deltaClass(growthHistory.period_delta)"
              class="chart-delta"
            >
              {{ chartComparisonText }}
            </p>
          </div>
          <div class="chart-controls">
            <div class="period-toggle" role="group" aria-label="Метрика графика">
              <button
                v-for="option in chartMetricOptions"
                :key="option.value"
                type="button"
                class="period-toggle-btn"
                :class="{ 'period-toggle-btn-active': chartMetric === option.value }"
                :aria-pressed="chartMetric === option.value"
                @click="chartMetric = option.value"
              >
                {{ option.label }}
              </button>
            </div>
            <div class="period-toggle" role="group" aria-label="Период графика">
              <button
                v-for="option in growthPeriodOptions"
                :key="option.value"
                type="button"
                class="period-toggle-btn"
                :class="{ 'period-toggle-btn-active': growthPeriod === option.value }"
                :aria-pressed="growthPeriod === option.value"
                @click="setGrowthPeriod(option.value)"
              >
                {{ option.label }}
              </button>
            </div>
          </div>
        </div>
        <p v-if="growthLoading" class="hint">Загрузка графика…</p>
        <BarLineChart
          v-else
          :key="`${growthPeriod}-${chartMetric}`"
          :series="growthSeries"
          :animate="true"
          class="channel-growth-chart"
        />
        <p v-if="!growthLoading && growthSeries.length < 2" class="hint">
          <template v-if="chartMetric === 'views'">
            На графике — прирост просмотров между замерами, не сумма всех просмотров постов.
            Нужно минимум 2 замера. Нажимайте «Обновить» периодически.
          </template>
          <template v-else>
            Нужно минимум 2 замера. Нажимайте «Обновить» периодически — точки появятся по мере сбора.
          </template>
        </p>
      </section>

      <section class="detail-block">
        <h2 class="section-title">Метрики постов</h2>
        <div v-if="!posts.length" class="empty-state panel-card p-6">
          Метрик постов пока нет.
          <template v-if="overview.channel.platform === 'telegram'">
            Просмотры по постам требуют Telethon (TELEGRAM_API_ID/HASH).
          </template>
          <template v-else-if="overview.channel.platform === 'max'">
            Просмотры появятся после сбора статистики (нужно право view_stats у бота).
          </template>
        </div>
        <div v-else class="table-wrap panel-card overflow-hidden">
          <table class="table-panel">
            <thead>
              <tr>
                <th>Пост</th>
                <th>
                  <button type="button" class="sort-header" @click="togglePostsSort('published_at')">
                    Опубликован
                    <span class="sort-indicator">{{ sortIndicator('published_at') }}</span>
                  </button>
                </th>
                <th>
                  <button type="button" class="sort-header" @click="togglePostsSort('views')">
                    Просмотры
                    <span class="sort-indicator">{{ sortIndicator('views') }}</span>
                  </button>
                </th>
                <th>
                  <button type="button" class="sort-header" @click="togglePostsSort('reactions')">
                    Реакции
                    <span class="sort-indicator">{{ sortIndicator('reactions') }}</span>
                  </button>
                </th>
                <th>
                  <button type="button" class="sort-header" @click="togglePostsSort('forwards')">
                    Репосты
                    <span class="sort-indicator">{{ sortIndicator('forwards') }}</span>
                  </button>
                </th>
                <th>
                  <button type="button" class="sort-header" @click="togglePostsSort('comments')">
                    Комменты
                    <span class="sort-indicator">{{ sortIndicator('comments') }}</span>
                  </button>
                </th>
                <th>
                  <button type="button" class="sort-header" @click="togglePostsSort('reach')">
                    Охват
                    <span class="sort-indicator">{{ sortIndicator('reach') }}</span>
                  </button>
                </th>
                <th>Собрано</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="post in posts" :key="post.id">
                <td><p class="line-clamp-2 text-sm max-w-md">{{ post.rewritten_text || post.platform_post_id }}</p></td>
                <td class="whitespace-nowrap text-xs font-mono text-[var(--text-secondary)]">{{ formatDate(post.published_at) }}</td>
                <td class="font-mono text-sm">{{ formatNum(post.views) }}</td>
                <td class="font-mono text-sm">{{ formatNum(post.reactions) }}</td>
                <td class="font-mono text-sm">{{ formatNum(post.forwards) }}</td>
                <td class="font-mono text-sm">{{ formatNum(post.comments) }}</td>
                <td class="font-mono text-sm">{{ formatNum(post.reach) }}</td>
                <td class="whitespace-nowrap text-xs font-mono text-[var(--text-secondary)]">{{ formatDate(post.collected_at) }}</td>
                <td>
                  <a v-if="post.post_url" :href="post.post_url" target="_blank" rel="noopener" class="text-xs text-accent hover:underline">Открыть</a>
                  <span v-else>—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="detail-block">
        <div class="section-head">
          <h2 class="section-title">Рекламные интеграции</h2>
          <button type="button" class="btn-primary btn-sm" @click="showAdForm = !showAdForm">
            {{ showAdForm ? 'Скрыть' : 'Добавить' }}
          </button>
        </div>

        <form v-if="showAdForm" class="ad-form panel-card" @submit.prevent="submitAd">
          <div class="ad-form-grid">
            <label class="form-field">
              <span>Рекламодатель</span>
              <input v-model="adForm.advertiser" required class="input-panel" />
            </label>
            <label class="form-field">
              <span>Цена</span>
              <input v-model.number="adForm.price" type="number" min="0" step="0.01" class="input-panel" />
            </label>
            <label class="form-field">
              <span>Дата</span>
              <input v-model="adForm.placed_at" type="datetime-local" required class="input-panel" />
            </label>
            <label class="form-field">
              <span>Статус</span>
              <select v-model="adForm.status" class="input-panel">
                <option value="planned">Запланировано</option>
                <option value="published">Опубликовано</option>
                <option value="completed">Завершено</option>
              </select>
            </label>
            <label class="form-field">
              <span>Ссылка на пост</span>
              <input v-model="adForm.post_url" class="input-panel" placeholder="https://..." />
            </label>
          </div>
          <label class="form-field">
            <span>Заметка</span>
            <textarea v-model="adForm.note" rows="2" class="input-panel" />
          </label>
          <div class="ad-form-actions">
            <button type="submit" class="btn-primary btn-sm" :disabled="adSaving">
              {{ adSaving ? 'Сохранение…' : 'Сохранить' }}
            </button>
          </div>
        </form>

        <div v-if="!ads.length" class="empty-state panel-card p-6">Рекламных интеграций пока нет.</div>
        <div v-else class="table-wrap panel-card overflow-hidden">
          <table class="table-panel">
            <thead>
              <tr>
                <th>Дата</th>
                <th>Рекламодатель</th>
                <th>Цена</th>
                <th>Статус</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="ad in ads" :key="ad.id">
                <td class="whitespace-nowrap text-xs font-mono">{{ formatDate(ad.placed_at) }}</td>
                <td>{{ ad.advertiser }}</td>
                <td class="font-mono text-sm">{{ ad.price != null ? `${ad.price} ${ad.currency}` : '—' }}</td>
                <td><span class="badge-muted">{{ adStatusLabel(ad.status) }}</span></td>
                <td>
                  <button type="button" class="text-xs text-danger hover:underline" @click="removeAd(ad.id)">Удалить</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>

    <AnalyticsRefreshModal
      :open="refreshModalOpen"
      :progress="refreshProgress"
      @close="closeRefreshModal"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeader from '../components/layout/PageHeader.vue'
import BarLineChart from '../components/analytics/BarLineChart.vue'
import AnalyticsRefreshModal from '../components/analytics/AnalyticsRefreshModal.vue'
import { analyticsApi } from '../api/index.js'
import { pollRefreshProgress, startRefreshChannel } from '../utils/analyticsRefresh.js'

const route = useRoute()
const router = useRouter()
const channelId = computed(() => Number(route.params.channelId))

const overview = ref(null)
const growthHistory = ref(null)
const growthPeriod = ref('month')
const chartMetric = ref('views')
const growthLoading = ref(false)
const posts = ref([])
const postsSortBy = ref('published_at')
const postsSortOrder = ref('desc')
const postsLoading = ref(false)
const ads = ref([])
const loading = ref(false)
const refreshing = ref(false)
const error = ref(null)
const showAdForm = ref(false)
const adSaving = ref(false)

const refreshModalOpen = ref(false)
const refreshProgress = ref(null)

const adForm = ref({
  advertiser: '',
  price: null,
  placed_at: '',
  status: 'published',
  post_url: '',
  note: '',
})

const growthPeriodOptions = [
  { value: 'today', label: 'Сегодня' },
  { value: 'week', label: 'Неделя' },
  { value: 'month', label: 'Месяц' },
  { value: 'all', label: 'Всё время' },
]

const chartMetricOptions = [
  { value: 'subscribers', label: 'Подписчики' },
  { value: 'views', label: 'Просмотры' },
]

const chartTitle = computed(() =>
  chartMetric.value === 'views' ? 'Новые просмотры' : 'Подписчики',
)

const metricsHint = computed(() => {
  if (!overview.value) return null
  const platform = overview.value.channel.platform
  if (platform === 'max') {
    return 'Просмотры 24/48/72ч — прирост между замерами. Охват MAX не отдаёт. «Ср. на пост» — накопленный итог по опубликованным через платформу постам.'
  }
  if (platform === 'telegram') {
    return 'Просмотры 24/48/72ч — прирост между замерами. Охват Telegram не отдаёт. «Ср. на пост» — накопленный итог по постам.'
  }
  return 'Просмотры 24/48/72ч — прирост между замерами. «Ср. на пост» — накопленный итог по постам.'
})

const chartComparisonText = computed(() => {
  const history = growthHistory.value
  if (!history || history.period_delta == null) return null
  const delta = formatDelta(history.period_delta)
  const pct =
    history.period_delta_percent != null
      ? ` (${history.period_delta_percent > 0 ? '+' : ''}${history.period_delta_percent}%)`
      : ''
  const vs = history.previous_period_label
    ? ` vs ${history.previous_period_label}`
    : ''
  const unsub =
    chartMetric.value === 'subscribers' && history.subscribers_unsubscribed != null
      ? ` · −${formatNum(history.subscribers_unsubscribed)} отписалось`
      : ''
  return `${delta}${pct}${vs}${unsub}`
})

const platformLabels = { telegram: 'Telegram', vk: 'VK', max: 'MAX' }
const adStatusLabels = { planned: 'Запланировано', published: 'Опубликовано', completed: 'Завершено' }

function platformLabel(p) {
  return platformLabels[p] || p
}
function adStatusLabel(s) {
  return adStatusLabels[s] || s
}

function periodLabel(period) {
  return growthPeriodOptions.find((item) => item.value === period)?.label?.toLowerCase() || period
}

const growthSeries = computed(() => {
  if (!growthHistory.value) return []
  const granularity = growthHistory.value.granularity || 'day'
  return growthHistory.value.points
    .filter((p) => p.value != null)
    .map((p) => ({
      value: p.value,
      label: formatGrowthLabel(p.captured_at, granularity),
      fullLabel: formatGrowthFullLabel(p.captured_at),
    }))
})

function formatGrowthFullLabel(iso) {
  const date = new Date(iso)
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatGrowthLabel(iso, granularity) {
  const date = new Date(iso)
  if (granularity === '30min') {
    return date.toLocaleString('ru-RU', {
      hour: '2-digit',
      minute: '2-digit',
    })
  }
  if (granularity === 'month') {
    return date.toLocaleDateString('ru-RU', {
      month: 'short',
      year: '2-digit',
    })
  }
  return date.toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
  })
}

function formatNum(n) {
  if (n == null) return '—'
  return new Intl.NumberFormat('ru-RU').format(n)
}
function formatMoney(n) {
  if (n == null) return '—'
  return new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 }).format(n)
}
function formatDate(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}
function formatDelta(delta) {
  if (delta === 0) return '0'
  return delta > 0 ? `+${formatNum(delta)}` : formatNum(delta)
}
function deltaClass(delta) {
  if (delta > 0) return 'text-accent'
  if (delta < 0) return 'text-danger'
  return 'text-[var(--text-secondary)]'
}
function defaultPlacedAt() {
  const d = new Date()
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset())
  return d.toISOString().slice(0, 16)
}

function goBack() {
  router.push({ name: 'analytics' })
}

async function loadGrowth() {
  growthLoading.value = true
  try {
    const res = await analyticsApi.channelGrowth(channelId.value, {
      period: growthPeriod.value,
      metric: chartMetric.value,
    })
    growthHistory.value = res.data
  } catch (e) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    growthLoading.value = false
  }
}

function setGrowthPeriod(period) {
  if (growthPeriod.value === period) return
  growthPeriod.value = period
}

function sortIndicator(column) {
  if (postsSortBy.value !== column) return '↕'
  return postsSortOrder.value === 'desc' ? '↓' : '↑'
}

function togglePostsSort(column) {
  if (postsSortBy.value === column) {
    postsSortOrder.value = postsSortOrder.value === 'desc' ? 'asc' : 'desc'
  } else {
    postsSortBy.value = column
    postsSortOrder.value = 'desc'
  }
  loadPosts()
}

async function loadPosts() {
  postsLoading.value = true
  try {
    const postsRes = await analyticsApi.channelPosts(channelId.value, {
      limit: 100,
      sort_by: postsSortBy.value,
      sort_order: postsSortOrder.value,
    })
    posts.value = postsRes.data
  } catch (e) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    postsLoading.value = false
  }
}

async function load() {
  loading.value = true
  error.value = null
  try {
    const [ovRes, adsRes] = await Promise.all([
      analyticsApi.channel(channelId.value),
      analyticsApi.ads({ channel_id: channelId.value }),
    ])
    overview.value = ovRes.data
    ads.value = adsRes.data
    await loadPosts()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}

function closeRefreshModal() {
  refreshModalOpen.value = false
}

async function refresh() {
  refreshing.value = true
  error.value = null
  refreshProgress.value = null
  refreshModalOpen.value = true
  try {
    const jobId = await startRefreshChannel(channelId.value)
    await pollRefreshProgress(jobId, (progress) => {
      refreshProgress.value = progress
    })
    await load()
    await loadGrowth()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message
    refreshModalOpen.value = false
  } finally {
    refreshing.value = false
  }
}

async function submitAd() {
  adSaving.value = true
  try {
    await analyticsApi.createAd({
      ...adForm.value,
      channel_id: channelId.value,
      placed_at: new Date(adForm.value.placed_at).toISOString(),
    })
    adForm.value = {
      advertiser: '',
      price: null,
      placed_at: defaultPlacedAt(),
      status: 'published',
      post_url: '',
      note: '',
    }
    showAdForm.value = false
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    adSaving.value = false
  }
}

async function removeAd(id) {
  if (!confirm('Удалить рекламную интеграцию?')) return
  try {
    await analyticsApi.removeAd(id)
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message
  }
}

onMounted(() => {
  adForm.value.placed_at = defaultPlacedAt()
  load()
  loadGrowth()
})

watch(growthPeriod, () => {
  loadGrowth()
})

watch(chartMetric, () => {
  loadGrowth()
})

watch(channelId, () => {
  load()
  loadGrowth()
})
</script>

<style scoped>
.kpi-grid {
  @apply mb-3 grid gap-4 grid-cols-2 md:grid-cols-3 xl:grid-cols-6;
}

.metrics-hint {
  @apply mb-6 text-xs leading-relaxed text-[var(--text-secondary)];
}

.kpi-card {
  @apply flex flex-col gap-1 p-4;
}

.kpi-label {
  @apply text-[10px] uppercase tracking-wide text-[var(--text-secondary)];
}

.kpi-value {
  @apply text-2xl font-semibold text-[var(--text-primary)];
}

.kpi-delta {
  @apply text-xs;
}

.chart-section {
  @apply mb-8 p-5;
}

.section-title {
  @apply mb-4 text-base font-semibold text-[var(--text-primary)];
}

.chart-section .section-title {
  @apply mb-0;
}

.chart-total {
  @apply mt-1 text-sm text-[var(--text-secondary)];
}

.chart-total strong {
  @apply font-semibold text-[var(--text-primary)];
}

.chart-delta {
  @apply mt-1 text-xs;
}

.chart-controls {
  @apply flex flex-wrap items-center justify-end gap-2;
}

.period-toggle {
  @apply inline-flex shrink-0 items-center gap-0.5 rounded-pill border border-panel-border bg-panel-surface p-0.5 shadow-sm;
}

.period-toggle-btn {
  @apply rounded-pill px-3 py-1.5 text-xs text-[var(--text-secondary)] transition-all duration-200
    hover:text-[var(--text-primary)];
}

.period-toggle-btn-active {
  @apply bg-accent text-white shadow-sm hover:text-white;
}

.detail-block {
  @apply mb-8;
}

.section-head {
  @apply mb-4 flex items-center justify-between gap-4;
}

.ad-form {
  @apply mb-4 space-y-4 p-4;
}

.ad-form-grid {
  @apply grid gap-4 md:grid-cols-2 lg:grid-cols-3;
}

.form-field {
  @apply flex flex-col gap-1 text-sm;
}

.form-field span {
  @apply text-[var(--text-secondary)];
}

.ad-form-actions {
  @apply flex justify-end;
}

.hint {
  @apply mt-3 text-xs text-[var(--text-secondary)];
}

.channel-growth-chart {
  @apply mt-2;
}

.sort-header {
  @apply inline-flex items-center gap-1 text-left text-[10px] uppercase tracking-wide
    text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)];
}

.sort-indicator {
  @apply font-mono text-[10px] text-accent;
}
</style>
