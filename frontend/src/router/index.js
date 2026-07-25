import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from '../api/index.js'
import QueueView from '../views/QueueView.vue'
import OverviewView from '../views/OverviewView.vue'
import SourcesView from '../views/SourcesView.vue'
import ChannelsView from '../views/ChannelsView.vue'
import HistoryView from '../views/HistoryView.vue'
import SettingsView from '../views/SettingsView.vue'
import JobsView from '../views/JobsView.vue'
import LogsView from '../views/LogsView.vue'
import MaterialsView from '../views/MaterialsView.vue'
import ApprovedView from '../views/ApprovedView.vue'
import AnalyticsView from '../views/AnalyticsView.vue'
import AnalyticsChannelView from '../views/AnalyticsChannelView.vue'
import LoginView from '../views/LoginView.vue'

const routes = [
  { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
  { path: '/', name: 'overview', component: OverviewView },
  { path: '/queue', name: 'queue', component: QueueView },
  { path: '/approved', name: 'approved', component: ApprovedView },
  { path: '/materials', name: 'materials', component: MaterialsView },
  { path: '/jobs', name: 'jobs', component: JobsView },
  { path: '/logs', name: 'logs', component: LogsView },
  { path: '/sources', name: 'sources', component: SourcesView },
  { path: '/channels', name: 'channels', component: ChannelsView },
  { path: '/analytics', name: 'analytics', component: AnalyticsView },
  {
    path: '/analytics/:channelId',
    name: 'analytics-channel',
    component: AnalyticsChannelView,
  },
  { path: '/history', name: 'history', component: HistoryView },
  { path: '/settings', name: 'settings', component: SettingsView },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const token = getToken()
  if (!to.meta.public && !token) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && token) {
    return { name: 'overview' }
  }
  return true
})

export default router
