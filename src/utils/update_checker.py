"""Проверка обновлений через GitHub API для YouTube Medialoader.

Предоставляет класс :class:`UpdateChecker`, который асинхронно запрашивает
последний релиз с GitHub и сравнивает с текущей версией приложения.
"""

from __future__ import annotations

import json
from typing import Callable, Optional

from PySide6.QtCore import QObject, QUrl
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

# URL API GitHub для последнего релиза
_GITHUB_API_URL = (
    "https://api.github.com/repos/MindlessMuse666/youtube-medialoader/releases/latest"
)

# Таймаут запроса (мс)
_REQUEST_TIMEOUT = 8000


class UpdateChecker(QObject):
    """Проверка последней версии на GitHub без блокировки GUI.

    Пример::

        checker = UpdateChecker("0.1.0")
        checker.on_result = lambda version, is_newer: print(version, is_newer)
        checker.check()
    """

    def __init__(
        self,
        current_version: str,
        parent: Optional[QObject] = None,
    ) -> None:
        """Инициализация проверщика обновлений.

        Args:
            current_version: Текущая версия приложения (например ``"0.1.0"``).
            parent: Родительский QObject (опционально).
        """
        super().__init__(parent)
        self._current_version = current_version
        self._manager = QNetworkAccessManager(self)
        self._reply: Optional[QNetworkReply] = None

        # Внешний колбэк: (latest_tag: str, is_newer: bool)
        self.on_result: Optional[Callable[[str, bool], None]] = None

    def check(self) -> None:
        """Запустить асинхронную проверку обновлений.

        Результат передатся в :attr:`on_result`.
        При ошибке сети или парсинга ``is_newer`` будет ``False``.
        """
        request = QNetworkRequest(QUrl(_GITHUB_API_URL))
        request.setRawHeader(b"Accept", b"application/vnd.github.v3+json")
        request.setRawHeader(b"User-Agent", b"YouTube-Medialoader")
        request.setTransferTimeout(_REQUEST_TIMEOUT)

        self._reply = self._manager.get(request)
        self._reply.finished.connect(self._on_reply_finished)

    def _on_reply_finished(self) -> None:
        """Обработать ответ от GitHub API."""
        if self._reply is None:
            self._emit_result("", False)
            return

        if self._reply.error() != QNetworkReply.NetworkError.NoError:
            self._reply.deleteLater()
            self._reply = None
            self._emit_result("", False)
            return

        try:
            data = bytes(self._reply.readAll()).decode("utf-8")
            parsed: dict = json.loads(data)
            latest_tag: str = str(parsed.get("tag_name", ""))
            is_newer = self._is_newer_version(latest_tag)
            self._emit_result(latest_tag, is_newer)
        except (json.JSONDecodeError, ValueError, TypeError):
            self._emit_result("", False)
        finally:
            self._reply.deleteLater()
            self._reply = None

    def _is_newer_version(self, latest_tag: str) -> bool:
        """Сравнить версии (семантическое версионирование).

        Args:
            latest_tag: Тег последнего релиза (например ``"v2.0-unstable"``).

        Returns:
            ``True``, если latest_tag новее текущей версии.
        """
        # Убираем префикс 'v' если есть
        tag = latest_tag.lstrip("vV")
        current = self._current_version.lstrip("vV")

        try:
            tag_parts = [int(x) for x in tag.split(".")]
            current_parts = [int(x) for x in current.split(".")]
        except (ValueError, AttributeError):
            return False

        # Дополняем списки до одинаковой длины нулями
        max_len = max(len(tag_parts), len(current_parts))
        tag_parts += [0] * (max_len - len(tag_parts))
        current_parts += [0] * (max_len - len(current_parts))

        return tag_parts > current_parts

    def _emit_result(self, latest_tag: str, is_newer: bool) -> None:
        """Вызвать внешний колбэк с результатом проверки.

        Args:
            latest_tag: Тег последнего релиза.
            is_newer: ``True`` если доступна новая версия.
        """
        if self.on_result is not None:
            self.on_result(latest_tag, is_newer)
