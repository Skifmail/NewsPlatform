"""Публикация полного текста статьи на Telegraph."""

import html
import re
from typing import Any

import httpx
from loguru import logger

from app.core.config import get_settings

_API_BASE = "https://api.telegra.ph"
_TELEGRAPH_TOKEN_SETTING = "telegraph_access_token"
_PROCESS_TOKEN_CACHE: str = ""
_TAG_RE = re.compile(r"<(/?)([a-zA-Z]+)([^>]*)>", re.DOTALL)
_ALLOWED_TAGS = frozenset({"b", "strong", "i", "em", "a", "blockquote", "br"})


class TelegraphPublisher:
    """Создаёт страницы на telegra.ph через HTTP API."""

    def __init__(self, access_token: str | None = None) -> None:
        settings = get_settings()
        self._token = (access_token or settings.telegraph_access_token).strip()

    async def ensure_token(self) -> str:
        """Возвращает access_token, создавая аккаунт при необходимости.

        Порядок: аргумент конструктора → env → кэш процесса → settings БД → createAccount.

        Returns:
            str: токен Telegraph.

        Raises:
            RuntimeError: при ошибке API.
        """
        global _PROCESS_TOKEN_CACHE
        if self._token:
            return self._token
        if _PROCESS_TOKEN_CACHE:
            self._token = _PROCESS_TOKEN_CACHE
            return self._token

        from app.infrastructure.database import async_session_factory
        from app.repositories.setting_repository import SettingRepository

        async with async_session_factory() as session:
            stored = (await SettingRepository(session).get(_TELEGRAPH_TOKEN_SETTING, "")).strip()
            if stored:
                self._token = stored
                _PROCESS_TOKEN_CACHE = stored
                return stored

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{_API_BASE}/createAccount",
                    params={
                        "short_name": "NewsPlatform",
                        "author_name": "NewsPlatform",
                    },
                )
                data = response.json()
            if not data.get("ok"):
                msg = f"Telegraph createAccount failed: {data}"
                raise RuntimeError(msg)
            result = data.get("result") or {}
            token = str(result.get("access_token") or "")
            if not token:
                msg = "Telegraph createAccount: пустой access_token"
                raise RuntimeError(msg)
            await SettingRepository(session).set(_TELEGRAPH_TOKEN_SETTING, token)
            await session.commit()
            self._token = token
            _PROCESS_TOKEN_CACHE = token
            logger.info("Telegraph account created and token saved to settings")
            return token

    async def create_page(
        self,
        title: str,
        body_html: str,
        *,
        author_name: str | None = None,
    ) -> str:
        """Публикует HTML-статью на Telegraph.

        Args:
            title: заголовок страницы.
            body_html: HTML-тело статьи.
            author_name: имя автора на странице (обычно название канала).

        Returns:
            str: публичный URL страницы.

        Raises:
            RuntimeError: при ошибке API.
        """
        token = await self.ensure_token()
        content = self._html_to_nodes(body_html)
        if not content:
            content = [{"tag": "p", "children": ["Статья"]}]
        author = (author_name or "Канал").strip()[:128] or "Канал"

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{_API_BASE}/createPage",
                data={
                    "access_token": token,
                    "title": title[:256],
                    "author_name": author,
                    "content": self._serialize_nodes(content),
                    "return_content": "false",
                },
            )
            data = response.json()

        if not data.get("ok"):
            msg = f"Telegraph createPage failed: {data}"
            raise RuntimeError(msg)
        result = data.get("result") or {}
        url = str(result.get("url") or "")
        if not url:
            msg = "Telegraph createPage: пустой URL"
            raise RuntimeError(msg)
        logger.info("Telegraph page created", url=url, title=title[:80], author=author)
        return url

    async def set_author_name(
        self,
        page_url: str,
        author_name: str,
        *,
        title: str | None = None,
    ) -> None:
        """Обновляет имя автора на существующей странице Telegraph.

        Args:
            page_url: публичный URL страницы.
            author_name: новое имя автора (название канала).
            title: заголовок страницы (если не передан — запрашивается у API).

        Raises:
            RuntimeError: при ошибке API.
        """
        token = await self.ensure_token()
        path = page_url.rstrip("/").rsplit("/", maxsplit=1)[-1]
        author = author_name.strip()[:128] or "Канал"
        async with httpx.AsyncClient(timeout=60.0) as client:
            meta = await client.get(
                f"{_API_BASE}/getPage",
                params={"path": path, "return_content": "true"},
            )
            meta_data = meta.json()
            if not meta_data.get("ok"):
                msg = f"Telegraph getPage failed: {meta_data}"
                raise RuntimeError(msg)
            result = meta_data.get("result") or {}
            page_title = (title or str(result.get("title") or "Статья")).strip()[:256]
            content = result.get("content")
            if not isinstance(content, list) or not content:
                msg = "Telegraph getPage: пустой content для editPage"
                raise RuntimeError(msg)

            current_author = str(result.get("author_name") or "").strip()
            current_title = str(result.get("title") or "").strip()
            needs_title_update = bool(title and title.strip() != current_title)
            if current_author == author and not needs_title_update:
                logger.debug(
                    "Telegraph author already set, skip editPage",
                    url=page_url,
                    author=author,
                )
                return

            response = await client.post(
                f"{_API_BASE}/editPage",
                data={
                    "access_token": token,
                    "path": path,
                    "title": page_title,
                    "author_name": author,
                    "content": self._serialize_nodes(content),
                },
            )
            data = response.json()
        if not data.get("ok"):
            msg = f"Telegraph editPage (author) failed: {data}"
            raise RuntimeError(msg)
        logger.info("Telegraph author updated", url=page_url, author=author)

    @staticmethod
    def _serialize_nodes(nodes: list[dict[str, Any]]) -> str:
        """Сериализует nodes для form-data Telegraph API.

        Args:
            nodes: список узлов Telegraph.

        Returns:
            str: JSON-строка content.
        """
        import json

        return json.dumps(nodes, ensure_ascii=False)

    def _html_to_nodes(self, body_html: str) -> list[dict[str, Any]]:
        """Конвертирует упрощённый HTML в nodes Telegraph.

        Args:
            body_html: HTML-текст статьи.

        Returns:
            list[dict[str, Any]]: узлы Telegraph API.
        """
        text = body_html.replace("\r\n", "\n").strip()
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        nodes: list[dict[str, Any]] = []
        for paragraph in paragraphs:
            children = self._parse_inline(paragraph)
            if children:
                nodes.append({"tag": "p", "children": children})
        return nodes

    def _parse_inline(self, fragment: str) -> list[Any]:
        """Парсит inline-разметку одного абзаца.

        Args:
            fragment: HTML-фрагмент.

        Returns:
            list[Any]: children для узла p.
        """
        pos = 0
        children: list[Any] = []
        for match in _TAG_RE.finditer(fragment):
            if match.start() > pos:
                plain = html.unescape(fragment[pos : match.start()])
                if plain:
                    children.append(plain)
            closing = match.group(1) == "/"
            tag = match.group(2).lower()
            if closing or tag not in _ALLOWED_TAGS:
                pos = match.end()
                continue
            if tag == "br":
                children.append({"tag": "br"})
                pos = match.end()
                continue
            close_pattern = re.compile(
                rf"</{re.escape(tag)}>",
                re.IGNORECASE,
            )
            close_match = close_pattern.search(fragment, match.end())
            if not close_match:
                pos = match.end()
                continue
            inner = fragment[match.end() : close_match.start()]
            if tag == "a":
                href_match = re.search(
                    r'href\s*=\s*["\']([^"\']+)["\']',
                    match.group(3),
                    re.IGNORECASE,
                )
                href = href_match.group(1) if href_match else ""
                link_children = self._parse_inline(inner) or [html.unescape(inner)]
                children.append(
                    {
                        "tag": "a",
                        "attrs": {"href": href},
                        "children": link_children,
                    }
                )
            elif tag in {"b", "strong"}:
                inner_children = self._parse_inline(inner) or [html.unescape(inner)]
                children.append({"tag": "b", "children": inner_children})
            elif tag in {"i", "em"}:
                inner_children = self._parse_inline(inner) or [html.unescape(inner)]
                children.append({"tag": "i", "children": inner_children})
            elif tag == "blockquote":
                inner_children = self._parse_inline(inner) or [html.unescape(inner)]
                children.append({"tag": "blockquote", "children": inner_children})
            pos = close_match.end()
        if pos < len(fragment):
            tail = html.unescape(fragment[pos:])
            if tail:
                children.append(tail)
        return children
