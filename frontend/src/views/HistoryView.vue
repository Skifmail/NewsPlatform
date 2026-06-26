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
      <div v-else class="table-wrap panel-card overflow-hidden">
        <table class="table-panel">
          <thead>
            <tr>
              <th>Статус</th>
              <th>Канал</th>
              <th>Дата</th>
              <th>Текст / ошибка</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in items" :key="row.id">
              <td class="whitespace-nowrap">
                <span :class="row.status === 'success' ? 'badge-accent' : 'badge-danger'">
                  {{ row.status === 'success' ? 'Успех' : 'Ошибка' }}
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
                  {{ row.rewritten_text }}
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

    <CuratedPublicationPanel v-else />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import PageHeader from '../components/layout/PageHeader.vue'
import CuratedPublicationPanel from '../components/history/CuratedPublicationPanel.vue'
import { historyApi } from '../api/index.js'

const items = ref([])
const loading = ref(false)
const activeTab = ref('publications')

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
  @apply mb-5 flex gap-1 border-b border-panel-border;
}

.tab {
  @apply -mb-px border-b-2 border-transparent px-4 py-2 text-sm font-medium
    text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)];
}

.tab-active {
  @apply border-accent text-accent;
}

.badge-danger {
  @apply inline-flex rounded px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide
    bg-danger/15 text-danger;
}
</style>
