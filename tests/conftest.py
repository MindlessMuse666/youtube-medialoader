"""Фикстуры и настройки pytest для проекта YouTube Medialoader.

Автоматически добавляет корневую директорию проекта в `sys.path`,
чтобы импорты вида `from src.downloader import ...` работали из любой
текущей рабочей директории (не только из корня проекта).
"""

import sys
from pathlib import Path


# Добавляем корень проекта в путь поиска модулей
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
