<template>
  <div>
    <PageHeader
      title="Каналы публикации"
      subtitle="Telegram, VK и MAX — настройка промптов и привязка каналов"
    />

    <form class="form-card" @submit.prevent="create">
      <h3 class="form-card-title">Новый канал</h3>
      <div class="form-grid">
        <input v-model="form.name" placeholder="Название" class="input" required />
        <select v-model="form.platform" class="select">
          <option value="telegram">Telegram</option>
          <option value="vk">VK</option>
          <option value="max">MAX</option>
        </select>
        <input
          v-model="form.platform_id"
          :placeholder="platformIdPlaceholder(form.platform)"
          class="input"
          required
        />
        <select v-model="form.topic" class="select">
          <option v-for="opt in TOPIC_OPTIONS" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
        <select v-model="form.content_mode" class="select">
          <option value="news">Новости (рерайт RSS)</option>
          <option value="article">Статьи (AI + веб-поиск)</option>
        </select>
      </div>
      <p v-if="form.content_mode === 'article'" class="field-hint mb-2">
        Для статей укажите в промпте нишу канала (наука, история, технологии). RSS не нужен.
      </p>
      <label class="field-label mt-4">{{ form.content_mode === 'article' ? 'Ниша и стиль канала' : 'Системный промпт рерайта' }}</label>
      <p class="field-hint mb-1">
        Полный шаблон с плейсхолдерами: {channel_name}, {topic}, {original_text}, {source_url}.
        Короткий текст без {original_text} — только описание стиля (дефолтный шаблон платформы).
      </p>
      <textarea
        v-model="form.style_prompt"
        placeholder="Вставьте полный шаблон рерайта или краткое описание стиля канала"
        rows="12"
        class="input w-full mt-1 font-mono text-xs"
      />
      <label class="field-label mt-4">Промпт обложек (Qwen-Image)</label>
      <p class="field-hint mb-1">
        Обязательно для AI-обложек. Шаблон на английском. Плейсхолдеры:
        {scene}, {tool_name}, {topic}. Без {title} — кириллица рисуется на картинке.
        Не пишите «science-pop», «audience», «telegram» — модель выведет их как текст.
      </p>
      <textarea
        v-model="form.image_prompt_guidelines"
        rows="5"
        class="input w-full mt-1 font-mono text-xs"
        placeholder="Landscape editorial illustration, no text on image. Scene: {scene}."
      />
      <template v-if="form.platform === 'telegram'">
        <label class="field-label mt-4">Перелив аудитории (ссылка в конце поста)</label>
        <p class="field-hint mb-1">
          Добавляется при публикации в Telegram после основного текста.
          Например, ссылка на тот же канал в MAX.
        </p>
        <input
          v-model="form.cross_promote_url"
          placeholder="https://max.ru/your_channel"
          class="input w-full mt-1 font-mono text-xs"
        />
        <input
          v-model="form.cross_promote_label"
          placeholder="Подписывайтесь на ПАРАГРАФ в MAX →"
          class="input w-full mt-2 text-xs"
        />
      </template>
      <button type="submit" class="btn-primary mt-4">Добавить канал</button>
    </form>

    <div v-if="!channels.length" class="empty-state">Каналы не добавлены</div>
    <div v-else class="channels-list">
      <article v-for="ch in channels" :key="ch.id" class="channel-card">
        <div class="channel-header">
          <div class="channel-header-main">
            <h3 class="channel-card-title">Канал #{{ ch.id }}</h3>
            <label class="active-toggle">
              <input
                v-model="editForms[ch.id].is_active"
                type="checkbox"
                class="active-checkbox"
              />
              <span>{{ editForms[ch.id].is_active ? 'Активен' : 'Отключён' }}</span>
            </label>
          </div>
          <div class="channel-badges">
            <span class="badge-info">{{ editForms[ch.id].platform }}</span>
            <span class="badge-purple">{{ topicLabelFn(editForms[ch.id].topic) }}</span>
            <span v-if="editForms[ch.id].content_mode === 'article'" class="badge-accent">Статьи</span>
          </div>
        </div>

        <div class="form-grid channel-fields">
          <div>
            <label class="field-label">Название</label>
            <input v-model="editForms[ch.id].name" class="input w-full mt-1" required />
          </div>
          <div>
            <label class="field-label">Платформа</label>
            <select v-model="editForms[ch.id].platform" class="select w-full mt-1">
              <option value="telegram">Telegram</option>
              <option value="vk">VK</option>
              <option value="max">MAX</option>
            </select>
          </div>
          <div class="md:col-span-2">
            <label class="field-label">ID канала</label>
            <input
              v-model="editForms[ch.id].platform_id"
              class="input w-full mt-1 font-mono"
              :placeholder="platformIdPlaceholder(editForms[ch.id].platform)"
              required
            />
            <p class="field-hint mt-1">
              {{ platformIdHint(editForms[ch.id].platform) }}
            </p>
          </div>
          <div>
            <label class="field-label">Тематика</label>
            <select v-model="editForms[ch.id].topic" class="select w-full mt-1">
              <option v-for="opt in TOPIC_OPTIONS" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </div>
          <div>
            <label class="field-label">Режим контента</label>
            <select v-model="editForms[ch.id].content_mode" class="select w-full mt-1">
              <option value="news">Новости</option>
              <option value="article">Статьи</option>
            </select>
          </div>
        </div>

        <label class="field-label mt-5">
          {{ editForms[ch.id].content_mode === 'article' ? 'Ниша и стиль канала' : 'Промпт рерайта' }}
        </label>
        <textarea
          v-model="editForms[ch.id].style_prompt"
          rows="12"
          class="input w-full text-xs font-mono mt-1"
        />

        <label class="field-label mt-5">Промпт обложек (Qwen-Image)</label>
        <p class="field-hint mb-1">
          Обязательно для AI-обложек. Шаблон на английском. Плейсхолдеры:
          {scene}, {tool_name}, {topic}. Без {title} — кириллица рисуется на картинке.
          Не пишите «science-pop», «audience», «telegram» — модель выведет их как текст.
        </p>
        <textarea
          v-model="editForms[ch.id].image_prompt_guidelines"
          rows="6"
          class="input w-full text-xs font-mono mt-1"
          placeholder="Landscape editorial illustration, no text on image. Scene: {scene}."
        />

        <template v-if="editForms[ch.id].platform === 'telegram'">
          <label class="field-label mt-5">Перелив аудитории (ссылка в конце поста)</label>
          <p class="field-hint mb-1">
            Добавляется при публикации в Telegram. Укажите ссылку на канал в MAX
            и текст кнопки-ссылки.
          </p>
          <input
            v-model="editForms[ch.id].cross_promote_url"
            placeholder="https://max.ru/your_channel"
            class="input w-full mt-1 font-mono text-xs"
          />
          <input
            v-model="editForms[ch.id].cross_promote_label"
            placeholder="Подписывайтесь на ПАРАГРАФ в MAX →"
            class="input w-full mt-2 text-xs"
          />
          <input
            v-model="editForms[ch.id].cross_promote_emoji_id"
            placeholder="ID анимированного эмодзи (custom_emoji_id)"
            class="input w-full mt-2 font-mono text-xs"
          />
          <p class="field-hint mt-1">
            Эмодзи MAX: перешлите сообщение с этим эмодзи боту @RawDataBot —
            скопируйте custom_emoji_id. В каналах работает только если у бота
            куплен username на Fragment или есть Telegram Premium у владельца.
          </p>
        </template>

        <div
          v-if="editForms[ch.id].content_mode === 'article'"
          class="article-schedule mt-5 pt-4 border-t border-panel-border"
        >
          <h4 class="schedule-title">Расписание генерации статей</h4>
          <p class="field-hint mb-3">
            Интервал и окно публикации (UTC). Автозапуск — в «Настройки» → «Автогенерация статей».
            Расписание публикации готовых постов — в разделе «Одобренные».
          </p>
          <div class="schedule-fields">
            <label class="field-mini">
              <span>Интервал (мин)</span>
              <input
                v-model.number="editForms[ch.id].publish_interval_minutes"
                type="number"
                min="1"
                max="1440"
                class="input input-sm"
              />
            </label>
            <label class="field-mini">
              <span>Окно с (UTC)</span>
              <input
                v-model="editForms[ch.id].publish_window_start"
                type="time"
                class="input input-sm"
              />
            </label>
            <label class="field-mini">
              <span>Окно до (UTC)</span>
              <input
                v-model="editForms[ch.id].publish_window_end"
                type="time"
                class="input input-sm"
              />
            </label>
          </div>
        </div>

        <div class="channel-actions">
          <button
            v-if="editForms[ch.id].content_mode === 'article'"
            type="button"
            class="btn-secondary btn-sm"
            :disabled="generatingChannel === ch.id"
            @click="generateArticle(ch.id)"
          >
            {{ generatingChannel === ch.id ? 'Запуск…' : 'Сгенерировать статью' }}
          </button>
          <button type="button" class="btn-primary btn-sm" @click="saveChannel(ch.id)">
            Сохранить изменения
          </button>
          <button type="button" class="btn-danger btn-sm" @click="removeChannel(ch)">
            Удалить канал
          </button>
        </div>
      </article>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import PageHeader from '../components/layout/PageHeader.vue'
import { channelsApi } from '../api/index.js'
import { useDialogStore } from '../stores/dialogStore'
import { useActivityStore } from '../stores/activityStore'
import { TOPIC_OPTIONS, topicLabel as topicLabelFn } from '../constants/topics.js'

const dialog = useDialogStore()
const activityStore = useActivityStore()

const channels = ref([])
const editForms = reactive({})
const generatingChannel = ref(null)
const form = ref({
  name: '',
  platform: 'telegram',
  platform_id: '',
  topic: 'it',
  content_mode: 'news',
  style_prompt: '',
    image_prompt_guidelines: '',
    cross_promote_url: '',
    cross_promote_label: '',
    cross_promote_emoji_id: '',
})

function platformIdPlaceholder(platform) {
  if (platform === 'max') return '123456789 или my_channel'
  if (platform === 'vk') return '-123456789 (owner_id группы)'
  return '@channel или -100...'
}

function platformIdHint(platform) {
  if (platform === 'max') {
    return 'MAX: числовой chat_id или slug канала (my_channel). Бот должен быть админом с правом публикации.'
  }
  if (platform === 'vk') {
    return 'VK: отрицательный owner_id сообщества, например -123456789.'
  }
  return 'Telegram: @username публичного канала или числовой id вида -100…'
}

function hhmmFromChannel(value) {
  if (!value) return '08:00'
  return value.length >= 5 ? value.slice(0, 5) : value
}

function timeInputToApi(t) {
  if (!t) return '08:00'
  return t.length === 5 ? t : t.slice(0, 5)
}

function buildEditForm(ch) {
  return {
    name: ch.name,
    platform: ch.platform,
    platform_id: ch.platform_id,
    topic: ch.topic,
    content_mode: ch.content_mode || 'news',
    is_active: ch.is_active,
    style_prompt: ch.style_prompt || '',
    image_prompt_guidelines: ch.image_prompt_guidelines || '',
    cross_promote_url: ch.cross_promote_url || '',
    cross_promote_label: ch.cross_promote_label || '',
    cross_promote_emoji_id: ch.cross_promote_emoji_id || '',
    publish_interval_minutes: ch.publish_interval_minutes ?? 60,
    publish_window_start: hhmmFromChannel(ch.publish_window_start),
    publish_window_end: hhmmFromChannel(ch.publish_window_end),
  }
}

async function load() {
  const { data } = await channelsApi.list()
  channels.value = data
  data.forEach((ch) => {
    editForms[ch.id] = buildEditForm(ch)
  })
}

async function create() {
  await channelsApi.create(form.value)
  form.value = {
    name: '',
    platform: 'telegram',
    platform_id: '',
    topic: 'it',
    content_mode: 'news',
    style_prompt: '',
    image_prompt_guidelines: '',
    cross_promote_url: '',
    cross_promote_label: '',
    cross_promote_emoji_id: '',
  }
  await load()
}

async function saveChannel(id) {
  const payload = editForms[id]
  if (!payload?.name?.trim() || !payload?.platform_id?.trim()) {
    await dialog.alert({
      title: 'Каналы',
      message: 'Заполните название и ID канала.',
    })
    return
  }
  await channelsApi.update(id, {
    name: payload.name.trim(),
    platform: payload.platform,
    platform_id: payload.platform_id.trim(),
    topic: payload.topic,
    content_mode: payload.content_mode,
    is_active: payload.is_active,
    style_prompt: payload.style_prompt,
    image_prompt_guidelines: payload.image_prompt_guidelines,
    cross_promote_url: payload.cross_promote_url?.trim() || null,
    cross_promote_label: payload.cross_promote_label?.trim() || null,
    cross_promote_emoji_id: payload.cross_promote_emoji_id?.trim() || null,
    ...(payload.content_mode === 'article'
      ? {
          publish_interval_minutes: payload.publish_interval_minutes,
          publish_window_start: timeInputToApi(payload.publish_window_start),
          publish_window_end: timeInputToApi(payload.publish_window_end),
        }
      : {}),
  })
  await dialog.alert({ title: 'Каналы', message: 'Изменения сохранены' })
  await load()
}

async function generateArticle(id) {
  generatingChannel.value = id
  try {
    const { data } = await channelsApi.generateArticle(id)
    await activityStore.syncActiveJobs()
    activityStore.startPolling()
    await dialog.alert({
      title: 'Статьи',
      message: `${data.message}\n\nПрогресс — всплывающее уведомление и раздел «Задачи».`,
    })
  } catch (e) {
    await dialog.alertApiError(e, 'Не удалось запустить генерацию статьи')
  } finally {
    generatingChannel.value = null
  }
}

async function removeChannel(ch) {
  const ok = await dialog.confirm({
    title: 'Удаление канала',
    message:
      `Удалить канал «${ch.name}»?\n\n` +
      'Связанные посты в очереди и история публикаций для этого канала будут удалены.',
    confirmLabel: 'Удалить',
    danger: true,
  })
  if (!ok) return
  try {
    await channelsApi.remove(ch.id)
    delete editForms[ch.id]
    await load()
  } catch (e) {
    await dialog.alertApiError(e, 'Не удалось удалить канал')
  }
}

onMounted(load)
</script>

<style scoped>
.form-card {
  @apply panel-card p-5 mb-6;
}

.form-card-title {
  @apply text-sm font-semibold text-[var(--text-primary)] mb-4;
}

.form-grid {
  @apply grid gap-3 md:grid-cols-2;
}

.field-label {
  @apply block text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)];
}

.channels-list {
  @apply flex flex-col gap-4;
}

.field-hint {
  @apply text-xs text-[var(--text-secondary)];
}

.channel-card {
  @apply panel-card p-5;
}

.channel-header {
  @apply flex flex-wrap items-start justify-between gap-3 mb-4 pb-4 border-b border-panel-border;
}

.channel-header-main {
  @apply flex flex-wrap items-center gap-4;
}

.channel-card-title {
  @apply text-sm font-semibold text-[var(--text-primary)];
}

.channel-badges {
  @apply flex gap-2;
}

.channel-fields {
  @apply mt-1;
}

.channel-actions {
  @apply flex flex-wrap gap-2 mt-4 pt-4 border-t border-panel-border;
}

.active-toggle {
  @apply inline-flex items-center gap-2 text-xs text-[var(--text-secondary)] cursor-pointer select-none;
}

.active-checkbox {
  @apply rounded border-panel-border;
}

.schedule-title {
  @apply text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)] mb-2;
}

.schedule-fields {
  @apply grid gap-3 sm:grid-cols-3;
}

.field-mini {
  @apply flex flex-col gap-1 text-xs text-[var(--text-secondary)];
}
</style>
