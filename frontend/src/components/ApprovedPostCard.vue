<template>
  <article class="post-card">
    <div class="post-card-header">
      <div class="post-card-tags">
        <span class="badge-accent">{{ post.channel?.name || 'Канал' }}</span>
        <span class="badge-muted">{{ topicLabel }}</span>
        <span v-if="post.content_mode === 'article'" class="badge-accent">Статья</span>
        <span v-if="isFailed" class="badge-danger">Ошибка публикации</span>
      </div>
      <time
        v-if="processedAt"
        class="post-processed-at"
        :datetime="post.created_at"
        :title="processedAtTitle"
      >
        {{ processedAt }}
      </time>
    </div>

    <div v-if="publishError" class="publish-error">
      <p class="publish-error-title">Не удалось опубликовать</p>
      <p class="publish-error-text">{{ publishError }}</p>
      <p v-if="attemptAt" class="publish-error-time">Попытка: {{ attemptAt }}</p>
    </div>

    <p class="post-text">{{ previewText }}</p>

    <div v-if="hasImage" class="post-image-wrap">
      <img :src="post.generated_image_url" alt="" class="post-image" />
    </div>

    <p v-if="post.telegraph_url" class="schedule-hint">
      <a :href="post.telegraph_url" target="_blank" rel="noopener">Полная статья на Telegraph</a>
    </p>

    <div class="post-actions">
      <button type="button" class="btn-secondary btn-sm" @click="previewOpen = true">
        Предпросмотр
      </button>
      <button type="button" class="btn-secondary btn-sm" @click="$emit('edit', post)">
        Редактировать
      </button>
      <button type="button" class="btn-primary btn-sm" @click="$emit('publish', post)">
        {{ isFailed ? 'Повторить' : 'Опубликовать' }}
      </button>
      <button type="button" class="btn-danger btn-sm" @click="$emit('delete', post)">
        Удалить
      </button>
    </div>

    <TelegramPreviewModal
      :post="post"
      :open="previewOpen"
      @close="previewOpen = false"
    />
  </article>
</template>

<script setup>
import { computed, ref } from 'vue'
import TelegramPreviewModal from './TelegramPreviewModal.vue'
import { formatProcessedAt } from '../utils/datetime.js'
import { stripHtmlForPreview } from '../utils/telegramHtml.js'

const props = defineProps({ post: { type: Object, required: true } })
defineEmits(['edit', 'publish', 'delete'])

const previewOpen = ref(false)

import { topicLabel as topicLabelFromCode } from '../constants/topics.js'

const isFailed = computed(
  () => props.post.status === 'failed' || props.post.last_publish_status === 'failed',
)

const publishError = computed(() => props.post.last_publish_error || null)

const attemptAt = computed(() => {
  if (!props.post.last_publish_attempt_at) return ''
  return new Date(props.post.last_publish_attempt_at).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
})

const topicLabel = computed(() => {
  const topic = props.post.channel?.topic || props.post.raw_post?.topic || ''
  return topicLabelFromCode(topic)
})

const processedAt = computed(() => formatProcessedAt(props.post.created_at))

const processedAtTitle = computed(() => {
  if (!props.post.created_at) return ''
  return new Date(props.post.created_at).toLocaleString('ru-RU')
})

const hasImage = computed(
  () =>
    props.post.generated_image_url &&
    !props.post.generated_image_url.startsWith('telegram://')
)

const previewText = computed(() => stripHtmlForPreview(props.post.rewritten_text || ''))
</script>

<style scoped>
.post-card {
  @apply panel-card flex flex-col gap-3 p-4 transition-shadow hover:shadow-panel;
}

.post-card-header {
  @apply flex items-start justify-between gap-3;
}

.post-card-tags {
  @apply flex min-w-0 flex-1 flex-wrap items-center gap-2;
}

.post-processed-at {
  @apply shrink-0 text-[10px] font-mono leading-none text-[var(--text-secondary)] tabular-nums;
}

.post-text {
  @apply flex-1 text-sm leading-relaxed text-[var(--text-secondary)] line-clamp-4;
}

.post-image-wrap {
  @apply flex max-h-52 items-center justify-center overflow-hidden rounded-lg
    border border-panel-border bg-panel-bg;
}

.post-image {
  @apply max-h-52 w-full object-contain;
}

.schedule-hint {
  @apply text-[10px] text-[var(--text-secondary)];
}

.post-actions {
  @apply mt-auto flex flex-wrap gap-2 border-t border-panel-border/60 pt-3;
}

.badge-danger {
  @apply rounded px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide
    bg-danger/15 text-danger;
}

.publish-error {
  @apply rounded-lg border border-danger/30 bg-danger/5 px-3 py-2;
}

.publish-error-title {
  @apply text-xs font-semibold text-danger;
}

.publish-error-text {
  @apply mt-1 text-xs text-[var(--text-secondary)] break-words;
}

.publish-error-time {
  @apply mt-1 text-[10px] text-[var(--text-tertiary)];
}
</style>
