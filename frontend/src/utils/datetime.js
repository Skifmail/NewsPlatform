/**
 * Форматирует ISO-дату обработки поста для карточки.
 *
 * @param {string | null | undefined} iso
 * @returns {string}
 */
/**
 * Значение по умолчанию для input datetime-local (+1 час).
 *
 * @returns {string}
 */
export function defaultScheduleLocalInput() {
  const d = new Date(Date.now() + 60 * 60 * 1000)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function localInputToIso(local) {
  if (!local) return null
  return new Date(local).toISOString()
}

/**
 * Форматирует ISO UTC для журнала и статусов планировщика.
 *
 * @param {string | null | undefined} iso
 * @returns {string}
 */
export function formatUtcDateTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'UTC',
    timeZoneName: 'short',
  })
}

export function formatProcessedAt(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
