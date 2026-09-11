"""Типизированные ошибки подготовки статьи."""


class ArticleGenerationError(RuntimeError):
    """Базовая ошибка домена генерации статей.

    Attributes:
        args: Описание причины, по которой черновик нельзя использовать.
    """


class InvalidArticleDraftError(ArticleGenerationError):
    """Модель не вернула пригодный для публикации черновик после повторной попытки.

    Attributes:
        args: Описание ошибки формата или незавершённости ответа.
    """
