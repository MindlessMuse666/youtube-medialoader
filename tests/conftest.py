"""Фикстуры и настройки pytest для проекта YouTube Medialoader.

Автоматически добавляет корневую директорию проекта в `sys.path`,
чтобы импорты вида `from src.downloader import ...` работали из любой
текущей рабочей директории (не только из корня проекта).
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication, QSystemTrayIcon


# Добавляем корень проекта в путь поиска модулей
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from src.gui.main_window import MainWindow  # noqa: E402


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """Сессионный экземпляр QApplication для тестов, работающих с виджетами.

    PySide6 требует, чтобы QApplication существовал до создания любых
    QWidget/QObject. Экземпляр создаётся один раз на весь прогон тестов.
    """
    app = QApplication.instance() or QApplication([])
    return app


@pytest.fixture
def main_window(qapp) -> MainWindow:
    """MainWindow с изолированными настройками и без побочных эффектов.

    Патчи сохраняются на время теста: QSettings возвращает пустые настройки,
    трей и анимированный фон отключены, тосты заглушены, история - мок.
    """
    with (
        patch("src.gui.main_window.QSettings") as mock_settings,
        patch.object(QSystemTrayIcon, "isSystemTrayAvailable", return_value=False),
        patch("src.gui.main_window.AnimatedBackground"),
        patch.object(MainWindow, "show_toast"),
    ):
        settings = MagicMock()
        settings.value.return_value = None
        mock_settings.return_value = settings

        window = MainWindow()
        window._history_manager = MagicMock()  # не пишем в реальный файл истории
        yield window
        window.deleteLater()
        qapp.processEvents()
