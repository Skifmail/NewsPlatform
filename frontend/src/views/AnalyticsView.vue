<template>
  <div>
    <PageHeader
      title="Аналитика каналов"
      subtitle="Подписчики, просмотры, публикации и рекламные интеграции по Telegram, VK и MAX"
    >
      <template #actions>
        <span class="last-updated">
          <span class="last-updated-label">Последнее обновление</span>
          <span class="last-updated-value">{{ lastUpdatedLabel }}</span>
        </span>
        <button
          type="button"
          class="btn-secondary btn-sm"
          :disabled="refreshing"
          @click="refreshAll"
        >
          {{ refreshing ? 'Обновление…' : 'Обновить статистику' }}
        </button>
        <button type="button" class="btn-secondary btn-sm" :disabled="loading" @click="load">
          Перезагрузить
        </button>
      </template>
    </PageHeader>

    <div class="auto-bar panel-card">
      <div class="auto-bar-main">
        <label class="switch">
          <input type="checkbox" :checked="autoEnabled" @change="toggleAuto($event)" />
          <span class="switch-slider" />
        </label>
        <div class="auto-bar-text">
          <span class="auto-bar-title">Автоматический сбор статистики</span>
          <span class="auto-bar-sub">
            {{ autoEnabled
              ? `Включён — данные обновляются каждые ${intervalMinutes} мин`
              : 'Выключен — статистика обновляется только вручную' }}
          </span>
        </div>
      </div>
      <div class="auto-bar-interval">
        <label class="interval-label">Интервал</label>
        <select
          v-model.number="intervalMinutes"
          class="input-panel interval-select"
          :disabled="savingSettings"
          @change="saveInterval"
        >
          <option :value="30">30 мин</option>
          <option :value="60">1 час</option>
          <option :value="180">3 часа</option>
          <option :value="360">6 часов</option>
          <option :value="720">12 часов</option>
          <option :value="1440">24 часа</option>
        </select>
      </div>
    </div>

    <div v-if="summary" class="stats-row">
      <div class="stat-card">
        <span class="stat-label">Каналов</span>
        <span class="stat-value">{{ summary.channels_total }}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">Подписчиков</span>
        <span class="stat-value text-accent">{{ formatNum(summary.subscribers_total) }}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">Публикаций</span>
        <span class="stat-value">{{ formatNum(summary.publications_total) }}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">Ср. на пост</span>
        <span class="stat-value">{{ summary.avg_views ?? '—' }}</span>
        <span v-if="summary.total_views != null" class="stat-sub">
          {{ formatNum(summary.total_views) }} накоплено
        </span>
      </div>
      <div class="stat-card">
        <span class="stat-label">Реклама</span>
        <span class="stat-value">{{ summary.ad_integrations_total }}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">Доход рекламы</span>
        <span class="stat-value">{{ formatMoney(summary.ad_revenue_total) }}</span>
      </div>
    </div>

    <p v-if="loading && !channels.length" class="empty-state">Загрузка…</p>
    <p v-else-if="error" class="empty-state text-danger">{{ error }}</p>
    <p v-else-if="!channels.length" class="empty-state">
      Каналов пока нет. Добавьте их в разделе «Каналы» и нажмите «Обновить статистику».
    </p>

    <div v-else class="channels-grid">
      <article
        v-for="(item, index) in channels"
        :key="item.channel.id"
        class="channel-card panel-card"
        role="button"
        tabindex="0"
        @click="openChannel(item.channel.id)"
        @keydown.enter="openChannel(item.channel.id)"
      >
        <div class="channel-card-head">
          <div>
            <h3 class="channel-name">{{ item.channel.name }}</h3>
            <span class="badge-muted">{{ platformLabel(item.channel.platform) }}</span>
          </div>
          <button
            type="button"
            class="btn-ghost btn-sm"
            title="Обновить канал"
            @click.stop="refreshChannel(item.channel.id)"
          >
            ↻
          </button>
        </div>

        <BarLineChart
          v-if="item.growth_points.length > 1"
          :key="`chart-${item.channel.id}`"
          :series="sparklineSeries(item.growth_points)"
          :animation-base-delay="channelChartDelay(index)"
          compact
          class="channel-sparkline"
        />
        <div v-else class="channel-sparkline-empty">нет данных для графика</div>

        <div class="channel-metrics">
          <div>
            <span class="metric-label">Подписчики</span>
            <span class="metric-value">
              {{ formatNum(item.subscribers) }}
              <span
                v-if="item.subscribers_today != null"
                :class="deltaClass(item.subscribers_today)"
                class="metric-delta"
              >
                {{ formatDelta(item.subscribers_today) }}
              </span>
            </span>
            <span
              v-if="item.subscribers_today != null"
              class="metric-sub text-[var(--text-secondary)]"
            >
              сегодня
            </span>
          </div>
          <div>
            <span class="metric-label">За 24ч</span>
            <span class="metric-value">{{ formatNum(item.views_24h) }}</span>
            <span
              v-if="item.views_72h != null"
              class="metric-sub text-[var(--text-secondary)]"
            >
              72ч: {{ formatNum(item.views_72h) }}
            </span>
          </div>
          <div>
            <span class="metric-label">ER 24ч</span>
            <span class="metric-value">{{ item.engagement_rate != null ? `${item.engagement_rate}%` : '—' }}</span>
          </div>
          <div>
            <span class="metric-label">Ср. на пост</span>
            <span class="metric-value">{{ item.avg_views ?? '—' }}</span>
          </div>
        </div>

        <div class="channel-card-foot">
          <span v-if="item.last_collected_at" class="channel-updated">
            Обновлено: {{ formatDate(item.last_collected_at) }}
          </span>
          <span class="channel-open">Подробнее →</span>
        </div>
      </article>
    </div>

    <section v-if="channels.length" class="detail-section">
      <div class="section-head">
        <h2 class="section-title">Рекламные интеграции</h2>
        <button type="button" class="btn-primary btn-sm" @click="showAdForm = !showAdForm">
          {{ showAdForm ? 'Скрыть форму' : 'Добавить' }}
        </button>
      </div>

      <form v-if="showAdForm" class="ad-form panel-card" @submit.prevent="submitAd">
        <div class="ad-form-grid">
          <label class="form-field">
            <span>Канал</span>
            <select v-model.number="adForm.channel_id" required class="input-panel">
              <option v-for="c in channels" :key="c.channel.id" :value="c.channel.id">
                {{ c.channel.name }}
              </option>
            </select>
          </label>
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

      <div v-if="!ads.length" class="empty-state panel-card p-6">
        Рекламных интеграций пока нет.
      </div>
      <div v-else class="table-wrap panel-card overflow-hidden">
        <table class="table-panel">
          <thead>
            <tr>
              <th>Дата</th>
              <th>Канал</th>
              <th>Рекламодатель</th>
              <th>Цена</th>
              <th>Статус</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="ad in ads" :key="ad.id">
              <td class="whitespace-nowrap text-xs font-mono">{{ formatDate(ad.placed_at) }}</td>
              <td>{{ ad.channel?.name || ad.channel_id }}</td>
              <td>{{ ad.advertiser }}</td>
              <td class="font-mono text-sm">
                {{ ad.price != null ? `${ad.price} ${ad.currency}` : '—' }}
              </td>
              <td><span class="badge-muted">{{ adStatusLabel(ad.status) }}</span></td>
              <td>
                <button type="button" class="text-xs text-danger hover:underline" @click="removeAd(ad.id)">
                  Удалить
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <AnalyticsRefreshModal
      :open="refreshModalOpen"
      :progress="refreshProgress"
      @close="closeRefreshModal"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import PageHeader from '../components/layout/PageHeader.vue'
import BarLineChart from '../components/analytics/BarLineChart.vue'
import AnalyticsRefreshModal from '../components/analytics/AnalyticsRefreshModal.vue'
import { analyticsApi, settingsApi } from '../api/index.js'
import {
  pollRefreshProgress,
  startRefreshAll,
  startRefreshChannel,
} from '../utils/analyticsRefresh.js'

const router = useRouter()

const summary = ref(null)
const channels = ref([])
const ads = ref([])
const loading = ref(false)
const refreshing = ref(false)
const error = ref(null)
const showAdForm = ref(false)
const adSaving = ref(false)

const refreshModalOpen = ref(false)
const refreshProgress = ref(null)

const lastUpdatedAt = computed(() => {
  const times = channels.value
    .map((item) => item.last_collected_at)
    .filter(Boolean)
    .map((iso) => new Date(iso).getTime())
  if (!times.length) return null
  return new Date(Math.max(...times)).toISOString()
})

const lastUpdatedLabel = computed(() =>
  lastUpdatedAt.value ? formatDate(lastUpdatedAt.value) : 'ещё не собиралась',
)

const autoEnabled = ref(false)
const intervalMinutes = ref(180)
const savingSettings = ref(false)

const adForm = ref({
  channel_id: null,
  advertiser: '',
  price: null,
  placed_at: '',
  status: 'published',
  post_url: '',
  note: '',
})

const platformLabels = { telegram: 'Telegram', vk: 'VK', max: 'MAX' }
const adStatusLabels = { planned: 'Запланировано', published: 'Опубликовано', completed: 'Завершено' }

function platformLabel(p) {
  return platformLabels[p] || p
}
function adStatusLabel(s) {
  return adStatusLabels[s] || s
}

function formatNum(n) {
  if (n == null) return '—'
  return new Intl.NumberFormat('ru-RU').format(n)
}
function formatMoney(n) {
  if (n == null) return '—'
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    maximumFractionDigits: 0,
  }).format(n)
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

function sparklineSeries(points) {
  return points
    .filter((p) => p.subscribers != null)
    .map((p) => ({
      value: p.subscribers,
      label: '',
      fullLabel: formatDate(p.captured_at),
    }))
}

function channelChartDelay(index) {
  return index * 60
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

function openChannel(channelId) {
  router.push({ name: 'analytics-channel', params: { channelId } })
}

async function loadSettings() {
  try {
    const { data } = await settingsApi.get()
    const s = data.settings || {}
    autoEnabled.value = s.schedule_analytics_enabled === 'true'
    intervalMinutes.value = Number(s.analytics_interval_minutes) || 180
  } catch (e) {
    error.value = e.response?.data?.detail || e.message
  }
}

async function toggleAuto(event) {
  const enabled = event.target.checked
  savingSettings.value = true
  try {
    await settingsApi.update({
      settings: { schedule_analytics_enabled: enabled ? 'true' : 'false' },
    })
    autoEnabled.value = enabled
  } catch (e) {
    error.value = e.response?.data?.detail || e.message
    event.target.checked = autoEnabled.value
  } finally {
    savingSettings.value = false
  }
}

async function saveInterval() {
  savingSettings.value = true
  try {
    await settingsApi.update({
      settings: { analytics_interval_minutes: String(intervalMinutes.value) },
    })
  } catch (e) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    savingSettings.value = false
  }
}

async function load() {
  loading.value = true
  error.value = null
  try {
    const [sumRes, chRes, adsRes] = await Promise.all([
      analyticsApi.summary(),
      analyticsApi.channels(),
      analyticsApi.ads(),
    ])
    summary.value = sumRes.data
    channels.value = chRes.data
    ads.value = adsRes.data

    if (!adForm.value.channel_id && channels.value.length) {
      adForm.value.channel_id = channels.value[0].channel.id
    }
  } catch (e) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}

function closeRefreshModal() {
  refreshModalOpen.value = false
}

async function runRefreshJob(startFn) {
  refreshing.value = true
  error.value = null
  refreshProgress.value = null
  refreshModalOpen.value = true
  try {
    const jobId = await startFn()
    await pollRefreshProgress(jobId, (progress) => {
      refreshProgress.value = progress
    })
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message
    refreshModalOpen.value = false
  } finally {
    refreshing.value = false
  }
}

async function refreshAll() {
  await runRefreshJob(() => startRefreshAll())
}

async function refreshChannel(channelId) {
  await runRefreshJob(() => startRefreshChannel(channelId))
}

async function submitAd() {
  adSaving.value = true
  try {
    await analyticsApi.createAd({
      ...adForm.value,
      placed_at: new Date(adForm.value.placed_at).toISOString(),
    })
    adForm.value = {
      channel_id: channels.value[0]?.channel.id ?? null,
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
  loadSettings()
  load()
})
</script>

<style scoped>
.last-updated {
  @apply mr-1 flex flex-col items-end leading-tight;
}

.last-updated-label {
  @apply text-[10px] uppercase tracking-wide text-[var(--text-secondary)];
}

.last-updated-value {
  @apply text-xs font-medium text-[var(--text-primary)];
}

.auto-bar {
  @apply mb-6 flex flex-wrap items-center justify-between gap-4 p-4;
}

.auto-bar-main {
  @apply flex items-center gap-3;
}

.auto-bar-text {
  @apply flex flex-col;
}

.auto-bar-title {
  @apply text-sm font-semibold text-[var(--text-primary)];
}

.auto-bar-sub {
  @apply text-xs text-[var(--text-secondary)];
}

.auto-bar-interval {
  @apply flex items-center gap-2;
}

.interval-label {
  @apply text-xs text-[var(--text-secondary)];
}

.interval-select {
  @apply w-auto;
}

.switch {
  @apply relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center;
}

.switch input {
  @apply sr-only;
}

.switch-slider {
  @apply h-6 w-11 rounded-full bg-panel-border transition-colors;
}

.switch-slider::after {
  content: '';
  @apply absolute left-1 top-1 h-4 w-4 rounded-full bg-white transition-transform;
}

.switch input:checked + .switch-slider {
  @apply bg-accent;
}

.switch input:checked + .switch-slider::after {
  @apply translate-x-5;
}

.stats-row {
  @apply mb-6 grid gap-4 grid-cols-2 md:grid-cols-3 xl:grid-cols-6;
}

.channels-grid {
  @apply mb-8 grid gap-4 md:grid-cols-2 xl:grid-cols-3;
}

.channel-card {
  @apply cursor-pointer p-4 transition-all hover:border-accent/40 hover:-translate-y-0.5;
}

.channel-card-head {
  @apply mb-3 flex items-start justify-between gap-2;
}

.channel-name {
  @apply text-sm font-semibold text-[var(--text-primary)];
}

.channel-sparkline {
  @apply mb-3 h-10 w-full;
}

.channel-sparkline-empty {
  @apply mb-3 flex h-10 w-full items-center justify-center text-[10px] text-[var(--text-secondary)];
}

.channel-metrics {
  @apply grid grid-cols-2 gap-3 text-sm;
}

.metric-label {
  @apply block text-[10px] uppercase tracking-wide text-[var(--text-secondary)];
}

.metric-value {
  @apply font-medium text-[var(--text-primary)];
}

.metric-sub {
  @apply mt-0.5 block text-[10px] text-accent;
}

.metric-delta {
  @apply ml-1 text-xs;
}

.metric-unsub {
  @apply mt-0.5 block text-[10px];
}

.channel-card-foot {
  @apply mt-3 flex items-center justify-between;
}

.channel-updated {
  @apply text-[10px] text-[var(--text-secondary)];
}

.channel-open {
  @apply text-xs font-medium text-accent;
}

.detail-section {
  @apply mb-8;
}

.section-head {
  @apply mb-4 flex items-center justify-between gap-4;
}

.section-title {
  @apply text-base font-semibold text-[var(--text-primary)];
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
</style>
