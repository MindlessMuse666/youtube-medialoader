"""Очередь загрузок для YouTube Medialoader.

Предоставляет виджет :class:`DownloadQueueWidget` и класс :class:`QueueItem`
для управления последовательной загрузкой нескольких видео/аудиофайлов.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    Qt,
    QVariantAnimation,
    Signal,
)
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.utils.theme import BORDER, CYAN, GRAY, GRAY_DARK, GREEN, PINK, WHITE, YELLOW


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


def _format_details(format_type: str, quality: str) -> str:
    """Строка деталей формата и качества для записи в очереди.

    Качество показывается только для видео: для MP3 расширения достаточно,
    а ``| 720p`` (или иное качество) для аудио не имеет смысла.

    Args:
        format_type: ``"mp4"`` или ``"mp3"``.
        quality: ``"1080p"``, ``"720p"`` или ``"480p"``.

    Returns:
        Строка вида ``"MP4 | 720p"`` или ``"MP3"``.
    """
    if format_type.lower() == "mp3":
        return "MP3"
    return f"{format_type.upper()} | {quality}"


class _QueueItemWidget(QWidget):
    """Виджет одного элемента очереди."""

    STATUS_COLORS = {
        QueueItemStatus.PENDING: GRAY,
        QueueItemStatus.DOWNLOADING: CYAN,
        QueueItemStatus.COMPLETED: GREEN,
        QueueItemStatus.ERROR: PINK,
        QueueItemStatus.CANCELLED: YELLOW,
    }

    STATUS_LABELS = {
        QueueItemStatus.PENDING: "в очереди",
        QueueItemStatus.DOWNLOADING: "скачивается…",
        QueueItemStatus.COMPLETED: "готово",
        QueueItemStatus.ERROR: "ошибка",
        QueueItemStatus.CANCELLED: "отмена",
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
        # Внутренние отступы самого элемента - вокруг блока с информацией
        # о видео. Именно здесь нужно пространство, чтобы записи очереди
        # выглядели просторнее и не прилипали к рамке списка.
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        # Индекс
        idx_label = QLabel(f"#{self.index + 1}")
        idx_label.setFixedWidth(24)
        idx_label.setStyleSheet(f"color: {GRAY}; font-size: 11px;")
        layout.addWidget(idx_label)

        # Информация о файле
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        title_text = self.item.title or self.item.filename or "untitled"
        if len(title_text) > 50:
            title_text = title_text[:47] + "…"
        title_label = QLabel(title_text)
        title_label.setStyleSheet(f"color: {WHITE}; font-size: 12px;")
        info_layout.addWidget(title_label)

        details = _format_details(self.item.format_type, self.item.quality)
        detail_label = QLabel(details)
        detail_label.setStyleSheet(f"color: {GRAY_DARK}; font-size: 10px;")
        info_layout.addWidget(detail_label)

        layout.addLayout(info_layout, 1)

        # Статус
        color = self.STATUS_COLORS.get(self.item.status, GRAY)
        label = self.STATUS_LABELS.get(self.item.status, "")
        status_label = QLabel(label)
        status_label.setStyleSheet(f"color: {color}; font-size: 11px;")
        layout.addWidget(status_label)


class DownloadQueueWidget(QGroupBox):
    """Виджет очереди загрузок в виде группы с заголовком.

    Отображает список добавленных в очередь элементов и их статус.
    Заголовок группы показывает текущее количество элементов; благодаря
    наследованию от :class:`QGroupBox` внешний вид и внутренние отступы
    совпадают с остальными блоками окна ("Информация", "Логи", …).

    Высота списка подстраивается под содержимое: пока элементов мало -
    область компактна и показывает их без прокрутки; с ростом очереди она
    увеличивается до :attr:`MAX_HEIGHT`, а дальше элементы прокручиваются
    внутри области. Изменение высоты анимируется.

    Сигналы:
        queue_changed: Срабатывает при любом изменении очереди.
    """

    # Минимальная высота списка (одна строка).
    MIN_HEIGHT = 64
    # Потолок высоты - дальше включается вертикальный скролл.
    MAX_HEIGHT = 240
    # Вертикальные отступы внутри скролл-области (сверху и снизу).
    _SCROLL_PADDING = 8
    # Длительность анимации изменения высоты, мс.
    _HEIGHT_ANIM_MS = 200

    queue_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Инициализация виджета очереди.

        Args:
            parent: Родительский виджет.
        """
        super().__init__("ОЧЕРЕДЬ: 0", parent)
        self._items: list[QueueItem] = []
        self._setup_ui()
        self.setVisible(False)

    def _setup_ui(self) -> None:
        # Отступы самого блока держим умеренными - "воздух" вокруг записей
        # очереди обеспечивают внутренние отступы _QueueItemWidget, а не
        # рамка группы (см. _QueueItemWidget._setup_ui).
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 10)
        layout.setSpacing(8)

        # Список элементов в скролле
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setFixedHeight(self.MIN_HEIGHT)
        self._scroll.setStyleSheet(
            f"QScrollArea {{ background: transparent; border: 1px solid {BORDER}; "
            f"border-radius: 4px; }}"
        )

        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setSpacing(4)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        # Два упора (сверху и снизу): пока строк меньше доступной высоты,
        # блок строк центрируется по вертикали, оставаясь прижатым к левому
        # краю. Когда очередь перерастает область, упоры схлопываются в ноль
        # и строки прокручиваются от верха как обычно.
        self._list_layout.addStretch()
        self._list_layout.addStretch()
        self._scroll.setWidget(self._list_widget)

        layout.addWidget(self._scroll)

        # Кнопка очистки завершённых - внизу блока
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.addStretch()
        clear_btn = QPushButton("ОЧИСТИТЬ ЗАВЕРШЕННЫЕ")
        # Стиль общий с кнопкой "ОЧИСТИТЬ ЛОГИ" (см. QSS #queueClearBtn)
        clear_btn.setObjectName("queueClearBtn")
        clear_btn.clicked.connect(self._clear_completed)
        btn_row.addWidget(clear_btn)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Публичный API
    # ------------------------------------------------------------------

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
        """Отметить элемент как завершённый.

        Args:
            item: Элемент для обновления.
        """
        item.status = QueueItemStatus.COMPLETED
        self._rebuild_list()
        self.queue_changed.emit()

    def mark_error(self, item: QueueItem, error: str) -> None:
        """Отметить элемент как завершённый с ошибкой.

        Args:
            item: Элемент для обновления.
            error: Текст ошибки.
        """
        item.status = QueueItemStatus.ERROR
        item.error_text = error
        self._rebuild_list()
        self.queue_changed.emit()

    def mark_cancelled(self, item: QueueItem) -> None:
        """Отметить элемент как отменённый пользователем.

        Args:
            item: Элемент для обновления.
        """
        item.status = QueueItemStatus.CANCELLED
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

    # ------------------------------------------------------------------
    # Внутренняя логика
    # ------------------------------------------------------------------

    def _clear_completed(self) -> None:
        """Удалить из очереди завершённые, ошибочные и отменённые элементы."""
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
        """Перестроить список виджетов и обновить заголовок группы."""
        # Очищаем layout, сохраняя два упора для вертикального центрирования
        # (индекс 0 и последний; строки всегда идут между ними).
        while self._list_layout.count() > 2:
            child = self._list_layout.takeAt(1)
            if child and child.widget():
                child.widget().deleteLater()

        # Вставляем новые виджеты между упорами
        for i, item in enumerate(self._items):
            widget = _QueueItemWidget(item, i)
            self._list_layout.insertWidget(i + 1, widget)

        # Обновляем заголовок группы с количеством элементов
        self.setTitle(f"ОЧЕРЕДЬ: {len(self._items)}")
        self._update_scroll_height()

    def _update_scroll_height(self) -> None:
        """Подогнать высоту списка под содержимое очереди.

        Идеальная высота - сумма высот всех строк плюс отступы. Пока она не
        превышает :attr:`MAX_HEIGHT`, область компактна и скролл не нужен;
        иначе высота фиксируется на потолке, а лишние элементы прокручиваются.
        """
        content_h = 0
        for i in range(self._list_layout.count()):
            item = self._list_layout.itemAt(i)
            widget = item.widget() if item is not None else None
            if widget is not None:
                content_h += widget.sizeHint().height()
        # Расстояния между строками (включая отступ перед stretch)
        if self._items:
            content_h += self._list_layout.spacing() * len(self._items)
        content_h += self._SCROLL_PADDING

        target = min(max(content_h, self.MIN_HEIGHT), self.MAX_HEIGHT)

        # Скрытый или практически не изменившийся виджет меняем без анимации.
        if not self.isVisible() or abs(self._scroll.height() - target) < 2:
            self._scroll.setFixedHeight(target)
            return
        self._animate_scroll_height(target)

    def _animate_scroll_height(self, target: int) -> None:
        """Плавно изменить высоту списка до *target*.

        Args:
            target: Целевая высота в пикселях.
        """
        anim = QVariantAnimation(self)
        anim.setStartValue(self._scroll.height())
        anim.setEndValue(target)
        anim.setDuration(self._HEIGHT_ANIM_MS)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.valueChanged.connect(
            lambda value: self._scroll.setFixedHeight(int(value))
        )
        anim.finished.connect(lambda: self._scroll.setFixedHeight(target))
        anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
