"""Фикстуры и настройки pytest для проекта YouTube Medialoader.

Автоматически добавляет корневую директорию проекта в `sys.path`,
чтобы импорты вида `from src.downloader import ...` работали из любой
текущей рабочей директории (не только из корня проекта).
"""

import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication


# Добавляем корень проекта в путь поиска модулей
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """Сессионный экземпляр QApplication для тестов, работающих с виджетами.

    PySide6 требует, чтобы QApplication существовал до создания любых
    QWidget/QObject. Экземпляр создаётся один раз на весь прогон тестов.
    """
    app = QApplication.instance() or QApplication([])
    return app
