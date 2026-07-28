"""Модульные тесты для worker.py (QThread-задачи).

Используются моки - никаких реальных сетевых запросов не выполняется.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

from src.gui.worker import DownloadWorker, VideoInfoWorker


# ---------------------------------------------------------------------------
# VideoInfoWorker
# ---------------------------------------------------------------------------


class TestVideoInfoWorker:
    """Тесты для :class:`VideoInfoWorker`."""

    def test_info_fetched_on_success(self) -> None:
        """При успешном получении данных должен сработать сигнал info_fetched."""
        mock_info = {
            "title": "Test",
            "duration": 120,
            "filesize": 1_000_000,
            "formats": [],
        }

        with patch.object(
            VideoInfoWorker,
            "_downloader",
            create=True,
        ):
            worker = VideoInfoWorker("https://youtube.com/watch?v=test")

            # Мокаем downloader
            mock_dl = MagicMock()
            mock_dl.get_video_info.return_value = mock_info
            worker._downloader = mock_dl

            result: list[dict | None] = [None]

            def on_fetched(info: dict) -> None:
                result[0] = info

            worker.info_fetched.connect(on_fetched)  # type: ignore[arg-type]
            worker.run()

            assert result[0] is not None
            assert result[0]["title"] == "Test"
            assert result[0]["duration"] == 120

    def test_error_on_invalid_url(self) -> None:
        """При неверной ссылке должен сработать сигнал error_occurred."""
        worker = VideoInfoWorker("invalid-url")

        # Мокаем downloader, чтобы он кидал исключение
        mock_dl = MagicMock()
        mock_dl.get_video_info.side_effect = ValueError("Invalid URL")
        worker._downloader = mock_dl

        errors: list[str] = []

        def on_error(text: str) -> None:
            errors.append(text)

        worker.error_occurred.connect(on_error)  # type: ignore[arg-type]
        worker.run()

        assert len(errors) == 1
        assert "Invalid URL" in errors[0]

    def test_run_emits_info_fetched_signal(self) -> None:
        """Проверка, что run вызывает info_fetched через сигнал."""
        worker = VideoInfoWorker("https://youtube.com/watch?v=test")
        mock_dl = MagicMock()
        mock_dl.get_video_info.return_value = {"title": "Test"}
        worker._downloader = mock_dl

        signals: list[dict] = []
        worker.info_fetched.connect(signals.append)  # type: ignore[arg-type]
        worker.run()

        assert len(signals) == 1
        assert signals[0]["title"] == "Test"


# ---------------------------------------------------------------------------
# DownloadWorker
# ---------------------------------------------------------------------------


class TestDownloadWorker:
    """Тесты для :class:`DownloadWorker`."""

    def test_download_success(self) -> None:
        """При успешной загрузке должен сработать сигнал finished."""
        worker = DownloadWorker(
            url="https://youtube.com/watch?v=test",
            output_path="/tmp",
            filename="video.mp4",
            format_type="mp4",
            quality="720p",
        )

        mock_dl = MagicMock()
        worker._downloader = mock_dl

        finished = False

        def on_finished() -> None:
            nonlocal finished
            finished = True

        worker.finished.connect(on_finished)  # type: ignore[arg-type]
        worker.run()

        assert finished
        mock_dl.download.assert_called_once()

    def test_download_error(self) -> None:
        """При ошибке загрузки должен сработать сигнал error_occurred."""
        worker = DownloadWorker(
            url="https://youtube.com/watch?v=test",
            output_path="/tmp",
            filename="video.mp4",
        )

        mock_dl = MagicMock()
        mock_dl.download.side_effect = RuntimeError("Download failed")
        worker._downloader = mock_dl

        errors: list[str] = []

        def on_error(text: str) -> None:
            errors.append(text)

        worker.error_occurred.connect(on_error)  # type: ignore[arg-type]
        worker.run()

        assert len(errors) == 1
        assert "Download failed" in errors[0]

    def test_download_cancelled(self) -> None:
        """При отмене не должно быть сигналов finished или error."""
        worker = DownloadWorker(
            url="https://youtube.com/watch?v=test",
            output_path="/tmp",
            filename="video.mp4",
        )

        # Устанавливаем cancel_event ДО запуска
        worker.cancel_event.set()

        mock_dl = MagicMock()
        mock_dl.download.side_effect = RuntimeError("Download failed")
        worker._downloader = mock_dl

        finished: list[bool] = []
        errors: list[str] = []

        worker.finished.connect(lambda: finished.append(True))  # type: ignore[arg-type]
        worker.error_occurred.connect(errors.append)  # type: ignore[arg-type]

        # При отменeнном событии run должен выйти без выброса ошибки
        worker.run()

        assert len(finished) == 0
        assert len(errors) == 0

    def test_cancel_event_property(self) -> None:
        """Свойство cancel_event должно возвращать threading.Event."""
        worker = DownloadWorker(
            url="https://youtube.com/watch?v=test",
            output_path="/tmp",
            filename="video.mp4",
        )
        assert isinstance(worker.cancel_event, threading.Event)
        assert not worker.cancel_event.is_set()

    def test_progress_signal_emitted(self) -> None:
        """Прогресс-колбэк должен отправлять данные через сигнал."""
        worker = DownloadWorker(
            url="https://youtube.com/watch?v=test",
            output_path="/tmp",
            filename="video.mp4",
        )

        mock_dl = MagicMock()

        # Собираем переданный в download() progress_callback и вызываем его
        def download_side_effect(**kwargs: object) -> None:
            cb = kwargs.get("progress_callback")
            if callable(cb):
                cb({"status": "downloading", "downloaded_bytes": 50, "total_bytes": 100})

        mock_dl.download.side_effect = download_side_effect
        worker._downloader = mock_dl

        progress_data: list[dict] = []
        worker.progress.connect(progress_data.append)  # type: ignore[arg-type]
        worker.run()

        assert len(progress_data) > 0
        assert progress_data[0]["status"] == "downloading"
