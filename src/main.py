"""Точка входа в приложение YouTube Medialoader.

Запускает QApplication, инициализирует логгер и показывает главное окно.
"""

from __future__ import annotations

import os
import signal
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from src.gui.main_window import MainWindow
from src.gui.widgets import Toast
from src.utils import constants
from src.utils.file_utils import assets_dir
from src.utils.logger import get_log_signal
from src.utils.theme import CYAN, GREEN, PINK, TEXT, YELLOW
from src.utils.update_checker import UpdateChecker

# Цветовые константы для логов - из единой палитры неоновой темы
LOG_COLORS = {
    "INFO": CYAN,
    "SUCCESS": GREEN,
    "WARNING": YELLOW,
    "ERROR": PINK,
}


def _app_icon_path() -> str:
    """Вернуть путь к иконке приложения (``.ico`` на Windows, ``.png`` иначе).

    Учитывает сборку PyInstaller (``sys._MEIPASS``).
    """
    icon_name = "app_icon.ico" if sys.platform == "win32" else "app_icon.png"
    return str(assets_dir() / "icons" / icon_name)


def main() -> None:
    """Запустить графическое приложение."""
    app = QApplication(sys.argv)
    app.setApplicationName(constants.APP_NAME)
    app.setApplicationVersion(constants.APP_VERSION)
    app.setOrganizationName(constants.ORG_NAME)

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

    window.log_message("😜 Готов к загрузке", LOG_COLORS["INFO"])
    window.show()

    # Асинхронная проверка обновлений
    _check_updates(window)

    # Завершение по CTRL+C (SIGINT) - timer-based, т.к. на Windows
    # вызов Qt напрямую из сигнального обработчика небезопасен
    _exit_requested = False

    def _handle_sigint(signum: int, frame: object) -> None:
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


def _check_updates(window: MainWindow) -> None:
    """Проверить наличие новых версий на GitHub (асинхронно).

    Если найдена новая версия, показывает уведомление в логе и через
    ``show_toast``.

    Args:
        window: Экземпляр главного окна.
    """
    current_ver = QApplication.applicationVersion()
    checker = UpdateChecker(current_ver)

    def _on_update_result(latest_tag: str, is_newer: bool) -> None:
        if is_newer and latest_tag:
            msg = f"🚀 Доступна новая версия: {latest_tag}"
            window.log_message(msg, LOG_COLORS["INFO"])
            window.show_toast(msg, Toast.INFO)
        elif not is_newer and latest_tag:
            window.log_message(
                f"✓ У вас актуальная версия ({current_ver})",
                LOG_COLORS["SUCCESS"],
            )

    checker.on_result = _on_update_result
    checker.check()


def _on_log_message(level: str, text: str) -> None:
    """Обработчик сигнала лога - обновляет GUI в главном потоке."""
    color = LOG_COLORS.get(level, TEXT)

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
