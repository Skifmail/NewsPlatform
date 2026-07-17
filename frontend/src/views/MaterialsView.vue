<template>
  <div>
    <PageHeader
      title="Материалы"
      subtitle="Сырые посты после парсинга — выберите и отправьте на AI, затем они попадут в очередь модерации"
    >
      <template #actions>
        <button type="button" class="btn-secondary btn-sm" :disabled="loading" @click="load">
          Обновить
        </button>
      </template>
    </PageHeader>

    <div class="stats-row">
      <div class="stat-card">
        <span class="stat-label">Всего</span>
        <span class="stat-value">{{ summary.total }}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">Ждут AI</span>
        <span class="stat-value text-accent">{{ summary.unprocessed }}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">Выбрано</span>
        <span class="stat-value">{{ selectedIds.size }}</span>
      </div>
    </div>

    <div class="toolbar panel-card">
      <div class="toolbar-filters">
        <label class="filter-label">
          Источник
          <select v-model="filterSourceId" class="select" @change="onFilterChange">
            <option :value="null">Все</option>
            <option v-for="s in summary.sources" :key="s.source_id" :value="s.source_id">
              {{ s.source_name }} ({{ s.unprocessed }}/{{ s.total }})
            </option>
          </select>
        </label>
        <label class="filter-label">
          Тема
          <select v-model="filterTopic" class="select" @change="onFilterChange">
            <option value="all">Все</option>
            <option v-for="opt in TOPIC_OPTIONS" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </label>
        <label class="filter-label">
          Статус AI
          <select v-model="filterProcessed" class="select" @change="onFilterChange">
            <option value="pending">Ждут обработки</option>
            <option value="done">Обработаны</option>
            <option value="all">Все</option>
          </select>
        </label>
        <label class="filter-label">
          Старше
          <select v-model="filterOlderThanDays" class="select" @change="onFilterChange">
            <option :value="null">Любой возраст</option>
            <option :value="1">1 дня</option>
            <option :value="3">3 дней</option>
            <option :value="7">7 дней</option>
            <option :value="30">30 дней</option>
          </select>
        </label>
      </div>
      <div class="toolbar-actions">
        <button
          type="button"
          class="btn-primary btn-sm"
          :disabled="!selectedIds.size || processing"
          @click="processSelected"
        >
          AI: выбранные ({{ selectedIds.size }})
        </button>
        <button
          type="button"
          class="btn-secondary btn-sm"
          :disabled="!posts.length || processing"
          @click="selectAllOnPage"
        >
          Выбрать все на странице
        </button>
        <button
          type="button"
          class="btn-danger btn-sm"
          :disabled="!selectedIds.size || deleting"
          @click="deleteSelected"
        >
          Удалить выбранные ({{ selectedIds.size }})
        </button>
        <button
          type="button"
          class="btn-ghost btn-sm"
          :disabled="!hasActiveFilters || deleting"
          @click="deleteByFilters"
        >
          Удалить по фильтру
        </button>
        <button
          v-if="selectedIds.size"
          type="button"
          class="btn-ghost btn-sm"
          @click="clearSelection"
        >
          Сбросить
        </button>
      </div>
    </div>

    <p v-if="message" class="hint text-accent">{{ message }}</p>
    <p v-if="loading && !posts.length" class="empty-state">Загрузка…</p>
    <p v-else-if="error" class="empty-state text-danger">{{ error }}</p>
    <p v-else-if="!posts.length" class="empty-state">
      Нет материалов. Запустите парсинг в разделе «Источники».
    </p>

    <div v-else>
      <div class="materials-cards">
        <div class="materials-select-all panel-card">
          <label class="materials-select-all-label">
            <input
              type="checkbox"
              :checked="allOnPageSelected"
              :disabled="!posts.length"
              @change="toggleSelectAll"
            />
            Выбрать все на странице
          </label>
        </div>

        <article
          v-for="post in posts"
          :key="`card-${post.id}`"
          class="material-card panel-card"
          :class="{ 'row-muted': post.is_processed }"
        >
          <div class="material-card-top">
            <label class="material-check">
              <input
                type="checkbox"
                :checked="selectedIds.has(post.id)"
                @change="toggleSelect(post.id)"
              />
            </label>
            <div class="material-card-main">
              <div class="material-card-meta">
                <span class="material-source">{{ post.source_name }}</span>
                <span class="badge-purple">{{ topicLabel(post.topic) }}</span>
                <span v-if="post.is_processed" class="badge-accent">AI готово</span>
                <span v-else class="badge-muted">Ждёт AI</span>
              </div>
              <p class="material-title">{{ post.title || 'Без заголовка' }}</p>
              <p v-if="post.content_preview" class="material-preview">
                {{ post.content_preview }}
              </p>
              <div class="material-card-foot">
                <span class="material-date">{{ formatTime(post.fetched_at) }} · #{{ post.id }}</span>
                <div class="material-card-actions">
                  <a
                    v-if="post.url"
                    :href="post.url"
                    target="_blank"
                    rel="noopener"
                    class="text-xs text-accent"
                  >
                    Оригинал ↗
                  </a>
                  <button
                    v-if="!post.is_processed"
                    type="button"
                    class="btn-primary btn-sm"
                    :disabled="processingId === post.id"
                    @click="processOne(post.id)"
                  >
                    {{ processingId === post.id ? '…' : 'На AI' }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </article>
      </div>

      <div class="table-wrap panel-card materials-table">
        <table class="table-panel">
          <thead>
            <tr>
              <th class="w-10">
                <input
                  type="checkbox"
                  :checked="allOnPageSelected"
                  :disabled="!posts.length"
                  @change="toggleSelectAll"
                />
              </th>
              <th>Источник</th>
              <th>Заголовок</th>
              <th>Тема</th>
              <th>Статус</th>
              <th>Дата</th>
              <th class="text-right">Действия</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="post in posts" :key="post.id" :class="{ 'row-muted': post.is_processed }">
              <td>
                <input
                  type="checkbox"
                  :checked="selectedIds.has(post.id)"
                  @change="toggleSelect(post.id)"
                />
              </td>
              <td>
                <span class="font-medium text-[var(--text-primary)]">{{ post.source_name }}</span>
                <p
                  v-if="post.source_url"
                  class="text-[10px] text-[var(--text-secondary)] truncate max-w-[140px]"
                  :title="post.source_url"
                >
                  RSS: {{ feedHost(post.source_url) }}
                </p>
                <p class="text-[10px] text-[var(--text-secondary)]">#{{ post.id }}</p>
              </td>
              <td class="max-w-md">
                <p class="text-sm font-medium text-[var(--text-primary)] line-clamp-2">
                  {{ post.title || 'Без заголовка' }}
                </p>
                <p class="text-xs text-[var(--text-secondary)] mt-1 line-clamp-2">
                  {{ post.content_preview }}
                </p>
                <a
                  v-if="post.url"
                  :href="post.url"
                  target="_blank"
                  rel="noopener"
                  class="text-xs text-accent hover:underline mt-1 inline-block"
                >
                  Оригинал ↗
                </a>
              </td>
              <td><span class="badge-purple">{{ topicLabel(post.topic) }}</span></td>
              <td>
                <span v-if="post.is_processed" class="badge-accent">AI готово</span>
                <span v-else class="badge-muted">Ждёт AI</span>
              </td>
              <td class="text-xs text-[var(--text-secondary)] whitespace-nowrap font-mono">
                {{ formatTime(post.fetched_at) }}
              </td>
              <td class="text-right">
                <button
                  v-if="!post.is_processed"
                  type="button"
                  class="btn-primary btn-sm"
                  :disabled="processingId === post.id"
                  @click="processOne(post.id)"
                >
                  {{ processingId === post.id ? '…' : 'На AI' }}
                </button>
                <span v-else class="text-xs text-[var(--text-secondary)]">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="posts.length >= limit" class="pagination">
      <button type="button" class="btn-secondary btn-sm" :disabled="offset === 0" @click="prevPage">
        Назад
      </button>
      <span class="text-sm text-[var(--text-secondary)]">Смещение {{ offset }}</span>
      <button type="button" class="btn-secondary btn-sm" @click="nextPage">Ещё</button>
    </div>

    <p class="hint">
      После успешного AI посты появятся в разделе «Очередь». Статус задач — в «Задачи».
    </p>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import PageHeader from '../components/layout/PageHeader.vue'
import { rawPostsApi } from '../api/index.js'
import { useDialogStore } from '../stores/dialogStore'

const dialog = useDialogStore()

const summary = ref({ total: 0, unprocessed: 0, sources: [] })
const posts = ref([])
const loading = ref(false)
const error = ref(null)
const message = ref('')
const processing = ref(false)
const deleting = ref(false)
const processingId = ref(null)
const selectedIds = ref(new Set())
const filterSourceId = ref(null)
const filterTopic = ref('all')
const filterProcessed = ref('pending')
const filterOlderThanDays = ref(null)
const limit = 50
const offset = ref(0)

import { TOPIC_OPTIONS, topicLabel } from '../constants/topics.js'

function feedHost(url) {
  try {
    return new URL(url).hostname
  } catch {
    return url
  }
}

const allOnPageSelected = computed(
  () => posts.value.length > 0 && posts.value.every((p) => selectedIds.value.has(p.id))
)
const hasActiveFilters = computed(
  () =>
    filterSourceId.value != null ||
    filterTopic.value !== 'all' ||
    filterProcessed.value !== 'all' ||
    filterOlderThanDays.value != null
)

function buildFiltersPayload() {
  const filters = {}
  if (filterSourceId.value != null) filters.source_id = filterSourceId.value
  if (filterTopic.value !== 'all') filters.topic = filterTopic.value
  const proc = processedParam()
  if (proc !== undefined) filters.is_processed = proc
  if (filterOlderThanDays.value != null) filters.older_than_days = filterOlderThanDays.value
  return filters
}

function processedParam() {
  if (filterProcessed.value === 'pending') return false
  if (filterProcessed.value === 'done') return true
  return undefined
}

function formatTime(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

async function loadSummary() {
  const { data } = await rawPostsApi.summary()
  summary.value = data
}

async function load() {
  loading.value = true
  error.value = null
  try {
    await loadSummary()
    const params = { limit, offset: offset.value }
    if (filterSourceId.value != null) params.source_id = filterSourceId.value
    if (filterTopic.value !== 'all') params.topic = filterTopic.value
    const proc = processedParam()
    if (proc !== undefined) params.is_processed = proc
    const { data } = await rawPostsApi.list(params)
    posts.value = data
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || 'Ошибка загрузки'
  } finally {
    loading.value = false
  }
}

function onFilterChange() {
  offset.value = 0
  clearSelection()
  load()
}

function toggleSelect(id) {
  const next = new Set(selectedIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selectedIds.value = next
}

function toggleSelectAll() {
  if (allOnPageSelected.value) {
    posts.value.forEach((p) => selectedIds.value.delete(p.id))
    selectedIds.value = new Set(selectedIds.value)
    return
  }
  const next = new Set(selectedIds.value)
  posts.value.forEach((p) => next.add(p.id))
  selectedIds.value = next
}

function selectAllOnPage() {
  const next = new Set(selectedIds.value)
  posts.value.forEach((p) => next.add(p.id))
  selectedIds.value = next
}

function clearSelection() {
  selectedIds.value = new Set()
}

async function processOne(id) {
  processingId.value = id
  message.value = ''
  try {
    await rawPostsApi.process(id)
    message.value = `Пост #${id} поставлен в очередь AI`
    selectedIds.value.delete(id)
    selectedIds.value = new Set(selectedIds.value)
    await load()
  } catch (e) {
    message.value = e.response?.data?.detail || 'Не удалось поставить в очередь'
  } finally {
    processingId.value = null
  }
}

async function processSelected() {
  const ids = [...selectedIds.value]
  if (!ids.length) return
  processing.value = true
  message.value = ''
  try {
    const { data } = await rawPostsApi.processBatch(ids)
    message.value = data.message
    if (data.skipped?.length) {
      message.value += `. Пропущено: ${data.skipped.length}`
    }
    clearSelection()
    await load()
  } catch (e) {
    message.value = e.response?.data?.detail || 'Ошибка пакетной обработки'
  } finally {
    processing.value = false
  }
}

async function deleteSelected() {
  const ids = [...selectedIds.value]
  if (!ids.length) return
  const ok = await dialog.confirm({
    title: 'Удалить материалы',
    message: `Удалить ${ids.length} материал(ов)? Связанные необработанные посты в очереди тоже будут удалены. Опубликованные пропускаются.`,
    confirmLabel: 'Удалить',
    danger: true,
  })
  if (!ok) return

  deleting.value = true
  message.value = ''
  try {
    const { data } = await rawPostsApi.bulkDelete({ raw_post_ids: ids })
    message.value = data.message
    if (data.skipped) {
      message.value += `. Пропущено (опубликованы): ${data.skipped}`
    }
    clearSelection()
    await load()
  } catch (e) {
    message.value = e.response?.data?.detail || 'Не удалось удалить материалы'
  } finally {
    deleting.value = false
  }
}

async function deleteByFilters() {
  if (!hasActiveFilters.value) return
  deleting.value = true
  message.value = ''
  try {
    const filters = buildFiltersPayload()
    const { data: preview } = await rawPostsApi.bulkDelete({
      filters,
      dry_run: true,
    })
    if (!preview.affected) {
      await dialog.alert({ message: 'Нет материалов для удаления по фильтру' })
      return
    }
    let confirmText = preview.message
    if (preview.skipped) {
      confirmText += `. Пропустим опубликованные: ${preview.skipped}`
    }
    const ok = await dialog.confirm({
      title: 'Удалить по фильтру',
      message: `${confirmText}. Продолжить?`,
      confirmLabel: 'Удалить',
      danger: true,
    })
    if (!ok) return

    const { data } = await rawPostsApi.bulkDelete({ filters })
    message.value = data.message
    if (data.skipped) {
      message.value += `. Пропущено: ${data.skipped}`
    }
    clearSelection()
    await load()
  } catch (e) {
    message.value = e.response?.data?.detail || 'Не удалось удалить материалы'
  } finally {
    deleting.value = false
  }
}

function prevPage() {
  offset.value = Math.max(0, offset.value - limit)
  load()
}

function nextPage() {
  offset.value += limit
  load()
}

onMounted(() => load())
</script>

<style scoped>
.stats-row {
  @apply mb-6 grid grid-cols-3 gap-2 max-w-3xl sm:gap-4;
}

.toolbar {
  @apply mb-4 flex flex-col gap-4 p-4 md:flex-row md:items-end md:justify-between;
}

.toolbar-filters {
  @apply grid w-full grid-cols-1 gap-3 sm:grid-cols-2 lg:flex lg:flex-wrap lg:gap-4;
}

.filter-label {
  @apply flex min-w-0 flex-col gap-1 text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)];
}

.filter-label .select {
  @apply w-full min-w-0;
}

.toolbar-actions {
  @apply flex flex-wrap gap-2;
}

.materials-cards {
  @apply flex flex-col gap-3 md:hidden;
}

.materials-select-all {
  @apply px-4 py-3;
}

.materials-select-all-label {
  @apply inline-flex items-center gap-2 text-sm text-[var(--text-secondary)];
}

.material-card {
  @apply p-4;
}

.material-card-top {
  @apply flex items-start gap-3;
}

.material-check {
  @apply mt-1 shrink-0;
}

.material-card-main {
  @apply min-w-0 flex-1;
}

.material-card-meta {
  @apply mb-2 flex flex-wrap items-center gap-1.5;
}

.material-source {
  @apply text-xs font-medium text-[var(--text-primary)];
}

.material-title {
  @apply text-sm font-medium leading-snug text-[var(--text-primary)];
}

.material-preview {
  @apply mt-1 text-xs leading-relaxed text-[var(--text-secondary)] line-clamp-3;
}

.material-card-foot {
  @apply mt-3 flex flex-wrap items-center justify-between gap-2;
}

.material-date {
  @apply font-mono text-[10px] text-[var(--text-secondary)];
}

.material-card-actions {
  @apply flex flex-wrap items-center gap-2;
}

.materials-table {
  @apply hidden max-w-full overflow-x-auto md:block;
}

.row-muted {
  @apply opacity-70;
}

.pagination {
  @apply mt-4 flex flex-wrap items-center gap-4;
}

.hint {
  @apply mt-4 text-xs text-[var(--text-secondary)];
}
</style>
