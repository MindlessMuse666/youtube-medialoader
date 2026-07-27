"""Кастомные неоновые виджеты для YouTube Medialoader.

Содержит:
  - NeonButton — кнопка с неоновым свечением
  - NeonProgressBar — прогресс-бар с анимацией заполнения
  - Toast — всплывающее уведомление с анимацией slide-in
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
from PySide6.QtGui import QColor, QEnterEvent, QShowEvent
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


# ---------------------------------------------------------------------------
# NeonButton
# ---------------------------------------------------------------------------


class NeonButton(QPushButton):
    """Плоская кнопка с неоновым свечением при наведении.

    Анимация свечения реализована через QPropertyAnimation
    над кастомным свойством ``glow_opacity``.
    """

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._glow_opacity: float = 0.0
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setMinimumHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._glow = QGraphicsDropShadowEffect(self)
        self._glow.setBlurRadius(24)
        self._glow.setColor(QColor(0, 229, 255, 0))
        self._glow.setOffset(0, 0)
        self.setGraphicsEffect(self._glow)

        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #00E5FF;
                border-radius: 6px;
                padding: 8px 24px;
                color: #00E5FF;
                font-family: "Press Start 2P";
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(0, 229, 255, 0.08);
                border: 1px solid #FF4081;
                color: #FF4081;
            }
            QPushButton:pressed {
                background-color: rgba(0, 229, 255, 0.15);
            }
            QPushButton:disabled {
                border-color: #2A2A2A;
                color: #555555;
            }
        """)

    # ---- glow opacity property ----

    def _get_glow_opacity(self) -> float:
        return self._glow_opacity

    def _set_glow_opacity(self, value: float) -> None:
        self._glow_opacity = value
        alpha = int(max(0, min(255, value * 255)))
        self._glow.setColor(QColor(0, 229, 255, alpha))

    glow_opacity = Property(
        float, _get_glow_opacity, _set_glow_opacity  # type: ignore[arg-type]
    )

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
# Toast
# ---------------------------------------------------------------------------


class Toast(QWidget):
    """Всплывающее уведомление с анимацией slide-in и авто-исчезанием.

    Появляется в правом нижнем углу родительского окна, через 3 секунды
    плавно исчезает.

    Цветовые константы:
        - ``Toast.INFO`` — голубой
        - ``Toast.SUCCESS`` — зелёный
        - ``Toast.ERROR`` — розовый
        - ``Toast.WARNING`` — жёлтый
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
        self.setFixedWidth(320)
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

    def showEvent(self, event: QShowEvent) -> None:
        """Запустить slide-in анимацию при появлении."""
        super().showEvent(event)
        self._start_slide_in()
        QTimer.singleShot(self.TOAST_DURATION_MS, self._start_fade_out)

    def _start_slide_in(self) -> None:
        """Анимация выезда справа."""
        parent_widget = self.parent()
        if isinstance(parent_widget, QWidget):
            parent_rect = parent_widget.rect()
        else:
            parent_rect = self.screen().geometry()
        start_x = parent_rect.width()
        end_x = parent_rect.width() - self.width() - 20
        y = parent_rect.height() - self.height() - 40

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
