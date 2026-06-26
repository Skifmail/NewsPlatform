"""Результат AI-обработки сырого поста."""

from dataclasses import dataclass

from app.domain.topics import TOPIC_LABELS as _TOPIC_LABELS


@dataclass
class ProcessResult:
    """Итог process_raw_post.

    Args:
        created_ids: ID созданных processed_posts.
        topic_used: тема, по которой искали каналы.
        message: пояснение при пустом результате.
    """

    created_ids: list[int]
    topic_used: str
    message: str | None = None

    def summary(self) -> str:
        """Краткий итог для панели «Задачи».

        Returns:
            str: текст результата.
        """
        if self.created_ids:
            label = _TOPIC_LABELS.get(self.topic_used, self.topic_used)
            return (
                f"В очередь модерации: {len(self.created_ids)} пост(ов) "
                f"(тема {label})"
            )
        if self.message:
            return self.message
        return "Посты в очередь модерации не добавлены"
