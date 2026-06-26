<template>
  <div>
    <PageHeader
      title="Одобренные"
      subtitle="Посты в очереди на публикацию — расписание по каналам"
    >
      <template #actions>
        <button class="btn-secondary btn-sm" type="button" @click="refresh">
          Обновить
        </button>
      </template>
    </PageHeader>

    <div class="stats-row">
      <div class="stat-card">
        <span class="stat-label">К публикации</span>
        <span class="stat-value text-accent">{{ approvedCount }}</span>
      </div>
      <div v-if="failedCount" class="stat-card">
        <span class="stat-label">С ошибкой</span>
        <span class="stat-value text-danger">{{ failedCount }}</span>
      </div>
    </div>

    <section class="schedule-section">
      <h2 class="section-title">Расписание по каналам</h2>
      <p class="section-hint">
        Интервал между постами и окно публикации (UTC). После сохранения очередь канала
        пересчитывается.
      </p>
      <div v-if="!channels.length" class="empty-state text-sm">Нет каналов</div>
      <div v-else class="channel-schedule-list">
        <article v-for="ch in channels" :key="ch.id" class="schedule-card">
          <div class="schedule-card-head">
            <h3>{{ ch.name }}</h3>
            <span class="badge-info">{{ ch.platform }}</span>
          </div>
          <div class="schedule-fields">
            <label class="field-mini">
              <span>Интервал (мин)</span>
              <input
                v-model.number="scheduleDraft[ch.id].interval"
                type="number"
                min="1"
                max="1440"
                class="input input-sm"
              />
            </label>
            <label class="field-mini">
              <span>Окно с (UTC)</span>
              <input
                v-model="scheduleDraft[ch.id].start"
                type="time"
                class="input input-sm"
              />
            </label>
            <label class="field-mini">
              <span>Окно до (UTC)</span>
              <input
                v-model="scheduleDraft[ch.id].end"
                type="time"
                class="input input-sm"
              />
            </label>
          </div>
          <div class="schedule-actions">
            <button
              type="button"
              class="btn-secondary btn-sm"
              :disabled="savingChannel === ch.id"
              @click="saveChannelSchedule(ch.id)"
            >
              Сохранить
            </button>
            <button
              type="button"
              class="btn-ghost btn-sm"
              :disabled="savingChannel === ch.id"
              @click="recalcChannel(ch.id)"
            >
              Пересчитать очередь
            </button>
          </div>
        </article>
      </div>
    </section>

    <section class="posts-section">
      <h2 class="section-title">Посты</h2>
      <p v-if="store.approvedLoading" class="empty-state">Загрузка…</p>
      <p v-else-if="store.approvedError" class="empty-state text-danger">
        {{ store.approvedError }}
      </p>
      <div v-else-if="!store.approved.length" class="empty-state">
        <p class="text-lg font-medium text-[var(--text-primary)] mb-1">Нет одобренных постов</p>
        <p class="text-sm">Одобрите посты в очереди модерации — они появятся здесь с таймером</p>
      </div>
      <div v-else class="posts-grid">
        <ApprovedPostCard
          v-for="post in store.approved"
          :key="post.id"
          :post="post"
          @edit="editing = post"
          @publish="quickPublish(post)"
          @delete="quickDelete(post)"
        />
      </div>
    </section>

    <ApprovedPostEditor :post="editing" @close="editing = null" @saved="refresh" />
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import PageHeader from '../components/layout/PageHeader.vue'
import ApprovedPostCard from '../components/ApprovedPostCard.vue'
import ApprovedPostEditor from '../components/ApprovedPostEditor.vue'
import { channelsApi } from '../api/index.js'
import { useDialogStore } from '../stores/dialogStore'
import { usePostsStore } from '../stores/postsStore'

const store = usePostsStore()
const dialog = useDialogStore()
const channels = ref([])
const scheduleDraft = reactive({})
const editing = ref(null)
const savingChannel = ref(null)

const approvedCount = computed(
  () => store.approved.filter((p) => p.status === 'approved').length,
)

const failedCount = computed(
  () => store.approved.filter((p) => p.status === 'failed').length,
)

function hhmmFromChannel(value) {
  if (!value) return '08:00'
  return value.length >= 5 ? value.slice(0, 5) : value
}

function timeInputToApi(t) {
  if (!t) return '08:00'
  return t.length === 5 ? t : t.slice(0, 5)
}

async function loadChannels() {
  const { data } = await channelsApi.list()
  channels.value = data
  data.forEach((ch) => {
    scheduleDraft[ch.id] = {
      interval: ch.publish_interval_minutes ?? 60,
      start: hhmmFromChannel(ch.publish_window_start),
      end: hhmmFromChannel(ch.publish_window_end),
    }
  })
}

async function refresh() {
  await Promise.all([store.loadApproved(), loadChannels()])
}

async function saveChannelSchedule(channelId) {
  const d = scheduleDraft[channelId]
  if (!d) return
  savingChannel.value = channelId
  try {
    await channelsApi.update(channelId, {
      publish_interval_minutes: d.interval,
      publish_window_start: timeInputToApi(d.start),
      publish_window_end: timeInputToApi(d.end),
    })
    await refresh()
  } catch (e) {
    await dialog.alertApiError(e, 'Не удалось сохранить')
  } finally {
    savingChannel.value = null
  }
}

async function recalcChannel(channelId) {
  savingChannel.value = channelId
  try {
    await channelsApi.recalculateSchedule(channelId)
    await store.loadApproved()
  } catch (e) {
    await dialog.alertApiError(e, 'Ошибка пересчёта')
  } finally {
    savingChannel.value = null
  }
}

async function quickPublish(post) {
  const isRetry = post.status === 'failed'
  const ok = await dialog.confirm({
    title: isRetry ? 'Повтор публикации' : 'Публикация',
    message: isRetry
      ? `Повторить публикацию в «${post.channel?.name}»?`
      : `Опубликовать «${post.channel?.name}» сейчас?`,
    confirmLabel: isRetry ? 'Повторить' : 'Опубликовать',
  })
  if (!ok) return
  try {
    await store.publishNow(post.id)
    await store.loadApproved()
  } catch (e) {
    await dialog.alertApiError(e, 'Ошибка публикации')
    await store.loadApproved()
  }
}

async function quickDelete(post) {
  const ok = await dialog.confirm({
    title: 'Удаление',
    message: 'Удалить пост?',
    confirmLabel: 'Удалить',
    danger: true,
  })
  if (!ok) return
  if (editing.value?.id === post.id) editing.value = null
  try {
    await store.deletePost(post.id)
  } catch (e) {
    await dialog.alertApiError(e, 'Не удалось удалить')
  }
}

onMounted(() => refresh())
</script>

<style scoped>
.stats-row {
  @apply mb-6 grid gap-4 sm:grid-cols-2 max-w-md;
}

.schedule-section {
  @apply mb-8;
}

.section-title {
  @apply mb-1 text-base font-semibold text-[var(--text-primary)];
}

.section-hint {
  @apply mb-4 text-sm text-[var(--text-secondary)];
}

.channel-schedule-list {
  @apply grid gap-4 md:grid-cols-2;
}

.schedule-card {
  @apply panel-card p-4;
}

.schedule-card-head {
  @apply mb-3 flex items-center justify-between gap-2;
}

.schedule-card-head h3 {
  @apply text-sm font-semibold text-[var(--text-primary)];
}

.schedule-fields {
  @apply grid gap-3 sm:grid-cols-3;
}

.field-mini {
  @apply flex flex-col gap-1 text-xs text-[var(--text-secondary)];
}

.schedule-actions {
  @apply mt-3 flex flex-wrap gap-2;
}

.posts-section {
  @apply mt-2;
}

.posts-grid {
  @apply grid gap-4 md:grid-cols-2 xl:grid-cols-3;
}
</style>
