"""Единые ограничения длины самостоятельных публикаций ПАРАГРАФА."""

from typing import Final

PARAGRAPH_TARGET_MIN: Final[int] = 1600
# Резерв до лимита MAX оставлен под хэштеги и служебное оформление.
PARAGRAPH_POST_MAX: Final[int] = 3600
