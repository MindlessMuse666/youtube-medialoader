"""Модульные тесты для formatters.py (форматирование величин).

Чистые функции без Qt - только математика и строки.
"""

from __future__ import annotations

from src.utils.formatters import (
    format_duration,
    format_eta,
    format_filesize,
    format_speed,
)


class TestFormatDuration:
    """Длительность в ``ЧЧ:ММ:СС`` / ``ММ:СС``."""

    def test_seconds_only(self) -> None:
        assert format_duration(0) == "0:00"
        assert format_duration(59) == "0:59"
        assert format_duration(60) == "1:00"
        assert format_duration(3599) == "59:59"

    def test_with_hours(self) -> None:
        assert format_duration(3600) == "1:00:00"
        assert format_duration(3661) == "1:01:01"

    def test_negative_clamped(self) -> None:
        assert format_duration(-5) == "0:00"


class TestFormatFilesize:
    """Размер файла в Б/КБ/МБ/ГБ."""

    def test_bytes(self) -> None:
        assert format_filesize(0) == "0 Б"
        assert format_filesize(1023) == "1023 Б"

    def test_kilobytes(self) -> None:
        assert format_filesize(1024) == "1.0 КБ"
        assert format_filesize(2 * 1024) == "2.0 КБ"

    def test_megabytes(self) -> None:
        assert format_filesize(1024**2) == "1.0 МБ"

    def test_gigabytes(self) -> None:
        assert format_filesize(1024**3) == "1.00 ГБ"


class TestFormatSpeed:
    """Скорость в B/s / KB/s / MB/s."""

    def test_zero_returns_empty(self) -> None:
        assert format_speed(0) == ""
        assert format_speed(None) == ""

    def test_bytes_per_sec(self) -> None:
        assert format_speed(500) == "500 B/s"

    def test_kilobytes_per_sec(self) -> None:
        assert format_speed(5 * 1024) == "5 KB/s"

    def test_megabytes_per_sec(self) -> None:
        assert format_speed(1_500_000) == "1.5 MB/s"


class TestFormatEta:
    """Остаток времени - пусто при нуле, иначе длительность."""

    def test_zero_returns_empty(self) -> None:
        assert format_eta(0) == ""
        assert format_eta(None) == ""

    def test_positive(self) -> None:
        assert format_eta(90) == "1:30"
        assert format_eta(3661) == "1:01:01"
