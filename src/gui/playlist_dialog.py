"""Диалог выбора видео из плейлиста YouTube.

Предоставляет класс :class:`PlaylistDialog` - модальное окно со списком
видео из плейлиста, возможность выбора отдельных элементов и добавления
их в очередь загрузки.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.gui import styles as gui_styles
from src.utils.formatters import format_duration
from src.utils.theme import BG, BG_BLACK, BORDER, CYAN, GRAY, GRAY_DARK, PINK, WHITE


class _PlaylistItemWidget(QWidget):
    """Виджет одного видео в списке плейлиста."""

    def __init__(
        self,
        entry: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        """Инициализация виджета элемента плейлиста.

        Args:
            entry: Словарь с данными видео (title, duration, url, index).
            parent: Родительский виджет.
        """
        super().__init__(parent)
        self.entry = entry
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        # Чекбокс
        self.checkbox = QCheckBox()
        self.checkbox.setStyleSheet(f"""
            QCheckBox::indicator {{
                width: 18px; height: 18px;
                border: 1px solid {CYAN}; border-radius: 3px;
                background: {BG};
            }}
            QCheckBox::indicator:checked {{
                background: {CYAN};
                border-color: {CYAN};
            }}
            QCheckBox::indicator:hover {{
                border-color: {PINK};
            }}
        """)
        layout.addWidget(self.checkbox)

        # Индекс
        idx = self.entry.get("index", "")
        idx_label = QLabel(f"#{idx}" if idx else "")
        idx_label.setFixedWidth(32)
        idx_label.setStyleSheet(f"color: {GRAY}; font-size: 11px;")
        layout.addWidget(idx_label)

        # Информация о видео
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        title = self.entry.get("title", "Untitled")
        title_label = QLabel(title)
        title_label.setWordWrap(True)
        title_label.setStyleSheet(f"color: {WHITE}; font-size: 12px; font-weight: bold;")
        info_layout.addWidget(title_label)

        # Длительность
        duration = self.entry.get("duration", 0)
        if duration:
            dur_label = QLabel(f"⏱ {format_duration(int(duration))}")
            dur_label.setStyleSheet(f"color: {GRAY_DARK}; font-size: 10px;")
            info_layout.addWidget(dur_label)

        layout.addLayout(info_layout, 1)

    @property
    def is_checked(self) -> bool:
        """Вернуть ``True``, если чекбокс отмечен."""
        return self.checkbox.isChecked()

    @is_checked.setter
    def is_checked(self, value: bool) -> None:
        """Установить состояние чекбокса.

        Args:
            value: ``True`` для отметки, ``False`` для снятия.
        """
        self.checkbox.setChecked(value)


class PlaylistDialog(QDialog):
    """Модальное окно со списком видео из плейлиста.

    Позволяет выбрать отдельные видео и добавить их в очередь загрузки.

    Атрибуты:
        selected_entries: Список выбранных словарей с данными видео.
    """

    def __init__(
        self,
        entries: list[dict[str, Any]],
        parent: QWidget | None = None,
    ) -> None:
        """Инициализация диалога плейлиста.

        Args:
            entries: Список словарей с данными видео из плейлиста.
            parent: Родительский виджет.
        """
        super().__init__(parent)
        self._entries = entries
        self._item_widgets: list[_PlaylistItemWidget] = []
        self.selected_entries: list[dict[str, Any]] = []

        self.setWindowTitle("Плейлист")
        self.setMinimumSize(520, 400)
        self.setModal(True)

        self._setup_ui()
        self.setStyleSheet(self._get_dialog_qss())

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Заголовок
        title_label = QLabel(f"Плейлист: {len(self._entries)} видео")
        title_label.setObjectName("playlistTitle")
        title_label.setStyleSheet(
            f"font-family: {gui_styles.PIXEL_FONT_FAMILY}; "
            f"font-size: 12pt; color: {CYAN}; font-weight: bold;"
        )
        layout.addWidget(title_label)

        # Кнопки Select All / Deselect All
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        select_all_btn = QPushButton("Выбрать все")
        select_all_btn.setObjectName("playlistActionBtn")
        select_all_btn.clicked.connect(self._select_all)
        btn_row.addWidget(select_all_btn)

        deselect_all_btn = QPushButton("Снять все")
        deselect_all_btn.setObjectName("playlistActionBtn")
        deselect_all_btn.clicked.connect(self._deselect_all)
        btn_row.addWidget(deselect_all_btn)

        btn_row.addStretch()

        count_label = QLabel(f"Выбрано: {len(self._entries)}")
        count_label.setObjectName("playlistCount")
        self._count_label = count_label
        btn_row.addWidget(count_label)

        layout.addLayout(btn_row)

        # Список видео
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: {BG}; border: 1px solid {BORDER}; "
            f"border-radius: 6px; }}"
        )

        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)
        list_layout.setSpacing(2)
        list_layout.setContentsMargins(4, 4, 4, 4)

        for entry in self._entries:
            item = _PlaylistItemWidget(entry)
            item.checkbox.toggled.connect(self._update_count)
            # Добавляем в список ДО отметки: setChecked дёргает сигнал
            # toggled -> _update_count, который считает только уже
            # добавленные элементы. Иначе последний не попадает в счётчик.
            self._item_widgets.append(item)
            item.checkbox.setChecked(True)  # все выбраны по умолчанию
            list_layout.addWidget(item)

        list_layout.addStretch()
        scroll.setWidget(list_widget)
        layout.addWidget(scroll, 1)

        # Кнопка "Скачать выбранные"
        download_btn = QPushButton(f"📥 Скачать выбранные ({len(self._entries)})")
        download_btn.setObjectName("playlistDownloadBtn")
        download_btn.clicked.connect(self._accept_selected)
        layout.addWidget(download_btn)

    def _select_all(self) -> None:
        """Отметить все видео в списке."""
        for w in self._item_widgets:
            w.is_checked = True
        self._update_count()

    def _deselect_all(self) -> None:
        """Снять отметки со всех видео."""
        for w in self._item_widgets:
            w.is_checked = False
        self._update_count()

    def _update_count(self, _checked: bool | None = None) -> None:
        """Обновить счeтчик выбранных элементов.

        Args:
            _checked: Не используется (для сигнала toggled).
        """
        count = sum(1 for w in self._item_widgets if w.is_checked)
        self._count_label.setText(f"Выбрано: {count}")

        # Обновляем текст кнопки
        for child in self.findChildren(QPushButton):
            if child.text().startswith("📥"):
                child.setText(f"📥 Скачать выбранные ({count})")
                break

    def _accept_selected(self) -> None:
        """Подтвердить выбор: сохранить выбранные элементы и закрыть диалог."""
        self.selected_entries = [
            w.entry for w in self._item_widgets if w.is_checked
        ]
        self.accept()

    @staticmethod
    def _get_dialog_qss() -> str:
        """Вернуть QSS-стили для диалога."""
        return f"""
            PlaylistDialog {{
                background-color: {BG_BLACK};
            }}
            QLabel#playlistCount {{
                color: {GRAY}; font-size: 12px;
            }}
            QPushButton#playlistActionBtn {{
                background-color: transparent;
                border: 1px solid {CYAN}; border-radius: 4px;
                padding: 6px 14px;
                color: {CYAN}; font-size: 11px;
            }}
            QPushButton#playlistActionBtn:hover {{
                background-color: rgba(0, 229, 255, 0.1);
                border-color: {PINK}; color: {PINK};
            }}
            QPushButton#playlistDownloadBtn {{
                background-color: {CYAN};
                border: none; border-radius: 6px;
                padding: 12px 24px;
                color: {BG_BLACK}; font-size: 13px; font-weight: bold;
            }}
            QPushButton#playlistDownloadBtn:hover {{
                background-color: {PINK};
            }}
            QScrollBar:vertical {{
                background: {BG}; width: 8px;
            }}
            QScrollBar::handle:vertical {{
                background: {CYAN}; border-radius: 4px;
                min-height: 30px;
            }}
        """
