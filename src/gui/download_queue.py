"""Очередь загрузок для YouTube Medialoader.

Предоставляет виджет :class:`DownloadQueueWidget` и класс :class:`QueueItem`
для управления последовательной загрузкой нескольких видео/аудиофайлов.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class QueueItemStatus(Enum):
    """Статус элемента в очереди загрузки."""

    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class QueueItem:
    """Один элемент очереди загрузки.

    Attributes:
        url: Ссылка на YouTube-видео.
        output_path: Папка для сохранения.
        filename: Имя файла (с расширением).
        format_type: ``"mp4"`` или ``"mp3"``.
        quality: ``"1080p"``, ``"720p"`` или ``"480p"``.
        status: Текущий статус загрузки.
        error_text: Текст ошибки (если статус ``ERROR``).
        title: Название видео (для отображения в очереди).
    """

    url: str
    output_path: str
    filename: str
    format_type: str = "mp4"
    quality: str = "720p"
    status: QueueItemStatus = QueueItemStatus.PENDING
    error_text: str = ""
    title: str = ""


class _QueueItemWidget(QWidget):
    """Виджет одного элемента очереди."""

    STATUS_COLORS = {
        QueueItemStatus.PENDING: "#AAAAAA",
        QueueItemStatus.DOWNLOADING: "#00E5FF",
        QueueItemStatus.COMPLETED: "#00FF88",
        QueueItemStatus.ERROR: "#FF4081",
        QueueItemStatus.CANCELLED: "#555555",
    }

    STATUS_LABELS = {
        QueueItemStatus.PENDING: "в очереди",
        QueueItemStatus.DOWNLOADING: "скачивается…",
        QueueItemStatus.COMPLETED: "готово",
        QueueItemStatus.ERROR: "ошибка",
        QueueItemStatus.CANCELLED: "отменено",
    }

    def __init__(
        self, item: QueueItem, index: int, parent: QWidget | None = None
    ) -> None:
        """Инициализация виджета элемента очереди.

        Args:
            item: Элемент очереди.
            index: Порядковый номер (для отображения).
            parent: Родительский виджет.
        """
        super().__init__(parent)
        self.item = item
        self.index = index
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # Индекс
        idx_label = QLabel(f"#{self.index + 1}")
        idx_label.setFixedWidth(24)
        idx_label.setStyleSheet("color: #AAAAAA; font-size: 11px;")
        layout.addWidget(idx_label)

        # Информация о файле
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        title_text = self.item.title or self.item.filename or "untitled"
        if len(title_text) > 50:
            title_text = title_text[:47] + "…"
        title_label = QLabel(title_text)
        title_label.setStyleSheet("color: #FFFFFF; font-size: 12px;")
        info_layout.addWidget(title_label)

        details = f"{self.item.format_type.upper()} | {self.item.quality}"
        detail_label = QLabel(details)
        detail_label.setStyleSheet("color: #888888; font-size: 10px;")
        info_layout.addWidget(detail_label)

        layout.addLayout(info_layout, 1)

        # Статус
        color = self.STATUS_COLORS.get(self.item.status, "#AAAAAA")
        label = self.STATUS_LABELS.get(self.item.status, "")
        status_label = QLabel(label)
        status_label.setStyleSheet(f"color: {color}; font-size: 11px;")
        layout.addWidget(status_label)


class DownloadQueueWidget(QWidget):
    """Виджет очереди загрузок.

    Отображает список добавленных в очередь элементов, их статус и прогресс.
    Позволяет очищать завершeнные элементы.

    Сигналы:
        queue_changed: Срабатывает при любом изменении очереди.
    """

    queue_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Инициализация виджета очереди.

        Args:
            parent: Родительский виджет.
        """
        super().__init__(parent)
        self._items: list[QueueItem] = []
        self._setup_ui()
        self.setVisible(False)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Заголовок
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        self._count_label = QLabel("Очередь: 0")
        self._count_label.setStyleSheet(
            "color: #00E5FF; font-size: 11px; font-weight: bold;"
        )
        header_layout.addWidget(self._count_label)

        header_layout.addStretch()

        clear_btn = QPushButton("Очистить")
        clear_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none;
                color: #FF4081; font-size: 11px;
                text-decoration: underline;
            }
            QPushButton:hover { color: #FF80AB; }
        """)
        clear_btn.clicked.connect(self._clear_completed)
        header_layout.addWidget(clear_btn)

        layout.addLayout(header_layout)

        # Список элементов в скролле
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMaximumHeight(200)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: 1px solid #2A2A2A; "
            "border-radius: 4px; }"
        )

        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setSpacing(2)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.addStretch()
        scroll.setWidget(self._list_widget)

        layout.addWidget(scroll)

    def add_item(self, item: QueueItem) -> None:
        """Добавить элемент в очередь.

        Args:
            item: Элемент для добавления.
        """
        self._items.append(item)
        self._rebuild_list()
        self.setVisible(True)
        self.queue_changed.emit()

    def next_pending(self) -> Optional[QueueItem]:
        """Вернуть следующий элемент, ожидающий загрузки.

        Returns:
            Элемент со статусом ``PENDING`` или ``None``, если таких нет.
        """
        for item in self._items:
            if item.status == QueueItemStatus.PENDING:
                return item
        return None

    def mark_downloading(self, item: QueueItem) -> None:
        """Отметить элемент как скачиваемый.

        Args:
            item: Элемент для обновления.
        """
        item.status = QueueItemStatus.DOWNLOADING
        self._rebuild_list()
        self.queue_changed.emit()

    def mark_completed(self, item: QueueItem) -> None:
        """Отметить элемент как завершeнный.

        Args:
            item: Элемент для обновления.
        """
        item.status = QueueItemStatus.COMPLETED
        self._rebuild_list()
        self.queue_changed.emit()

    def mark_error(self, item: QueueItem, error: str) -> None:
        """Отметить элемент как завершeнный с ошибкой.

        Args:
            item: Элемент для обновления.
            error: Текст ошибки.
        """
        item.status = QueueItemStatus.ERROR
        item.error_text = error
        self._rebuild_list()
        self.queue_changed.emit()

    @property
    def is_empty(self) -> bool:
        """Вернуть ``True``, если в очереди нет активных элементов."""
        return not self._items or all(
            i.status
            in (
                QueueItemStatus.COMPLETED,
                QueueItemStatus.ERROR,
                QueueItemStatus.CANCELLED,
            )
            for i in self._items
        )

    def has_pending(self) -> bool:
        """Вернуть ``True``, если есть ожидающие загрузки элементы."""
        return any(i.status == QueueItemStatus.PENDING for i in self._items)

    def _clear_completed(self) -> None:
        """Удалить из очереди завершeнные и ошибочные элементы."""
        self._items = [
            i
            for i in self._items
            if i.status
            not in (
                QueueItemStatus.COMPLETED,
                QueueItemStatus.ERROR,
                QueueItemStatus.CANCELLED,
            )
        ]
        self._rebuild_list()
        if self.is_empty:
            self.setVisible(False)
        self.queue_changed.emit()

    def _rebuild_list(self) -> None:
        """Перестроить список виджетов на основе ``_items``."""
        # Очищаем layout (оставляем stretch)
        while self._list_layout.count() > 1:
            child = self._list_layout.takeAt(0)
            if child and child.widget():
                child.widget().deleteLater()

        # Вставляем новые виджеты
        for i, item in enumerate(self._items):
            widget = _QueueItemWidget(item, i)
            self._list_layout.insertWidget(i, widget)

        # Обновляем счeтчик
        total = len(self._items)
        self._count_label.setText(f"Очередь: {total}")
