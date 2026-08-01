"""Утилиты для работы с файлами в YouTube Medialoader.

Содержит функции для очистки имeн файлов от недопустимых символов
и построения путей.
"""

import ctypes
import os
import re
import subprocess
import sys
from ctypes import wintypes
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


def _get_shell32() -> ctypes.CDLL | None:
    """Загрузить ``shell32.dll`` с настроенными сигнатурами Shell API.

    Явная настройка ``argtypes``/``restype`` обязательна для 64-битных
    сборок: без неё ctypes трактует указатели как 32-битные, и вызов
    ``SHOpenFolderAndSelectItems`` завершится ошибкой. Возвращает ``None``,
    если Shell API недоступен (не-Windows платформа или ошибка инициализации).
    """
    try:
        shell32 = ctypes.windll.shell32
        shell32.SHParseDisplayName.argtypes = [
            wintypes.LPCWSTR,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
            wintypes.ULONG,
            ctypes.POINTER(wintypes.ULONG),
        ]
        shell32.SHParseDisplayName.restype = wintypes.HRESULT
        shell32.SHOpenFolderAndSelectItems.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        shell32.SHOpenFolderAndSelectItems.restype = wintypes.HRESULT
        shell32.ILFree.argtypes = [ctypes.c_void_p]
        shell32.ILFree.restype = None
        return shell32
    except (OSError, AttributeError, ValueError):
        return None


def _parse_pidl(shell32: ctypes.CDLL, path: str) -> ctypes.c_void_p | None:
    """Разобрать *path* в PIDL (Item ID List) через ``SHParseDisplayName``.

    Возвращает ``None`` при любой ошибке (включая несуществующий путь).
    Успешный результат вызывающий обязан освободить через ``shell32.ILFree``.
    """
    pidl = ctypes.c_void_p()
    attrs = wintypes.ULONG()
    result = shell32.SHParseDisplayName(
        path, None, ctypes.byref(pidl), 0, ctypes.byref(attrs)
    )
    return pidl if result == 0 else None


def _free_pidl(shell32: ctypes.CDLL, pidl: ctypes.c_void_p) -> None:
    """Освободить PIDL, полученный через :func:`_parse_pidl`."""
    shell32.ILFree(pidl)


def _shell_select_file(directory: str, filename: str) -> bool:
    """Выделить файл в его папке через Windows Shell API.

    Более надёжная альтернатива ``explorer /select,``: корректно работает
    с именами, содержащими ``&``, ``—`` и CJK-символы, которые ломают
    парсинг аргументов командной строки ``explorer.exe``. Возвращает
    ``False`` при недоступности Shell API или ошибке - в этом случае
    вызывающий переходит на фолбэк через ``explorer.exe``.
    """
    shell32 = _get_shell32()
    if shell32 is None:
        return False
    pidl_folder = _parse_pidl(shell32, directory)
    if pidl_folder is None:
        return False
    pidl_file = _parse_pidl(shell32, os.path.join(directory, filename))
    if pidl_file is None:
        _free_pidl(shell32, pidl_folder)
        return False
    try:
        result = shell32.SHOpenFolderAndSelectItems(
            pidl_folder, 1, ctypes.byref(pidl_file), 0
        )
    except (OSError, ValueError):
        result = -1
    finally:
        _free_pidl(shell32, pidl_folder)
        _free_pidl(shell32, pidl_file)
    return result == 0


def _shell_open_folder(folder: str) -> bool:
    """Открыть *folder* в новом окне Explorer через Windows Shell API.

    Как и :func:`_shell_select_file`, устойчив к специальным символам в
    пути. Возвращает ``False`` при недоступности Shell API или ошибке.
    """
    shell32 = _get_shell32()
    if shell32 is None:
        return False
    pidl = _parse_pidl(shell32, folder)
    if pidl is None:
        return False
    try:
        result = shell32.SHOpenFolderAndSelectItems(pidl, 0, None, 0)
    except (OSError, ValueError):
        result = -1
    finally:
        _free_pidl(shell32, pidl)
    return result == 0


def _explorer_select(path: str) -> None:
    """Открыть новое окно Explorer с выделением файла (фолбэк)."""
    subprocess.Popen(["explorer", "/n,/select," + path])


def _explorer_open(folder: str) -> None:
    """Открыть папку в Explorer (фолбэк)."""
    subprocess.Popen(["explorer", folder])


def reveal_in_file_manager(path: str) -> bool:
    """Показать файл/папку в системном файловом менеджере (Windows).

    Если *path* - существующий файл, открывает Explorer с выделением этого
    файла. Если *path* - папка, открывает её; если файл отсутствует, но
    существует родительская папка - открывает её.

    Основной способ выделения - Windows Shell API (:func:`_shell_select_file`),
    который корректно обрабатывает имена со специальными символами
    (``&``, ``—``, CJK). Если Shell API недоступен, используется фолбэк
    ``explorer /n,/select,``.

    Флаг ``CREATE_NO_WINDOW`` намеренно **не** передаётся: с ним Explorer
    игнорирует аргументы командной строки и открывает папку по умолчанию
    (обычно "Документы"). Explorer - GUI-приложение, поэтому без флага
    отдельное консольное окно не появится.

    Args:
        path: Полный путь к файлу или папке.

    Returns:
        ``True`` если удалось открыть/выделить что-то, иначе ``False``.
    """
    if sys.platform != "win32":
        return False

    path = os.path.abspath(path)
    try:
        # Существующий файл - выделяем его
        if os.path.isfile(path):
            directory, filename = os.path.split(path)
            if not _shell_select_file(directory, filename):
                _explorer_select(path)
            return True
        # Папка (или родитель удалeнного файла) - открываем её
        target = path if os.path.isdir(path) else os.path.dirname(path)
        if target and os.path.isdir(target):
            if not _shell_open_folder(target):
                _explorer_open(target)
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
