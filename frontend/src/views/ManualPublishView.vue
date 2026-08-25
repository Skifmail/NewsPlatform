<template>
  <div>
    <PageHeader
      title="Ручная публикация"
      subtitle="Обложка, видео, текст и две callback-кнопки — сразу в канал (ПАРАГРАФ, Открытки и др.)"
    />

    <form class="publish-card" @submit.prevent="submit">
      <label class="field-label">Канал</label>
      <select v-model="form.channelId" class="select w-full mb-4" required>
        <option disabled value="">Выберите канал</option>
        <option v-for="ch in preferredChannels" :key="ch.id" :value="ch.id">
          {{ ch.name }} · {{ platformLabel(ch.platform) }}
        </option>
        <option v-if="otherChannels.length" disabled>────────</option>
        <option v-for="ch in otherChannels" :key="ch.id" :value="ch.id">
          {{ ch.name }} · {{ platformLabel(ch.platform) }}
        </option>
      </select>

      <label class="field-label">Медиа</label>
      <p class="field-hint mb-2">
        Можно загрузить обложку и видео вместе — уйдёт одним постом (фото + видео).
      </p>
      <div class="media-grid mb-4">
        <div class="media-slot">
          <p class="media-slot-title">Обложка (фото)</p>
          <input
            ref="imageInput"
            type="file"
            accept="image/jpeg,image/png,image/webp,image/gif"
            class="hidden"
            @change="onImagePick"
          />
          <div v-if="uploadingImage" class="upload-progress">
            <img v-if="imageLocalPreview" :src="imageLocalPreview" alt="" class="upload-thumb" />
            <div class="upload-progress-body">
              <p class="upload-progress-label">
                Загрузка фото… {{ imageProgress }}%
                <span v-if="imageProgressDetail" class="upload-progress-size">
                  {{ imageProgressDetail }}
                </span>
              </p>
              <div class="progress-track" role="progressbar" :aria-valuenow="imageProgress" aria-valuemin="0" aria-valuemax="100">
                <div class="progress-fill" :style="{ width: `${imageProgress}%` }" />
              </div>
            </div>
          </div>
          <div v-else-if="imagePreview" class="media-preview">
            <img :src="imagePreview" alt="Обложка" />
            <button type="button" class="btn-ghost btn-sm" @click="clearImage">Убрать</button>
          </div>
          <button
            v-else
            type="button"
            class="media-drop"
            @click="imageInput?.click()"
          >
            Выбрать фото
          </button>
        </div>
        <div class="media-slot">
          <p class="media-slot-title">Видео к обложке</p>
          <input
            ref="videoInput"
            type="file"
            accept="video/mp4,video/webm,video/quicktime"
            class="hidden"
            @change="onVideoPick"
          />
          <div v-if="uploadingVideo" class="upload-progress">
            <video
              v-if="videoLocalPreview"
              :src="videoLocalPreview"
              muted
              playsinline
              class="upload-thumb"
            />
            <div class="upload-progress-body">
              <p class="upload-progress-label">
                Загрузка видео… {{ videoProgress }}%
                <span v-if="videoProgressDetail" class="upload-progress-size">
                  {{ videoProgressDetail }}
                </span>
              </p>
              <div class="progress-track" role="progressbar" :aria-valuenow="videoProgress" aria-valuemin="0" aria-valuemax="100">
                <div class="progress-fill" :style="{ width: `${videoProgress}%` }" />
              </div>
            </div>
          </div>
          <div v-else-if="videoPreview" class="media-preview">
            <video :src="videoPreview" controls muted playsinline />
            <button type="button" class="btn-ghost btn-sm" @click="clearVideo">Убрать</button>
          </div>
          <button
            v-else
            type="button"
            class="media-drop"
            @click="videoInput?.click()"
          >
            Выбрать видео
          </button>
        </div>
      </div>

      <label class="field-label">Текст поста</label>
      <div class="fmt-toolbar">
        <button type="button" class="fmt-btn" title="Жирный" @click="wrapTag('b')"><b>B</b></button>
        <button type="button" class="fmt-btn" title="Курсив" @click="wrapTag('i')"><i>I</i></button>
        <button type="button" class="fmt-btn" title="Подчёркнутый" @click="wrapTag('u')"><u>U</u></button>
        <button type="button" class="fmt-btn" title="Ссылка" @click="insertLink">A</button>
        <button type="button" class="fmt-btn" title="Абзац" @click="wrapTag('p')">¶</button>
      </div>
      <textarea
        ref="textArea"
        v-model="form.text"
        rows="12"
        class="input w-full mb-4 resize-y min-h-[200px] font-mono text-sm"
        placeholder="Текст поста. Можно HTML: &lt;b&gt;, &lt;i&gt;, &lt;a href=&quot;…&quot;&gt;"
        required
      />

      <div class="buttons-grid mb-4">
        <div>
          <label class="field-label">Кнопка 1</label>
          <input
            v-model="form.button1"
            type="text"
            maxlength="64"
            class="input w-full"
            placeholder="Например: Да, интересно"
            required
          />
        </div>
        <div>
          <label class="field-label">Кнопка 2</label>
          <input
            v-model="form.button2"
            type="text"
            maxlength="64"
            class="input w-full"
            placeholder="Например: Уже знал"
            required
          />
        </div>
      </div>
      <p class="field-hint mb-4">
        Callback-кнопки для MAX: подписчик нажимает — ответ уходит ботом. Нужны обе подписи.
      </p>

      <div class="form-actions">
        <button type="submit" class="btn-primary" :disabled="submitting || !canSubmit">
          {{ submitting ? 'Отправка…' : 'Отправить в канал' }}
        </button>
        <button type="button" class="btn-ghost" :disabled="submitting" @click="resetForm">
          Очистить
        </button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import PageHeader from '../components/layout/PageHeader.vue'
import { channelsApi, mediaApi, postsApi } from '../api/index.js'
import { useDialogStore } from '../stores/dialogStore'

const dialog = useDialogStore()

const channels = ref([])
const imageInput = ref(null)
const videoInput = ref(null)
const textArea = ref(null)
const uploadingImage = ref(false)
const uploadingVideo = ref(false)
const imageProgress = ref(0)
const videoProgress = ref(0)
const imageProgressDetail = ref('')
const videoProgressDetail = ref('')
const imageLocalPreview = ref('')
const videoLocalPreview = ref('')
const submitting = ref(false)
const imagePreview = ref('')
const videoPreview = ref('')

function formatBytes(n) {
  if (!n || n <= 0) return ''
  if (n < 1024) return `${n} Б`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} КБ`
  return `${(n / (1024 * 1024)).toFixed(1)} МБ`
}

function progressDetail(loaded, total) {
  if (!total) return formatBytes(loaded)
  return `${formatBytes(loaded)} / ${formatBytes(total)}`
}

function revokeLocalPreview(urlRef) {
  const url = urlRef.value
  if (url && url.startsWith('blob:')) {
    URL.revokeObjectURL(url)
  }
  urlRef.value = ''
}

const form = reactive({
  channelId: '',
  text: '',
  button1: '',
  button2: '',
  imageUrl: null,
  videoUrl: null,
})

function isPreferredChannel(ch) {
  const name = (ch.name || '').toLowerCase()
  return (
    name.includes('параграф') ||
    name.includes('открытк') ||
    ch.topic === 'postcard'
  )
}

const preferredChannels = computed(() =>
  channels.value.filter(isPreferredChannel)
)
const otherChannels = computed(() =>
  channels.value.filter((ch) => !isPreferredChannel(ch))
)

const canSubmit = computed(
  () =>
    form.channelId &&
    form.text.trim() &&
    form.button1.trim() &&
    form.button2.trim() &&
    !uploadingImage.value &&
    !uploadingVideo.value
)

function platformLabel(platform) {
  const map = { telegram: 'Telegram', vk: 'VK', max: 'MAX' }
  return map[platform] || platform
}

onMounted(async () => {
  try {
    const { data } = await channelsApi.list()
    channels.value = data || []
    const preferred = preferredChannels.value
    if (preferred.length === 1) {
      form.channelId = preferred[0].id
    } else {
      const paragraph = preferred.find((c) =>
        (c.name || '').toLowerCase().includes('параграф')
      )
      if (paragraph) form.channelId = paragraph.id
    }
  } catch (e) {
    await dialog.alertApiError(e, 'Не удалось загрузить каналы')
  }
})

const MAX_UPLOAD_BYTES = 250 * 1024 * 1024

async function uploadFile(file, kind, onProgress) {
  if (file.size > MAX_UPLOAD_BYTES) {
    throw new Error(
      `Файл слишком большой (${formatBytes(file.size)}). Максимум ${formatBytes(MAX_UPLOAD_BYTES)}.`
    )
  }
  const { data } = await mediaApi.upload(file, { onProgress })
  if (kind === 'image' && data.kind !== 'image') {
    throw new Error('Ожидалось изображение')
  }
  if (kind === 'video' && data.kind !== 'video') {
    throw new Error('Ожидалось видео')
  }
  return data
}

async function onImagePick(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  revokeLocalPreview(imageLocalPreview)
  imageLocalPreview.value = URL.createObjectURL(file)
  uploadingImage.value = true
  imageProgress.value = 0
  imageProgressDetail.value = `0 / ${formatBytes(file.size)}`
  try {
    const data = await uploadFile(file, 'image', (percent, loaded, total) => {
      imageProgress.value = percent
      imageProgressDetail.value = progressDetail(loaded, total || file.size)
    })
    imageProgress.value = 100
    form.imageUrl = data.url
    imagePreview.value = data.public_url
  } catch (e) {
    await dialog.alertApiError(e, 'Не удалось загрузить изображение')
  } finally {
    uploadingImage.value = false
    imageProgress.value = 0
    imageProgressDetail.value = ''
    revokeLocalPreview(imageLocalPreview)
  }
}

async function onVideoPick(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  revokeLocalPreview(videoLocalPreview)
  videoLocalPreview.value = URL.createObjectURL(file)
  uploadingVideo.value = true
  videoProgress.value = 0
  videoProgressDetail.value = `0 / ${formatBytes(file.size)}`
  try {
    const data = await uploadFile(file, 'video', (percent, loaded, total) => {
      videoProgress.value = percent
      videoProgressDetail.value = progressDetail(loaded, total || file.size)
    })
    videoProgress.value = 100
    form.videoUrl = data.url
    videoPreview.value = data.public_url
  } catch (e) {
    await dialog.alertApiError(e, 'Не удалось загрузить видео')
  } finally {
    uploadingVideo.value = false
    videoProgress.value = 0
    videoProgressDetail.value = ''
    revokeLocalPreview(videoLocalPreview)
  }
}

function clearImage() {
  form.imageUrl = null
  imagePreview.value = ''
  revokeLocalPreview(imageLocalPreview)
}

function clearVideo() {
  form.videoUrl = null
  videoPreview.value = ''
  revokeLocalPreview(videoLocalPreview)
}

function wrapTag(tag) {
  const el = textArea.value
  if (!el) return
  const start = el.selectionStart
  const end = el.selectionEnd
  const selected = form.text.slice(start, end) || 'текст'
  const wrapped = `<${tag}>${selected}</${tag}>`
  form.text = form.text.slice(0, start) + wrapped + form.text.slice(end)
  requestAnimationFrame(() => {
    el.focus()
    const cursor = start + wrapped.length
    el.setSelectionRange(cursor, cursor)
  })
}

async function insertLink() {
  const url = await dialog.prompt({
    title: 'Ссылка',
    message: 'Вставьте URL',
    label: 'URL',
    defaultValue: 'https://',
    confirmLabel: 'Вставить',
  })
  if (!url) return
  const el = textArea.value
  if (!el) return
  const start = el.selectionStart
  const end = el.selectionEnd
  const selected = form.text.slice(start, end) || 'ссылка'
  const wrapped = `<a href="${url}">${selected}</a>`
  form.text = form.text.slice(0, start) + wrapped + form.text.slice(end)
}

function resetForm() {
  form.text = ''
  form.button1 = ''
  form.button2 = ''
  clearImage()
  clearVideo()
}

async function submit() {
  if (!canSubmit.value) return
  submitting.value = true
  try {
    const { data } = await postsApi.createManual({
      channel_id: Number(form.channelId),
      text: form.text.trim(),
      button_1: form.button1.trim(),
      button_2: form.button2.trim(),
      image_url: form.imageUrl || null,
      video_url: form.videoUrl || null,
      publish_immediately: true,
    })
    await dialog.alert({
      title: 'Отправлено',
      message: `Пост #${data.id} поставлен в очередь публикации.`,
    })
    resetForm()
  } catch (e) {
    await dialog.alertApiError(e, 'Не удалось опубликовать пост')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.publish-card {
  @apply panel-card p-5 max-w-3xl;
}

.field-label {
  @apply mb-1.5 block text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)];
}

.field-hint {
  @apply text-xs text-[var(--text-secondary)] leading-relaxed;
}

.media-grid {
  @apply grid gap-3 sm:grid-cols-2;
}

.media-slot {
  @apply rounded-lg border border-panel-border bg-panel-bg p-3;
}

.media-slot-title {
  @apply mb-2 text-xs font-medium text-[var(--text-secondary)];
}

.media-drop {
  @apply flex h-32 w-full items-center justify-center rounded-lg border border-dashed border-panel-border
    text-sm text-[var(--text-secondary)] hover:border-accent/50 hover:text-accent transition-colors
    disabled:opacity-50;
}

.media-preview {
  @apply flex flex-col gap-2;
}

.media-preview img,
.media-preview video {
  @apply max-h-40 w-full rounded-lg object-cover bg-panel-hover;
}

.upload-progress {
  @apply flex flex-col gap-2;
}

.upload-thumb {
  @apply max-h-28 w-full rounded-lg object-cover bg-panel-hover opacity-80;
}

.upload-progress-body {
  @apply flex flex-col gap-1.5;
}

.upload-progress-label {
  @apply text-xs font-medium text-[var(--text-primary)] tabular-nums;
}

.upload-progress-size {
  @apply ml-1 font-normal text-[var(--text-secondary)];
}

.progress-track {
  @apply h-2 w-full overflow-hidden rounded-full bg-panel-hover;
}

.progress-fill {
  @apply h-full rounded-full bg-accent transition-[width] duration-150 ease-out;
}

.fmt-toolbar {
  @apply mb-1.5 flex flex-wrap gap-1;
}

.fmt-btn {
  @apply inline-flex h-8 min-w-8 items-center justify-center rounded-md border border-panel-border
    bg-panel-hover px-2 text-sm text-[var(--text-primary)] hover:border-accent/40;
}

.buttons-grid {
  @apply grid gap-3 sm:grid-cols-2;
}

.form-actions {
  @apply flex flex-wrap gap-2 border-t border-panel-border pt-4;
}

.hidden {
  @apply sr-only;
}
</style>
