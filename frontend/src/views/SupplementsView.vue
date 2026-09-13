<template>
  <div class="supplements-page">
    <PageHeader title="Дополнительные публикации" subtitle="Короткие открытия для «Параграфа» · отправка только после вашего одобрения в MAX">
      <template #actions><button class="btn-ghost" :disabled="busy" @click="refresh">Обновить</button></template>
    </PageHeader>
    <p v-if="error" class="notice error" role="alert">{{ error }}</p>
    <p v-if="notice" class="notice success" role="status">{{ notice }}</p>
    <section class="panel intro">
      <div><span class="eyebrow">ОТ ПОДГОТОВКИ ДО ПУБЛИКАЦИИ</span><h2>Платформа предлагает. Вы решаете.</h2>
        <p>Поиск источников → простой короткий текст → обложка OpenAI → личное сообщение бота → ваше одобрение → канал.</p>
        <p class="muted">Утренние статьи не меняются. Без ответа материал остаётся на проверке, а не публикуется автоматически.</p>
      </div>
      <label class="channel-label">Канал MAX
        <select v-model="channelId" class="select" :disabled="busy" @change="changeChannel">
          <option v-for="channel in channels" :key="channel.id" :value="channel.id">{{ channel.name }}</option>
        </select>
      </label>
    </section>
    <p v-if="!loading && !channels.length" class="panel">Нет каналов MAX. Добавьте канал в разделе «Каналы».</p>
    <p v-if="loading" role="status">Загружаю настройки…</p>
    <template v-if="config && !loading">
      <div class="settings-grid">
        <section class="panel">
          <div class="section-heading"><span class="step">01</span><h2>Согласование в MAX</h2></div>
          <p v-if="config.recipient_id" class="connected">✓ Редактор: {{ config.recipient_name }} · ID {{ config.recipient_id }}</p>
          <p v-else class="muted">Личный диалог ещё не привязан. Новый бот не нужен.</p>
          <p v-if="!connection.bot_configured" class="notice error">На сервере не задан MAX_BOT_TOKEN. Подключение бота недоступно.</p>
          <details :open="!connection.webhook_url">
            <summary>Подключение обработчика событий</summary>
            <p class="muted">Один раз укажите публичный HTTPS-адрес этой платформы. Используется существующий бот; его токен не показывается.</p>
            <label>Адрес обработчика<input v-model="webhookUrl" class="input" placeholder="https://ваша-платформа.ru/api/webhooks/max" /></label>
            <button class="btn-secondary" :disabled="busy || !connection.bot_configured" @click="setupConnection">Подключить обработчик</button>
            <p v-if="connection.webhook_url" class="muted">Сохранённая подписка: {{ connection.webhook_url }}</p>
          </details>
          <button class="btn-primary" :disabled="busy || !connection.webhook_url" @click="pair">{{ config.recipient_id ? 'Переподключить редактора' : 'Получить ссылку на бота' }}</button>
          <div v-if="pairUrl" class="notice"><a :href="pairUrl" target="_blank" rel="noopener noreferrer">Открыть MAX и запустить бота →</a><p>Ссылка действует 15 минут и используется один раз. Не пересылайте её. После запуска нажмите «Проверить привязку».</p><button class="btn-ghost" @click="refresh">Проверить привязку</button></div>
        </section>
        <section class="panel">
          <div class="section-heading"><span class="step">02</span><h2>Когда готовить</h2></div>
          <label class="supplement-toggle"><input v-model="form.enabled" type="checkbox" :disabled="!config.recipient_id" /> Подготовка по расписанию</label>
          <p class="muted">В это время материал приходит вам на проверку. Одобрение отправит его в канал сразу, без ожидания другого слота.</p>
          <div class="schedule-fields">
            <label>Первый факт<select v-model.number="form.fact_days[0]" class="select"><option v-for="(day, i) in days" :key="day" :value="i">{{ day }}</option></select></label>
            <label>Новость<select v-model.number="form.news_day" class="select"><option v-for="(day, i) in days" :key="day" :value="i">{{ day }}</option></select></label>
            <label>Второй факт<select v-model.number="form.fact_days[1]" class="select"><option v-for="(day, i) in days" :key="day" :value="i">{{ day }}</option></select></label>
            <label>Время, МСК<input v-model="form.clock" type="time" class="input" required /></label>
          </div>
          <p class="calendar-title">Предпросмотр дат подготовки</p>
          <div class="calendar" :class="{ disabled: !form.enabled }"><span v-for="slot in config.upcoming?.slice(0, 6)" :key="slot.at" class="slot"><strong>{{ formatDate(slot.at) }}</strong>{{ kindLabel(slot.kind) }}</span></div>
          <p class="muted">
            {{ config.enabled ? 'Сохранённое расписание включено.' : 'Сохранённое расписание выключено: задания в эти даты не создаются.' }}
            <strong v-if="scheduleStateChanged"> Изменение галочки ещё не сохранено.</strong>
            Это не даты автоматической публикации: каждый материал сначала придёт вам в MAX и потребует одобрения.
          </p>
          <div class="actions">
            <button class="btn-primary" :disabled="busy || !dirty" @click="save">{{ scheduleSaveLabel }}</button>
            <span v-if="dirty" class="muted">Нажмите кнопку, чтобы применить галочку, дни и время.</span>
          </div>
        </section>
      </div>
      <section class="panel">
        <div class="section-heading"><span class="step">03</span><h2>Как формируется материал</h2></div>
        <div class="rules-grid">
          <label>Темы, источники и исключения<textarea v-model="form.rules" class="input" rows="6" maxlength="6000" /></label>
          <div><label>Правила короткого факта<textarea v-model="form.fact_rules" class="input" rows="3" maxlength="3000" /></label><label>Правила научной новости<textarea v-model="form.news_rules" class="input" rows="3" maxlength="3000" /></label></div>
        </div>
        <p class="muted">Факт: одна понятная мысль в предложении из 12–22 слов. Новость: 2–3 коротких предложения; источники не старше семи дней. Сложный первый вариант автоматически переписывается проще.</p>
        <p class="muted">После текста OpenAI создаёт обложку тем же способом, что и для статей ПАРАГРАФА. Без готовой картинки материал не придёт на одобрение.</p>
        <p class="muted">Если подходящей новости нет — готовится факт с отметкой о замене. Сбой поиска не маскируется заменой. Достоверность и свежесть самого события проверяете вы: программная проверка источников не заменяет редактора.</p>
        <div class="actions"><button class="btn-primary" :disabled="busy || !dirty" @click="save">Сохранить настройки</button><span v-if="dirty" class="muted">Есть несохранённые изменения</span></div>
      </section>
      <section class="panel">
        <div class="section-heading"><span class="step">04</span><h2>Материалы и решения</h2></div>
        <div class="actions"><button class="btn-secondary" :disabled="busy || !config.recipient_id || dirty" @click="generate('fact')">Подготовить факт</button><button class="btn-secondary" :disabled="busy || !config.recipient_id || dirty" @click="generate('news')">Подготовить новость</button><label class="filter-label">Показать<select v-model="filter" class="select"><option value="all">Все материалы</option><option value="review">На проверке</option><option value="errors">Ошибки</option><option value="published">Опубликованные</option></select></label></div>
        <p class="muted">Ручная подготовка использует сохранённые правила и платные API поиска, текстовой модели и OpenAI для картинки. Это может занять несколько минут. Черновики не попадут в канал без кнопки «Одобрить» в MAX.</p>
        <p v-if="!visibleDrafts.length" class="empty">Материалов пока нет. Подготовьте первый факт, чтобы проверить весь путь согласования.</p>
        <article v-for="draft in visibleDrafts" :key="draft.id" class="draft">
          <div class="draft-header"><span class="badge" :class="{ failed: draft.error, done: draft.status === 'published' }">{{ statusLabel(draft.status) }}</span><span class="muted">{{ kindLabel(draft.kind) }} · версия {{ draft.revision }} · {{ formatDate(draft.created_at) }}</span></div>
          <h3>{{ draft.title || 'Материал готовится' }}</h3>
          <div v-if="draft.image_url" class="cover-block">
            <img class="draft-cover" :src="mediaUrl(draft.image_url)" :alt="draft.title || 'Обложка материала'" />
            <p class="muted">Эта картинка придёт в MAX на одобрение и после одобрения будет опубликована вместе с текстом.</p>
          </div>
          <p v-if="draft.trace?.fallback_reason" class="notice">Вместо новости — факт: {{ draft.trace.fallback_reason }}</p>
          <p v-if="draft.error" class="notice error">{{ draft.error }}</p>
          <p v-if="draft.status === 'publish_unknown'" class="notice error">MAX мог принять пост. Не повторяйте отправку, пока не проверите канал вручную.</p>
          <pre class="post-preview">{{ draft.publication_text }}</pre>
          <a v-if="safeLink(draft.platform_url)" :href="safeLink(draft.platform_url)" target="_blank" rel="noopener noreferrer">Открыть опубликованный пост →</a>
          <p v-if="draft.decided_at" class="muted">Решение: {{ formatDate(draft.decided_at) }} · редактор {{ draft.decided_by }}</p>
          <div class="actions">
            <button v-if="editable(draft)" class="btn-ghost" :disabled="busy" @click="startEdit(draft)">Изменить текст</button>
            <button v-if="canRegenerate(draft)" class="btn-ghost" :disabled="busy" @click="act(draft, 'regenerate')">Перегенерировать</button>
            <button v-if="canRegenerate(draft) && draft.status !== 'rejected'" class="btn-ghost" :disabled="busy" @click="act(draft, 'skip')">Пропустить</button>
            <button v-if="isError(draft)" class="btn-secondary" :disabled="busy" @click="retry(draft)">{{ draft.status === 'publish_unknown' ? 'Я проверил: поста нет' : 'Повторить подготовку / согласование' }}</button>
          </div>
          <div v-if="editId === draft.id" class="edit-box"><label>Новая версия<textarea v-model="editText" class="input" rows="5" :maxlength="draft.kind === 'fact' ? 500 : 1000" /></label><p class="muted">Старые кнопки перестанут действовать. Для изменённого текста будет создана новая картинка, затем бот пришлёт новую версию для одобрения.</p><div class="actions"><button class="btn-primary" :disabled="busy" @click="submitEdit(draft)">Сохранить и создать новую обложку</button><button class="btn-ghost" @click="editId = null">Отмена</button></div></div>
          <details class="trace"><summary>Как подготовлено: источники, правила и проверки</summary>
            <p><strong>Почему выбрано — объяснение модели:</strong> {{ draft.trace?.selection_reason || 'Ещё не сформировано' }}</p>
            <p v-if="draft.image_prompt"><strong>Как создана картинка:</strong> OpenAI получил описание «{{ draft.image_prompt }}». В MAX и канал отправляется сохранённый результат, а не новая случайная версия.</p>
            <ul><li v-for="source in draft.sources" :key="source.url"><a v-if="safeLink(source.url)" :href="safeLink(source.url)" target="_blank" rel="noopener noreferrer">{{ source.title || source.url }}</a><span v-else>{{ source.title || 'Источник' }}</span><span class="muted"> {{ source.published_date || 'Дата не указана' }}</span><p class="source-snippet">{{ source.content }}</p></li></ul>
            <p><strong>Поисковые запросы:</strong> {{ draft.trace?.queries?.join(' · ') || 'Ещё не выполнены' }}</p>
            <p><strong>Технические проверки:</strong> {{ draft.trace?.checks?.join(' · ') || 'Ещё не выполнены' }}</p>
            <p class="muted">{{ draft.trace?.limitations }}</p>
            <details><summary>Полный журнал и снимок инструкций</summary><pre class="trace-json">{{ JSON.stringify(draft.trace, null, 2) }}</pre></details>
          </details>
        </article>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { onBeforeRouteLeave, useRoute } from 'vue-router'
import api, { channelsApi } from '../api/index.js'
import PageHeader from '../components/layout/PageHeader.vue'
import { useDialogStore } from '../stores/dialogStore.js'

const route = useRoute()
const dialog = useDialogStore()
const days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
const channels = ref([]), channelId = ref(null), config = ref(null), form = ref(null), drafts = ref([])
const connection = ref({}), webhookUrl = ref(''), pairUrl = ref(''), busy = ref(false), loading = ref(true)
const error = ref(''), notice = ref(''), filter = ref('all'), editId = ref(null), editText = ref('')
let timer, refreshPending = false, loadedChannelId = null
const configFields = ['enabled', 'clock', 'fact_days', 'news_day', 'rules', 'fact_rules', 'news_rules']
const editableConfig = (value) => Object.fromEntries(configFields.map((key) => [key, JSON.parse(JSON.stringify(value[key]))]))
const dirty = computed(() => config.value && form.value && JSON.stringify(form.value) !== JSON.stringify(editableConfig(config.value)))
const scheduleStateChanged = computed(() => config.value && form.value && form.value.enabled !== config.value.enabled)
const scheduleSaveLabel = computed(() => form.value?.enabled ? 'Сохранить и включить расписание' : 'Сохранить и выключить расписание')
const isError = (draft) => ['generation_failed', 'delivery_failed', 'delivery_unknown', 'publish_failed', 'publish_unknown'].includes(draft.status)
const editable = (draft) => ['awaiting', 'review_pending', 'delivery_failed', 'delivery_unknown', 'rejected'].includes(draft.status)
const canRegenerate = (draft) => editable(draft) || ['generation_failed', 'publish_failed'].includes(draft.status)
const visibleDrafts = computed(() => drafts.value.filter((draft) => filter.value === 'all' || (filter.value === 'review' && ['awaiting', 'review_pending'].includes(draft.status)) || (filter.value === 'errors' && isError(draft)) || (filter.value === 'published' && draft.status === 'published')))
const kindLabel = (kind) => kind === 'news' ? 'Научная новость' : 'Короткий факт'
const statusLabel = (status) => ({ queued: 'В очереди подготовки', generating: 'Текст и обложка готовятся', review_pending: 'Ожидает отправки в MAX', delivering: 'Отправляется редактору', awaiting: 'Ждёт вашего решения в MAX', approved: 'Одобрено · ожидает отправки', publishing: 'Публикуется', published: 'Опубликовано', rejected: 'Отклонено / пропущено', generation_failed: 'Ошибка подготовки', delivery_failed: 'Не доставлено редактору', delivery_unknown: 'Доставка карточки не подтверждена', publish_failed: 'Публикация отклонена', publish_unknown: 'Проверьте канал вручную' }[status] || status)
const formatDate = (value) => value ? new Intl.DateTimeFormat('ru-RU', { timeZone: 'Europe/Moscow', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(value)) + ' МСК' : ''
const safeLink = (value) => { try { const url = new URL(value); return url.protocol === 'https:' ? url.href : null } catch { return null } }
const mediaUrl = (value) => { if (!value) return ''; if (value.startsWith('/api/media/')) return value; return safeLink(value) || '' }
const errorText = (exc) => { const detail = exc.response?.data?.detail; return typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((item) => item.msg).join('; ') : 'Не удалось выполнить действие. Проверьте подключение и повторите.' }

async function run(action) {
  if (busy.value) return false
  busy.value = true; error.value = ''; notice.value = ''
  try { await action(); return true } catch (exc) { error.value = errorText(exc); return false } finally { busy.value = false }
}
async function loadChannel(resetForm = false) {
  const id = channelId.value
  if (!id) return
  const { data } = await api.get(`/supplements/${id}`)
  if (id !== channelId.value) return
  const keepEdits = !resetForm && dirty.value
  config.value = data.config; drafts.value = data.drafts
  if (!keepEdits) form.value = editableConfig(data.config)
  loadedChannelId = id
}
async function refresh() {
  await run(async () => { connection.value = (await api.get('/supplements/connection')).data; await loadChannel() })
}
async function changeChannel() {
  if ((dirty.value || editId.value) && !await dialog.confirm({ message: 'Несохранённые изменения будут потеряны. Переключить канал?', confirmLabel: 'Переключить' })) { channelId.value = loadedChannelId; return }
  pairUrl.value = ''; editId.value = null
  await run(() => loadChannel(true))
}
async function setupConnection() {
  if (!await dialog.confirm({ message: 'Подключить события существующего MAX-бота к указанному адресу этой платформы?', confirmLabel: 'Подключить' })) return
  await run(async () => { await api.post('/supplements/connection', { url: webhookUrl.value }); connection.value = (await api.get('/supplements/connection')).data; notice.value = 'Обработчик подключён. Получите ссылку на бота.' })
}
async function pair() {
  if (config.value.recipient_id && !await dialog.confirm({ message: 'Создать новую ссылку привязки редактора? Текущий редактор сохранится до её использования.', confirmLabel: 'Создать ссылку' })) return
  await run(async () => { pairUrl.value = (await api.post(`/supplements/${channelId.value}/pair`)).data.url })
}
async function save() {
  const requestedEnabled = form.value.enabled
  const saved = await run(async () => { await api.put(`/supplements/${channelId.value}`, form.value); await loadChannel(true) })
  if (!saved) { form.value.enabled = config.value.enabled; return }
  notice.value = requestedEnabled ? 'Настройки сохранены. Подготовка по расписанию включена.' : 'Настройки сохранены. Подготовка по расписанию выключена.'
}
async function generate(kind) {
  await run(async () => { await api.post(`/supplements/${channelId.value}/generate`, { kind }); await loadChannel(); notice.value = 'Подготовка поставлена в очередь. Результат придёт в MAX для одобрения.' })
}
async function act(draft, action, extra = {}) {
  if (['skip', 'regenerate'].includes(action) && !await dialog.confirm({ message: action === 'skip' ? 'Пропустить материал? Старые кнопки перестанут действовать.' : 'Отклонить эту версию и подготовить новый материал с повторным поиском?', confirmLabel: 'Продолжить' })) return
  await run(async () => { await api.post(`/supplements/drafts/${draft.id}/action`, { action, ...extra }); await loadChannel(); notice.value = 'Изменения сохранены.' })
}
function startEdit(draft) { editId.value = draft.id; editText.value = draft.text }
async function submitEdit(draft) { await act(draft, 'edit', { text: editText.value }); if (!error.value) editId.value = null }
async function retry(draft) {
  const unknown = draft.status === 'publish_unknown'
  if (!await dialog.confirm({ message: unknown ? 'Продолжайте только если вы открыли канал и убедились, что этого поста нет. Иначе возможен дубль. Будет запрошено новое одобрение.' : 'Повторить операцию? Для отправки в канал снова потребуется одобрение в MAX.', confirmLabel: unknown ? 'Проверил: поста нет' : 'Повторить', danger: unknown })) return
  await act(draft, 'retry', { confirmed_absent: unknown })
}
onBeforeRouteLeave(async () => !(dirty.value || editId.value) || await dialog.confirm({ message: 'Есть несохранённые изменения. Покинуть страницу?', confirmLabel: 'Покинуть' }))
onMounted(async () => {
  await run(async () => {
    channels.value = (await channelsApi.list()).data.filter((channel) => channel.platform === 'max')
    channelId.value = channels.value.find((channel) => String(channel.id) === route.query.channel)?.id || channels.value.find((channel) => /параграф/i.test(channel.name))?.id || channels.value[0]?.id
    connection.value = (await api.get('/supplements/connection')).data
    webhookUrl.value = connection.value.webhook_url || `${window.location.origin}/api/webhooks/max`
    await loadChannel(true)
  })
  loading.value = false
  timer = setInterval(async () => {
    if (busy.value || refreshPending || document.hidden || !channelId.value) return
    refreshPending = true
    try { await loadChannel() } catch (exc) { error.value = errorText(exc) } finally { refreshPending = false }
  }, 10000)
})
onUnmounted(() => clearInterval(timer))
</script>

<style scoped>
.supplements-page { max-width: 1240px; margin: 0 auto; }
.panel { background: rgb(var(--panel-surface-rgb)); border: 1px solid rgb(var(--panel-border-rgb)); border-radius: 16px; padding: 24px; margin-bottom: 20px; }
.intro { display: flex; align-items: center; justify-content: space-between; gap: 24px; background: linear-gradient(115deg, #14b8a612, transparent); }
h2 { font-size: 1.1rem; font-weight: 650; margin: 5px 0 12px; } h3 { font-size: 1rem; font-weight: 650; margin: 12px 0; }
p { line-height: 1.6; margin: 8px 0; font-size: .9rem; } .muted { color: var(--text-secondary); font-size: .83rem; }
.eyebrow { color: #0d9488; font-size: .68rem; letter-spacing: .1em; font-weight: 700; }
.settings-grid, .rules-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.section-heading { display: flex; align-items: baseline; gap: 10px; } .step { color: #0d9488; font-weight: 700; font-size: .8rem; }
label { display: block; font-size: .83rem; font-weight: 550; margin: 12px 0; } label .input, label .select { display: block; width: 100%; margin-top: 7px; }
.channel-label { min-width: 230px; } .schedule-fields { display: grid; grid-template-columns: 1fr 1fr; gap: 0 12px; }
.supplement-toggle { display: flex; align-items: center; gap: 10px; } .supplement-toggle input { accent-color: #0d9488; }
.actions { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin: 14px 0; } .filter-label { margin-left: auto; }
.calendar-title { margin-top: 18px; font-size: .8rem; font-weight: 650; }
.calendar { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; transition: opacity .2s ease; } .calendar.disabled { opacity: .42; } .slot { display: flex; flex-direction: column; gap: 4px; font-size: .72rem; border-radius: 8px; padding: 9px 12px; background: #14b8a60d; border: 1px solid #14b8a633; } .slot strong { font-weight: 550; }
.notice { padding: 12px 16px; border-radius: 10px; background: #0ea5e912; border: 1px solid #0ea5e933; overflow-wrap: anywhere; } .notice.error { background: #ef444412; border-color: #ef444455; } .notice.success { background: #14b8a612; border-color: #14b8a655; } .connected { color: #0d9488; font-weight: 550; }
details { margin: 16px 0; } summary { cursor: pointer; font-size: .85rem; font-weight: 550; } details .btn-secondary { margin-top: 6px; }
.draft { border-top: 1px solid #64748b33; padding: 22px 0 8px; } .draft-header { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; } .badge { border-radius: 20px; padding: 5px 10px; font-size: .73rem; background: #0ea5e919; color: var(--text-primary); } .badge.failed { background: #ef444419; } .badge.done { background: #14b8a619; }
.post-preview { white-space: pre-wrap; overflow-wrap: anywhere; font-family: inherit; font-size: .95rem; line-height: 1.75; margin: 16px 0; max-width: 850px; }
.cover-block { max-width: 720px; margin: 16px 0; } .draft-cover { display: block; width: 100%; max-height: 420px; object-fit: cover; border-radius: 12px; border: 1px solid #64748b33; }
.trace { background: #64748b08; padding: 14px; border-radius: 10px; } .trace-json { white-space: pre-wrap; overflow-wrap: anywhere; font-size: .75rem; max-height: 450px; overflow-y: auto; } .source-snippet { font-size: .8rem; color: var(--text-secondary); }
a { color: #0d9488; text-decoration: underline; overflow-wrap: anywhere; } .empty { padding: 25px 0; color: var(--text-secondary); } button:disabled { opacity: .45; cursor: not-allowed; } .edit-box { padding: 16px; border: 1px solid #14b8a644; border-radius: 12px; }
@media (max-width: 850px) { .settings-grid, .rules-grid { grid-template-columns: 1fr; } .intro { align-items: stretch; flex-direction: column; } .panel { padding: 18px; } .filter-label { margin-left: 0; } }
</style>
