"""Модульные тесты для класса YouTubeDownloader.

Используются моки `yt-dlp` - никаких сетевых запросов не выполняется.
"""

import threading
from unittest.mock import MagicMock, patch

import pytest
from yt_dlp.utils import DownloadError

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


# ---------------------------------------------------------------------------
# YouTubeDownloader._resolve_out_name
# ---------------------------------------------------------------------------


class TestResolveOutName:
    """outtmpl не должен давать двойное расширение (баг ".mp3.mp3")."""

    def test_mp3_omits_extension(self, downloader: YouTubeDownloader) -> None:
        """Для mp3 в шаблоне вывода расширение не указывается."""
        assert downloader._resolve_out_name("My Song", "mp3") == "My Song"
        assert downloader._resolve_out_name("My Song.mp3", "mp3") == "My Song"

    def test_mp4_keeps_extension(self, downloader: YouTubeDownloader) -> None:
        """Для mp4 имя в шаблоне фиксируется с расширением .mp4."""
        assert downloader._resolve_out_name("My Video", "mp4") == "My Video.mp4"
        assert downloader._resolve_out_name("My Video.mp4", "mp4") == "My Video.mp4"

    def test_mp4_replaces_foreign_extension(
        self, downloader: YouTubeDownloader
    ) -> None:
        """Чужое расширение заменяется на .mp4 (совпадает с merge_format)."""
        assert downloader._resolve_out_name("My Video.mkv", "mp4") == "My Video.mp4"

    def test_sanitizes_invalid_chars(self, downloader: YouTubeDownloader) -> None:
        """Недопустимые символы очищаются до построения шаблона."""
        assert downloader._resolve_out_name('A:B"C?', "mp3") == "A_B_C_"


# ---------------------------------------------------------------------------
# Удаление .part-файлов после отмены (баг 1)
# ---------------------------------------------------------------------------


class TestPartialCleanup:
    """Частично скачанные файлы удаляются после отмены, готовые - сохраняются."""

    def test_removes_part_and_merge_intermediates(self, tmp_path) -> None:
        """Удаляются .part-файлы и промежуточные файлы слияния."""
        target = tmp_path / "video.mp4"
        part = tmp_path / "video.mp4.part"
        intermediate = tmp_path / "video.mp4.f137.mp4"
        part.write_bytes(b"partial")
        intermediate.write_bytes(b"stream")
        completed = tmp_path / "video.mp4"
        completed.write_bytes(b"done")

        YouTubeDownloader._cleanup_partial_files(str(target))

        assert not part.exists()
        assert not intermediate.exists()
        assert completed.exists()

    def test_mp3_removes_stream_part_keeps_final(self, tmp_path) -> None:
        """Для mp3 удаляется <имя>.m4a.part, а готовый <имя>.mp3 сохраняется."""
        target = tmp_path / "My Song"
        part = tmp_path / "My Song.m4a.part"
        part.write_bytes(b"partial")
        final = tmp_path / "My Song.mp3"
        final.write_bytes(b"done")

        YouTubeDownloader._cleanup_partial_files(str(target))

        assert not part.exists()
        assert final.exists()

    def test_unrelated_files_untouched(self, tmp_path) -> None:
        """Файлы, не связанные с шаблоном вывода, не удаляются."""
        target = tmp_path / "video.mp4"
        other = tmp_path / "other.mp4.part"
        other.write_bytes(b"partial")

        YouTubeDownloader._cleanup_partial_files(str(target))

        assert other.exists()

    @patch("yt_dlp.YoutubeDL")
    def test_cancel_removes_part_file_and_raises(
        self, mock_ydl_cls: MagicMock, downloader: YouTubeDownloader, tmp_path
    ) -> None:
        """При отмене .part-файл удаляется, а DownloadError пробрасывается."""
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        mock_ydl.download.side_effect = DownloadError("Отменено пользователем")

        cancel = threading.Event()
        cancel.set()
        part = tmp_path / "video.mp4.part"
        part.write_bytes(b"partial")

        with pytest.raises(DownloadError):
            downloader.download(
                url="https://youtube.com/watch?v=test",
                output_path=str(tmp_path),
                filename="video.mp4",
                cancel_event=cancel,
            )

        assert not part.exists()


# ---------------------------------------------------------------------------
# Cookie-фоллбек (повтор без кук при ошибке)
# ---------------------------------------------------------------------------


class TestCookieFallback:
    """При ошибке запроса с куками попытка повторяется без них."""

    @patch("yt_dlp.YoutubeDL")
    def test_get_video_info_retries_without_cookies(
        self, mock_ydl_cls: MagicMock, sample_info: dict
    ) -> None:
        """Первая попытка с куками падает -> повтор без опций кук."""
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.side_effect = [
            DownloadError("Blocked by YouTube"),
            sample_info,
        ]

        downloader = YouTubeDownloader(cookies_from_browser=("chrome",))
        result = downloader.get_video_info("https://youtube.com/watch?v=test")

        assert result["title"] == "Test Video"
        first_opts = mock_ydl_cls.call_args_list[0][0][0]
        second_opts = mock_ydl_cls.call_args_list[1][0][0]
        assert "cookiesfrombrowser" in first_opts
        assert "cookiesfrombrowser" not in second_opts

    @patch("yt_dlp.YoutubeDL")
    def test_get_video_info_raises_when_no_cookies(
        self, mock_ydl_cls: MagicMock
    ) -> None:
        """Без кук ошибка пробрасывается сразу, без повторной попытки."""
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.side_effect = DownloadError("Blocked")

        downloader = YouTubeDownloader()
        with pytest.raises(DownloadError):
            downloader.get_video_info("https://youtube.com/watch?v=test")

        assert mock_ydl_cls.call_count == 1

    @patch("yt_dlp.YoutubeDL")
    def test_download_retries_without_cookies(
        self, mock_ydl_cls: MagicMock
    ) -> None:
        """Загрузка с куками, упавшая, повторяется без них."""
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        mock_ydl.download.side_effect = [DownloadError("Blocked"), None]

        downloader = YouTubeDownloader(cookies_from_browser=("chrome",))
        downloader.download(
            url="https://youtube.com/watch?v=test",
            output_path="/tmp",
            filename="video.mp4",
        )

        assert mock_ydl.download.call_count == 2
        first_opts = mock_ydl_cls.call_args_list[0][0][0]
        second_opts = mock_ydl_cls.call_args_list[1][0][0]
        assert "cookiesfrombrowser" in first_opts
        assert "cookiesfrombrowser" not in second_opts


class TestResolveCookies:
    """Приоритет явных аргументов над значениями конструктора."""

    def test_explicit_args_override_constructor(self) -> None:
        downloader = YouTubeDownloader(cookies_from_browser=("chrome",))
        browsers, file = downloader._resolve_cookies(("firefox",), "/tmp/c.txt")
        assert browsers == ("firefox",)
        assert file == "/tmp/c.txt"

    def test_none_args_fall_back_to_constructor(self) -> None:
        downloader = YouTubeDownloader(
            cookies_from_browser=("chrome",), cookies_file="/x.txt"
        )
        browsers, file = downloader._resolve_cookies(None, None)
        assert browsers == ("chrome",)
        assert file == "/x.txt"

    def test_remove_cookie_opts(self) -> None:
        opts = {"cookiesfrombrowser": ("chrome",), "cookiefile": "/c.txt", "quiet": True}
        YouTubeDownloader._remove_cookie_opts(opts)
        assert "cookiesfrombrowser" not in opts
        assert "cookiefile" not in opts
        assert opts["quiet"] is True


# ---------------------------------------------------------------------------
# YouTubeDownloader.get_playlist_info
# ---------------------------------------------------------------------------


class TestGetPlaylistInfo:
    """Получение списка видео из плейлиста."""

    @patch("yt_dlp.YoutubeDL")
    def test_returns_cleaned_entries(self, mock_ydl_cls: MagicMock) -> None:
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            "entries": [
                {
                    "title": "V1",
                    "url": "u1",
                    "duration": 10,
                    "thumbnail": "t1",
                    "playlist_index": 1,
                },
                None,  # пропускается
                {
                    "title": "V2",
                    "webpage_url": "u2",
                    "duration": 20,
                    "thumbnail": "t2",
                    "playlist_index": 2,
                },
            ]
        }

        downloader = YouTubeDownloader()
        result = downloader.get_playlist_info(
            "https://youtube.com/playlist?list=PL123"
        )

        assert len(result) == 2
        assert result[0]["title"] == "V1"
        assert result[0]["url"] == "u1"
        assert result[0]["index"] == 1
        # url берётся из webpage_url, когда нет короткого url
        assert result[1]["url"] == "u2"
        assert result[1]["index"] == 2

        opts = mock_ydl_cls.call_args[0][0]
        assert opts.get("extract_flat") is True

    @patch("yt_dlp.YoutubeDL")
    def test_empty_playlist(self, mock_ydl_cls: MagicMock) -> None:
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {}

        downloader = YouTubeDownloader()
        assert downloader.get_playlist_info("https://youtube.com/playlist?list=PL1") == []


# ---------------------------------------------------------------------------
# YouTubeDownloader._normalize_info
# ---------------------------------------------------------------------------


class TestNormalizeInfo:
    """Нормализация информации о видео (filesize и fallback)."""

    def test_filesize_from_requested_formats(self) -> None:
        info = {
            "title": "T",
            "duration": 10,
            "requested_formats": [
                {"filesize": 1_000},
                {"filesize": 2_000},
            ],
            "formats": [],
        }
        result = YouTubeDownloader._normalize_info(info)
        assert result["filesize"] == 3_000

    def test_filesize_fallback_to_max_format(self) -> None:
        info = {
            "requested_formats": [],
            "formats": [
                {"filesize": 500},
                {"filesize_approx": 9_000},
            ],
        }
        result = YouTubeDownloader._normalize_info(info)
        assert result["filesize"] == 9_000

    def test_filesize_none_when_no_sizes(self) -> None:
        result = YouTubeDownloader._normalize_info({"formats": []})
        assert result["filesize"] is None
