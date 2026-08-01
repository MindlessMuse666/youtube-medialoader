"""Интеграционные тесты с реальной сетью (opt-in).

Запускаются только с переменной окружения ``YML_INTEGRATION=1``.
Для Windows PowerShell::

    $env:YML_INTEGRATION = "1"; pytest tests/test_integration.py -v
    Remove-Item Env:YML_INTEGRATION

Иначе помечаются skip, чтобы обычный прогон оставался полностью без сети.
"""

from __future__ import annotations

import os

import pytest

from src.downloader import YouTubeDownloader

# "Подопытное" видео для проверки реального получения метаданных.
_TEST_VIDEO_URL = "https://youtu.be/KC-r-cmsBeo?si=RPAtQ8kNs2rHiG0u"

pytestmark = pytest.mark.integration


def _integration_enabled() -> bool:
    """Сетевой режим включается только явной переменной окружения."""
    return os.environ.get("YML_INTEGRATION") == "1"


@pytest.mark.skipif(
    not _integration_enabled(),
    reason="Сетевой тест: задайте YML_INTEGRATION=1 для запуска",
)
def test_get_video_info_network() -> None:
    """Реальное получение метаданных подопытного видео."""
    downloader = YouTubeDownloader()
    info = downloader.get_video_info(_TEST_VIDEO_URL)

    assert info["title"]
    assert info["duration"] > 0
    assert isinstance(info["filesize"], (int, type(None)))
    assert isinstance(info["formats"], list)
