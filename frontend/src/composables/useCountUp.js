import { onUnmounted, ref, toValue, watch } from 'vue'

/**
 * Проверяет системную настройку reduced motion.
 *
 * @returns {boolean}
 */
function prefersReducedMotion() {
  if (typeof window === 'undefined') return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/**
 * Анимирует число от текущего к целевому значению.
 *
 * @param {import('vue').MaybeRefOrGetter<number|null|undefined>} target
 * @param {{ duration?: number }} [options]
 * @returns {import('vue').Ref<number>}
 */
export function useCountUp(target, options = {}) {
  const duration = options.duration ?? 1200
  const display = ref(0)
  let rafId = null

  function cancelAnimation() {
    if (rafId != null) {
      cancelAnimationFrame(rafId)
      rafId = null
    }
  }

  function animateTo(nextValue) {
    cancelAnimation()
    const to = Number(nextValue) || 0
    if (prefersReducedMotion()) {
      display.value = to
      return
    }

    const from = display.value
    const start = performance.now()

    const step = (now) => {
      const progress = Math.min(1, (now - start) / duration)
      const eased = 1 - (1 - progress) ** 3
      display.value = Math.round(from + (to - from) * eased)
      if (progress < 1) {
        rafId = requestAnimationFrame(step)
      }
    }

    rafId = requestAnimationFrame(step)
  }

  watch(
    () => toValue(target),
    (value) => animateTo(value),
    { immediate: true },
  )

  onUnmounted(cancelAnimation)

  return display
}
