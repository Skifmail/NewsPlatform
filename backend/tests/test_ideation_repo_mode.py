"""Тест: для devtools/trending-каналов идеация не режется словесным дедупом."""

import pytest

from app.infrastructure.ai.topic_ideation import TopicIdeationService
from app.infrastructure.models.channel import Channel


class _FakeClient:
    """DeepSeek-заглушка: всегда отдаёт одну и ту же тему-репозиторий."""

    async def chat_completion(self, **_kwargs: object) -> str:
        return (
            '{"topic": "foo/bar: open-source design alternative", '
            '"angle": "новый инструмент дизайна", '
            '"search_queries": ["foo/bar github stars"]}'
        )


def _github_channel() -> Channel:
    return Channel(
        id=6,
        name="Github | Находки",
        platform="telegram",
        platform_id="@finds",
        topic="it",
        content_mode="article",
        style_prompt="находки с гитхаба",
    )


@pytest.mark.asyncio
async def test_repo_mode_bypasses_word_similarity() -> None:
    """С trending-кандидатами тема принимается, даже если делит слова с recent."""
    svc = TopicIdeationService(client=_FakeClient())
    # recent сильно пересекается по словам с кандидатом — раньше это роняло идеацию
    recent = [
        "baz/qux: open-source design alternative",
        "another/repo: design tool alternative",
    ]
    plan = await svc.plan_topic(
        _github_channel(),
        recent,
        "",
        candidate_repos=["foo/bar — ⭐5000, TS — open-source design (url)"],
    )
    assert plan.topic.startswith("foo/bar")


@pytest.mark.asyncio
async def test_paragraph_still_dedups_without_candidates() -> None:
    """Без кандидатов (Параграф) словесный дедуп по-прежнему работает."""
    svc = TopicIdeationService(client=_FakeClient())
    # тот же заголовок в recent → все попытки отвергаются → RuntimeError
    recent = ["foo/bar: open-source design alternative"]
    channel = _github_channel()
    channel.name = "ПАРАГРАФ"
    with pytest.raises(RuntimeError):
        await svc.plan_topic(channel, recent, "", candidate_repos=None)
