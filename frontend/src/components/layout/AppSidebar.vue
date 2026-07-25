<template>
  <aside class="sidebar">
    <div class="sidebar-brand">
      <div class="brand-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M12 6v12m-6-6h12M4 4h16v16H4z"
          />
        </svg>
      </div>
      <div>
        <p class="brand-title">Content Platform</p>
        <p class="brand-sub">Панель управления</p>
      </div>
    </div>

    <nav class="sidebar-nav">
      <RouterLink
        v-for="item in navItems"
        :key="item.to"
        :to="item.to"
        class="nav-item"
        active-class="nav-item-active"
      >
        <span class="nav-icon" v-html="item.icon" />
        {{ item.label }}
        <span v-if="item.badge != null" class="nav-badge">{{ item.badge }}</span>
      </RouterLink>
    </nav>

    <div class="sidebar-footer">
      <p class="user-label">Пользователь</p>
      <p class="user-name">{{ username || 'admin' }}</p>
      <button type="button" class="btn-ghost btn-sm w-full mt-2" @click="$emit('logout')">
        Выйти
      </button>
    </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  username: { type: String, default: '' },
  queueCount: { type: Number, default: 0 },
  approvedCount: { type: Number, default: 0 },
  materialsCount: { type: Number, default: 0 },
  activeJobsCount: { type: Number, default: 0 },
})
defineEmits(['logout'])

const navItems = computed(() => [
  {
    to: '/',
    label: 'Обзор',
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path stroke-linecap="round" stroke-linejoin="round" d="M4 5a1 1 0 011-1h4a1 1 0 011 1v5a1 1 0 01-1 1H5a1 1 0 01-1-1V5zm10 0a1 1 0 011-1h4a1 1 0 011 1v3a1 1 0 01-1 1h-4a1 1 0 01-1-1V5zM4 15a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1v-4zm10-2a1 1 0 011-1h4a1 1 0 011 1v6a1 1 0 01-1 1h-4a1 1 0 01-1-1v-6z"/></svg>`,
  },
  {
    to: '/queue',
    label: 'Очередь',
    badge: props.queueCount > 0 ? props.queueCount : null,
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/></svg>`,
  },
  {
    to: '/approved',
    label: 'Одобренные',
    badge: props.approvedCount > 0 ? props.approvedCount : null,
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`,
  },
  {
    to: '/materials',
    label: 'Материалы',
    badge: props.materialsCount > 0 ? props.materialsCount : null,
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path stroke-linecap="round" stroke-linejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/></svg>`,
  },
  {
    to: '/jobs',
    label: 'Задачи',
    badge: props.activeJobsCount > 0 ? props.activeJobsCount : null,
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 10h16M4 14h16M4 18h16"/></svg>`,
  },
  {
    to: '/logs',
    label: 'Диагностика',
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path stroke-linecap="round" stroke-linejoin="round" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 7h10v10H7z"/></svg>`,
  },
  {
    to: '/sources',
    label: 'Источники',
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path stroke-linecap="round" stroke-linejoin="round" d="M4 7v10c0 2 1 3 3 3h10c2 0 3-1 3-3V7M4 7l8-4 8 4M4 7l8 4 8-4"/></svg>`,
  },
  {
    to: '/channels',
    label: 'Каналы',
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path stroke-linecap="round" stroke-linejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>`,
  },
  {
    to: '/analytics',
    label: 'Аналитика',
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path stroke-linecap="round" stroke-linejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>`,
  },
  {
    to: '/history',
    label: 'История',
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`,
  },
  {
    to: '/settings',
    label: 'Настройки',
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path stroke-linecap="round" stroke-linejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>`,
  },
])
</script>

<style scoped>
.sidebar {
  @apply fixed left-0 top-0 z-20 flex h-full w-[220px] flex-col border-r border-panel-border bg-panel-surface/95 backdrop-blur-md
    max-md:w-full max-md:h-auto max-md:relative max-md:border-r-0 max-md:border-b;
}

@media (max-width: 768px) {
  .sidebar-nav {
    @apply flex-row flex-wrap overflow-x-auto py-2;
  }

  .nav-item,
  .nav-item-active {
    @apply shrink-0;
  }

  .sidebar-footer {
    @apply hidden;
  }
}

.sidebar-brand {
  @apply flex items-center gap-3 border-b border-panel-border px-5 py-5;
}

.brand-icon {
  @apply flex h-10 w-10 shrink-0 items-center justify-center rounded-panel bg-accent-muted text-accent;
}

.brand-icon svg {
  @apply h-5 w-5;
}

.brand-title {
  @apply text-sm font-semibold leading-tight text-[var(--text-primary)];
}

.brand-sub {
  @apply text-[10px] uppercase tracking-wider text-[var(--text-secondary)];
}

.sidebar-nav {
  @apply flex flex-1 flex-col gap-1 overflow-y-auto px-3 py-4;
}

.nav-icon :deep(svg) {
  @apply h-[18px] w-[18px] shrink-0 opacity-90;
}

.nav-badge {
  @apply ml-auto rounded-pill bg-accent-muted px-2 py-0.5 text-[10px] font-semibold text-accent;
}

.nav-item-active .nav-badge {
  @apply bg-white/20 text-white;
}

.sidebar-footer {
  @apply border-t border-panel-border p-4;
}

.user-label {
  @apply text-[10px] font-medium uppercase tracking-wider text-[var(--text-secondary)];
}

.user-name {
  @apply mt-1 text-sm font-medium text-[var(--text-primary)] truncate;
}
</style>
