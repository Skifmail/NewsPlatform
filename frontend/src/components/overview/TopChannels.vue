<template>
  <section class="top-channels panel-card">
    <header class="top-head">
      <h2 class="top-title">Топ каналов</h2>
      <RouterLink to="/analytics" class="top-link">Аналитика →</RouterLink>
    </header>

    <p v-if="!items.length" class="top-empty">Каналов пока нет.</p>

    <ul v-else class="top-list">
      <li
        v-for="(item, index) in items"
        :key="item.channel_id"
        class="top-item"
        role="button"
        tabindex="0"
        @click="openChannel(item.channel_id)"
        @keydown.enter="openChannel(item.channel_id)"
      >
        <span class="top-rank">{{ index + 1 }}</span>
        <div class="top-main">
          <span class="top-name">{{ item.name }}</span>
          <span class="badge-muted">{{ platformLabel(item.platform) }}</span>
        </div>
        <div class="top-stats">
          <span class="top-subs">{{ formatNum(item.subscribers) }}</span>
          <span
            v-if="item.subscribers_delta != null"
            class="top-delta"
            :class="deltaClass(item.subscribers_delta)"
          >
            {{ formatDelta(item.subscribers_delta) }}
          </span>
        </div>
      </li>
    </ul>
  </section>
</template>

<script setup>
import { useRouter } from 'vue-router'

defineProps({
  items: { type: Array, default: () => [] },
})

const router = useRouter()
const platformLabels = { telegram: 'Telegram', vk: 'VK', max: 'MAX' }

function platformLabel(p) {
  return platformLabels[p] || p
}

function formatNum(n) {
  if (n == null) return '—'
  return new Intl.NumberFormat('ru-RU').format(n)
}

function formatDelta(delta) {
  if (delta === 0) return '0'
  return delta > 0 ? `+${formatNum(delta)}` : formatNum(delta)
}

function deltaClass(delta) {
  if (delta > 0) return 'text-accent'
  if (delta < 0) return 'text-danger'
  return 'text-[var(--text-secondary)]'
}

function openChannel(channelId) {
  router.push({ name: 'analytics-channel', params: { channelId } })
}
</script>

<style scoped>
.top-channels {
  @apply p-4 h-full;
}

.top-head {
  @apply mb-4 flex items-center justify-between gap-2;
}

.top-title {
  @apply text-sm font-semibold text-[var(--text-primary)];
}

.top-link {
  @apply text-xs font-medium text-accent hover:underline;
}

.top-empty {
  @apply text-sm text-[var(--text-secondary)];
}

.top-list {
  @apply flex flex-col gap-2;
}

.top-item {
  @apply flex items-center gap-3 rounded-lg border border-panel-border px-3 py-2.5
    cursor-pointer transition-all duration-200 hover:border-accent/40 hover:bg-panel-hover/40;
}

.top-rank {
  @apply flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent-muted
    text-xs font-bold text-accent;
}

.top-main {
  @apply flex min-w-0 flex-1 flex-col gap-0.5;
}

.top-name {
  @apply truncate text-sm font-medium text-[var(--text-primary)];
}

.top-stats {
  @apply flex flex-col items-end gap-0.5 text-right;
}

.top-subs {
  @apply text-sm font-semibold tabular-nums text-[var(--text-primary)];
}

.top-delta {
  @apply text-[10px] font-medium tabular-nums;
}
</style>
