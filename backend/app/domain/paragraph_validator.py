"""Предпубликационная проверка черновиков канала «Параграф»."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import unescape

from app.utils.text_format import MAX_MESSAGE_MAX, repair_telegram_html, to_max_api_html

# Узкопрофессиональные / внетематические маркеры (эксперт: пост про 1С).
_OFF_TOPIC_MARKERS: tuple[str, ...] = (
    "1с",
    "1c ",
    "язык запросов",
    "sql-подобн",
    "hibernate",
    "spring boot",
    "kubernetes yaml",
    "dockerfile",
    "react hooks",
    "typescript generic",
    "питон-скрипт для бэкенда",
)

_FORBIDDEN_OPENERS: tuple[str, ...] = (
    "представь",
    "представьте",
    "вы когда-нибудь задумывались",
    "в мире существует",
    "а вы знали",
    "интересный факт:",
)

_GENERIC_ENDINGS: tuple[str, ...] = (
    "природа удивительна",
    "насколько удивителен наш мир",
    "мир полон чудес",
    "наука не стоит на месте",
)

_INCOMPLETE_TRAILING = re.compile(
    r"(?:создавали|которые|чтобы|потому что|из-за|через|после|"
    r"когда|если|пока|однако|а также|или|и)\s*$",
    re.IGNORECASE,
)
_BROKEN_HREF = re.compile(
    r"""href\s*=\s*['"][^'"]*$|href\s*=\s*['"]https?://[^'"]{0,40}$""",
    re.IGNORECASE,
)
_OPEN_TAG_TAIL = re.compile(r"<[^>]*$")
_SENTENCE_END = re.compile(r"[.!?…][»\")\]]?\s*$")
_ENGLISH_QUOTE = re.compile(
    r"[“\"]([A-Za-z][^”\"]{15,})[”\"]",
)
_CYRILLIC = re.compile(r"[а-яёА-ЯЁ]")

# Имперские единицы и «машинный» метрический перевод (8000 ft → 2438 м).
_IMPERIAL_UNITS = re.compile(
    r"(?i)"
    r"(?<![а-яёa-z])"
    r"(?:"
    r"фут(?:а|ов|у|е|ами|ах)?"
    r"|дюйм(?:а|ов|у|е|ами|ах)?"
    r"|мил(?:я|и|ь|ями|ях)"
    r"|фунт(?:а|ов|у|е|ами|ах)?"
    r"|yard(?:s)?"
    r"|feet|foot|inches|inch|miles?|pounds?|lbs?"
    r"|fahrenheit"
    r"|°\s*f"
    r"|\bpsi\b"
    r"|\bmph\b"
    r")"
    r"(?![а-яёa-z])"
)

# «2438 метров» / «1 524 м» — точный пересчёт, а не живая метрика.
_SUSPICIOUS_METERS = re.compile(
    r"(?<![\d.,])"
    r"(\d{1,3}(?:[ \u00a0]\d{3})+|\d{4,})"
    r"(?:[.,]\d+)?"
    r"\s*"
    r"(?:м(?![а-яё])|метр(?:а|ов|у|е)?|metres?|meters?)"
    r"\b",
    re.IGNORECASE,
)



@dataclass
class ValidationIssue:
    """Одна проблема проверки.

    Attributes:
        code: машинный код.
        message: человекочитаемое описание.
        blocking: блокирует ли публикацию.
    """

    code: str
    message: str
    blocking: bool = True


@dataclass
class ValidationResult:
    """Результат предпубликационной проверки.

    Attributes:
        ok: True если нет блокирующих проблем.
        issues: список замечаний.
    """

    ok: bool
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def blocking_messages(self) -> list[str]:
        """Тексты блокирующих замечаний."""
        return [i.message for i in self.issues if i.blocking]


def validate_paragraph_draft(
    *,
    title: str,
    teaser: str,
    body_html: str,
    cover_title: str = "",
    interaction_question: str = "",
    button_options: list[str] | None = None,
    target_min: int = 850,
    target_max: int = 1400,
    hard_max: int = MAX_MESSAGE_MAX,
    recent_topics: list[str] | None = None,
    topic_too_similar: bool = False,
) -> ValidationResult:
    """Проверяет черновик Параграфа перед сохранением/публикацией.

    Args:
        title: заголовок.
        teaser: анонс HTML.
        body_html: тело HTML.
        cover_title: короткий текст обложки.
        interaction_question: вопрос вовлечения.
        button_options: варианты кнопок.
        target_min: желаемый минимум видимых символов.
        target_max: желаемый максимум видимых символов.
        hard_max: жёсткий лимит платформы после сборки.
        recent_topics: недавние темы (для контекста сообщений).
        topic_too_similar: уже вычисленный флаг дедупа.

    Returns:
        ValidationResult: итог проверки.
    """
    issues: list[ValidationIssue] = []
    plain = _visible_text(f"{title}\n{teaser}\n{body_html}")
    combined_lower = plain.lower()

    if topic_too_similar:
        issues.append(
            ValidationIssue(
                "topic_duplicate",
                "Тема повторяет публикацию за последние 90 дней "
                f"(сверка с {len(recent_topics or [])} недавними).",
            )
        )

    for marker in _OFF_TOPIC_MARKERS:
        if marker in combined_lower:
            issues.append(
                ValidationIssue(
                    "off_topic",
                    f"Материал вне тематики канала (маркер «{marker.strip()}»).",
                )
            )
            break

    for block in (_visible_text(teaser), _visible_text(body_html)):
        lead = block.lstrip().lower()[:100]
        hit = False
        for forbidden in _FORBIDDEN_OPENERS:
            if lead.startswith(forbidden):
                issues.append(
                    ValidationIssue(
                        "forbidden_opener",
                        f"Запрещённый зачин «{forbidden}…».",
                    )
                )
                hit = True
                break
        if hit:
            break

    for ending in _GENERIC_ENDINGS:
        if ending in combined_lower:
            issues.append(
                ValidationIssue(
                    "generic_ending",
                    f"Общий вывод «{ending}» — убрать.",
                    blocking=False,
                )
            )

    visible_len = len(plain)
    if visible_len < target_min - 150:
        issues.append(
            ValidationIssue(
                "too_short",
                f"Текст слишком короткий ({visible_len} симв., цель {target_min}–{target_max}).",
                blocking=False,
            )
        )
    if visible_len > target_max + 200:
        issues.append(
            ValidationIssue(
                "too_long",
                f"Текст длиннее целевого формата ({visible_len} симв., цель до {target_max}).",
            )
        )

    assembled = to_max_api_html(
        repair_telegram_html(f"{teaser}\n\n{body_html}".strip())
    )
    if len(assembled) > hard_max:
        issues.append(
            ValidationIssue(
                "platform_limit",
                f"После форматирования текст не влезает в лимит MAX "
                f"({len(assembled)} > {hard_max}).",
            )
        )

    if _OPEN_TAG_TAIL.search(body_html.strip()) or _BROKEN_HREF.search(body_html):
        issues.append(
            ValidationIssue(
                "broken_html",
                "Обнаружен оборванный HTML-тег или повреждённая ссылка.",
            )
        )

    if _has_unbalanced_tags(body_html):
        issues.append(
            ValidationIssue(
                "unclosed_tags",
                "В HTML есть незакрытые теги.",
            )
        )

    last_plain = _visible_text(body_html).rstrip()
    if last_plain and not _SENTENCE_END.search(last_plain):
        issues.append(
            ValidationIssue(
                "incomplete_sentence",
                "Текст заканчивается незавершённым предложением.",
            )
        )
    elif last_plain and _INCOMPLETE_TRAILING.search(last_plain):
        issues.append(
            ValidationIssue(
                "incomplete_clause",
                "Концовка обрывается на служебном слове (незаконченная мысль).",
            )
        )

    for match in _ENGLISH_QUOTE.finditer(plain):
        quote = match.group(1)
        if not _CYRILLIC.search(quote):
            issues.append(
                ValidationIssue(
                    "untranslated_quote",
                    "Английская цитата без перевода — убрать или перевести.",
                )
            )
            break

    imperial_hit = _IMPERIAL_UNITS.search(plain)
    if imperial_hit:
        issues.append(
            ValidationIssue(
                "imperial_units",
                "Имперские единицы («"
                f"{imperial_hit.group(0)}») — только метрика "
                "(м/км/кг/°C), с естественным округлением.",
            )
        )

    for match in _SUSPICIOUS_METERS.finditer(plain):
        token = re.sub(r"\s+", "", match.group(1)).replace(",", ".")
        try:
            meters = int(float(token))
        except ValueError:
            continue
        # Живая метрика: «около 2400 м», «2,5 км». Точные 2438 м — признак
        # машинного перевода из футов (8000 ft).
        if meters >= 1000 and meters % 50 != 0:
            issues.append(
                ValidationIssue(
                    "unnatural_metric",
                    f"Число «{match.group(0)}» выглядит как слепой пересчёт "
                    "из имперских единиц. Округли: «около 2400 м» / «примерно 2,5 км».",
                )
            )
            break

    if cover_title and len(cover_title.split()) > 8:
        issues.append(
            ValidationIssue(
                "cover_too_long",
                "Заголовок обложки длиннее 5–8 слов — сократить.",
                blocking=False,
            )
        )

    has_question = bool(interaction_question.strip()) or "?" in plain[-400:]
    buttons = [b for b in (button_options or []) if b.strip()]
    if not has_question and len(buttons) < 2:
        issues.append(
            ValidationIssue(
                "no_interaction",
                "Нет конкретного вопроса или интерактивных кнопок.",
                blocking=False,
            )
        )

    blocking = [i for i in issues if i.blocking]
    return ValidationResult(ok=not blocking, issues=issues)


def _visible_text(html: str) -> str:
    """Убирает теги и декодирует HTML-сущности."""
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _has_unbalanced_tags(html: str) -> bool:
    """Проверяет баланс основных inline/block тегов."""
    for tag in ("a", "b", "i", "blockquote", "strong", "em"):
        opens = len(re.findall(rf"<{tag}(?:\s[^>]*)?>", html, re.IGNORECASE))
        closes = len(re.findall(rf"</{tag}>", html, re.IGNORECASE))
        if opens != closes:
            return True
    return False
