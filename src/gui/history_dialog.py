"""Диалог истории загрузок для YouTube Medialoader.

Предоставляет класс :class:`HistoryDialog` - модальное окно с таблицей
завершeнных загрузок, возможностью открыть папку с файлом и очисткой истории.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
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

from src.utils.history import HistoryEntry, HistoryManager

_DATETIME_FMT = "%Y-%m-%d %H:%M"


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
        title_label = QLabel("История загрузок")
        title_label.setObjectName("historyTitle")
        layout.addWidget(title_label)

        # Таблица
        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels([
            "Дата", "Название", "Тип", "Качество", "Размер", ""
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
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self._table, 1)

        # Кнопки
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        clear_btn = QPushButton("Очистить историю")
        clear_btn.setObjectName("historyClearBtn")
        clear_btn.clicked.connect(self._on_clear)
        btn_layout.addWidget(clear_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("Закрыть")
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

            # Качество
            quality_item = QTableWidgetItem(entry.quality)
            quality_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 3, quality_item)

            # Размер
            size_str = self._format_size(entry.file_size)
            size_item = QTableWidgetItem(size_str)
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 4, size_item)

            # Кнопка "Открыть папку"
            open_btn = QPushButton("📂 Открыть")
            open_btn.setObjectName("historyOpenBtn")
            open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            file_path = entry.file_path
            if file_path and os.path.exists(os.path.dirname(file_path)):
                open_btn.clicked.connect(
                    lambda _checked=False, fp=file_path: self._open_folder(fp)
                )
            else:
                open_btn.setEnabled(False)
                open_btn.setText("-")
            self._table.setCellWidget(row, 5, open_btn)

        # Высота строк
        for row in range(len(entries)):
            self._table.setRowHeight(row, 32)

    def _on_clear(self) -> None:
        """Очистить всю историю и обновить таблицу."""
        self._history.clear()
        self._table.setRowCount(0)

    @staticmethod
    def _open_folder(file_path: str) -> None:
        """Открыть папку с файлом в системном файловом менеджере.

        Args:
            file_path: Полный путь к файлу.
        """
        folder = os.path.dirname(file_path)
        if folder and os.path.isdir(folder):
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    @staticmethod
    def _format_ts(iso_str: str) -> str:
        """Форматировать ISO-метку времени в короткую строку.

        Args:
            iso_str: Время в ISO-формате.

        Returns:
            Отформатированная строка ``YYYY-MM-DD HH:MM``.
        """
        if not iso_str:
            return "-"
        try:
            dt = datetime.fromisoformat(iso_str)
            return dt.strftime(_DATETIME_FMT)
        except (ValueError, TypeError):
            return iso_str[:16]

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Преобразовать байты в читаемый размер.

        Args:
            size_bytes: Размер в байтах.

        Returns:
            Отформатированная строка.
        """
        if size_bytes <= 0:
            return "-"
        if size_bytes < 1024:
            return f"{size_bytes} Б"
        elif size_bytes < 1024**2:
            return f"{size_bytes / 1024:.1f} КБ"
        elif size_bytes < 1024**3:
            return f"{size_bytes / 1024**2:.1f} МБ"
        else:
            return f"{size_bytes / 1024**3:.2f} ГБ"

    @staticmethod
    def _get_dialog_qss() -> str:
        """Вернуть QSS-стили для диалога истории."""
        return """
            HistoryDialog {
                background-color: #0A0A0A;
            }
            QLabel#historyTitle {
                font-size: 14pt;
                color: #00E5FF;
                font-weight: bold;
            }
            QTableWidget {
                background-color: #111111;
                alternate-background-color: #1A1A1A;
                color: #CCCCCC;
                border: 1px solid #2A2A2A;
                border-radius: 6px;
                font-size: 11px;
                outline: none;
            }
            QTableWidget::item {
                padding: 4px 8px;
            }
            QTableWidget::item:selected {
                background-color: rgba(0, 229, 255, 0.15);
                color: #00E5FF;
            }
            QHeaderView::section {
                background-color: #1A1A1A;
                color: #00E5FF;
                border: none;
                border-bottom: 1px solid #2A2A2A;
                padding: 6px 8px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton#historyClearBtn {
                background-color: transparent;
                border: 1px solid #FF4081;
                border-radius: 4px;
                padding: 6px 14px;
                color: #FF4081;
                font-size: 11px;
            }
            QPushButton#historyClearBtn:hover {
                background-color: rgba(255, 64, 129, 0.1);
            }
            QPushButton#historyCloseBtn {
                background-color: transparent;
                border: 1px solid #00E5FF;
                border-radius: 4px;
                padding: 6px 16px;
                color: #00E5FF;
                font-size: 11px;
            }
            QPushButton#historyCloseBtn:hover {
                background-color: rgba(0, 229, 255, 0.1);
            }
            QPushButton#historyOpenBtn {
                background-color: transparent;
                border: 1px solid #00FF88;
                border-radius: 3px;
                padding: 2px 8px;
                color: #00FF88;
                font-size: 10px;
            }
            QPushButton#historyOpenBtn:hover {
                background-color: rgba(0, 255, 136, 0.15);
            }
            QScrollBar:vertical {
                background: #1A1A1A;
                width: 8px;
            }
            QScrollBar::handle:vertical {
                background: #00E5FF;
                border-radius: 4px;
                min-height: 30px;
            }
        """
