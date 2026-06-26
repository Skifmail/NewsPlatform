<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="post" class="modal-backdrop" @click.self="$emit('close')">
        <div class="modal-panel" role="dialog" aria-modal="true">
          <div class="modal-header">
            <h2 class="modal-title">Пост #{{ post.id }} · {{ post.channel?.name }}</h2>
            <button type="button" class="btn-ghost btn-sm" aria-label="Закрыть" @click="$emit('close')">
              <svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <PublishCountdown :scheduled-at="scheduledAt || post.scheduled_at" class="mb-4" />

          <label class="field-label">Текст публикации</label>
          <textarea v-model="text" rows="8" class="input mb-4 resize-y min-h-[160px]" />

          <ImagePicker
            v-model="imageUrl"
            :post="post"
            :pulling="saving"
            :fallback-url="post?.raw_post?.image_url"
            @pull-from-source="pullImage"
          />

          <label class="field-label mt-4">Время публикации (локальное)</label>
          <input v-model="scheduledLocal" type="datetime-local" class="input mb-4" />

          <div class="modal-actions">
            <button type="button" class="btn-primary" :disabled="saving" @click="save">
              Сохранить
            </button>
            <button type="button" class="btn-primary" :disabled="saving" @click="publish">
              Опубликовать сейчас
            </button>
            <button type="button" class="btn-danger" :disabled="saving" @click="remove">
              Удалить
            </button>
            <button type="button" class="btn-ghost" @click="$emit('close')">Закрыть</button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, watch } from 'vue'
import ImagePicker from './ImagePicker.vue'
import PublishCountdown from './PublishCountdown.vue'
import { postsApi } from '../api/index.js'
import { useDialogStore } from '../stores/dialogStore'
import { usePostsStore } from '../stores/postsStore'

const dialog = useDialogStore()

const props = defineProps({ post: { type: Object, default: null } })
const emit = defineEmits(['close', 'saved'])
const store = usePostsStore()
const text = ref('')
const imageUrl = ref('')
const scheduledLocal = ref('')
const scheduledAt = ref(null)
const saving = ref(false)

function toLocalInput(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function localToIso(local) {
  if (!local) return null
  return new Date(local).toISOString()
}

watch(
  () => props.post,
  (p) => {
    if (p) {
      text.value = p.rewritten_text
      imageUrl.value = p.generated_image_url || p.raw_post?.image_url || ''
      scheduledLocal.value = toLocalInput(p.scheduled_at)
      scheduledAt.value = p.scheduled_at
    }
  },
  { immediate: true }
)

async function pullImage() {
  saving.value = true
  try {
    const { data } = await postsApi.refreshImage(props.post.id)
    imageUrl.value = data.generated_image_url || ''
  } catch (e) {
    await dialog.alertApiError(e, 'Не удалось подтянуть изображение')
  } finally {
    saving.value = false
  }
}

async function save() {
  saving.value = true
  try {
    const iso = localToIso(scheduledLocal.value)
    await store.updatePost(props.post.id, {
      rewritten_text: text.value,
      generated_image_url: imageUrl.value || null,
      scheduled_at: iso,
    })
    scheduledAt.value = iso
    emit('saved')
    emit('close')
  } finally {
    saving.value = false
  }
}

async function publish() {
  const ok = await dialog.confirm({
    title: 'Публикация',
    message: 'Опубликовать пост в канал сейчас?',
    confirmLabel: 'Опубликовать',
  })
  if (!ok) return
  saving.value = true
  try {
    await store.publishNow(props.post.id)
    emit('close')
  } finally {
    saving.value = false
  }
}

async function remove() {
  const ok = await dialog.confirm({
    title: 'Удаление',
    message: 'Удалить пост без публикации?',
    confirmLabel: 'Удалить',
    danger: true,
  })
  if (!ok) return
  saving.value = true
  try {
    await store.deletePost(props.post.id)
    emit('close')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.modal-backdrop {
  @apply fixed inset-0 z-50 flex items-center justify-center bg-[var(--overlay-bg)] p-4 backdrop-blur-sm;
}

.modal-panel {
  @apply panel-card-elevated max-h-[90vh] w-full max-w-2xl overflow-y-auto p-6 shadow-panel;
}

.modal-header {
  @apply mb-5 flex items-start justify-between gap-4;
}

.modal-title {
  @apply text-lg font-semibold text-[var(--text-primary)];
}

.field-label {
  @apply mb-1.5 block text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)];
}

.modal-actions {
  @apply mt-6 flex flex-wrap gap-2 border-t border-panel-border pt-4;
}

.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
</style>
