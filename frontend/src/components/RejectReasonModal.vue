<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="open"
        class="modal-backdrop"
        role="presentation"
        @click.self="close"
      >
        <div class="modal-panel" role="dialog" aria-modal="true" aria-labelledby="reject-title">
          <div class="modal-header">
            <h2 id="reject-title" class="modal-title">
              <template v-if="count && count > 1">Отклонить {{ count }} постов</template>
              <template v-else>
                Отклонить пост<span v-if="postId"> #{{ postId }}</span>
              </template>
            </h2>
            <button
              type="button"
              class="btn-ghost btn-sm"
              aria-label="Закрыть"
              @click="close"
            >
              <svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <p class="modal-hint">Укажите причину или выберите готовый вариант.</p>

          <div class="preset-row">
            <button
              v-for="preset in REJECT_REASON_PRESETS"
              :key="preset"
              type="button"
              class="preset-chip"
              :class="{ 'preset-chip-active': reason === preset }"
              @click="reason = preset"
            >
              {{ preset }}
            </button>
          </div>

          <label class="field-label" for="reject-reason-input">Причина отклонения</label>
          <textarea
            id="reject-reason-input"
            v-model="reason"
            rows="3"
            class="input resize-y min-h-[88px]"
            placeholder="Введите причину…"
            @keydown.enter.exact.prevent="submit"
          />

          <p v-if="error" class="error-text">{{ error }}</p>

          <div class="modal-actions">
            <button type="button" class="btn-danger" @click="submit">
              Отклонить
            </button>
            <button type="button" class="btn-ghost" @click="close">
              Отмена
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, watch } from 'vue'
import { REJECT_REASON_PRESETS } from '../constants/rejectReasons.js'

const props = defineProps({
  open: { type: Boolean, default: false },
  postId: { type: Number, default: null },
  count: { type: Number, default: null },
})

const emit = defineEmits(['update:open', 'confirm'])

const reason = ref('')
const error = ref('')

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      reason.value = ''
      error.value = ''
    }
  }
)

function close() {
  emit('update:open', false)
}

function submit() {
  const trimmed = reason.value.trim()
  if (!trimmed) {
    error.value = 'Укажите причину отклонения'
    return
  }
  error.value = ''
  emit('confirm', trimmed)
}
</script>

<style scoped>
.modal-backdrop {
  @apply fixed inset-0 z-[65] flex items-center justify-center bg-[var(--overlay-bg)] p-4 backdrop-blur-sm;
}

.modal-panel {
  @apply panel-card-elevated w-full max-w-md p-6 shadow-panel;
}

.modal-header {
  @apply mb-3 flex items-start justify-between gap-4;
}

.modal-title {
  @apply text-lg font-semibold text-[var(--text-primary)];
}

.modal-hint {
  @apply mb-4 text-sm text-[var(--text-secondary)];
}

.preset-row {
  @apply mb-4 flex flex-wrap gap-2;
}

.preset-chip {
  @apply rounded-pill border border-panel-border bg-panel-bg px-3 py-1.5 text-xs
    text-[var(--text-secondary)] transition-colors hover:border-accent/40 hover:text-accent;
}

.preset-chip-active {
  @apply border-accent/50 bg-accent-muted text-accent;
}

.field-label {
  @apply mb-1.5 block text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)];
}

.error-text {
  @apply mt-2 text-sm text-danger;
}

.modal-actions {
  @apply mt-5 flex flex-wrap gap-2 border-t border-panel-border pt-4;
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
