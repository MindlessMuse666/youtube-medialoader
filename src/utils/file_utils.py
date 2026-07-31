"""Утилиты для работы с файлами в YouTube Medialoader.

Содержит функции для очистки имeн файлов от недопустимых символов
и построения путей.
"""

import re
import os
import sys
from pathlib import Path


# Известные медиа-расширения, которые нужно сохранять как расширение файла.
KNOWN_EXTENSIONS: frozenset[str] = frozenset({
    ".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv",
    ".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma", ".opus",
    ".jpg", ".jpeg", ".png", ".gif", ".webp",
})


def _split_ext(filename: str) -> tuple[str, str]:
    """Разделить имя файла на основу и расширение.

    Использует белый список известных расширений, чтобы случайно не
    отрезать часть имени, содержащую точку (например, ``ft.初音ミク``).

    Args:
        filename: Имя файла.

    Returns:
        Кортеж ``(stem, suffix)``.
    """
    lower = filename.lower()
    for ext in sorted(KNOWN_EXTENSIONS, key=len, reverse=True):
        if lower.endswith(ext):
            return filename[: -len(ext)], filename[-len(ext) :]
    # Ни одно известное расширение не найдено - вся строка это основа
    return filename, ""


def sanitize_filename(filename: str, max_length: int = 200) -> str:
    """Удалить или заменить символы, недопустимые в имени файла на текущей ОС.

    Вырезает символы, запрещeнные в Windows/macOS/Linux, и обрезает результат
    до `max_length` символов (без учeта расширения).
    Если после очистки имя пустое, возвращает `"untitled"`.

    Args:
        filename: Исходное имя файла (может содержать расширение).
        max_length: Максимальная длина имени файла без расширения.

    Returns:
        Очищенное имя файла, безопасное для любой ОС.
    """
    # Отделяем расширение от основы (только по известным расширениям)
    stem, suffix = _split_ext(filename)

    # Заменяем недопустимые символы на подчeркивание
    invalid_chars = r'[<>:"/\\|?*]'
    stem = re.sub(invalid_chars, "_", stem)

    # Удаляем управляющие символы и точки/пробелы по краям
    stem = re.sub(r"[\x00-\x1f\x7f]", "", stem)
    stem = stem.strip(". ")

    # Склеиваем повторяющиеся подчeркивания и пробелы
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


def assets_dir() -> Path:
    """Вернуть путь к каталогу ``assets``.

    В режиме разработки - ``<корень проекта>/assets``, в собранном
    PyInstaller-приложении - ``sys._MEIPASS/assets`` (ресурсы вшиты
    флагом ``--add-data "assets;assets"``).
    """
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        return Path(str(meipass)) / "assets" if meipass else Path("assets")
    return Path(__file__).resolve().parent.parent.parent / "assets"
