<template>
  <div class="space-y-6">
    <PageHeader title="Промпты" subtitle="Все AI-промпты платформы по этапам пайплайна" />

    <div v-if="loading" class="panel-card p-6 text-sm text-[var(--text-secondary)]">
      Загрузка промптов…
    </div>
    <div v-else-if="loadError" class="panel-card p-6 text-sm text-red-500">
      {{ loadError }}
    </div>

    <section
      v-for="category in categories"
      :key="category.category"
      class="panel-card prompts-category"
    >
      <button
        type="button"
        class="category-toggle"
        @click="toggleCategory(category.category)"
      >
        <div>
          <h2 class="category-title">{{ category.label }}</h2>
          <p class="category-subtitle">
            {{ category.prompts.length }} промпт(ов)
            <span v-if="modifiedCount(category)" class="text-accent">
              · изменено: {{ modifiedCount(category) }}
            </span>
          </p>
        </div>
        <span class="chevron" :class="{ open: isOpen(category.category) }">▾</span>
      </button>

      <div v-if="isOpen(category.category)" class="space-y-3 mt-3">
        <article
          v-for="prompt in category.prompts"
          :key="prompt.key"
          class="prompt-card"
        >
          <button type="button" class="prompt-head" @click="togglePrompt(prompt.key)">
            <div class="min-w-0">
              <div class="flex flex-wrap items-center gap-2">
                <span class="prompt-name">{{ prompt.name }}</span>
                <span class="badge badge-key">{{ prompt.key }}</span>
                <span v-if="prompt.is_system_prompt" class="badge badge-system">system</span>
                <span v-if="prompt.channel_scope !== 'all'" class="badge badge-scope">
                  {{ scopeLabel(prompt.channel_scope) }}
                </span>
                <span v-if="!prompt.is_default" class="badge badge-modified">изменён</span>
              </div>
              <p class="prompt-desc">{{ prompt.description }}</p>
            </div>
            <span class="chevron" :class="{ open: openPrompts.has(prompt.key) }">▾</span>
          </button>

          <div v-if="openPrompts.has(prompt.key)" class="prompt-body">
            <div v-if="variablesOf(prompt).length" class="prompt-vars">
              Переменные:
              <code v-for="v in variablesOf(prompt)" :key="v" class="var-chip">{{ '{' + v + '}' }}</code>
            </div>
            <textarea
              v-model="drafts[prompt.key]"
              :rows="textareaRows(prompt)"
              class="input w-full font-mono text-xs"
              spellcheck="false"
            />
            <div class="prompt-actions">
              <button
                type="button"
                class="btn-primary btn-sm"
                :disabled="!isDraftDirty(prompt) || savingKey === prompt.key"
                @click="savePrompt(prompt)"
              >
                {{ savingKey === prompt.key ? 'Сохранение…' : 'Сохранить' }}
              </button>
              <button
                type="button"
                class="btn-ghost btn-sm"
                :disabled="savingKey === prompt.key"
                @click="resetPrompt(prompt)"
              >
                Сбросить к дефолту
              </button>
              <span v-if="isDraftDirty(prompt)" class="dirty-hint">не сохранено</span>
              <span v-if="prompt.updated_at" class="updated-hint">
                обновлён {{ formatDate(prompt.updated_at) }}
              </span>
            </div>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import PageHeader from '../components/layout/PageHeader.vue'
import { promptsApi } from '../api/index.js'
import { useDialogStore } from '../stores/dialogStore'

const dialog = useDialogStore()

const loading = ref(true)
const loadError = ref('')
const categories = ref([])
const drafts = reactive({})
const openCategories = ref(new Set())
const openPrompts = ref(new Set())
const savingKey = ref('')

const SCOPE_LABELS = {
  devtools: 'GitHub находки',
  paragraph: 'Параграф',
  postcard: 'Открытки',
  news: 'Новости',
}

function scopeLabel(scope) {
  return SCOPE_LABELS[scope] || scope
}

function variablesOf(prompt) {
  try {
    const parsed = JSON.parse(prompt.template_variables || '[]')
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function textareaRows(prompt) {
  const lines = (drafts[prompt.key] || '').split('\n').length
  return Math.min(28, Math.max(6, lines + 1))
}

function isOpen(cat) {
  return openCategories.value.has(cat)
}

function toggleCategory(cat) {
  const next = new Set(openCategories.value)
  if (next.has(cat)) next.delete(cat)
  else next.add(cat)
  openCategories.value = next
}

function togglePrompt(key) {
  const next = new Set(openPrompts.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  openPrompts.value = next
}

function findPrompt(key) {
  for (const cat of categories.value) {
    const found = cat.prompts.find((p) => p.key === key)
    if (found) return found
  }
  return null
}

function isDraftDirty(prompt) {
  return (drafts[prompt.key] ?? '') !== prompt.template_text
}

function modifiedCount(category) {
  return category.prompts.filter((p) => !p.is_default).length
}

function formatDate(iso) {
  try {
    return new Date(iso).toLocaleString('ru-RU')
  } catch {
    return iso
  }
}

function applyPromptUpdate(updated) {
  const existing = findPrompt(updated.key)
  if (existing) Object.assign(existing, updated)
  drafts[updated.key] = updated.template_text
}

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const { data } = await promptsApi.list()
    categories.value = data.categories
    for (const cat of data.categories) {
      for (const p of cat.prompts) {
        drafts[p.key] = p.template_text
      }
    }
    if (!openCategories.value.size && data.categories.length) {
      openCategories.value = new Set([data.categories[0].category])
    }
  } catch (err) {
    loadError.value = err.response?.data?.detail || 'Не удалось загрузить промпты'
  } finally {
    loading.value = false
  }
}

async function savePrompt(prompt) {
  savingKey.value = prompt.key
  try {
    const { data } = await promptsApi.update(prompt.key, {
      template_text: drafts[prompt.key] ?? '',
    })
    applyPromptUpdate(data)
  } catch (err) {
    await dialog.alert({
      title: 'Ошибка сохранения',
      message: err.response?.data?.detail || 'Не удалось сохранить промпт',
    })
  } finally {
    savingKey.value = ''
  }
}

async function resetPrompt(prompt) {
  const confirmed = await dialog.confirm({
    title: 'Сбросить промпт?',
    message: `«${prompt.name}» вернётся к стандартному тексту. Текущая версия будет потеряна.`,
  })
  if (!confirmed) return
  savingKey.value = prompt.key
  try {
    const { data } = await promptsApi.reset(prompt.key)
    applyPromptUpdate(data)
  } catch (err) {
    await dialog.alert({
      title: 'Ошибка сброса',
      message: err.response?.data?.detail || 'Не удалось сбросить промпт',
    })
  } finally {
    savingKey.value = ''
  }
}

onMounted(load)
</script>

<style scoped>
.prompts-category {
  @apply p-5;
}

.category-toggle {
  @apply flex w-full items-center justify-between gap-3 text-left;
}

.category-title {
  @apply text-base font-semibold text-[var(--text-primary)];
}

.category-subtitle {
  @apply mt-0.5 text-xs text-[var(--text-secondary)];
}

.chevron {
  @apply shrink-0 text-sm text-[var(--text-secondary)] transition-transform;
}

.chevron.open {
  @apply rotate-180;
}

.prompt-card {
  @apply rounded-panel border border-panel-border bg-panel-surface/60 p-4;
}

.prompt-head {
  @apply flex w-full items-start justify-between gap-3 text-left;
}

.prompt-name {
  @apply text-sm font-medium text-[var(--text-primary)];
}

.prompt-desc {
  @apply mt-1 text-xs text-[var(--text-secondary)];
}

.badge {
  @apply rounded-pill px-2 py-0.5 text-[10px] font-semibold;
}

.badge-key {
  @apply bg-panel-border/60 font-mono text-[var(--text-secondary)];
}

.badge-system {
  @apply bg-violet-500/15 text-violet-500;
}

.badge-scope {
  @apply bg-sky-500/15 text-sky-500;
}

.badge-modified {
  @apply bg-amber-500/15 text-amber-500;
}

.prompt-body {
  @apply mt-3 space-y-2;
}

.prompt-vars {
  @apply flex flex-wrap items-center gap-1.5 text-xs text-[var(--text-secondary)];
}

.var-chip {
  @apply rounded bg-panel-border/60 px-1.5 py-0.5 font-mono text-[11px] text-[var(--text-primary)];
}

.prompt-actions {
  @apply flex flex-wrap items-center gap-3;
}

.dirty-hint {
  @apply text-xs text-amber-500;
}

.updated-hint {
  @apply text-xs text-[var(--text-secondary)];
}
</style>
