"""Проверка точечного обновления редакционных промптов."""

import importlib.util
from pathlib import Path

from pytest_mock import MockerFixture
from sqlalchemy import create_engine, text


def test_upgrade_when_custom_hashtags_exist_should_preserve_them(
    mocker: MockerFixture,
) -> None:
    """Меняет три промпта, сохраняя правила тегов и остальные каналы."""
    migration = (
        Path(__file__).resolve().parents[3]
        / "alembic/versions/047_paragraph_completion.py"
    )
    spec = importlib.util.spec_from_file_location("completion_migration", migration)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE prompt_templates (key TEXT PRIMARY KEY, "
                "template_text TEXT, template_variables TEXT, updated_at TIMESTAMP)"
            )
        )
        custom = "- hashtags — мои правила: #катастрофы только для аварий.\n"
        for key, value in [
            (
                "writing.paragraph_instructions",
                "Старое начало\n" + custom + "- title — заголовок",
            ),
            ("writing.system_paragraph", "Старая роль"),
            ("ideation.system_paragraph", "Старый поиск"),
            ("writing.default", "Не менять"),
        ]:
            connection.execute(
                text(
                    "INSERT INTO prompt_templates (key,template_text) "
                    "VALUES (:key,:value)"
                ),
                {"key": key, "value": value},
            )
        mocker.patch.object(module.op, "get_bind", return_value=connection)
        module.upgrade()
        rows = dict(
            connection.execute(text("SELECT key, template_text FROM prompt_templates"))
            .tuples()
            .all()
        )
        assert rows["writing.default"] == "Не менять"
        assert custom in rows["writing.paragraph_instructions"]
        assert "1600–2800" in rows["writing.paragraph_instructions"]
        assert "последств" in rows["ideation.system_paragraph"]
        module.upgrade()
        assert (
            dict(
                connection.execute(
                    text("SELECT key, template_text FROM prompt_templates")
                )
                .tuples()
                .all()
            )
            == rows
        )
