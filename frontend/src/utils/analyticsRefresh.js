import { analyticsApi } from '../api/index.js'

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * Запускает сбор статистики всех каналов и возвращает job_id для отслеживания.
 * @returns {Promise<string>}
 */
export async function startRefreshAll() {
  const { data } = await analyticsApi.refreshAll()
  return data.job_id
}

/**
 * Запускает сбор статистики одного канала и возвращает job_id.
 * @param {number} channelId
 * @returns {Promise<string>}
 */
export async function startRefreshChannel(channelId) {
  const { data } = await analyticsApi.refreshChannel(channelId)
  return data.job_id
}

/**
 * Опрашивает прогресс задачи сбора статистики до завершения.
 *
 * @param {string} jobId
 * @param {(progress: object) => void} onUpdate колбэк состояния прогресса.
 * @param {{ timeoutMs?: number, intervalMs?: number }} [opts]
 * @returns {Promise<object>} финальное состояние прогресса.
 */
export async function pollRefreshProgress(
  jobId,
  onUpdate,
  { timeoutMs = 180000, intervalMs = 1200 } = {},
) {
  const deadline = Date.now() + timeoutMs
  let last = null

  while (Date.now() < deadline) {
    let progress = null
    try {
      const { data } = await analyticsApi.refreshProgress(jobId)
      progress = data
    } catch (e) {
      // Прогресс ещё не успел появиться в Redis — ждём и пробуем снова.
      if (e.response?.status !== 404) throw e
    }

    if (progress) {
      last = progress
      if (typeof onUpdate === 'function') onUpdate(progress)
      if (progress.status === 'done' || progress.status === 'error') {
        return progress
      }
    }

    await sleep(intervalMs)
  }

  if (last) return last
  throw new Error('Сбор статистики ещё идёт. Подождите и обновите страницу.')
}
