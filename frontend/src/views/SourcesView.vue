<template>
  <div>
    <PageHeader
      title="Источники"
      subtitle="RSS, Telegram и веб-источники для парсинга контента"
    />

    <form class="form-card" @submit.prevent="create">
      <h3 class="form-card-title">Добавить источник</h3>
      <div class="form-grid">
        <input v-model="form.name" placeholder="Название" class="input" required />
        <select v-model="form.type" class="select">
          <option value="rss">RSS</option>
          <option value="telegram">Telegram</option>
          <option value="web">Web</option>
        </select>
        <input v-model="form.url" placeholder="URL" class="input form-url" required />
        <select v-model="form.topic" class="select">
          <option v-for="opt in TOPIC_OPTIONS" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
        <div class="form-actions">
          <button type="submit" class="btn-primary">Добавить</button>
        </div>
      </div>
    </form>

    <div v-if="!sources.length" class="empty-state">Источники не настроены</div>
    <template v-else>
      <div class="sources-cards">
        <article v-for="s in sources" :key="`card-${s.id}`" class="source-card panel-card">
          <div class="source-card-head">
            <h3 class="source-name">{{ s.name }}</h3>
            <div class="source-badges">
              <span class="badge-info">{{ typeLabel(s.type) }}</span>
              <span class="badge-purple">{{ topicLabel(s.topic) }}</span>
            </div>
          </div>
          <p class="source-url" :title="s.url">{{ s.url }}</p>
          <div class="source-card-actions">
            <button type="button" class="btn-secondary btn-sm" @click="fetch(s.id)">
              Парсить
            </button>
            <button type="button" class="btn-danger btn-sm" @click="remove(s.id)">
              Удалить
            </button>
          </div>
        </article>
      </div>

      <div class="table-wrap panel-card sources-table">
        <table class="table-panel">
          <thead>
            <tr>
              <th>Название</th>
              <th>Тип</th>
              <th>Тема</th>
              <th class="text-right">Действия</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in sources" :key="s.id">
              <td>
                <span class="font-medium text-[var(--text-primary)]">{{ s.name }}</span>
                <p class="text-xs text-[var(--text-secondary)] truncate max-w-xs mt-0.5">{{ s.url }}</p>
              </td>
              <td><span class="badge-info">{{ typeLabel(s.type) }}</span></td>
              <td><span class="badge-purple">{{ topicLabel(s.topic) }}</span></td>
              <td class="text-right">
                <div class="inline-flex gap-2">
                  <button type="button" class="btn-secondary btn-sm" @click="fetch(s.id)">Парсить</button>
                  <button type="button" class="btn-danger btn-sm" @click="remove(s.id)">Удалить</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import PageHeader from '../components/layout/PageHeader.vue'
import { sourcesApi } from '../api/index.js'
import { useDialogStore } from '../stores/dialogStore'
import { TOPIC_OPTIONS, topicLabel } from '../constants/topics.js'

const dialog = useDialogStore()

const sources = ref([])
const form = ref({ name: '', type: 'rss', url: '', topic: 'it' })

const typeLabels = {
  rss: 'RSS',
  telegram: 'Telegram',
  web: 'Web',
}

function typeLabel(type) {
  return typeLabels[type] || type
}

async function load() {
  const { data } = await sourcesApi.list()
  sources.value = data
}

async function create() {
  await sourcesApi.create(form.value)
  form.value = { name: '', type: 'rss', url: '', topic: 'it' }
  await load()
}

async function fetch(id) {
  const { data } = await sourcesApi.fetchNow(id)
  await dialog.alert({
    title: 'Парсинг запущен',
    message: `${data.message}\n\nСмотрите статус в разделе «Задачи».`,
  })
}

async function remove(id) {
  const ok = await dialog.confirm({
    title: 'Удаление источника',
    message: 'Удалить источник?',
    confirmLabel: 'Удалить',
    danger: true,
  })
  if (!ok) return
  await sourcesApi.remove(id)
  await load()
}

onMounted(load)
</script>

<style scoped>
.form-card {
  @apply panel-card mb-6 p-4 sm:p-5;
}

.form-card-title {
  @apply mb-4 text-sm font-semibold text-[var(--text-primary)];
}

.form-grid {
  @apply grid gap-3 md:grid-cols-2;
}

.form-url {
  @apply md:col-span-2;
}

.form-actions {
  @apply flex items-end md:col-span-2;
}

.sources-cards {
  @apply flex flex-col gap-3 md:hidden;
}

.source-card {
  @apply flex flex-col gap-3 p-4;
}

.source-card-head {
  @apply flex flex-col gap-2;
}

.source-name {
  @apply text-sm font-semibold text-[var(--text-primary)];
}

.source-badges {
  @apply flex flex-wrap gap-1.5;
}

.source-url {
  @apply break-all text-xs leading-relaxed text-[var(--text-secondary)];
}

.source-card-actions {
  @apply flex flex-wrap gap-2 border-t border-panel-border pt-3;
}

.sources-table {
  @apply hidden max-w-full overflow-x-auto md:block;
}
</style>
