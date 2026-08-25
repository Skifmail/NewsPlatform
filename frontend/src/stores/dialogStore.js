import { defineStore } from 'pinia'
import { ref } from 'vue'

/**
 * @typedef {object} DialogBase
 * @property {string} [title]
 * @property {string} message
 */

let resolver = null

export const useDialogStore = defineStore('dialog', () => {
  const active = ref(null)

  function _open(payload) {
    return new Promise((resolve) => {
      resolver = resolve
      active.value = payload
    })
  }

  function _finish(value) {
    const r = resolver
    resolver = null
    active.value = null
    r?.(value)
  }

  /**
   * @param {DialogBase & { confirmLabel?: string }} options
   * @returns {Promise<void>}
   */
  function alert(options) {
    return _open({
      kind: 'alert',
      title: options.title || 'Уведомление',
      message: options.message,
      confirmLabel: options.confirmLabel || 'OK',
    }).then(() => undefined)
  }

  /**
   * @param {DialogBase & {
   *   confirmLabel?: string
   *   cancelLabel?: string
   *   danger?: boolean
   * }} options
   * @returns {Promise<boolean>}
   */
  function confirm(options) {
    return _open({
      kind: 'confirm',
      title: options.title || 'Подтвердите действие',
      message: options.message,
      confirmLabel: options.confirmLabel || 'OK',
      cancelLabel: options.cancelLabel || 'Отмена',
      danger: Boolean(options.danger),
    })
  }

  /**
   * @param {DialogBase & {
   *   stayLabel?: string
   *   discardLabel?: string
   *   saveLabel?: string
   * }} options
   * @returns {Promise<'stay' | 'discard' | 'save'>}
   */
  function unsavedChanges(options) {
    return _open({
      kind: 'unsaved',
      title: options.title || 'Несохранённые изменения',
      message:
        options.message ||
        'Вы изменили настройки, но не сохранили их. Что сделать?',
      stayLabel: options.stayLabel || 'Остаться',
      discardLabel: options.discardLabel || 'Выйти без сохранения',
      saveLabel: options.saveLabel || 'Сохранить и выйти',
    })
  }

  /**
   * @param {DialogBase & {
   *   label?: string
   *   placeholder?: string
   *   defaultValue?: string
   *   inputType?: string
   *   confirmLabel?: string
   *   cancelLabel?: string
   * }} options
   * @returns {Promise<string | null>}
   */
  function prompt(options) {
    return _open({
      kind: 'prompt',
      title: options.title || 'Введите значение',
      message: options.message || '',
      label: options.label || '',
      placeholder: options.placeholder || '',
      defaultValue: options.defaultValue || '',
      inputValue: options.defaultValue || '',
      inputType: options.inputType || 'text',
      confirmLabel: options.confirmLabel || 'OK',
      cancelLabel: options.cancelLabel || 'Отмена',
    })
  }

  function confirmAction() {
    const kind = active.value?.kind
    if (kind === 'prompt') {
      _finish(active.value.inputValue ?? '')
      return
    }
    _finish(true)
  }

  /**
   * @param {unknown} value
   */
  function chooseAction(value) {
    _finish(value)
  }

  function cancelAction() {
    const kind = active.value?.kind
    if (kind === 'unsaved') {
      _finish('stay')
      return
    }
    if (kind === 'prompt') {
      _finish(null)
      return
    }
    if (kind === 'confirm') {
      _finish(false)
      return
    }
    _finish(undefined)
  }

  /**
   * @param {unknown} error
   * @param {string} fallback
   * @returns {Promise<void>}
   */
  async function alertApiError(error, fallback) {
    const status = error?.response?.status
    const detail = error?.response?.data?.detail
    let message =
      typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.join(', ') : fallback
    if (status === 413) {
      message =
        'Файл слишком большой для сервера. Максимум около 250 МБ — сожмите видео или выберите файл поменьше.'
    } else if (!detail && error?.message && error.message !== 'Network Error') {
      message = error.message || fallback
    } else if (!detail && error?.message === 'Network Error') {
      message =
        'Сеть оборвала загрузку. Часто так бывает при слишком большом файле или обрыве соединения.'
    }
    await alert({ message })
  }

  return {
    active,
    alert,
    confirm,
    unsavedChanges,
    prompt,
    confirmAction,
    chooseAction,
    cancelAction,
    alertApiError,
  }
})
