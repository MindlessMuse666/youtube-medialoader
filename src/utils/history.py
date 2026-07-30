"""Менеджер истории загрузок для YouTube Medialoader.

Хранит историю загрузок в QSettings в формате JSON-списка,
ограниченного последними 100 записями.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime

from PySide6.QtCore import QSettings


@dataclass
class HistoryEntry:
    """Одна запись в истории загрузок.

    Attributes:
        timestamp: Время завершения загрузки (ISO-формат).
        title: Название видео.
        url: Ссылка на YouTube-видео.
        format_type: ``"mp4"`` или ``"mp3"``.
        quality: Качество видео или ``"-"`` для аудио.
        file_path: Полный путь к сохранeнному файлу.
        file_size: Размер файла в байтах (опционально).
    """

    timestamp: str = ""
    title: str = "Untitled"
    url: str = ""
    format_type: str = "mp4"
    quality: str = "720p"
    file_path: str = ""
    file_size: int = 0


class HistoryManager:
    """Управление историей загрузок, сохраняемой в QSettings.

    Пример::

        manager = HistoryManager()
        manager.add(HistoryEntry(title="My Video", ...))
        all_entries = manager.get_all()
        manager.clear()
    """

    _SETTINGS_KEY = "download_history"
    _MAX_ENTRIES = 100

    def __init__(self) -> None:
        """Инициализация менеджера истории."""
        self._settings = QSettings("MindlessMuse666", "YouTube-Medialoader")
        self._entries: list[HistoryEntry] = []
        self._load()

    def add(self, entry: HistoryEntry) -> None:
        """Добавить запись в историю.

        Args:
            entry: Запись о завершeнной загрузке.
        """
        if not entry.timestamp:
            entry.timestamp = datetime.now().isoformat()
        self._entries.insert(0, entry)
        # Ограничиваем количество записей
        if len(self._entries) > self._MAX_ENTRIES:
            self._entries = self._entries[: self._MAX_ENTRIES]
        self._save()

    def get_all(self) -> list[HistoryEntry]:
        """Вернуть список всех записей (от новых к старым).

        Returns:
            Список HistoryEntry.
        """
        return list(self._entries)

    def clear(self) -> None:
        """Очистить всю историю."""
        self._entries.clear()
        self._save()

    def _load(self) -> None:
        """Загрузить историю из QSettings."""
        raw = self._settings.value(self._SETTINGS_KEY, "")
        if not raw:
            self._entries = []
            return
        try:
            data: list[dict] = json.loads(raw)
            self._entries = [HistoryEntry(**item) for item in data]
        except (json.JSONDecodeError, TypeError):
            self._entries = []

    def _save(self) -> None:
        """Сохранить историю в QSettings."""
        data = [asdict(e) for e in self._entries]
        self._settings.setValue(self._SETTINGS_KEY, json.dumps(data, ensure_ascii=False))
