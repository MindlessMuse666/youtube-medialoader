"""Проверка YouTube-ссылок.

Чистые функции валидации и классификации URL, выделенные из
``main_window.py`` (ранее статические методы ``_validate_url`` и
``_is_playlist_url``) для независимости от GUI и лёгкого тестирования.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

# Домены, которые мы считаем ссылками на YouTube.
_YOUTUBE_DOMAINS = ("youtube.com", "youtu.be")


def is_youtube_url(url: str) -> bool:
    """Проверить, что ссылка ведёт на youtube.com или youtu.be.

    Args:
        url: Ссылка для проверки.

    Returns:
        ``True`` если хост относится к YouTube.
    """
    parsed = urlparse(url.strip())
    netloc = parsed.netloc.lower()
    return any(domain in netloc for domain in _YOUTUBE_DOMAINS)


def validate_url(url: str) -> str | None:
    """Проверить, что ссылка является корректным YouTube-URL.

    Args:
        url: Ссылка для проверки.

    Returns:
        ``None`` если URL корректен, иначе строка с описанием ошибки.
    """
    url = url.strip()
    if not url:
        return "Ссылка пуста"

    # Должна начинаться с http:// или https://
    if not url.startswith(("http://", "https://")):
        return "Ссылка должна начинаться с http:// или https://"

    # Проверяем дублирование - явный признак мусора
    if url.count("youtube.com") > 1 or url.count("youtu.be") > 1:
        return "Обнаружено дублирование домена в ссылке"

    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    if not is_youtube_url(url):
        return "Ссылка должна вести на youtube.com или youtu.be"

    # Для youtube.com - нужен параметр v (id видео)
    if "youtube.com" in netloc:
        params = parse_qs(parsed.query)
        if not params.get("v"):
            return "Не указан ID видео (параметр v=)"

    # Для youtu.be - нужен path
    if "youtu.be" in netloc:
        if not parsed.path.strip("/"):
            return "Не указан ID видео"

    return None


def is_playlist_url(url: str) -> bool:
    """Проверить, является ли ссылка ссылкой на плейлист.

    Args:
        url: Ссылка для проверки.

    Returns:
        ``True`` если URL содержит ``list=`` параметр.
    """
    parsed = urlparse(url)
    if not is_youtube_url(url):
        return False
    return "list=" in parsed.query
