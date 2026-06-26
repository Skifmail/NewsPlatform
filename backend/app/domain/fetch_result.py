"""Результат парсинга источника."""

from dataclasses import dataclass


@dataclass
class FetchResult:
    """Итог одного запуска парсера.

    Args:
        created_ids: ID новых raw_posts.
        feed_items: записей получено из ленты/парсера.
        skipped_duplicates: пропущено как уже есть в БД.
        skipped_too_old: пропущено — старше окна (вчера/сегодня).
        fetch_error: ошибка загрузки (пустая лента из-за сбоя).
    """

    created_ids: list[int]
    feed_items: int = 0
    skipped_duplicates: int = 0
    skipped_too_old: int = 0
    fetch_error: str | None = None

    def summary(self) -> str:
        """Краткий итог для панели «Задачи».

        Returns:
            str: описание результата.
        """
        if self.fetch_error:
            return f"Ошибка ленты: {self.fetch_error[:200]}"
        if self.feed_items == 0:
            return (
                "Лента пуста или URL недоступен — проверьте тип источника и адрес RSS"
            )
        created = len(self.created_ids)
        if created > 0:
            return f"Найдено новых материалов: {created}"
        if self.skipped_duplicates > 0 and self.skipped_too_old == 0:
            return (
                f"В ленте {self.feed_items} записей, все уже сохранены "
                f"(дубликаты по external_id)"
            )
        if self.skipped_too_old > 0:
            parts = [f"Пропущено устаревших: {self.skipped_too_old}"]
            if self.skipped_duplicates:
                parts.append(f"дубликатов: {self.skipped_duplicates}")
            return "; ".join(parts)
        return "Новых материалов не найдено (свежих за вчера/сегодня)"
