<template>
  <div>
    <PageHeader
      title="История"
      subtitle="Публикации и журнал умного выбора новостей"
    />

    <div class="tabs">
      <button
        type="button"
        class="tab"
        :class="{ 'tab-active': activeTab === 'publications' }"
        @click="activeTab = 'publications'"
      >
        Публикации
      </button>
      <button
        type="button"
        class="tab"
        :class="{ 'tab-active': activeTab === 'curated' }"
        @click="activeTab = 'curated'"
      >
        Умная публикация
      </button>
    </div>

    <template v-if="activeTab === 'publications'">
      <div v-if="loading && !items.length" class="empty-state">Загрузка…</div>
      <div v-else-if="!items.length" class="empty-state">Публикаций пока нет</div>
      <template v-else>
        <p class="history-hint">
          Здесь показаны попытки публикации: канал, время, опубликованный текст или причина ошибки.
        </p>

        <div class="history-cards">
          <article v-for="row in items" :key="`card-${row.id}`" class="history-card panel-card">
            <div class="history-card-head">
              <span :class="row.status === 'success' ? 'badge-accent' : 'badge-danger'">
                {{ row.status === 'success' ? 'Опубликовано' : 'Ошибка публикации' }}
              </span>
              <time class="history-time">{{ formatDate(row.attempted_at) }}</time>
            </div>
            <div>
              <span class="history-label">Канал</span>
              <p class="history-channel">{{ row.channel?.name || 'Канал не указан' }}</p>
            </div>
            <div>
              <span class="history-label">
                {{ row.status === 'success' ? 'Опубликованный текст' : 'Причина ошибки' }}
              </span>
              <p
                class="history-message"
                :class="{ 'text-danger': row.status !== 'success' }"
              >
                {{
                  row.status === 'success'
                    ? publicationPreview(row.rewritten_text)
                    : row.error_message || 'Причина ошибки не указана'
                }}
              </p>
            </div>
            <RouterLink
              v-if="row.processed_post_id && row.status === 'failed'"
              :to="{ name: 'approved' }"
              class="history-retry"
            >
              Перейти к повторной публикации →
            </RouterLink>
          </article>
        </div>

        <div class="table-wrap panel-card history-table">
        <table class="table-panel">
          <thead>
            <tr>
              <th>Результат</th>
              <th>Канал</th>
              <th>Когда</th>
              <th>Текст / ошибка</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in items" :key="row.id">
              <td class="whitespace-nowrap">
                <span :class="row.status === 'success' ? 'badge-accent' : 'badge-danger'">
                  {{ row.status === 'success' ? 'Опубликовано' : 'Ошибка' }}
                </span>
              </td>
              <td class="whitespace-nowrap">
                <span class="badge-muted">{{ row.channel?.name || '—' }}</span>
              </td>
              <td class="whitespace-nowrap text-[var(--text-secondary)] font-mono text-xs">
                {{ formatDate(row.attempted_at) }}
              </td>
              <td>
                <p v-if="row.status === 'success'" class="line-clamp-2 text-[var(--text-primary)]">
                  {{ publicationPreview(row.rewritten_text) }}
                </p>
                <p v-else class="line-clamp-3 text-danger text-sm">
                  {{ row.error_message || 'Неизвестная ошибка' }}
                </p>
              </td>
              <td class="whitespace-nowrap">
                <RouterLink
                  v-if="row.processed_post_id && row.status === 'failed'"
                  :to="{ name: 'approved' }"
                  class="text-xs text-accent hover:underline"
                >
                  К повтору
                </RouterLink>
              </td>
            </tr>
          </tbody>
        </table>
        </div>
      </template>
    </template>

    <CuratedPublicationPanel v-else />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import PageHeader from '../components/layout/PageHeader.vue'
import CuratedPublicationPanel from '../components/history/CuratedPublicationPanel.vue'
import { historyApi } from '../api/index.js'
import { stripHtmlForPreview } from '../utils/telegramHtml.js'

const items = ref([])
const loading = ref(false)
const activeTab = ref('publications')

function publicationPreview(text) {
  return stripHtmlForPreview(text || '') || 'Текст публикации не сохранён'
}

function formatDate(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

onMounted(async () => {
  loading.value = true
  try {
    const { data } = await historyApi.list({ limit: 50 })
    items.value = data
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  margin-bottom: 1.25rem;
  border-bottom: 1px solid rgb(var(--panel-border-rgb));
}

.tab {
  margin-bottom: -1px;
  border-bottom: 2px solid transparent;
  padding: 0.5rem 1rem;
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-secondary);
}

.tab-active {
  border-bottom-color: rgb(var(--accent-rgb));
  color: rgb(var(--accent-rgb));
}

.history-hint {
  display: block;
  margin-bottom: 0.75rem;
  font-size: 0.75rem;
  line-height: 1.45;
  color: var(--text-secondary);
}

.history-cards {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.history-card {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 1rem;
  min-width: 0;
}

.history-card-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.history-time {
  font-family: ui-monospace, monospace;
  font-size: 0.65rem;
  color: var(--text-secondary);
}

.history-label {
  display: block;
  font-size: 0.65rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--text-secondary);
}

.history-channel {
  margin-top: 0.25rem;
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-primary);
  overflow-wrap: anywhere;
}

.history-message {
  margin-top: 0.25rem;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 4;
  overflow: hidden;
  font-size: 0.875rem;
  line-height: 1.45;
  color: var(--text-primary);
  overflow-wrap: anywhere;
}

.history-retry {
  border-top: 1px solid rgb(var(--panel-border-rgb));
  padding-top: 0.75rem;
  font-size: 0.75rem;
  color: rgb(var(--accent-rgb));
}

.history-table {
  display: none;
  max-width: 100%;
  overflow-x: auto;
}

@media (min-width: 768px) {
  .history-hint,
  .history-cards {
    display: none;
  }

  .history-table {
    display: block;
  }
}

.badge-danger {
  display: inline-flex;
  border-radius: 0.25rem;
  background: rgb(var(--danger-rgb) / 0.15);
  padding: 0.125rem 0.5rem;
  font-size: 0.65rem;
  font-weight: 500;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: rgb(var(--danger-rgb));
}
</style>
