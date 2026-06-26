"""Ошибки публикации."""


class PublishPermanentError(RuntimeError):
    """Ошибка публикации, повтор Celery-задачи не исправит ситуацию."""
