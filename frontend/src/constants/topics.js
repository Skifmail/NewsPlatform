/** Тематики контента платформы. */

export const TOPIC_LABELS = {
  it: 'IT',
  auto: 'Авто',
  russia: 'Россия',
  sport: 'Спорт',
}

export const TOPIC_OPTIONS = [
  { value: 'it', label: 'IT' },
  { value: 'auto', label: 'Авто' },
  { value: 'russia', label: 'Россия' },
  { value: 'sport', label: 'Спорт' },
]

/**
 * @param {string | undefined | null} topic
 * @returns {string}
 */
export function topicLabel(topic) {
  return TOPIC_LABELS[topic] || topic || '—'
}
