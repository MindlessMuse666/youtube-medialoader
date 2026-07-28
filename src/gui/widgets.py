"""Кастомные неоновые виджеты для YouTube Medialoader.

Содержит:
  - NeonButton - кнопка с неоновым свечением
  - NeonProgressBar - прогресс-бар с анимацией заполнения
  - LoadingSpinner - анимированный индикатор загрузки (спиннер)
  - Toast - всплывающее уведомление с анимацией slide-in
"""

from PySide6.QtCore import (
    Property,
    QAbstractAnimation,
    QEasingCurve,
    QEvent,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
)
from PySide6.QtGui import QColor, QEnterEvent, QFont, QFontMetrics, QShowEvent
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.gui import styles as gui_styles


# ---------------------------------------------------------------------------
# NeonButton
# ---------------------------------------------------------------------------


class NeonButton(QPushButton):
    """Плоская кнопка с неоновым свечением при наведении.

    Анимация свечения реализована через QPropertyAnimation
    над кастомным свойством ``glow_opacity``.

    Args:
        text: Текст на кнопке.
        parent: Родительский виджет.
        accent_color: Основной цвет кнопки в HEX (по умолчанию ``#00E5FF``).
            Для кнопки "Отмена" используйте ``"#FF4081"``.
    """

    def __init__(
        self,
        text: str = "",
        parent: QWidget | None = None,
        accent_color: str = "#00E5FF",
    ) -> None:
        super().__init__(text, parent)
        self._accent_color = accent_color
        self._hover_color = "#FF4081"  # при наведении - розовый для всех
        self._glow_opacity: float = 0.0
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setMinimumHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        accent = self._accent_color
        hover = self._hover_color

        self._glow = QGraphicsDropShadowEffect(self)
        self._glow.setBlurRadius(24)
        r, g, b = self._parse_hex(accent).split(", ")
        self._glow.setColor(QColor(int(r), int(g), int(b), 0))
        self._glow.setOffset(0, 0)
        self.setGraphicsEffect(self._glow)

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {accent};
                border-radius: 6px;
                padding: 8px 24px;
                color: {accent};
                font-family: {gui_styles.PIXEL_FONT_FAMILY};
                font-size: 9pt;
            }}
            QPushButton:hover {{
                background-color: rgba({self._parse_hex(hover)}, 0.08);
                border: 1px solid {hover};
                color: {hover};
            }}
            QPushButton:pressed {{
                background-color: rgba({self._parse_hex(accent)}, 0.15);
            }}
            QPushButton:disabled {{
                border-color: #2A2A2A;
                color: #555555;
            }}
        """)

    # ---- helpers ----

    @staticmethod
    def _parse_hex(hex_color: str) -> str:
        """Преобразовать HEX-цвет в строку RGB для rgba().

        Args:
            hex_color: Цвет в формате ``#RRGGBB``.

        Returns:
            Строка вида ``R, G, B``.
        """
        h = hex_color.lstrip("#")
        return f"{int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)}"

    # ---- glow opacity property ----

    def _get_glow_opacity(self) -> float:
        return self._glow_opacity

    def _set_glow_opacity(self, value: float) -> None:
        self._glow_opacity = value
        alpha = int(max(0, min(255, value * 255)))
        r, g, b = self._parse_hex(self._accent_color).split(", ")
        self._glow.setColor(QColor(int(r), int(g), int(b), alpha))

    glow_opacity = Property(
        float,
        _get_glow_opacity,
        _set_glow_opacity,
        # PySide6.Property stub expects Callable[[object], Any], но методы
        # принимают NeonButton (self). Игнорируем - во время выполнения Property
        # корректно передаeт self во все колбэки.
    )  # type: ignore[arg-type]

    # ---- events ----

    def enterEvent(self, event: QEnterEvent) -> None:
        """Плавное появление свечения при наведении."""
        self._start_glow_anim(0.6)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        """Плавное исчезание свечения при уходе курсора."""
        self._start_glow_anim(0.0)
        super().leaveEvent(event)

    def _start_glow_anim(self, target: float) -> None:
        anim = QPropertyAnimation(self, b"glow_opacity", self)
        anim.setEndValue(target)
        anim.setDuration(250)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)


# ---------------------------------------------------------------------------
# NeonProgressBar
# ---------------------------------------------------------------------------


class NeonProgressBar(QProgressBar):
    """Прогресс-бар с плавной анимацией заполнения.

    Пример использования::

        progress = NeonProgressBar()
        progress.animate_to(85)  # плавно заполнить до 85%
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimum(0)
        self.setMaximum(100)
        self.setValue(0)
        self.setTextVisible(True)

    def animate_to(self, value: int, duration: int = 400) -> None:
        """Анимированно установить значение прогресса.

        Args:
            value: Целевое значение (0-100).
            duration: Длительность анимации в миллисекундах.
        """
        anim = QPropertyAnimation(self, b"value", self)
        anim.setEndValue(value)
        anim.setDuration(duration)
        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

    def reset(self) -> None:
        """Сбросить прогресс до нуля без анимации."""
        self.setValue(0)


# ---------------------------------------------------------------------------
# LoadingSpinner
# ---------------------------------------------------------------------------


class LoadingSpinner(QLabel):
    """Анимированный индикатор загрузки (спиннер).

    Отображает вращающиеся символы Брайля. Запускается через :meth:`start`,
    останавливается через :meth:`stop`. Скрыт по умолчанию.

    Пример использования::

        spinner = LoadingSpinner()
        spinner.start()   # начать анимацию
        spinner.stop()    # остановить и скрыть
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        self._index: int = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.setStyleSheet("color: #00E5FF; font-size: 18px; background: transparent;")
        self.hide()

    def start(self) -> None:
        """Запустить анимацию спиннера и показать его."""
        self._index = 0
        self.setText(self._chars[0])
        self.show()
        self._timer.start(80)

    def stop(self) -> None:
        """Остановить анимацию спиннера и скрыть его."""
        self._timer.stop()
        self.hide()

    def _tick(self) -> None:
        """Переключиться на следующий символ анимации."""
        self._index = (self._index + 1) % len(self._chars)
        self.setText(self._chars[self._index])


# ---------------------------------------------------------------------------
# Toast
# ---------------------------------------------------------------------------


class Toast(QWidget):
    """Всплывающее уведомление с анимацией slide-in и авто-исчезанием.

    Появляется в правом нижнем углу родительского окна, через 3 секунды
    плавно исчезает.

    Цветовые константы:
        - ``Toast.INFO`` - голубой
        - ``Toast.SUCCESS`` - зелeный
        - ``Toast.ERROR`` - розовый
        - ``Toast.WARNING`` - жeлтый
    """

    INFO = "#00E5FF"
    SUCCESS = "#00FF88"
    ERROR = "#FF4081"
    WARNING = "#FFC107"

    TOAST_DURATION_MS = 3000

    def __init__(
        self,
        text: str,
        border_color: str = INFO,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._border_color = border_color
        self._opacity: float = 1.0
        self.setup_ui(text)
        self.raise_()

    def setup_ui(self, text: str) -> None:
        """Настроить внешний вид тоста."""
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # Контейнер с тенью
        container = QWidget(self)
        container.setObjectName("toastContainer")
        container.setStyleSheet(f"""
            #toastContainer {{
                background-color: rgba(26, 26, 26, 0.95);
                border: 1px solid {self._border_color};
                border-radius: 8px;
                padding: 12px 16px;
            }}
        """)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(12, 10, 12, 10)

        # Иконка-эмодзи
        icon_map = {
            self.INFO: "ℹ",
            self.SUCCESS: "✅",
            self.ERROR: "❌",
            self.WARNING: "⚠",
        }
        icon_label = QLabel(icon_map.get(self._border_color, "ℹ"))
        icon_label.setStyleSheet(f"font-size: 16px; color: {self._border_color};")
        icon_label.setFixedWidth(20)
        layout.addWidget(icon_label)

        # Текст
        text_label = QLabel(text)
        text_label.setStyleSheet("color: #FFFFFF; font-size: 12px; background: transparent;")
        text_label.setWordWrap(True)
        layout.addWidget(text_label, 1)

        # Основной layout для тоста
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(container)

        self.adjustSize()
        # Ограничиваем максимальную ширину, но не фиксируем жeстко
        self.setMaximumWidth(420)
        self.setMinimumWidth(280)

    def showEvent(self, event: QShowEvent) -> None:
        """Запустить slide-in анимацию при появлении."""
        super().showEvent(event)
        self._start_slide_in()
        QTimer.singleShot(self.TOAST_DURATION_MS, self._start_fade_out)

    def _start_slide_in(self) -> None:
        """Анимация выезда - тост появляется в правом нижнем углу окна.

        Использует глобальные координаты родительского окна, чтобы тост
        (который является топ-левел окном с флагом Tool) корректно
        позиционировался относительно родителя, а не экрана.
        """
        parent_widget = self.parent()
        if isinstance(parent_widget, QWidget):
            parent_global = parent_widget.mapToGlobal(parent_widget.rect().topLeft())
            pw = parent_widget.width()
            ph = parent_widget.height()
            start_x = parent_global.x() + pw
            end_x = max(parent_global.x() + pw - self.width() - 20, parent_global.x() + 10)
            y = max(parent_global.y() + ph - self.height() - 40, parent_global.y() + 10)
        else:
            screen_rect = self.screen().geometry()
            start_x = screen_rect.width()
            end_x = screen_rect.width() - self.width() - 20
            y = screen_rect.height() - self.height() - 40

        self.move(start_x, y)

        anim = QPropertyAnimation(self, b"pos", self)
        anim.setEndValue(QPoint(end_x, y))
        anim.setDuration(350)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

    def _start_fade_out(self) -> None:
        """Плавное исчезание перед закрытием."""
        self._fade_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.setDuration(500)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._fade_anim.finished.connect(self.close)
        self._fade_anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
