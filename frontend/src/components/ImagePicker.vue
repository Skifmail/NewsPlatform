<template>
  <div class="image-picker">
    <div class="picker-head">
      <label class="field-label">Изображение</label>
      <button
        type="button"
        class="btn-ghost btn-sm"
        :disabled="pulling"
        @click="$emit('pull-from-source')"
      >
        {{ pulling ? 'Загрузка…' : 'Из источника' }}
      </button>
    </div>
    <input
      :value="modelValue"
      type="url"
      class="input"
      placeholder="https://..."
      @input="$emit('update:modelValue', $event.target.value)"
    />
    <p v-if="fallbackHint" class="fallback-hint">{{ fallbackHint }}</p>
    <div v-if="showPreview" class="preview-wrap">
      <img :src="modelValue" alt="preview" class="preview-img" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  post: { type: Object, default: null },
  fallbackUrl: { type: String, default: '' },
  pulling: { type: Boolean, default: false },
})
defineEmits(['update:modelValue', 'pull-from-source'])

const showPreview = computed(
  () => props.modelValue && !props.modelValue.startsWith('telegram://')
)

const fallbackHint = computed(() => {
  if (props.modelValue || !props.fallbackUrl) return ''
  return 'В материале есть картинка — нажмите «Из источника» или вставьте URL'
})
</script>

<style scoped>
.image-picker {
  @apply mt-2;
}

.picker-head {
  @apply mb-1.5 flex items-center justify-between gap-2;
}

.field-label {
  @apply text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)];
}

.fallback-hint {
  @apply mt-2 text-xs text-[var(--text-secondary)];
}

.preview-wrap {
  @apply mt-3 flex max-h-[min(50vh,28rem)] items-center justify-center overflow-hidden
    rounded-lg border border-panel-border bg-panel-bg;
}

.preview-img {
  @apply max-h-[min(50vh,28rem)] w-full object-contain;
}
</style>
