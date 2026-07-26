"""Утилиты для работы с файлами в YouTube Medialoader.

Содержит функции для очистки имён файлов от недопустимых символов
и построения путей.
"""

import re
import os
from pathlib import Path


def sanitize_filename(filename: str, max_length: int = 200) -> str:
    """Удалить или заменить символы, недопустимые в имени файла на текущей ОС.

    Вырезает символы, запрещённые в Windows/macOS/Linux, и обрезает результат
    до `max_length` символов (без учёта расширения).
    Если после очистки имя пустое, возвращает `"untitled"`.

    Args:
        filename: Исходное имя файла (может содержать расширение).
        max_length: Максимальная длина имени файла без расширения.

    Returns:
        Очищенное имя файла, безопасное для любой ОС.
    """
    # Отделяем расширение от основы
    name_parts = Path(filename)
    stem = name_parts.stem
    suffix = name_parts.suffix if len(name_parts.suffix) <= 10 else ""

    # Заменяем недопустимые символы на подчёркивание
    invalid_chars = r'[<>:"/\\|?*]'
    stem = re.sub(invalid_chars, "_", stem)

    # Удаляем управляющие символы и точки/пробелы по краям
    stem = re.sub(r"[\x00-\x1f\x7f]", "", stem)
    stem = stem.strip(". ")

    # Склеиваем повторяющиеся подчёркивания и пробелы
    stem = re.sub(r"[_ ]+", "_", stem).strip("_")

    # Обрезаем
    if len(stem) > max_length:
        stem = stem[:max_length].rstrip("_. ")

    # Запасной вариант, если основа пустая
    if not stem:
        stem = "untitled"

    # Собираем обратно с расширением
    result = f"{stem}{suffix}" if suffix and not stem.endswith(suffix) else stem
    result = result.rstrip(". ")  # финальная зачистка точек по краям (Windows не терпит)
    return result or "untitled"


def resolve_output_path(directory: str, filename: str) -> str:
    """Склеить директорию и имя файла в абсолютный путь сохранения.

    Args:
        directory: Путь к папке назначения.
        filename: Очищенное имя файла (рекомендуется предварительно
                  пропустить через :func:`sanitize_filename`).

    Returns:
        Абсолютный путь к файлу.
    """
    return os.path.abspath(os.path.join(directory, filename))
