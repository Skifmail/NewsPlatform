<template>
  <Teleport to="body">
    <Transition name="preview-modal">
      <div v-if="open && post" class="preview-backdrop" @click.self="$emit('close')">
        <div class="preview-shell" role="dialog" aria-modal="true" aria-label="Предпросмотр Telegram">
          <div class="preview-toolbar">
            <div>
              <h2 class="preview-title">Предпросмотр в Telegram</h2>
              <p class="preview-subtitle">
                Как увидят подписчики канала «{{ channelName }}»
              </p>
            </div>
            <button type="button" class="btn-ghost btn-sm" aria-label="Закрыть" @click="$emit('close')">
              <svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <p v-if="splitPublish" class="split-hint">
            Текст длиннее {{ captionLimit }} символов —
            без userbot опубликуется фото и текст ответом.
          </p>
          <p v-else-if="hasImageUrl" class="split-hint split-hint--ok">
            Пост с картинкой — одно сообщение (userbot, до {{ TELEGRAM_USER_CAPTION_MAX }} символов).
          </p>

          <div class="tg-phone">
            <div class="tg-phone-notch" aria-hidden="true" />

            <div class="tg-channel-bar">
              <div class="tg-channel-avatar" aria-hidden="true">{{ channelInitial }}</div>
              <div class="tg-channel-meta">
                <span class="tg-channel-name">{{ channelName }}</span>
                <span class="tg-channel-sub">канал</span>
              </div>
            </div>

            <div class="tg-feed">
              <!-- Режим: одно сообщение (фото + подпись) -->
              <article v-if="!splitPublish" class="tg-post">
                <div v-if="hasImageUrl" class="tg-media">
                  <img
                    :src="imageUrl"
                    alt=""
                    class="tg-media-img"
                    @error="imageFailed = true"
                  />
                  <div v-if="imageFailed" class="tg-media-fallback">Изображение недоступно</div>
                </div>
                <div
                  class="tg-message-body"
                  :class="{ 'tg-message-body--caption': hasImageUrl }"
                  v-html="previewHtml"
                />
                <footer class="tg-post-footer">
                  <span class="tg-views">👁 {{ mockViews }}</span>
                  <time class="tg-time">{{ mockTime }}</time>
                </footer>
              </article>

              <!-- Режим: фото + ответ с текстом -->
              <template v-else>
                <article class="tg-post">
                  <div v-if="hasImageUrl" class="tg-media">
                    <img
                      :src="imageUrl"
                      alt=""
                      class="tg-media-img"
                      @error="imageFailed = true"
                    />
                    <div v-if="imageFailed" class="tg-media-fallback">Изображение недоступно</div>
                  </div>
                  <footer class="tg-post-footer">
                    <span class="tg-views">👁 {{ mockViews }}</span>
                    <time class="tg-time">{{ mockTime }}</time>
                  </footer>
                </article>

                <article class="tg-post tg-post--reply">
                  <div class="tg-reply-line" aria-hidden="true" />
                  <div class="tg-message-body" v-html="previewHtml" />
                  <footer class="tg-post-footer">
                    <span class="tg-views">👁 {{ mockViews }}</span>
                    <time class="tg-time">{{ mockTimeReply }}</time>
                  </footer>
                </article>
              </template>
            </div>
          </div>

          <p class="preview-footnote">
            Форматирование: HTML (жирный, курсив, ссылки). Хэштеги добавляются при публикации отдельно.
          </p>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import {
  TELEGRAM_CAPTION_MAX,
  TELEGRAM_USER_CAPTION_MAX,
  buildArticlePreviewText,
  formatTelegramPreviewHtml,
  isLongFormTelegramChannel,
  usesSplitTelegramPublish,
} from '../utils/telegramHtml.js'

const props = defineProps({
  post: { type: Object, default: null },
  open: { type: Boolean, default: false },
})

defineEmits(['close'])

const imageFailed = ref(false)

watch(
  () => props.post?.id,
  () => {
    imageFailed.value = false
  }
)

const channelName = computed(() => props.post?.channel?.name || 'Канал')

const channelInitial = computed(() => {
  const name = channelName.value.trim()
  return name ? name.charAt(0).toUpperCase() : 'T'
})

const imageUrl = computed(() => props.post?.generated_image_url || '')

const hasImageUrl = computed(
  () => imageUrl.value && !imageUrl.value.startsWith('telegram://')
)

const longFormChannel = computed(() =>
  isLongFormTelegramChannel(props.post?.channel)
)

const publishText = computed(() => {
  if (props.post?.content_mode === 'article' && longFormChannel.value) {
    return buildArticlePreviewText(props.post)
  }
  return props.post?.rewritten_text || ''
})

const previewHtml = computed(() =>
  formatTelegramPreviewHtml(publishText.value)
)

const captionLimit = computed(() =>
  hasImageUrl.value ? TELEGRAM_USER_CAPTION_MAX : TELEGRAM_CAPTION_MAX
)

const splitPublish = computed(() =>
  usesSplitTelegramPublish(publishText.value, hasImageUrl.value, {
    longForm: hasImageUrl.value || longFormChannel.value,
  })
)

const mockViews = computed(() => {
  const id = props.post?.id || 1
  return ((id * 137) % 9000 + 120).toLocaleString('ru-RU')
})

const mockTime = computed(() => {
  const iso = props.post?.created_at
  if (!iso) return 'сейчас'
  return new Date(iso).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
})

const mockTimeReply = computed(() => {
  const iso = props.post?.created_at
  if (!iso) return 'сейчас'
  const d = new Date(iso)
  d.setMinutes(d.getMinutes() + 1)
  return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
})
</script>

<style scoped>
.preview-backdrop {
  @apply fixed inset-0 z-[60] flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm;
}

.preview-shell {
  @apply w-full max-w-md max-h-[92vh] overflow-y-auto rounded-2xl border border-panel-border
    bg-panel-surface p-4 shadow-panel;
}

.preview-toolbar {
  @apply mb-4 flex items-start justify-between gap-3;
}

.preview-title {
  @apply text-base font-semibold text-[var(--text-primary)];
}

.preview-subtitle {
  @apply text-xs text-[var(--text-secondary)] mt-0.5;
}

.split-hint {
  @apply mb-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs
    leading-relaxed text-amber-200/90;
}

.split-hint--ok {
  @apply border-emerald-500/30 bg-emerald-500/10 text-emerald-200/90;
}

.tg-phone {
  @apply overflow-hidden rounded-2xl border border-[#0d1218];
  background: #17212b;
}

.tg-phone-notch {
  @apply mx-auto mt-2 h-1 w-16 rounded-full bg-[#2b3945];
}

.tg-channel-bar {
  @apply flex items-center gap-3 border-b border-[#0d1218] px-4 py-3;
  background: #232e3c;
}

.tg-channel-avatar {
  @apply flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white;
  background: linear-gradient(135deg, #2aabee, #229ed9);
}

.tg-channel-meta {
  @apply flex min-w-0 flex-col;
}

.tg-channel-name {
  @apply truncate text-sm font-semibold text-white;
}

.tg-channel-sub {
  @apply text-xs text-[#7f91a4];
}

.tg-feed {
  @apply px-3 py-4 space-y-3;
  background: #0e1621;
}

.tg-post {
  @apply relative overflow-hidden rounded-xl;
  background: #182533;
}

.tg-post--reply {
  @apply ml-4;
}

.tg-reply-line {
  @apply absolute left-0 top-0 bottom-0 w-0.5;
  background: #2aabee;
}

.tg-media {
  @apply relative w-full bg-[#0e1621];
}

.tg-media-img {
  @apply block w-full max-h-[320px] object-cover;
}

.tg-media-fallback {
  @apply flex h-40 items-center justify-center text-sm text-[#7f91a4];
  background: #1c2733;
}

.tg-message-body {
  @apply px-3 py-3 text-[15px] leading-[1.45] text-white;
  word-break: break-word;
}

.tg-message-body--caption {
  @apply pt-2;
}

.tg-message-body :deep(p) {
  @apply mb-3 last:mb-0;
}

.tg-message-body :deep(p + p) {
  @apply mt-1;
}

.tg-message-body :deep(b),
.tg-message-body :deep(strong) {
  @apply font-semibold text-white;
}

.tg-message-body :deep(i),
.tg-message-body :deep(em) {
  @apply italic text-[#e8edf2];
}

.tg-message-body :deep(blockquote) {
  @apply relative my-3 rounded-r-lg border-l-[3px] border-[#2aabee] px-3 py-2.5 text-[14px]
    leading-relaxed text-[#c5d3e0];
  background: rgba(30, 44, 58, 0.95);
}

.tg-message-body :deep(blockquote)::before {
  content: '“';
  @apply absolute right-2 top-1 text-2xl leading-none text-[#4a5f73];
}

.tg-message-body :deep(a) {
  color: #6ab3f3;
  text-decoration: none;
}

.tg-message-body :deep(a:hover) {
  text-decoration: underline;
}

.tg-post-footer {
  @apply flex items-center justify-end gap-3 px-3 pb-2 text-[11px] text-[#7f91a4];
}

.tg-views {
  @apply tabular-nums;
}

.preview-footnote {
  @apply mt-3 text-[10px] leading-relaxed text-[var(--text-secondary)];
}

.preview-modal-enter-active,
.preview-modal-leave-active {
  transition: opacity 0.2s ease;
}

.preview-modal-enter-active .preview-shell,
.preview-modal-leave-active .preview-shell {
  transition: transform 0.2s ease;
}

.preview-modal-enter-from,
.preview-modal-leave-to {
  opacity: 0;
}

.preview-modal-enter-from .preview-shell,
.preview-modal-leave-to .preview-shell {
  transform: scale(0.96) translateY(8px);
}
</style>
