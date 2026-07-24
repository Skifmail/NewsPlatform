<template>
  <div>
    <PageHeader
      title="Одобренные"
      subtitle="Посты в очереди на публикацию по расписанию канала (МСК)"
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

    <section class="posts-section">
      <h2 class="section-title">Посты</h2>
      <p v-if="store.approvedLoading" class="empty-state">Загрузка…</p>
      <p v-else-if="store.approvedError" class="empty-state text-danger">
        {{ store.approvedError }}
      </p>
      <div v-else-if="!store.approved.length" class="empty-state">
        <p class="text-lg font-medium text-[var(--text-primary)] mb-1">Нет одобренных постов</p>
        <p class="text-sm">Одобрите посты в очереди модерации — они появятся здесь</p>
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
import { computed, onMounted, ref } from 'vue'
import PageHeader from '../components/layout/PageHeader.vue'
import ApprovedPostCard from '../components/ApprovedPostCard.vue'
import ApprovedPostEditor from '../components/ApprovedPostEditor.vue'
import { useDialogStore } from '../stores/dialogStore'
import { usePostsStore } from '../stores/postsStore'

const store = usePostsStore()
const dialog = useDialogStore()
const editing = ref(null)

const approvedCount = computed(
  () => store.approved.filter((p) => p.status === 'approved').length,
)

const failedCount = computed(
  () => store.approved.filter((p) => p.status === 'failed').length,
)

async function refresh() {
  await store.loadApproved()
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

.section-title {
  @apply mb-1 text-base font-semibold text-[var(--text-primary)];
}

.posts-section {
  @apply mt-2;
}

.posts-grid {
  @apply grid gap-4 md:grid-cols-2 xl:grid-cols-3;
}
</style>
