"""Тесты классификатора AI/LLM-инструментов (правило ≤1 AI из 3 подряд)."""

from app.domain.tool_category import is_ai_tool


def test_real_ai_titles_that_clustered() -> None:
    """Реальные заголовки, из-за которых канал скатился в AI-поток."""
    assert is_ai_tool(
        "Caveman: ИИ-агент, который говорит как пещерный человек и экономит 65% токенов"
    )
    assert is_ai_tool("RTK: CLI-прокси, который режет токены LLM на 60-90%")
    assert is_ai_tool(
        "Open Design: бесплатная open-source альтернатива Claude Design"
    )


def test_english_ai_descriptions() -> None:
    assert is_ai_tool("langchain/langchain — build LLM apps")
    assert is_ai_tool("some/repo — autonomous AI agent for coding")
    assert is_ai_tool("acme/rag-kit — retrieval augmented generation toolkit")
    assert is_ai_tool("x/y — a machine learning pipeline")


def test_non_ai_tools_not_flagged() -> None:
    assert not is_ai_tool("Hurl: HTTP-запросы как код — тестируй API без Postman")
    assert not is_ai_tool("Broot: дерево директорий с fuzzy-поиском")
    assert not is_ai_tool("Just: command runner, который заменит Makefile")
    assert not is_ai_tool("GoAccess: анализ веб-логов в реальном времени")
    assert not is_ai_tool("owner/repo — a fast terminal file manager in Rust")


def test_no_false_positive_on_substrings() -> None:
    # «домен», «детали», «линии» не должны срабатывать как AI
    assert not is_ai_tool("owner/domain-tool — manage your DNS domains")
    assert not is_ai_tool("Детали: инструмент для линии сборки")


def test_empty() -> None:
    assert not is_ai_tool("")
    assert not is_ai_tool(None)
