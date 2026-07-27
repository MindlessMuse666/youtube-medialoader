"""Анимированный фон с градиентными сферами для YouTube Medialoader.

Класс :class:`AnimatedBackground` рисует несколько больших полупрозрачных
сфер, которые медленно дрейфуют по экрану, создавая эффект глубины.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, QTimer, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QPainter,
    QPaintEvent,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget


class AnimatedBackground(QWidget):
    """Фон с анимированными градиентными сферами.

    Сферы двигаются с разной скоростью и имеют разный цвет (голубой/розовый
    с низкой альфой). Анимация обновляется по таймеру (~20 FPS).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._spheres = [
            {
                "x": 0.2,
                "y": 0.3,
                "dx": 0.003,
                "dy": 0.002,
                "r": 0.35,
                "color": QColor(0, 229, 255, 30),
            },
            {
                "x": 0.7,
                "y": 0.6,
                "dx": -0.002,
                "dy": 0.003,
                "r": 0.30,
                "color": QColor(255, 64, 129, 22),
            },
            {
                "x": 0.5,
                "y": 0.2,
                "dx": 0.001,
                "dy": -0.004,
                "r": 0.25,
                "color": QColor(0, 229, 255, 18),
            },
        ]

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._timer.start(50)  # ~20 FPS

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def _step(self) -> None:
        """Сдвинуть сферы и запросить перерисовку."""
        w = self.width()
        h = self.height()
        if w == 0 or h == 0:
            return

        for s in self._spheres:
            s["x"] += s["dx"]
            s["y"] += s["dy"]

            # Отскок от краёв
            r = s["r"]
            if s["x"] < -r or s["x"] > 1 + r:
                s["dx"] *= -1
            if s["y"] < -r or s["y"] > 1 + r:
                s["dy"] *= -1

        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Нарисовать градиентные сферы на чёрном фоне."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        if w == 0 or h == 0:
            return

        # Базовый фон
        painter.fillRect(QRect(0, 0, w, h), QColor(10, 10, 10))

        dim = min(w, h)

        for s in self._spheres:
            cx = s["x"] * w
            cy = s["y"] * h
            radius = s["r"] * dim

            color = s["color"]
            gradient = QRadialGradient(QPointF(cx, cy), radius)
            gradient.setColorAt(0.0, color)
            gradient.setColorAt(
                0.5,
                QColor(
                    color.red(),
                    color.green(),
                    color.blue(),
                    color.alpha() // 2,
                ),
            )
            gradient.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))

            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(cx, cy), radius, radius)
