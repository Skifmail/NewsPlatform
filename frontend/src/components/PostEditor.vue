<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="post" class="modal-backdrop" @click.self="$emit('close')">
        <div class="modal-panel" role="dialog" aria-modal="true">
          <div class="modal-header">
            <h2 class="modal-title">Редактирование поста #{{ post.id }}</h2>
            <button type="button" class="btn-ghost btn-sm" aria-label="Закрыть" @click="$emit('close')">
              <svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div v-if="post.raw_post" class="original-block">
            <div class="original-header">
              <p class="original-label">Оригинал</p>
              <a
                v-if="post.raw_post.url"
                :href="post.raw_post.url"
                target="_blank"
                rel="noopener noreferrer"
                class="original-link"
              >
                Источник ↗
              </a>
            </div>
            <p class="original-text">{{ post.raw_post.content }}</p>
          </div>

          <label class="field-label">Текст публикации</label>
          <textarea v-model="text" rows="8" class="input mb-4 resize-y min-h-[160px]" />

          <ImagePicker
            v-model="imageUrl"
            :post="post"
            :pulling="saving"
            :fallback-url="post?.raw_post?.image_url"
            @pull-from-source="pullImage"
          />

          <div class="modal-actions">
            <button type="button" class="btn-primary" :disabled="saving" @click="approve(false)">
              Одобрить
            </button>
            <button type="button" class="btn-primary" :disabled="saving" @click="approve(true)">
              Одобрить и опубликовать
            </button>
            <button type="button" class="btn-secondary" :disabled="saving" @click="schedule">
              В расписание
            </button>
            <button type="button" class="btn-danger" :disabled="saving" @click="rejectOpen = true">
              Отклонить
            </button>
            <button type="button" class="btn-ghost" @click="$emit('close')">Закрыть</button>
          </div>
        </div>
      </div>
    </Transition>

    <RejectReasonModal
      v-model:open="rejectOpen"
      :post-id="post?.id ?? null"
      @confirm="confirmReject"
    />
  </Teleport>
</template>

<script setup>
import { ref, watch } from 'vue'
import ImagePicker from './ImagePicker.vue'
import RejectReasonModal from './RejectReasonModal.vue'
import { postsApi } from '../api/index.js'
import { useDialogStore } from '../stores/dialogStore'
import { usePostsStore } from '../stores/postsStore'
import { defaultScheduleLocalInput, localInputToIso } from '../utils/datetime.js'

const dialog = useDialogStore()

const props = defineProps({ post: { type: Object, default: null } })
const emit = defineEmits(['close'])
const store = usePostsStore()
const text = ref('')
const imageUrl = ref('')
const saving = ref(false)
const rejectOpen = ref(false)

watch(
  () => props.post,
  (p) => {
    if (p) {
      text.value = p.rewritten_text
      imageUrl.value = p.generated_image_url || p.raw_post?.image_url || ''
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

async function approve(immediate) {
  saving.value = true
  try {
    await store.approve(props.post.id, {
      rewritten_text: text.value,
      generated_image_url: imageUrl.value || null,
      publish_immediately: immediate,
    })
    emit('close')
  } finally {
    saving.value = false
  }
}

async function schedule() {
  const local = await dialog.prompt({
    title: 'В расписание',
    message: 'Укажите дату и время публикации (ваше локальное время).',
    label: 'Дата и время',
    inputType: 'datetime-local',
    defaultValue: defaultScheduleLocalInput(),
    confirmLabel: 'Запланировать',
  })
  const at = localInputToIso(local)
  if (!at) return
  saving.value = true
  try {
    await store.schedule(props.post.id, at)
    emit('close')
  } finally {
    saving.value = false
  }
}

async function confirmReject(reason) {
  saving.value = true
  try {
    await store.reject(props.post.id, reason)
    rejectOpen.value = false
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

.original-block {
  @apply mb-4 rounded-lg border border-panel-border bg-panel-bg p-3;
}

.original-header {
  @apply mb-1 flex items-center justify-between gap-2;
}

.original-label {
  @apply text-xs font-medium uppercase tracking-wider text-accent;
}

.original-link {
  @apply shrink-0 text-xs text-accent hover:underline;
}

.original-text {
  @apply text-xs leading-relaxed text-[var(--text-secondary)] line-clamp-6;
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

.modal-enter-active .modal-panel,
.modal-leave-active .modal-panel {
  transition: transform 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .modal-panel,
.modal-leave-to .modal-panel {
  transform: scale(0.96) translateY(8px);
}
</style>
