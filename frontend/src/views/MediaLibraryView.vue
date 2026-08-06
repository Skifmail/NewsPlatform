<template>
  <div>
    <PageHeader
      title="Медиатека"
      subtitle="Оригиналы сгенерированных обложек и анимаций — скачайте и прикрепите к посту вручную"
    >
      <template #actions>
        <button type="button" class="btn-secondary btn-sm" :disabled="loading" @click="load">
          Обновить
        </button>
        <button
          type="button"
          class="btn-ghost btn-sm"
          :disabled="backfilling"
          @click="backfill"
        >
          Импорт из постов
        </button>
      </template>
    </PageHeader>

    <div class="toolbar panel-card">
      <label class="filter-label">
        Канал
        <select v-model="filterChannelId" class="select" @change="load">
          <option :value="null">Все каналы</option>
          <option v-for="ch in channels" :key="ch.id" :value="ch.id">
            {{ ch.name }}
          </option>
        </select>
      </label>
      <label class="filter-label">
        Тип
        <select v-model="filterKind" class="select" @change="load">
          <option value="all">Все</option>
          <option value="cover">Обложки</option>
          <option value="animation">Анимации</option>
        </select>
      </label>
    </div>

    <p v-if="hint" class="media-hint">{{ hint }}</p>

    <div v-if="loading && !assets.length" class="empty-state">Загрузка…</div>
    <div v-else-if="!assets.length" class="empty-state">
      Пока нет сохранённых изображений. После генерации статей они появятся здесь.
      Можно нажать «Импорт из постов», чтобы подтянуть уже существующие.
    </div>

    <div v-else class="media-grid">
      <article v-for="asset in assets" :key="asset.id" class="media-card panel-card">
        <div class="media-preview">
          <video
            v-if="asset.kind === 'animation' && asset.storage_url"
            :src="asset.storage_url"
            class="media-thumb"
            muted
            loop
            playsinline
            @mouseenter="($event) => $event.target.play()"
            @mouseleave="($event) => { $event.target.pause(); $event.target.currentTime = 0 }"
          />
          <img
            v-else-if="asset.storage_url"
            :src="asset.storage_url"
            :alt="asset.title || 'Обложка'"
            class="media-thumb"
            loading="lazy"
          />
          <div v-else class="media-thumb media-thumb-empty">Нет превью</div>
        </div>
        <div class="media-meta">
          <div class="media-badges">
            <span class="badge-muted">{{ asset.channel?.name || 'Канал' }}</span>
            <span :class="asset.kind === 'animation' ? 'badge-accent' : 'badge-muted'">
              {{ asset.kind === 'animation' ? 'Анимация' : 'Обложка' }}
            </span>
            <span v-if="asset.image_source === 'generated'" class="badge-accent">AI</span>
          </div>
          <p class="media-title" :title="asset.title || ''">
            {{ asset.title || 'Без названия' }}
          </p>
          <time class="media-time">{{ formatDate(asset.created_at) }}</time>
          <div class="media-actions">
            <button
              v-if="asset.is_downloadable"
              type="button"
              class="btn-primary btn-sm"
              @click="download(asset)"
            >
              Скачать
            </button>
            <a
              v-else-if="asset.storage_url"
              :href="asset.storage_url"
              target="_blank"
              rel="noopener"
              class="btn-secondary btn-sm"
            >
              Открыть
            </a>
            <RouterLink
              v-if="asset.processed_post_id"
              :to="{ name: 'queue' }"
              class="btn-ghost btn-sm"
            >
              К посту #{{ asset.processed_post_id }}
            </RouterLink>
            <button
              type="button"
              class="btn-danger btn-sm"
              :disabled="deletingId === asset.id"
              @click="remove(asset)"
            >
              Удалить
            </button>
          </div>
        </div>
      </article>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import PageHeader from '../components/layout/PageHeader.vue'
import { channelsApi, mediaAssetsApi } from '../api/index.js'

const assets = ref([])
const channels = ref([])
const loading = ref(false)
const backfilling = ref(false)
const deletingId = ref(null)
const filterChannelId = ref(null)
const filterKind = ref('all')
const hint = ref('')

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

async function load() {
  loading.value = true
  hint.value = ''
  try {
    const params = { limit: 200 }
    if (filterChannelId.value != null) params.channel_id = filterChannelId.value
    if (filterKind.value !== 'all') params.kind = filterKind.value
    const { data } = await mediaAssetsApi.list(params)
    assets.value = data
  } catch (err) {
    hint.value = err.response?.data?.detail || 'Не удалось загрузить медиатеку'
  } finally {
    loading.value = false
  }
}

async function backfill() {
  backfilling.value = true
  hint.value = ''
  try {
    const { data } = await mediaAssetsApi.backfill({ limit: 1000 })
    hint.value = data.imported
      ? `Импортировано записей: ${data.imported}`
      : 'Новых записей нет — всё уже в медиатеке'
    await load()
  } catch (err) {
    hint.value = err.response?.data?.detail || 'Импорт не удался'
  } finally {
    backfilling.value = false
  }
}

async function download(asset) {
  try {
    const { data } = await mediaAssetsApi.download(asset.id)
    const url = URL.createObjectURL(data)
    const a = document.createElement('a')
    a.href = url
    const ext = asset.kind === 'animation' ? 'mp4' : 'png'
    a.download = `channel-${asset.channel_id}-media-${asset.id}.${ext}`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  } catch (err) {
    hint.value = err.response?.data?.detail || 'Скачивание не удалось'
  }
}

async function remove(asset) {
  if (!confirm('Удалить файл из медиатеки и с диска?')) return
  deletingId.value = asset.id
  try {
    await mediaAssetsApi.remove(asset.id)
    assets.value = assets.value.filter((a) => a.id !== asset.id)
  } catch (err) {
    hint.value = err.response?.data?.detail || 'Удаление не удалось'
  } finally {
    deletingId.value = null
  }
}

onMounted(async () => {
  try {
    const { data } = await channelsApi.list()
    channels.value = data
  } catch {
    channels.value = []
  }
  await load()
})
</script>

<style scoped>
.toolbar {
  @apply mb-4 flex flex-wrap items-end gap-4 p-4;
}

.filter-label {
  @apply flex flex-col gap-1 text-xs font-medium text-[var(--text-secondary)];
}

.select {
  @apply min-w-[180px] rounded-panel border border-panel-border bg-panel-surface px-3 py-2 text-sm text-[var(--text-primary)];
}

.media-hint {
  @apply mb-3 text-sm text-[var(--text-secondary)];
}

.media-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 1rem;
}

.media-card {
  @apply flex flex-col overflow-hidden;
}

.media-preview {
  @apply aspect-[4/3] overflow-hidden bg-[var(--panel-muted,rgba(0,0,0,0.04))];
}

.media-thumb {
  @apply h-full w-full object-cover;
}

.media-thumb-empty {
  @apply flex items-center justify-center text-sm text-[var(--text-secondary)];
}

.media-meta {
  @apply flex flex-1 flex-col gap-2 p-3;
}

.media-badges {
  @apply flex flex-wrap gap-1.5;
}

.media-title {
  @apply line-clamp-2 text-sm font-medium text-[var(--text-primary)];
}

.media-time {
  @apply font-mono text-xs text-[var(--text-secondary)];
}

.media-actions {
  @apply mt-auto flex flex-wrap gap-2 pt-1;
}

.empty-state {
  @apply rounded-panel border border-dashed border-panel-border px-6 py-12 text-center text-sm text-[var(--text-secondary)];
}
</style>
