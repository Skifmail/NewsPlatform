<template>
  <div class="login-page">
    <form class="login-card" @submit.prevent="submit">
      <div class="login-brand">
        <div class="brand-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M12 6v12m-6-6h12M4 4h16v16H4z"
            />
          </svg>
        </div>
        <h1 class="login-title">Content Platform</h1>
        <p class="login-sub">Вход в панель управления</p>
      </div>

      <label class="field-label">Логин</label>
      <input
        v-model="user"
        type="text"
        class="input"
        autocomplete="username"
        required
      />

      <label class="field-label mt-3">Пароль</label>
      <input
        v-model="password"
        type="password"
        class="input"
        autocomplete="current-password"
        required
      />

      <p v-if="auth.error" class="login-error">{{ auth.error }}</p>

      <button type="submit" class="btn-primary w-full mt-5" :disabled="auth.loading">
        {{ auth.loading ? 'Вход…' : 'Войти' }}
      </button>
    </form>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/authStore'

const auth = useAuthStore()
const router = useRouter()
const user = ref('')
const password = ref('')

async function submit() {
  const ok = await auth.login(user.value, password.value)
  if (ok) {
    await router.replace('/')
  }
}
</script>

<style scoped>
.login-page {
  @apply min-h-[100dvh] flex items-center justify-center p-4;
}

.login-card {
  @apply panel-card w-full max-w-sm p-8;
}

.login-brand {
  @apply text-center mb-8;
}

.brand-icon {
  @apply mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-panel bg-accent-muted text-accent;
}

.brand-icon svg {
  @apply h-6 w-6;
}

.login-title {
  @apply text-lg font-semibold text-[var(--text-primary)];
}

.login-sub {
  @apply text-sm text-[var(--text-secondary)] mt-1;
}

.field-label {
  @apply block text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)];
}

.login-error {
  @apply mt-3 text-sm text-danger;
}
</style>
