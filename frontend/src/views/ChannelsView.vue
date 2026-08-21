<template>
  <div>
    <PageHeader
      title="Каналы публикации"
      subtitle="Telegram, VK и MAX — настройка промптов и привязка каналов"
    />

    <!-- Добавление канала — скрыто по умолчанию -->
    <div class="add-channel">
      <button type="button" class="add-toggle" @click="showNewForm = !showNewForm">
        <span class="chevron" :class="{ open: showNewForm }">▸</span>
        <span>＋ Добавить канал</span>
      </button>
      <transition
        name="expand"
        @enter="startExpand"
        @after-enter="endExpand"
        @before-leave="startCollapse"
        @leave="doCollapse"
      >
        <div v-if="showNewForm" class="expand-body">
          <form class="form-card mt-3" @submit.prevent="create">
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
              <input
                v-model="form.publish_times"
                type="text"
                inputmode="numeric"
                placeholder="Времена выхода МСК: 09:00, 13:00, 17:00, 21:00"
                class="input"
                required
              />
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
            <label class="field-label mt-4">Футер поста</label>
            <p class="field-hint mb-1">
              Добавляется в конец каждого поста на любой платформе. Например,
              призыв поставить реакцию и ссылка на канал.
            </p>
            <textarea
              v-model="form.post_footer"
              rows="3"
              class="input w-full mt-1 text-xs"
              placeholder="❤️ Ставьте реакцию, если понравилось!"
            />
            <button type="submit" class="btn-primary mt-4">Добавить канал</button>
          </form>
        </div>
      </transition>
    </div>

    <div v-if="!channels.length" class="empty-state">Каналы не добавлены</div>
    <div v-else class="channels-list">
      <article
        v-for="ch in sortedChannels"
        :key="ch.id"
        class="channel-card"
        :class="{ 'is-open': expandedId === ch.id }"
      >
        <button type="button" class="channel-header" @click="toggleChannel(ch.id)">
          <div class="channel-header-main">
            <span class="chevron" :class="{ open: expandedId === ch.id }">▸</span>
            <span class="channel-card-title">{{ editForms[ch.id].name || ('Канал #' + ch.id) }}</span>
            <span
              v-if="isDirty(ch.id)"
              class="dirty-dot"
              title="Есть несохранённые изменения"
            >●</span>
          </div>
          <div class="channel-badges">
            <span class="badge-info">{{ platformLabel(editForms[ch.id].platform) }}</span>
            <span class="badge-purple">{{ topicLabelFn(editForms[ch.id].topic) }}</span>
            <span v-if="editForms[ch.id].content_mode === 'article'" class="badge-accent">Статьи</span>
            <span class="status-pill" :class="editForms[ch.id].is_active ? 'on' : 'off'">
              {{ editForms[ch.id].is_active ? 'Активен' : 'Отключён' }}
            </span>
          </div>
        </button>

        <transition
          name="expand"
          @enter="startExpand"
          @after-enter="endExpand"
          @before-leave="startCollapse"
          @leave="doCollapse"
        >
          <div v-if="expandedId === ch.id" class="expand-body channel-body">
            <label class="active-toggle mb-4">
              <input
                v-model="editForms[ch.id].is_active"
                type="checkbox"
                class="active-checkbox"
              />
              <span>{{ editForms[ch.id].is_active ? 'Канал активен' : 'Канал отключён' }}</span>
            </label>

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


            <label
              v-if="editForms[ch.id].content_mode === 'article'"
              class="active-toggle mt-5 block"
            >
              <input
                v-model="editForms[ch.id].animate_postcards"
                type="checkbox"
                class="active-checkbox"
              />
              <span>Анимировать обложки (Grok Imagine Video через OpenRouter)</span>
            </label>
            <p
              v-if="editForms[ch.id].content_mode === 'article'"
              class="field-hint mb-1"
            >
              После генерации обложки платформа может создать короткое видео:
              движется только сцена (волны, пар, свечи), текст остаётся неподвижным.
              Нужен ключ OpenRouter в настройках и включённая анимация в платформе.
            </p>

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

            <label class="field-label mt-5">Футер поста</label>
            <p class="field-hint mb-1">
              Добавляется в конец каждого поста на любой платформе. Например,
              призыв поставить реакцию и ссылка на канал.
            </p>
            <textarea
              v-model="editForms[ch.id].post_footer"
              rows="3"
              class="input w-full text-xs mt-1"
              placeholder="❤️ Ставьте реакцию, если понравилось!"
            />

            <div
              v-if="editForms[ch.id].content_mode === 'article' && isParagraphChannelForm(editForms[ch.id])"
              class="topic-queue mt-5 pt-4 border-t border-panel-border"
            >
              <h4 class="schedule-title">Очередь тем (2 недели)</h4>
              <p class="field-hint mb-2">
                Вставьте список тем — по одной на строку. Генерация и расписание
                берут следующую pending-тему автоматически. Опубликованные темы
                отмечаются галочкой и не повторяются 90 дней.
              </p>
              <textarea
                v-model="topicQueueDrafts[ch.id]"
                rows="6"
                class="input w-full text-xs mt-1"
                placeholder="Одна тема на строку. Пример: Почему иллюминаторы самолётов круглые."
                :disabled="topicQueueBusy === ch.id"
              />
              <div class="channel-actions mt-2">
                <button
                  type="button"
                  class="btn-secondary btn-sm"
                  :disabled="topicQueueBusy === ch.id || !(topicQueueDrafts[ch.id] || '').trim()"
                  @click="appendTopicQueue(ch.id)"
                >
                  {{ topicQueueBusy === ch.id ? 'Добавление…' : 'Добавить в очередь' }}
                </button>
                <button
                  type="button"
                  class="btn-secondary btn-sm"
                  :disabled="topicQueueBusy === ch.id"
                  @click="refreshTopicQueue(ch.id)"
                >
                  Обновить список
                </button>
              </div>
              <div v-if="topicQueueSummaries[ch.id]" class="topic-queue-summary field-hint mt-2">
                В очереди: {{ topicQueueSummaries[ch.id].pending || 0 }} ·
                опубликовано: {{ topicQueueSummaries[ch.id].published || 0 }} ·
                пропущено: {{ topicQueueSummaries[ch.id].skipped || 0 }}
              </div>
              <ul v-if="(topicQueueItems[ch.id] || []).length" class="topic-queue-list mt-3">
                <li
                  v-for="item in topicQueueItems[ch.id]"
                  :key="item.id"
                  class="topic-queue-item"
                  :data-status="item.status"
                >
                  <span class="topic-queue-status">{{ topicStatusLabel(item.status) }}</span>
                  <span class="topic-queue-title">{{ item.title }}</span>
                  <span v-if="item.published_at" class="topic-queue-date">{{ formatQueueDate(item.published_at) }}</span>
                  <button
                    v-if="item.status === 'pending'"
                    type="button"
                    class="btn-danger btn-sm"
                    @click="topicQueueAction(ch.id, item.id, 'skip')"
                  >Пропустить</button>
                  <button
                    v-else-if="item.status === 'skipped'"
                    type="button"
                    class="btn-secondary btn-sm"
                    @click="topicQueueAction(ch.id, item.id, 'restore_pending')"
                  >Вернуть</button>
                </li>
              </ul>
            </div>

            <div class="article-schedule mt-5 pt-4 border-t border-panel-border">
              <h4 class="schedule-title">Расписание публикаций</h4>
              <label class="field-mini w-full">
                <span>Времена выхода по МСК</span>
                <input
                  v-model="editForms[ch.id].publish_times"
                  type="text"
                  inputmode="numeric"
                  placeholder="09:00, 13:00, 17:00, 21:00"
                  class="input input-sm"
                />
              </label>
              <p class="field-hint mt-1">
                Пост уходит в канал точно в эти времена по Москве (через запятую). В каждый
                слот публикуется один пост из очереди (для article-каналов — генерируется
                статья).
              </p>
            </div>

            <div class="channel-actions">
              <template v-if="editForms[ch.id].content_mode === 'article'">
                <label class="manual-topic-field">
                  <span class="sr-only">Тема</span>
                  <input
                    v-model="manualTopics[ch.id]"
                    type="text"
                    class="input input-sm"
                    maxlength="200"
                    :placeholder="manualTopicPlaceholder(editForms[ch.id])"
                    :disabled="generatingChannel === ch.id"
                    @keydown.enter.prevent="generateArticle(ch.id)"
                  />
                </label>
                <button
                  type="button"
                  class="btn-secondary btn-sm"
                  :disabled="generatingChannel === ch.id"
                  @click="generateArticle(ch.id)"
                >
                  {{ generatingChannel === ch.id ? 'Запуск…' : 'Сгенерировать статью' }}
                </button>
              </template>
              <button type="button" class="btn-primary btn-sm" @click="saveChannel(ch.id)">
                Сохранить изменения
              </button>
              <button type="button" class="btn-danger btn-sm" @click="removeChannel(ch)">
                Удалить канал
              </button>
            </div>
          </div>
        </transition>
      </article>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import PageHeader from '../components/layout/PageHeader.vue'
import { channelsApi } from '../api/index.js'
import { useDialogStore } from '../stores/dialogStore'
import { useActivityStore } from '../stores/activityStore'
import { TOPIC_OPTIONS, topicLabel as topicLabelFn } from '../constants/topics.js'

const dialog = useDialogStore()
const activityStore = useActivityStore()

const channels = ref([])
const sortedChannels = computed(() =>
  [...channels.value].sort((a, b) => Number(b.is_active) - Number(a.is_active))
)
const editForms = reactive({})
const originalForms = reactive({})
const generatingChannel = ref(null)
const manualTopics = reactive({})
const expandedId = ref(null)
const showNewForm = ref(false)
const DEFAULT_PUBLISH_TIMES = '09:00, 13:00, 17:00, 21:00'
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
  post_footer: '',
  publish_times: DEFAULT_PUBLISH_TIMES,
})

const PLATFORM_LABELS = { telegram: 'Telegram', vk: 'VK', max: 'MAX' }
function platformLabel(p) {
  return PLATFORM_LABELS[p] || p
}

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

function buildEditForm(ch) {
  return {
    name: ch.name,
    platform: ch.platform,
    platform_id: ch.platform_id,
    topic: ch.topic,
    content_mode: ch.content_mode || 'news',
    animate_postcards: Boolean(ch.animate_postcards),
    is_active: ch.is_active,
    style_prompt: ch.style_prompt || '',
    image_prompt_guidelines: ch.image_prompt_guidelines || '',
    cross_promote_url: ch.cross_promote_url || '',
    cross_promote_label: ch.cross_promote_label || '',
    cross_promote_emoji_id: ch.cross_promote_emoji_id || '',
    post_footer: ch.post_footer || '',
    publish_times: ch.publish_times || '',
  }
}

function isDirty(id) {
  if (!editForms[id] || !originalForms[id]) return false
  return JSON.stringify(editForms[id]) !== JSON.stringify(originalForms[id])
}

/* Плавная анимация высоты (надёжнее grid-rows при любой раскладке) */
function startExpand(el) {
  el.style.height = '0'
  el.style.overflow = 'hidden'
  void el.offsetHeight
  el.style.height = `${el.scrollHeight}px`
}
function endExpand(el) {
  el.style.height = ''
  el.style.overflow = ''
}
function startCollapse(el) {
  el.style.height = `${el.scrollHeight}px`
  el.style.overflow = 'hidden'
  void el.offsetHeight
}
function doCollapse(el) {
  el.style.height = '0'
}

async function load() {
  const { data } = await channelsApi.list()
  channels.value = data
  data.forEach((ch) => {
    const built = buildEditForm(ch)
    editForms[ch.id] = built
    originalForms[ch.id] = JSON.parse(JSON.stringify(built))
    if (isParagraphChannelForm(built)) {
      refreshTopicQueue(ch.id)
    }
  })
}

/**
 * Проверяет несохранённые изменения перед сворачиванием канала.
 * @returns {Promise<boolean>} можно ли покидать (свернуть) канал
 */
async function guardBeforeLeave(id) {
  if (!isDirty(id)) return true
  const choice = await dialog.unsavedChanges({
    title: 'Несохранённые изменения канала',
    message: `Вы изменили настройки канала «${editForms[id]?.name || '#' + id}», но не сохранили их. Что сделать?`,
  })
  if (choice === 'stay') return false
  if (choice === 'save') {
    return await saveChannel(id)
  }
  // discard — возвращаем исходные значения
  editForms[id] = JSON.parse(JSON.stringify(originalForms[id]))
  return true
}

async function toggleChannel(id) {
  if (expandedId.value === id) {
    if (await guardBeforeLeave(id)) expandedId.value = null
    return
  }
  const current = expandedId.value
  if (current != null && current !== id) {
    if (!(await guardBeforeLeave(current))) return
  }
  expandedId.value = id
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
    post_footer: '',
    publish_times: DEFAULT_PUBLISH_TIMES,
  }
  showNewForm.value = false
  await load()
}

/**
 * @returns {Promise<boolean>} успешно ли сохранено
 */
async function saveChannel(id) {
  const payload = editForms[id]
  if (!payload?.name?.trim() || !payload?.platform_id?.trim()) {
    await dialog.alert({
      title: 'Каналы',
      message: 'Заполните название и ID канала.',
    })
    return false
  }
  try {
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
      post_footer: payload.post_footer?.trim() || null,
      publish_times: payload.publish_times?.trim(),
      animate_postcards: Boolean(payload.animate_postcards),
    })
  } catch (e) {
    await dialog.alertApiError(e, 'Не удалось сохранить канал')
    return false
  }
  await load()
  return true
}

function isPostcardChannelForm(form) {
  if (!form) return false
  if (form.topic === 'postcard') return true
  return String(form.name || '').toLowerCase().includes('открытк')
}

function manualTopicPlaceholder(form) {
  return isPostcardChannelForm(form)
    ? 'Повод или праздник (необязательно)'
    : 'Тема статьи (необязательно)'
}

async function generateArticle(id) {
  generatingChannel.value = id
  try {
    const topic = String(manualTopics[id] || '').trim()
    const { data } = await channelsApi.generateArticle(
      id,
      topic ? { topic } : {},
    )
    manualTopics[id] = ''
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
    if (expandedId.value === ch.id) expandedId.value = null
    delete editForms[ch.id]
    delete originalForms[ch.id]
    await load()
  } catch (e) {
    await dialog.alertApiError(e, 'Не удалось удалить канал')
  }
}

onMounted(load)
</script>

<style scoped>
.form-card {
  @apply panel-card p-5;
}

.form-grid {
  @apply grid gap-3 md:grid-cols-2;
}

.field-label {
  @apply block text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)];
}

.field-hint {
  @apply text-xs text-[var(--text-secondary)];
}

/* Добавление канала */
.add-channel {
  @apply mb-6;
}

.add-toggle {
  @apply flex items-center gap-2 text-sm font-medium text-[var(--text-primary)]
         panel-card w-full p-4 hover:bg-panel-hover transition-colors;
}

/* Аккордеон каналов */
.channels-list {
  @apply flex flex-col gap-3;
}

.channel-card {
  @apply panel-card overflow-hidden transition-colors;
}

.channel-card.is-open {
  @apply ring-1 ring-accent;
}

.channel-header {
  @apply flex w-full flex-wrap items-center justify-between gap-3 p-4 text-left
         cursor-pointer hover:bg-panel-hover transition-colors;
}

.channel-header-main {
  @apply flex items-center gap-3 min-w-0;
}

.channel-card-title {
  @apply text-sm font-semibold text-[var(--text-primary)] truncate;
}

.channel-badges {
  @apply flex flex-wrap items-center gap-2;
}

.chevron {
  @apply inline-block text-[var(--text-secondary)] text-xs transition-transform duration-200;
}

.chevron.open {
  @apply rotate-90;
}

.dirty-dot {
  @apply text-amber-400 text-xs leading-none;
}

.status-pill {
  @apply text-[10px] px-2 py-0.5 rounded-full;
}

.status-pill.on {
  @apply bg-emerald-500/15 text-emerald-400;
}

.status-pill.off {
  @apply bg-panel-hover text-[var(--text-secondary)];
}

/* Плавное раскрытие через анимацию высоты */
.expand-enter-active,
.expand-leave-active {
  transition: height 0.28s ease;
  overflow: hidden;
}

.channel-body {
  @apply px-4 pb-5 pt-1 border-t border-panel-border;
}

.channel-fields {
  @apply mt-1;
}

.channel-actions {
  @apply flex flex-wrap gap-2 mt-4 pt-4 border-t border-panel-border items-center;
}

.topic-queue-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.topic-queue-item {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  padding: 0.45rem 0.6rem;
  border: 1px solid var(--panel-border, #333);
  border-radius: 6px;
  font-size: 0.8rem;
}
.topic-queue-item[data-status="published"] {
  opacity: 0.75;
}
.topic-queue-item[data-status="skipped"] {
  opacity: 0.55;
  text-decoration: line-through;
}
.topic-queue-title {
  flex: 1;
  min-width: 12rem;
}
.topic-queue-date {
  opacity: 0.7;
  font-size: 0.75rem;
}
.manual-topic-field {
  @apply flex-1 min-w-[12rem] max-w-md;
}

.manual-topic-field .input {
  @apply w-full text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)];
  background-color: rgb(var(--panel-bg-rgb));
  color: var(--text-primary);
  -webkit-text-fill-color: var(--text-primary);
}

.manual-topic-field .input::placeholder {
  color: var(--text-secondary);
  opacity: 0.85;
  -webkit-text-fill-color: var(--text-secondary);
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
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
