"""Точка входа в приложение YouTube Medialoader.

Запускает QApplication, инициализирует логгер и показывает главное окно.
"""

from __future__ import annotations

import os
import signal
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from src.gui.main_window import MainWindow
from src.utils.logger import get_log_signal

# Цветовые константы для логов (HEX)
LOG_COLORS = {
    "INFO": "#00E5FF",
    "SUCCESS": "#00FF88",
    "WARNING": "#FFC107",
    "ERROR": "#FF4081",
}


def _app_icon_path() -> str:
    """Вернуть путь к иконке приложения (``.ico`` на Windows, ``.png`` иначе).

    Учитывает сборку PyInstaller (``sys._MEIPASS``).
    """
    base: Path
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        base = Path(str(meipass)) if meipass else Path()
    else:
        base = Path(__file__).resolve().parent.parent / "assets"

    icon_name = "app_icon.ico" if sys.platform == "win32" else "app_icon.png"
    return str(base / "icons" / icon_name)


def main() -> None:
    """Запустить графическое приложение."""
    app = QApplication(sys.argv)
    app.setApplicationName("YouTube Medialoader")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("MindlessMuse666")

    # Базовый шрифт приложения - чтобы Qt не ругался на Point size <= 0
    default_font = QFont("Press Start 2P", 10)
    default_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(default_font)

    # Иконка приложения
    icon_path = _app_icon_path()
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Создаeм главное окно
    window = MainWindow()

    # Подключаем логгер к окну
    log_signal = get_log_signal()
    log_signal.message_emitted.connect(_on_log_message)

    window.log_message("● готов к загрузке", LOG_COLORS["INFO"])
    window.show()

    # Завершение по CTRL+C (SIGINT) - timer-based, т.к. на Windows
    # вызов Qt напрямую из сигнального обработчика небезопасен
    _exit_requested = False

    def _handle_sigint(signum: int, frame: object) -> None:  # noqa: ANN401
        nonlocal _exit_requested
        _exit_requested = True

    signal.signal(signal.SIGINT, _handle_sigint)

    # Таймер опрашивает флаг каждые 200 мс
    _exit_timer = QTimer()
    _exit_timer.timeout.connect(
        lambda: app.quit() if _exit_requested else None
    )
    _exit_timer.start(200)

    sys.exit(app.exec())


def _on_log_message(level: str, text: str) -> None:
    """Обработчик сигнала лога - обновляет GUI в главном потоке."""
    color = LOG_COLORS.get(level, "#CCCCCC")

    # Ищем активное окно для обновления
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, MainWindow):
            widget.log_message(text, color)
            break
    else:
        # Если окна ещe нет - пишем в консоль
        sys.stderr.write(f"[{level}] {text}\n")


if __name__ == "__main__":
    main()
