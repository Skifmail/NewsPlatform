<template>
  <article class="post-card" :class="{ 'post-card-selected': selected }">
    <div class="post-card-top">
      <label v-if="selectable" class="post-select">
        <input
          type="checkbox"
          :checked="selected"
          @change="$emit('toggle-select', post)"
        />
      </label>
      <div class="post-card-header">
      <div class="post-card-tags">
        <span class="badge-accent">{{ post.channel?.name || 'Канал' }}</span>
        <span class="badge-muted">{{ topicLabel }}</span>
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
    </div>

    <p class="post-text">{{ previewText }}</p>

    <div v-if="hasImage" class="post-image-wrap">
      <img :src="post.generated_image_url" alt="" class="post-image" />
    </div>

    <div class="post-actions">
      <button type="button" class="btn-secondary btn-sm" @click="previewOpen = true">
        Предпросмотр
      </button>
      <button type="button" class="btn-secondary btn-sm" @click="$emit('edit', post)">
        Редактировать
      </button>
      <button type="button" class="btn-primary btn-sm" @click="$emit('approve', post)">
        Одобрить
      </button>
      <button type="button" class="btn-danger btn-sm" @click="$emit('reject', post)">
        Отклонить
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
import { topicLabel as topicLabelFromCode } from '../constants/topics.js'
import { formatProcessedAt } from '../utils/datetime.js'
import { stripHtmlForPreview } from '../utils/telegramHtml.js'

const props = defineProps({
  post: { type: Object, required: true },
  selectable: { type: Boolean, default: false },
  selected: { type: Boolean, default: false },
})
defineEmits(['edit', 'approve', 'reject', 'toggle-select'])

const previewOpen = ref(false)

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
  @apply panel-card flex flex-col p-4 transition-shadow hover:shadow-panel;
}

.post-card-selected {
  @apply ring-1 ring-accent/40;
}

.post-card-top {
  @apply mb-3 flex items-start gap-2;
}

.post-select {
  @apply mt-0.5 shrink-0;
}

.post-card-header {
  @apply flex min-w-0 flex-1 items-start justify-between gap-3;
}

.post-card-tags {
  @apply flex min-w-0 flex-1 flex-wrap items-center gap-2;
}

.post-processed-at {
  @apply shrink-0 text-[10px] font-mono leading-none text-[var(--text-secondary)] tabular-nums;
}

.post-text {
  @apply mb-3 flex-1 text-sm leading-relaxed text-[var(--text-secondary)] line-clamp-4;
}

.post-image-wrap {
  @apply mb-3 flex max-h-52 items-center justify-center overflow-hidden rounded-lg
    border border-panel-border bg-panel-bg;
}

.post-image {
  @apply max-h-52 w-full object-contain;
}

.post-actions {
  @apply mt-auto flex flex-wrap gap-2 border-t border-panel-border/60 pt-3;
}
</style>
