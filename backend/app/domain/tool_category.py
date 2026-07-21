"""Определение категории dev-инструмента (AI/LLM или нет).

Нужно, чтобы канал находок не скатывался в монотонный AI-поток: правило
«не более 1 AI-инструмента из 3 подряд». Работает и для русских заголовков
постов, и для английских описаний репозиториев.
"""

from __future__ import annotations

import re
from typing import Final

# Отдельные слова-маркеры AI/LLM (целиком, с границами; \b в re.UNICODE
# корректно работает и для кириллицы).
_AI_WORDS: Final[frozenset[str]] = frozenset(
    {
        # английские
        "ai", "llm", "llms", "gpt", "chatgpt", "agent", "agents", "agentic",
        "rag", "genai", "openai", "anthropic", "claude", "gemini", "llama",
        "mistral", "prompt", "prompts", "chatbot", "chatbots", "embedding",
        "embeddings", "neural", "transformer", "transformers", "diffusion",
        "copilot", "tokenizer", "mcp", "ocr",
        # русские
        "ии", "ллм", "промпт", "промпты", "агент", "агенты", "агентов",
        "чатбот", "инференс",
    }
)

_AI_WORD_RE = re.compile(
    r"\b(" + "|".join(sorted(_AI_WORDS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE | re.UNICODE,
)

# Подстроки/стемы и фразы (границы слов не нужны).
_AI_SUBSTRINGS: Final[tuple[str, ...]] = (
    "machine learning", "language model", "large language", "deep learning",
    "generative", "fine-tun", "нейросет", "нейронн", "языкова модел",
    "искусственн интеллект", "искусственного интеллект",
)


def is_ai_tool(text: str | None) -> bool:
    """True, если текст описывает AI/LLM-инструмент.

    Args:
        text: заголовок поста или «repo — описание».

    Returns:
        bool: относится ли к AI/LLM-категории.
    """
    if not text:
        return False
    lowered = text.lower()
    if _AI_WORD_RE.search(lowered):
        return True
    return any(sub in lowered for sub in _AI_SUBSTRINGS)
