"""Модульные тесты для HistoryManager (история загрузок в QSettings).

QSettings заменяется in-memory fake - без записи в реальный файл настроек.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.utils.history import HistoryEntry, HistoryManager


class _FakeSettings:
    """Минимальная in-memory замена QSettings для тестов."""

    def __init__(self) -> None:
        self._store: dict[str, object] = {}

    def value(self, key: str, default: object = None) -> object:
        return self._store.get(key, default)

    def setValue(self, key: str, value: object) -> None:
        self._store[key] = value


def make_entry(**overrides: object) -> HistoryEntry:
    """Хелпер: запись истории с дефолтными полями."""
    data: dict[str, object] = {
        "title": "Video",
        "url": "https://youtube.com/watch?v=test",
        "format_type": "mp4",
        "quality": "720p",
        "file_path": "C:/Downloads/video.mp4",
        "file_size": 1234,
    }
    data.update(overrides)
    return HistoryEntry(**data)  # type: ignore[arg-type]


@pytest.fixture
def manager() -> HistoryManager:
    """HistoryManager поверх fake-QSettings (общий store на тест)."""
    fake = _FakeSettings()
    with patch("src.utils.history.QSettings", return_value=fake):
        yield HistoryManager()


class TestHistoryManager:
    """add/get_all/clear и лимит записей."""

    def test_add_then_get_all(self, manager: HistoryManager) -> None:
        """Новые записи появляются в начале списка."""
        manager.add(make_entry(title="First"))
        manager.add(make_entry(title="Second"))

        titles = [e.title for e in manager.get_all()]
        assert titles == ["Second", "First"]

    def test_auto_timestamp(self, manager: HistoryManager) -> None:
        """Пустая метка времени заполняется автоматически."""
        entry = make_entry()
        assert entry.timestamp == ""

        manager.add(entry)

        assert entry.timestamp

    def test_max_entries_limit(self, manager: HistoryManager) -> None:
        """Хранится не более 100 последних записей."""
        for i in range(105):
            manager.add(make_entry(title=f"Video {i}"))

        all_entries = manager.get_all()
        assert len(all_entries) == 100
        assert all_entries[0].title == "Video 104"
        assert all(e.title != "Video 0" for e in all_entries)

    def test_clear(self, manager: HistoryManager) -> None:
        manager.add(make_entry())
        manager.clear()
        assert manager.get_all() == []

    def test_persists_across_instances(self) -> None:
        """Запись переживает пересоздание менеджера (как в QSettings)."""
        fake = _FakeSettings()
        with patch("src.utils.history.QSettings", return_value=fake):
            m1 = HistoryManager()
            m1.add(make_entry(title="Persisted"))
            m2 = HistoryManager()

        entries = m2.get_all()
        assert len(entries) == 1
        assert entries[0].title == "Persisted"

    def test_corrupted_store_loaded_as_empty(self) -> None:
        """Повреждённые данные в настройках не роняют загрузку."""
        fake = _FakeSettings()
        fake._store[HistoryManager._SETTINGS_KEY] = "{ not valid json"
        with patch("src.utils.history.QSettings", return_value=fake):
            manager = HistoryManager()

        assert manager.get_all() == []
