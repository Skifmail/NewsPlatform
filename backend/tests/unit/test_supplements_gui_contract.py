"""Контракт понятного включения расписания в интерфейсе."""

from pathlib import Path
from typing import Final

VIEW_PATH: Final = Path(__file__).parents[3] / "frontend/src/views/SupplementsView.vue"


def _schedule_section() -> str:
    """Возвращает разметку блока расписания.

    Returns:
        Разметка между блоками расписания и правил генерации.
    """
    source = VIEW_PATH.read_text(encoding="utf-8")
    return source.split('<span class="step">02</span>', maxsplit=1)[1].split(
        '<span class="step">03</span>', maxsplit=1
    )[0]


def test_schedule_section_when_toggle_changed_should_show_save_action() -> None:
    """Галочка должна иметь собственное понятное действие сохранения."""
    section = _schedule_section()

    assert "scheduleSaveLabel" in section
    assert '@click="save"' in section
    assert ':disabled="busy || !dirty"' in section


def test_schedule_calendar_when_disabled_should_explain_preview() -> None:
    """Будущие даты не должны выглядеть как уже включённые публикации."""
    section = _schedule_section()

    assert "Предпросмотр дат подготовки" in section
    assert "Это не даты автоматической публикации" in section
    assert ':class="{ disabled: !form.enabled }"' in section


def test_draft_when_image_exists_should_show_approved_cover() -> None:
    """Панель показывает картинку, которая уйдёт редактору и в канал."""
    page = VIEW_PATH.read_text(encoding="utf-8")

    assert 'v-if="draft.image_url"' in page
    assert 'class="draft-cover"' in page
    assert "mediaUrl(draft.image_url)" in page
    assert "Эта картинка придёт в MAX" in page
