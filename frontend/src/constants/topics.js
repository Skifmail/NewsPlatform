/** Тематики контента платформы. */

export const TOPIC_LABELS = {
  it: 'IT',
  auto: 'Авто',
  russia: 'Россия',
  sport: 'Спорт',
  postcard: 'Открытки',
}

export const TOPIC_OPTIONS = [
  { value: 'it', label: 'IT' },
  { value: 'auto', label: 'Авто' },
  { value: 'russia', label: 'Россия' },
  { value: 'sport', label: 'Спорт' },
  { value: 'postcard', label: 'Открытки' },
]

/**
 * @param {string | undefined | null} topic
 * @returns {string}
 */
export function topicLabel(topic) {
  return TOPIC_LABELS[topic] || topic || '—'
}
