"""Модульные тесты для диалога истории загрузок (history_dialog.py).

Проверяют формат даты (``ГГГГ.ММ.ДД ЧЧ:ММ``) и отсутствие в таблице
колонок «Качество» и «Размер».
"""

from __future__ import annotations

from unittest.mock import MagicMock

from src.gui.history_dialog import HistoryDialog


class TestHistoryFormatting:
    """Форматирование метки времени."""

    def test_date_format_dots(self) -> None:
        """Дата отображается как ГГГГ.ММ.ДД ЧЧ:ММ (с точками)."""
        assert HistoryDialog._format_ts("2026-07-31T14:30:00") == "2026.07.31 14:30"

    def test_empty_timestamp(self) -> None:
        assert HistoryDialog._format_ts("") == "-"
        assert HistoryDialog._format_ts(None) == "-"

    def test_invalid_timestamp_fallback(self) -> None:
        assert HistoryDialog._format_ts("not-a-date") == "not-a-date"


class TestHistoryDialogLayout:
    """Структура таблицы истории."""

    def test_columns_exclude_quality_and_size(self, qapp) -> None:
        """Колонок 4: Дата, Название, Тип и кнопка (без Качества/Размера)."""
        manager = MagicMock()
        manager.get_all.return_value = []
        dialog = HistoryDialog(manager)

        assert dialog._table.columnCount() == 4
        labels = [
            dialog._table.horizontalHeaderItem(i).text()
            for i in range(dialog._table.columnCount())
        ]
        assert "Качество" not in labels
        assert "Размер" not in labels
        dialog.close()
