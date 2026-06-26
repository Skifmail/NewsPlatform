<template>
  <div>
    <PageHeader
      title="Очередь модерации"
      subtitle="Посты, ожидающие проверки перед публикацией"
    >
      <template #actions>
        <button class="btn-secondary btn-sm" type="button" @click="store.loadQueue">
          <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Обновить
        </button>
      </template>
    </PageHeader>

    <div class="stats-row">
      <div class="stat-card">
        <span class="stat-label">В очереди</span>
        <span class="stat-value text-accent">{{ store.queue.length }}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">По фильтру</span>
        <span class="stat-value">{{ filteredQueue.length }}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">Выбрано</span>
        <span class="stat-value">{{ selectedIds.size }}</span>
      </div>
    </div>

    <div class="toolbar panel-card">
      <div class="toolbar-filters">
        <label class="filter-label">
          Канал
          <select v-model="filterChannelId" class="select">
            <option :value="null">Все</option>
            <option v-for="ch in channelOptions" :key="ch.id" :value="ch.id">
              {{ ch.name }}
            </option>
          </select>
        </label>
        <label class="filter-label">
          Тема
          <select v-model="filterTopic" class="select">
            <option value="all">Все</option>
            <option v-for="opt in TOPIC_OPTIONS" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </label>
        <label class="filter-label">
          Старше
          <select v-model="filterOlderThanDays" class="select">
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
          class="btn-secondary btn-sm"
          :disabled="!filteredQueue.length"
          @click="selectAllFiltered"
        >
          Выбрать все ({{ filteredQueue.length }})
        </button>
        <button
          type="button"
          class="btn-danger btn-sm"
          :disabled="!selectedIds.size || bulkBusy"
          @click="bulkRejectSelected"
        >
          Отклонить выбранные
        </button>
        <button
          type="button"
          class="btn-danger btn-sm"
          :disabled="!selectedIds.size || bulkBusy"
          @click="bulkDeleteSelected"
        >
          Удалить выбранные
        </button>
        <button
          type="button"
          class="btn-ghost btn-sm"
          :disabled="!hasActiveFilters || bulkBusy"
          @click="bulkRejectFiltered"
        >
          Отклонить по фильтру
        </button>
        <button
          type="button"
          class="btn-ghost btn-sm"
          :disabled="!hasActiveFilters || bulkBusy"
          @click="bulkDeleteFiltered"
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

    <p v-if="bulkMessage" class="hint text-accent">{{ bulkMessage }}</p>
    <p v-if="store.loading" class="empty-state">Загрузка очереди…</p>
    <p v-else-if="store.error" class="empty-state text-danger">{{ store.error }}</p>
    <div v-else-if="!filteredQueue.length" class="empty-state">
      <p class="text-lg font-medium text-[var(--text-primary)] mb-1">
        {{ store.queue.length ? 'Нет постов по фильтру' : 'Очередь пуста' }}
      </p>
      <p class="text-sm">
        {{ store.queue.length ? 'Измените фильтры' : 'Новые посты появятся после парсинга источников' }}
      </p>
    </div>
    <div v-else class="posts-grid">
      <PostCard
        v-for="post in filteredQueue"
        :key="post.id"
        :post="post"
        selectable
        :selected="selectedIds.has(post.id)"
        @toggle-select="toggleSelect(post)"
        @edit="editing = post"
        @approve="quickApprove(post)"
        @reject="quickReject(post)"
      />
    </div>

    <PostEditor :post="editing" @close="editing = null" />

    <RejectReasonModal
      v-model:open="rejectOpen"
      :post-id="rejectTarget?.id ?? null"
      :count="rejectBulkCount"
      @confirm="confirmReject"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import PageHeader from '../components/layout/PageHeader.vue'
import PostCard from '../components/PostCard.vue'
import PostEditor from '../components/PostEditor.vue'
import RejectReasonModal from '../components/RejectReasonModal.vue'
import { TOPIC_OPTIONS } from '../constants/topics.js'
import { useDialogStore } from '../stores/dialogStore'
import { usePostsStore } from '../stores/postsStore'

const dialog = useDialogStore()
const store = usePostsStore()
const editing = ref(null)
const rejectOpen = ref(false)
const rejectTarget = ref(null)
const rejectBulkCount = ref(null)
const rejectMode = ref('single')
const selectedIds = ref(new Set())
const bulkBusy = ref(false)
const bulkMessage = ref('')

const filterChannelId = ref(null)
const filterTopic = ref('all')
const filterOlderThanDays = ref(null)

const channelOptions = computed(() => {
  const map = new Map()
  for (const post of store.queue) {
    const ch = post.channel
    if (ch?.id) map.set(ch.id, ch)
  }
  return [...map.values()].sort((a, b) => a.name.localeCompare(b.name, 'ru'))
})

const filteredQueue = computed(() => {
  const now = Date.now()
  return store.queue.filter((post) => {
    if (filterChannelId.value != null && post.channel_id !== filterChannelId.value) {
      return false
    }
    const topic = post.channel?.topic || post.raw_post?.topic || ''
    if (filterTopic.value !== 'all' && topic !== filterTopic.value) {
      return false
    }
    if (filterOlderThanDays.value != null && post.created_at) {
      const ageMs = now - new Date(post.created_at).getTime()
      const minAgeMs = filterOlderThanDays.value * 24 * 60 * 60 * 1000
      if (ageMs < minAgeMs) return false
    }
    return true
  })
})

const hasActiveFilters = computed(
  () =>
    filterChannelId.value != null ||
    filterTopic.value !== 'all' ||
    filterOlderThanDays.value != null
)

onMounted(() => store.loadQueue())

function buildFiltersPayload() {
  const filters = {}
  if (filterChannelId.value != null) filters.channel_id = filterChannelId.value
  if (filterTopic.value !== 'all') filters.topic = filterTopic.value
  if (filterOlderThanDays.value != null) filters.older_than_days = filterOlderThanDays.value
  return filters
}

function toggleSelect(post) {
  const next = new Set(selectedIds.value)
  if (next.has(post.id)) next.delete(post.id)
  else next.add(post.id)
  selectedIds.value = next
}

function selectAllFiltered() {
  const next = new Set(selectedIds.value)
  filteredQueue.value.forEach((p) => next.add(p.id))
  selectedIds.value = next
}

function clearSelection() {
  selectedIds.value = new Set()
}

async function quickApprove(post) {
  await store.approve(post.id, {
    rewritten_text: post.rewritten_text,
    publish_immediately: false,
  })
}

function quickReject(post) {
  rejectMode.value = 'single'
  rejectBulkCount.value = null
  rejectTarget.value = post
  rejectOpen.value = true
}

function openBulkReject(count) {
  rejectMode.value = 'bulk'
  rejectBulkCount.value = count
  rejectTarget.value = null
  rejectOpen.value = true
}

async function confirmReject(reason) {
  if (rejectMode.value === 'bulk') {
    await runBulkReject(reason)
    rejectOpen.value = false
    rejectBulkCount.value = null
    return
  }

  const post = rejectTarget.value
  if (!post) return
  if (editing.value?.id === post.id) editing.value = null
  try {
    await store.reject(post.id, reason)
    selectedIds.value.delete(post.id)
    selectedIds.value = new Set(selectedIds.value)
    rejectOpen.value = false
    rejectTarget.value = null
  } catch (e) {
    await dialog.alertApiError(e, 'Не удалось отклонить пост')
    await store.loadQueue()
  }
}

async function previewBulk(payload) {
  const { data } = await store.bulkQueueAction({ ...payload, dry_run: true })
  return data
}

async function runBulkReject(reason) {
  const payload = { action: 'reject', reason, dry_run: false }
  if (rejectMode.value === 'bulk-selected') {
    payload.post_ids = [...selectedIds.value]
  } else {
    payload.filters = buildFiltersPayload()
  }

  bulkBusy.value = true
  bulkMessage.value = ''
  try {
    const result = await store.bulkQueueAction(payload)
    bulkMessage.value = result.message
    clearSelection()
  } catch (e) {
    await dialog.alertApiError(e, 'Не удалось отклонить посты')
  } finally {
    bulkBusy.value = false
  }
}

async function bulkRejectSelected() {
  if (!selectedIds.value.size) return
  rejectMode.value = 'bulk-selected'
  openBulkReject(selectedIds.value.size)
}

async function bulkRejectFiltered() {
  if (!hasActiveFilters.value) return
  try {
    const preview = await previewBulk({
      action: 'reject',
      filters: buildFiltersPayload(),
    })
    if (!preview.affected) {
      await dialog.alert({ message: 'Нет постов для отклонения по фильтру' })
      return
    }
    rejectMode.value = 'bulk'
    openBulkReject(preview.affected)
  } catch (e) {
    await dialog.alertApiError(e, 'Не удалось подготовить отклонение')
  }
}

async function bulkDeleteSelected() {
  const ids = [...selectedIds.value]
  if (!ids.length) return
  const ok = await dialog.confirm({
    title: 'Удалить выбранные',
    message: `Удалить ${ids.length} пост(ов) из очереди безвозвратно?`,
    confirmLabel: 'Удалить',
    danger: true,
  })
  if (!ok) return

  bulkBusy.value = true
  bulkMessage.value = ''
  try {
    const result = await store.bulkQueueAction({
      action: 'delete',
      post_ids: ids,
    })
    bulkMessage.value = result.message
    clearSelection()
  } catch (e) {
    await dialog.alertApiError(e, 'Не удалось удалить посты')
  } finally {
    bulkBusy.value = false
  }
}

async function bulkDeleteFiltered() {
  if (!hasActiveFilters.value) return
  bulkBusy.value = true
  try {
    const preview = await previewBulk({
      action: 'delete',
      filters: buildFiltersPayload(),
    })
    if (!preview.affected) {
      await dialog.alert({ message: 'Нет постов для удаления по фильтру' })
      return
    }
    const ok = await dialog.confirm({
      title: 'Удалить по фильтру',
      message: `${preview.message}. Это действие нельзя отменить.`,
      confirmLabel: 'Удалить',
      danger: true,
    })
    if (!ok) return

    bulkMessage.value = ''
    const result = await store.bulkQueueAction({
      action: 'delete',
      filters: buildFiltersPayload(),
    })
    bulkMessage.value = result.message
    clearSelection()
  } catch (e) {
    await dialog.alertApiError(e, 'Не удалось удалить посты')
  } finally {
    bulkBusy.value = false
  }
}
</script>

<style scoped>
.stats-row {
  @apply mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 max-w-3xl;
}

.toolbar {
  @apply mb-4 flex flex-col gap-4 p-4 md:flex-row md:items-end md:justify-between;
}

.toolbar-filters {
  @apply flex flex-wrap gap-4;
}

.filter-label {
  @apply flex flex-col gap-1 text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)];
}

.toolbar-actions {
  @apply flex flex-wrap gap-2;
}

.hint {
  @apply mb-4 text-sm;
}

.posts-grid {
  @apply grid gap-4 md:grid-cols-2 xl:grid-cols-3;
}
</style>
