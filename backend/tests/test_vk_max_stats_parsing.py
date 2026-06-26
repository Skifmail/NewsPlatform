"""Тесты парсинга ответов VK и MAX API."""

from app.infrastructure.stats.max_stats import (
    parse_max_chat_info,
    parse_max_message_metrics,
)
from app.infrastructure.stats.vk_stats import (
    parse_vk_group_members,
    parse_vk_post_reach,
    parse_vk_wall_post,
)


def test_parse_vk_group_members() -> None:
    """members_count из groups.getById."""
    payload = {"response": [{"id": 1, "members_count": 12500}]}
    assert parse_vk_group_members(payload) == 12500


def test_parse_vk_group_members_error() -> None:
    """Ошибка VK API -> None."""
    payload = {"error": {"error_code": 15}}
    assert parse_vk_group_members(payload) is None


def test_parse_vk_wall_post() -> None:
    """Метрики поста из wall.getById."""
    payload = {
        "response": [
            {
                "id": 42,
                "owner_id": -123,
                "date": 1710000000,
                "views": {"count": 900},
                "likes": {"count": 55},
                "reposts": {"count": 12},
                "comments": {"count": 7},
            }
        ]
    }
    metric = parse_vk_wall_post(payload)
    assert metric is not None
    assert metric.platform_post_id == "42"
    assert metric.views == 900
    assert metric.reactions == 55
    assert metric.forwards == 12
    assert metric.comments == 7
    assert metric.published_at is not None
    assert "wall-123_42" in metric.post_url


def test_parse_vk_post_reach() -> None:
    """Охват из stats.getPostReach."""
    payload = {"response": [{"reach_total": 1500, "reach_subscribers": 800}]}
    assert parse_vk_post_reach(payload) == 1500


def test_parse_max_chat_info() -> None:
    """Подписчики и сообщения из GET /chats."""
    payload = {"chat_id": 1, "participants_count": 3400, "messages_count": 128}
    subscribers, messages = parse_max_chat_info(payload)
    assert subscribers == 3400
    assert messages == 128


def test_parse_max_message_metrics() -> None:
    """Просмотры постов канала из GET /messages."""
    payload = {
        "messages": [
            {
                "body": {"mid": "mid-1", "text": "hi"},
                "timestamp": 1710000000000,
                "stat": {"views": 1500},
                "url": "https://max.ru/example/1",
            },
            {
                "body": {"mid": "mid-2"},
                "timestamp": 1710000500000,
                "stat": {"views": 42},
                "url": None,
            },
        ]
    }
    metrics = parse_max_message_metrics(payload)
    assert len(metrics) == 2
    assert metrics[0].platform_post_id == "mid-1"
    assert metrics[0].views == 1500
    assert metrics[0].post_url == "https://max.ru/example/1"
    assert metrics[0].published_at is not None
    assert metrics[1].platform_post_id == "mid-2"
    assert metrics[1].views == 42
    assert metrics[1].post_url is None


def test_parse_max_message_metrics_without_stat() -> None:
    """Без stat (нет права view_stats) — просмотры None, пост не теряется."""
    payload = {"messages": [{"body": {"mid": "mid-3"}, "timestamp": 1710000000000}]}
    metrics = parse_max_message_metrics(payload)
    assert len(metrics) == 1
    assert metrics[0].platform_post_id == "mid-3"
    assert metrics[0].views is None


def test_parse_max_message_metrics_empty() -> None:
    """Пустой/некорректный ответ -> пустой список."""
    assert parse_max_message_metrics({}) == []
    assert parse_max_message_metrics({"messages": None}) == []
