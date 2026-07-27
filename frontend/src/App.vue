<template>
  <ThemeToggle v-if="!auth.isAuthenticated" class="login-theme-toggle" />

  <RouterView v-if="!auth.isAuthenticated" />

  <div v-else class="app-shell">
    <AppSidebar
      :username="auth.username"
      :queue-count="postsStore.queue.length"
      :approved-count="postsStore.approvedCount"
      :materials-count="materialsCount"
      :active-jobs-count="activeJobsCount"
      @logout="onLogout"
    />

    <div class="app-main">
      <RouterView />
    </div>

    <ActivityToastStack />
    <PipelineMissionModal />
    <AppDialog />
  </div>
</template>

<script setup>
import { onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import ActivityToastStack from './components/ActivityToastStack.vue'
import PipelineMissionModal from './components/pipeline/PipelineMissionModal.vue'
import AppDialog from './components/AppDialog.vue'
import AppSidebar from './components/layout/AppSidebar.vue'
import ThemeToggle from './components/layout/ThemeToggle.vue'
import { jobsApi, rawPostsApi } from './api/index.js'
import { useActivityStore } from './stores/activityStore'
import { usePipelineStore } from './stores/pipelineStore'
import { useAuthStore } from './stores/authStore'
import { usePostsStore } from './stores/postsStore'

const auth = useAuthStore()
const postsStore = usePostsStore()
const activityStore = useActivityStore()
const pipelineStore = usePipelineStore()
const router = useRouter()
const activeJobsCount = ref(0)
const materialsCount = ref(0)
let jobsPollTimer = null

async function pollSidebarBadges() {
  try {
    const [jobsRes, materialsRes] = await Promise.all([
      jobsApi.summary(),
      rawPostsApi.summary(),
    ])
    activeJobsCount.value = jobsRes.data.active_total
    materialsCount.value = materialsRes.data.unprocessed
    if (jobsRes.data.active_total > 0) {
      await activityStore.syncActiveJobs()
    }
  } catch {
    /* ignore */
  }
}

function onActivityEvent(msg) {
  activityStore.handleWebSocketMessage(msg)
  if (msg.type === 'pipeline' && msg.payload) {
    pipelineStore.applyWsUpdate(msg.payload)
  }
  postsStore.loadQueue()
  postsStore.loadApproved()
  postsStore.loadApprovedSummary()
  pollSidebarBadges()
}

async function onLogout() {
  if (jobsPollTimer) clearInterval(jobsPollTimer)
  postsStore.disconnectWebSocket()
  activityStore.reset()
  pipelineStore.reset()
  auth.logout()
  await router.push('/login')
}

async function initAuthenticatedSession() {
  const ok = await auth.fetchMe()
  if (!ok) {
    await router.push('/login')
    return
  }
  await pollSidebarBadges()
  if (!jobsPollTimer) {
    jobsPollTimer = setInterval(pollSidebarBadges, 8000)
  }
  postsStore.loadQueue()
  postsStore.loadApprovedSummary()
  postsStore.connectWebSocket(onActivityEvent)
}

function stopSession() {
  if (jobsPollTimer) {
    clearInterval(jobsPollTimer)
    jobsPollTimer = null
  }
  postsStore.disconnectWebSocket()
  activityStore.stopPolling()
}

watch(
  () => auth.isAuthenticated,
  async (authenticated) => {
    if (authenticated) {
      await initAuthenticatedSession()
    } else {
      stopSession()
    }
  },
  { immediate: true },
)

onUnmounted(() => {
  stopSession()
})
</script>

<style scoped>
.login-theme-toggle {
  @apply fixed top-4 right-4 z-40 md:right-8;
}

.app-shell {
  @apply flex min-h-[100dvh] max-md:flex-col;
}

.app-main {
  @apply min-h-[100dvh] flex-1 px-4 py-4 max-md:ml-0 ml-[220px] md:px-6 md:py-6 lg:px-8 lg:py-8;
}
</style>
