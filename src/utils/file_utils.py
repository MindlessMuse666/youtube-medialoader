"""Утилиты для работы с файлами в YouTube Medialoader.

Содержит функции для очистки имeн файлов от недопустимых символов
и построения путей.
"""

import re
import os
import subprocess
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

    Пробелы и подчeркивания **сохраняются** - они допустимы в именах файлов
    и важны для читаемости оригинального названия. Заменяются только
    по-настоящему запрещeнные символы ``<>:"/\\|?*`` и управляющие.
    Результат обрезается до `max_length` символов (без учeта расширения).
    Если после очистки имя пустое, возвращает ``"untitled"``.

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

    # Удаляем управляющие символы
    stem = re.sub(r"[\x00-\x1f\x7f]", "", stem)

    # Схлопываем подряд идущие пробелы, обрезаем пробелы/точки по краям.
    # Подчeркивания по краям сохраняются (как и внутри) - они допустимы в именах.
    stem = re.sub(r" +", " ", stem).strip(" .")

    # Обрезаем до max_length
    if len(stem) > max_length:
        stem = stem[:max_length].rstrip("_. ")

    # Запасной вариант, если основа пустая или состоит только из подчeркиваний
    # (например, весь заголовок был недопустимым: "<>:|?" -> "____").
    if not stem or not stem.strip("_"):
        stem = "untitled"

    # Собираем обратно с расширением
    result = f"{stem}{suffix}" if suffix and not stem.endswith(suffix) else stem
    result = result.rstrip(". ")  # финальная зачистка точек по краям (Windows не терпит)
    return result or "untitled"


def resolve_filename(base_name: str, format_type: str) -> str:
    """Собрать имя выходного файла из названия и выбранного формата.

    Название очищается от недопустимых символов, затем к нему добавляется
    расширение, соответствующее *format_type*, если имя ещё не содержит
    подходящего расширения. Чужое медиа-расширение заменяется на целевое,
    а точки внутри имени (например, ``ft.初音ミク``) не теряются.

    Args:
        base_name: Название (заголовок видео или введённое пользователем имя).
        format_type: ``"mp4"`` или ``"mp3"``.

    Returns:
        Очищенное имя файла с корректным расширением.
    """
    safe = sanitize_filename(base_name)
    stem, suffix = _split_ext(safe)
    if suffix and suffix.lower() == f".{format_type}":
        return safe
    return f"{stem}.{format_type}"


def reveal_in_file_manager(path: str) -> bool:
    """Показать файл/папку в системном файловом менеджере (Windows).

    Если *path* - существующий файл, открывает Explorer с выделением этого
    файла. Используется ``explorer /n,/select,``: префикс ``/n`` заставляет
    Explorer открыть **новое** окно. Без него команда может лишь переключить
    уже открытое окно (часто показывающее другую папку), и пользователь
    увидит не ту директорию. Если *path* - папка, открывает её. Если файл
    отсутствует, но существует родительская папка - открывает её.

    Args:
        path: Полный путь к файлу или папке.

    Returns:
        ``True`` если удалось открыть/выделить что-то, иначе ``False``.
    """
    if sys.platform != "win32":
        return False

    path = os.path.abspath(path)
    try:
        # Существующий файл - выделяем его в новом окне Explorer
        if os.path.isfile(path):
            subprocess.Popen(
                ["explorer", "/n,/select," + path],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return True
        # Папка (или родитель удалeнного файла) - открываем её
        target = path if os.path.isdir(path) else os.path.dirname(path)
        if target and os.path.isdir(target):
            subprocess.Popen(
                ["explorer", target],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return True
    except OSError:
        pass
    return False


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
