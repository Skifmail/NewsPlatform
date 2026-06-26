<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="dialog.active"
        class="modal-backdrop"
        role="presentation"
        @click.self="dialog.cancelAction()"
      >
        <div
          class="modal-panel"
          :class="{ 'modal-panel-wide': dialog.active?.kind === 'unsaved' }"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="dialog.active.kind + '-dialog-title'"
        >
          <div class="modal-header">
            <h2 :id="dialog.active.kind + '-dialog-title'" class="modal-title">
              {{ dialog.active.title }}
            </h2>
            <button
              type="button"
              class="btn-ghost btn-sm"
              aria-label="Закрыть"
              @click="dialog.cancelAction()"
            >
              <svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <p v-if="dialog.active.message" class="modal-message">
            {{ dialog.active.message }}
          </p>

          <div v-if="dialog.active.kind === 'prompt'" class="prompt-field">
            <label v-if="dialog.active.label" class="field-label">{{ dialog.active.label }}</label>
            <input
              v-if="dialog.active.inputType !== 'textarea'"
              v-model="dialog.active.inputValue"
              :type="dialog.active.inputType"
              class="input"
              :placeholder="dialog.active.placeholder"
              @keydown.enter.prevent="dialog.confirmAction()"
            />
            <textarea
              v-else
              v-model="dialog.active.inputValue"
              rows="3"
              class="input resize-y"
              :placeholder="dialog.active.placeholder"
            />
          </div>

          <div v-if="dialog.active.kind === 'unsaved'" class="modal-actions modal-actions-unsaved">
            <button type="button" class="btn-secondary" @click="dialog.cancelAction()">
              {{ dialog.active.stayLabel }}
            </button>
            <button
              type="button"
              class="btn-secondary"
              @click="dialog.chooseAction('discard')"
            >
              {{ dialog.active.discardLabel }}
            </button>
            <button
              type="button"
              class="btn-primary"
              @click="dialog.chooseAction('save')"
            >
              {{ dialog.active.saveLabel }}
            </button>
          </div>
          <div v-else class="modal-actions">
            <button
              v-if="dialog.active.kind !== 'alert'"
              type="button"
              class="btn-ghost"
              @click="dialog.cancelAction()"
            >
              {{ dialog.active.cancelLabel }}
            </button>
            <button
              type="button"
              :class="confirmButtonClass"
              @click="dialog.confirmAction()"
            >
              {{ dialog.active.confirmLabel }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed } from 'vue'
import { useDialogStore } from '../stores/dialogStore'

const dialog = useDialogStore()

const confirmButtonClass = computed(() => {
  if (!dialog.active) return 'btn-primary'
  if (dialog.active.kind === 'confirm' && dialog.active.danger) return 'btn-danger'
  return 'btn-primary'
})
</script>

<style scoped>
.modal-backdrop {
  @apply fixed inset-0 z-[70] flex items-center justify-center bg-[var(--overlay-bg)] p-4 backdrop-blur-sm;
}

.modal-panel {
  @apply panel-card-elevated w-full max-w-md p-6 shadow-panel;
}

.modal-panel-wide {
  @apply max-w-2xl;
}

.modal-header {
  @apply mb-3 flex items-start justify-between gap-4;
}

.modal-title {
  @apply text-lg font-semibold text-[var(--text-primary)];
}

.modal-message {
  @apply mb-4 text-sm leading-relaxed text-[var(--text-secondary)] whitespace-pre-line;
}

.prompt-field {
  @apply mb-4;
}

.field-label {
  @apply mb-1.5 block text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)];
}

.modal-actions {
  @apply flex flex-wrap justify-end gap-2 border-t border-panel-border pt-4;
}

.modal-actions-unsaved {
  @apply grid grid-cols-3 gap-2;
}

.modal-actions-unsaved button {
  @apply w-full min-w-0 px-2 text-center text-xs sm:text-sm;
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
