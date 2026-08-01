"""Форматирование величин для отображения в GUI.

Чистые функции без Qt-зависимостей: длительность, размер файла, скорость
и ETA в человекочитаемых единицах. Раньше эта логика дублировалась в
``main_window.py`` (методы ``_format_duration``/``_format_filesize`` и inline
блоки в ``_on_download_progress``) и в ``playlist_dialog.py``.
"""

from __future__ import annotations


def format_duration(seconds: int) -> str:
    """Преобразовать секунды в ``ЧЧ:ММ:СС`` (если есть часы) или ``ММ:СС``.

    Args:
        seconds: Длительность в секундах.

    Returns:
        Отформатированная строка длительности.
    """
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_filesize(size_bytes: int) -> str:
    """Преобразовать байты в читаемый размер (Б, КБ, МБ, ГБ).

    Args:
        size_bytes: Размер в байтах.

    Returns:
        Отформатированная строка размера.
    """
    if size_bytes < 1024:
        return f"{size_bytes} Б"
    if size_bytes < 1024**2:
        return f"{size_bytes / 1024:.1f} КБ"
    if size_bytes < 1024**3:
        return f"{size_bytes / 1024**2:.1f} МБ"
    return f"{size_bytes / 1024**3:.2f} ГБ"


def format_speed(bytes_per_sec: float | int) -> str:
    """Преобразовать скорость загрузки в ``MB/s`` / ``KB/s`` / ``B/s``.

    Args:
        bytes_per_sec: Скорость в байтах в секунду (0 и ``None`` -> ``""``).

    Returns:
        Отформатированная строка скорости или пустая строка при нуле.
    """
    speed = float(bytes_per_sec or 0)
    if speed <= 0:
        return ""
    if speed > 1_000_000:
        return f"{speed / 1_000_000:.1f} MB/s"
    if speed > 1_000:
        return f"{speed / 1_000:.0f} KB/s"
    return f"{speed:.0f} B/s"


def format_eta(seconds: float | int) -> str:
    """Преобразовать ETA в ``ЧЧ:ММ:СС`` или ``ММ:СС``.

    Args:
        seconds: Остаток времени в секундах (0 и ``None`` -> ``""``).

    Returns:
        Отформатированная строка ETA или пустая строка при нуле.
    """
    eta = int(seconds or 0)
    if eta <= 0:
        return ""
    return format_duration(eta)
