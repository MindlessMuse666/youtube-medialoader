"""Модульные тесты для класса YouTubeDownloader.

Используются моки `yt-dlp` - никаких сетевых запросов не выполняется.
"""

import threading
from unittest.mock import MagicMock, patch

import pytest

from src.downloader import YouTubeDownloader


# ---------------------------------------------------------------------------
# Фикстуры
# ---------------------------------------------------------------------------


@pytest.fixture
def downloader() -> YouTubeDownloader:
    """Вернуть новый экземпляр YouTubeDownloader."""
    return YouTubeDownloader()


@pytest.fixture
def sample_info() -> dict:
    """Имитация возврата yt-dlp extract_info."""
    return {
        "title": "Test Video",
        "duration": 300,
        "formats": [
            {
                "format_id": "137",
                "ext": "mp4",
                "height": 1080,
                "width": 1920,
                "filesize": 50_000_000,
                "tbr": 2000,
                "acodec": "none",
                "vcodec": "avc1",
            },
            {
                "format_id": "136",
                "ext": "mp4",
                "height": 720,
                "width": 1280,
                "filesize": 20_000_000,
                "tbr": 1000,
                "acodec": "none",
                "vcodec": "avc1",
            },
            {
                "format_id": "140",
                "ext": "m4a",
                "height": None,
                "width": None,
                "filesize": 5_000_000,
                "tbr": 128,
                "acodec": "mp4a",
                "vcodec": "none",
            },
        ],
    }


# ---------------------------------------------------------------------------
# YouTubeDownloader.get_video_info
# ---------------------------------------------------------------------------


class TestGetVideoInfo:
    """Тесты для :meth:`YouTubeDownloader.get_video_info`."""

    @patch("yt_dlp.YoutubeDL")
    def test_returns_expected_keys(
        self, mock_ydl_cls: MagicMock, downloader: YouTubeDownloader, sample_info: dict
    ) -> None:
        """Возвращаемый словарь должен содержать title, duration, filesize, formats."""
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = sample_info

        result = downloader.get_video_info("https://youtube.com/watch?v=test")

        assert result["title"] == "Test Video"
        assert result["duration"] == 300
        assert isinstance(result["filesize"], int)
        assert isinstance(result["formats"], list)

    @patch("yt_dlp.YoutubeDL")
    def test_formats_are_cleaned(
        self, mock_ydl_cls: MagicMock, downloader: YouTubeDownloader, sample_info: dict
    ) -> None:
        """Возвращаемые форматы должны быть очищенным подмножеством."""
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = sample_info

        result = downloader.get_video_info("https://youtube.com/watch?v=test")

        for fmt in result["formats"]:
            assert "format_id" in fmt
            assert "ext" in fmt
            assert "height" in fmt
            assert "filesize" in fmt

    @patch("yt_dlp.YoutubeDL")
    def test_title_fallback(
        self, mock_ydl_cls: MagicMock, downloader: YouTubeDownloader
    ) -> None:
        """Должен вернуть 'Untitled' при отсутствии названия."""
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {}

        result = downloader.get_video_info("https://youtube.com/watch?v=test")
        assert result["title"] == "Untitled"


# ---------------------------------------------------------------------------
# YouTubeDownloader.download
# ---------------------------------------------------------------------------


class TestDownload:
    """Тесты для :meth:`YouTubeDownloader.download`."""

    @patch("yt_dlp.YoutubeDL")
    def test_video_download_called(
        self, mock_ydl_cls: MagicMock, downloader: YouTubeDownloader
    ) -> None:
        """Должен вызвать ydl.download для видео-формата."""
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl

        downloader.download(
            url="https://youtube.com/watch?v=test",
            output_path="/tmp",
            filename="video",
            format_type="mp4",
            quality="720p",
        )

        mock_ydl.download.assert_called_once_with(
            ["https://youtube.com/watch?v=test"]
        )

    @patch("yt_dlp.YoutubeDL")
    def test_audio_download_called(
        self, mock_ydl_cls: MagicMock, downloader: YouTubeDownloader
    ) -> None:
        """Должен вызвать ydl.download для аудио-формата."""
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl

        downloader.download(
            url="https://youtube.com/watch?v=test",
            output_path="/tmp",
            filename="audio",
            format_type="mp3",
        )

        mock_ydl.download.assert_called_once()

    @patch("yt_dlp.YoutubeDL")
    def test_progress_callback_invoked(
        self, mock_ydl_cls: MagicMock, downloader: YouTubeDownloader
    ) -> None:
        """Прогресс-колбэк должен вызываться во время загрузки."""
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl

        progress_data: list[dict] = []
        cb = progress_data.append

        downloader.download(
            url="https://youtube.com/watch?v=test",
            output_path="/tmp",
            filename="video",
            format_type="mp4",
            quality="720p",
            progress_callback=cb,
        )

        # Получаем список progress_hooks и вручную дергаем хук
        params: dict = mock_ydl_cls.call_args[0][0]  # первый позиционный аргумент
        hooks = params.get("progress_hooks", [])
        for hook in hooks:
            hook({"status": "downloading", "downloaded_bytes": 50, "total_bytes": 100})

        assert len(progress_data) > 0

    def test_cancellation_event_detected(self, downloader: YouTubeDownloader) -> None:
        """При установленном cancel_event _build_opts должен добавить хук."""
        cancel = threading.Event()
        cancel.set()
        downloader._cancel_event = cancel  # Имитируем то, что делает download()

        # _build_opts должен создать хуки
        opts = downloader._build_opts(
            format_type="mp4",
            quality="720p",
            outtmpl="/tmp/video.mp4",
        )

        # С cancel_event, но без progress_callback - нет progress_hooks,
        # но есть raw 'hook' для отмены без прогресса
        opts2 = downloader._build_opts(
            format_type="mp4",
            quality="720p",
            outtmpl="/tmp/video.mp4",
            progress_callback=lambda _: None,
        )

        assert "progress_hooks" in opts2
        assert "hook" in opts

    def test_invalid_format_raises(self, downloader: YouTubeDownloader) -> None:
        """Неподдерживаемый format_type должен вызвать ValueError."""
        with pytest.raises(ValueError, match="Неподдерживаемый format_type"):
            downloader.download(
                url="https://youtube.com/watch?v=test",
                output_path="/tmp",
                filename="video",
                format_type="avi",
            )

    def test_invalid_quality_raises(self, downloader: YouTubeDownloader) -> None:
        """Неподдерживаемое quality должен вызвать ValueError."""
        with pytest.raises(ValueError, match="Неподдерживаемое качество"):
            downloader.download(
                url="https://youtube.com/watch?v=test",
                output_path="/tmp",
                filename="video",
                format_type="mp4",
                quality="4k",
            )
