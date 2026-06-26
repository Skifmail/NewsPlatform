/** Лимит подписи к фото в Telegram Bot API. */
export const TELEGRAM_CAPTION_MAX = 1024

/** Лимит подписи к медиа через userbot (MTProto + Premium). */
export const TELEGRAM_USER_CAPTION_MAX = 4096

const ALLOWED_TAGS = new Set(['B', 'STRONG', 'I', 'EM', 'A', 'BR', 'BLOCKQUOTE'])

/**
 * Экранирует спецсимволы HTML.
 *
 * @param {string} text
 * @returns {string}
 */
function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/**
 * Рекурсивно очищает DOM-узел до разрешённых Telegram HTML-тегов.
 *
 * @param {Node} node
 * @returns {string}
 */
function sanitizeNode(node) {
  if (node.nodeType === Node.TEXT_NODE) {
    return escapeHtml(node.textContent || '')
  }
  if (node.nodeType !== Node.ELEMENT_NODE) {
    return ''
  }

  const tag = node.tagName
  if (!ALLOWED_TAGS.has(tag)) {
    return Array.from(node.childNodes).map(sanitizeNode).join('')
  }

  if (tag === 'BR') {
    return '<br>'
  }

  const inner = Array.from(node.childNodes).map(sanitizeNode).join('')

  if (tag === 'A') {
    const href = node.getAttribute('href') || ''
    if (!/^https?:\/\//i.test(href)) {
      return inner
    }
    const safeHref = href.replace(/"/g, '%22')
    return `<a href="${safeHref}" target="_blank" rel="noopener noreferrer">${inner}</a>`
  }

  return `<${tag.toLowerCase()}>${inner}</${tag.toLowerCase()}>`
}

/**
 * Преобразует plain text с переносами в абзацы.
 *
 * @param {string} text
 * @returns {string}
 */
function plainTextToHtml(text) {
  return text
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean)
    .map((block) => `<p class="tg-paragraph">${escapeHtml(block).replace(/\n/g, '<br>')}</p>`)
    .join('')
}

/**
 * Готовит HTML текста поста для предпросмотра Telegram.
 *
 * @param {string} text
 * @returns {string}
 */
export function formatTelegramPreviewHtml(text) {
  if (!text) return ''
  const trimmed = text.trim()
  if (!trimmed) return ''

  if (/<[a-z][\s\S]*>/i.test(trimmed)) {
    const withoutP = trimmed
      .replace(/<\/p>\s*/gi, '\n\n')
      .replace(/<p[^>]*>\s*/gi, '')
    const doc = new DOMParser().parseFromString(withoutP, 'text/html')
    const bodyHtml = Array.from(doc.body.childNodes).map(sanitizeNode).join('')
    if (bodyHtml.includes('\n\n')) {
      return bodyHtml
        .split(/\n{2,}/)
        .map((block) => block.trim())
        .filter(Boolean)
        .map((block) => `<p class="tg-paragraph">${block}</p>`)
        .join('')
    }
    return bodyHtml
      ? `<p class="tg-paragraph">${bodyHtml}</p>`
      : plainTextToHtml(trimmed)
  }

  return plainTextToHtml(trimmed)
}

/**
 * Убирает HTML для короткого превью в карточке.
 *
 * @param {string} text
 * @returns {string}
 */
export function stripHtmlForPreview(text) {
  if (!text) return ''
  if (!/<[a-z][\s\S]*>/i.test(text)) {
    return text
  }
  const doc = new DOMParser().parseFromString(text, 'text/html')
  return (doc.body.textContent || '').replace(/\s+/g, ' ').trim()
}

/**
 * Каналы Github / Параграф — полный текст в одном сообщении без Telegraph.
 *
 * @param {{ name?: string, content_mode?: string } | null | undefined} channel
 * @returns {boolean}
 */
export function isLongFormTelegramChannel(channel) {
  if (!channel || channel.content_mode !== 'article') return false
  const name = (channel.name || '').toLowerCase()
  return (
    name.includes('github') ||
    name.includes('находк') ||
    name.includes('параграф')
  )
}

/**
 * Текст article-поста для предпросмотра (карточка + тело).
 *
 * @param {{ rewritten_text?: string, article_body?: string } | null | undefined} post
 * @returns {string}
 */
export function buildArticlePreviewText(post) {
  const teaser = post?.rewritten_text || ''
  const body = post?.article_body || ''
  if (!body) return teaser
  if (!teaser) return body
  return `${teaser.trim()}\n\n${body.trim()}`
}

/**
 * Нужна ли публикация «фото + ответ с текстом» (fallback бота при длинной подписи).
 *
 * @param {string} text
 * @param {boolean} hasImage
 * @param {{ longForm?: boolean }} [options]
 * @returns {boolean}
 */
export function usesSplitTelegramPublish(text, hasImage, options = {}) {
  const cap = options.longForm ? TELEGRAM_USER_CAPTION_MAX : TELEGRAM_CAPTION_MAX
  return Boolean(hasImage && text && text.length > cap)
}
