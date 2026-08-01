"""Диалог истории загрузок для YouTube Medialoader.

Предоставляет класс :class:`HistoryDialog` - модальное окно с таблицей
завершeнных загрузок, возможностью открыть папку с файлом и очисткой истории.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.gui.widgets import Toast
from src.utils.file_utils import reveal_in_file_manager
from src.utils.history import HistoryEntry, HistoryManager
from src.utils.theme import BG, BG_BLACK, BG_TABLE, BORDER, CYAN, GREEN, PINK, TEXT

_DATETIME_FMT = "%Y.%m.%d %H:%M"


class HistoryDialog(QDialog):
    """Модальное окно с таблицей истории загрузок.

    Позволяет просматривать завершeнные загрузки, открывать папку
    с файлом и очищать историю.
    """

    def __init__(
        self,
        history_manager: HistoryManager,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Инициализация диалога истории.

        Args:
            history_manager: Экземпляр :class:`HistoryManager`.
            parent: Родительский виджет.
        """
        super().__init__(parent)
        self._history = history_manager

        self.setWindowTitle("История загрузок")
        self.setMinimumSize(720, 420)
        self.setModal(True)

        self._setup_ui()
        self._populate()
        self.setStyleSheet(self._get_dialog_qss())

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Заголовок
        title_label = QLabel("ИСТОРИЯ ЗАГРУЗОК")
        title_label.setObjectName("historyTitle")
        layout.addWidget(title_label)

        # Таблица
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels([
            "Дата", "Название", "Тип", ""
        ])
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)

        header = self._table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        # Ширина колонки с кнопкой фиксирована: ResizeToContents не учитывает
        # размер виджета в ячейке, поэтому текст кнопки "ОТКРЫТЬ" обрезался.
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(3, 112)

        layout.addWidget(self._table, 1)

        # Кнопки
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        clear_btn = QPushButton("ОЧИСТИТЬ ИСТОРИЮ")
        clear_btn.setObjectName("historyClearBtn")
        clear_btn.clicked.connect(self._on_clear)
        btn_layout.addWidget(clear_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("ЗАКРЫТЬ")
        close_btn.setObjectName("historyCloseBtn")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _populate(self) -> None:
        """Заполнить таблицу данными из истории."""
        entries = self._history.get_all()
        self._table.setRowCount(len(entries))

        for row, entry in enumerate(entries):
            # Дата
            ts_item = QTableWidgetItem(self._format_ts(entry.timestamp))
            ts_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 0, ts_item)

            # Название
            self._table.setItem(row, 1, QTableWidgetItem(entry.title[:80]))

            # Тип
            type_item = QTableWidgetItem(entry.format_type.upper())
            type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 2, type_item)

            # Кнопка "Открыть папку" (выделяет файл в Explorer)
            open_btn = QPushButton("ОТКРЫТЬ")
            open_btn.setObjectName("historyOpenBtn")
            open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            file_path = entry.file_path
            if file_path and os.path.exists(os.path.dirname(file_path)):
                open_btn.clicked.connect(
                    lambda _checked=False, fp=file_path: self._on_open_file(fp)
                )
            else:
                open_btn.setEnabled(False)
                open_btn.setText("-")
            self._table.setCellWidget(row, 3, open_btn)

        # Высота строк
        for row in range(len(entries)):
            self._table.setRowHeight(row, 32)

    def _on_clear(self) -> None:
        """Очистить всю историю и обновить таблицу."""
        self._history.clear()
        self._table.setRowCount(0)

    def _on_open_file(self, file_path: str) -> None:
        """Открыть файл в Explorer с выделением, с обработкой удалeнного файла.

        Если файл был удалeн или перемещeн - открывает содержащую папку
        и показывает тост-предупреждение.

        Args:
            file_path: Полный путь к файлу.
        """
        if os.path.isfile(file_path):
            reveal_in_file_manager(file_path)
            return

        folder = os.path.dirname(file_path)
        if folder and os.path.isdir(folder):
            reveal_in_file_manager(folder)
        toast = Toast("Файл был удалён или перемещён", Toast.WARNING, parent=self)
        toast.show()

    @staticmethod
    def _format_ts(iso_str: str) -> str:
        """Форматировать ISO-метку времени в короткую строку.

        Args:
            iso_str: Время в ISO-формате.

        Returns:
            Отформатированная строка ``YYYY.MM.DD HH:MM``.
        """
        if not iso_str:
            return "-"
        try:
            dt = datetime.fromisoformat(iso_str)
            return dt.strftime(_DATETIME_FMT)
        except (ValueError, TypeError):
            return iso_str[:16]

    @staticmethod
    def _get_dialog_qss() -> str:
        """Вернуть QSS-стили для диалога истории."""
        return f"""
            HistoryDialog {{
                background-color: {BG_BLACK};
            }}
            QLabel#historyTitle {{
                font-size: 14pt;
                color: {CYAN};
                font-weight: bold;
            }}
            QTableWidget {{
                background-color: {BG_TABLE};
                alternate-background-color: {BG};
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 6px;
                font-size: 11px;
                outline: none;
            }}
            QTableWidget::item {{
                padding: 4px 8px;
            }}
            QTableWidget::item:selected {{
                background-color: rgba(0, 229, 255, 0.15);
                color: {CYAN};
            }}
            QHeaderView::section {{
                background-color: {BG};
                color: {CYAN};
                border: none;
                border-bottom: 1px solid {BORDER};
                padding: 6px 8px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton#historyClearBtn {{
                background-color: transparent;
                border: 1px solid {PINK};
                border-radius: 4px;
                padding: 6px 14px;
                color: {PINK};
                font-size: 11px;
                min-height: 32px;
            }}
            QPushButton#historyClearBtn:hover {{
                background-color: rgba(255, 64, 129, 0.1);
            }}
            QPushButton#historyCloseBtn {{
                background-color: transparent;
                border: 1px solid {CYAN};
                border-radius: 4px;
                padding: 6px 16px;
                color: {CYAN};
                font-size: 11px;
                min-height: 32px;
            }}
            QPushButton#historyCloseBtn:hover {{
                background-color: rgba(0, 229, 255, 0.1);
            }}
            QPushButton#historyOpenBtn {{
                background-color: transparent;
                border: 1px solid {GREEN};
                border-radius: 3px;
                padding: 2px 8px;
                color: {GREEN};
                font-size: 10px;
            }}
            QPushButton#historyOpenBtn:hover {{
                background-color: rgba(0, 255, 136, 0.15);
            }}
            QScrollBar:vertical {{
                background: {BG};
                width: 8px;
            }}
            QScrollBar::handle:vertical {{
                background: {CYAN};
                border-radius: 4px;
                min-height: 30px;
            }}
        """
