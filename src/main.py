"""Точка входа в приложение YouTube Medialoader.

Запускает QApplication, инициализирует логгер и показывает главное окно.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
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
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # type: ignore[arg-type]
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

    # Иконка приложения
    icon_path = _app_icon_path()
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Создаём главное окно
    window = MainWindow()

    # Подключаем логгер к окну
    log_signal = get_log_signal()
    log_signal.message_emitted.connect(_on_log_message)

    window.log_message("● готов к загрузке", LOG_COLORS["INFO"])
    window.show()

    sys.exit(app.exec())


def _on_log_message(level: str, text: str) -> None:
    """Обработчик сигнала лога — обновляет GUI в главном потоке.

    Заглушка: будет заменена на прямое обновление окна в Этапе 4.
    Пока просто печатает в stderr для отладки.
    """
    color = LOG_COLORS.get(level, "#CCCCCC")
    # pylint: disable=import-outside-toplevel
    from src.gui.main_window import MainWindow  # noqa: F811

    # Ищем активное окно для обновления (пока fallback на print)
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, MainWindow):
            widget.log_message(text, color)
            break
    else:
        # Если окна ещё нет — пишем в консоль
        import sys as _sys
        _sys.stderr.write(f"[{level}] {text}\n")  # noqa: NP100


if __name__ == "__main__":
    main()
