"""Модульные тесты для url_utils.py (валидация YouTube-ссылок).

Чистые функции без Qt и сети - только проверка строк URL.
"""

from __future__ import annotations

from src.utils.url_utils import is_playlist_url, is_youtube_url, validate_url

# Подопытное видео, используемое и в интеграционных тестах.
_YOUTU_BE_VIDEO = "https://youtu.be/KC-r-cmsBeo?si=RPAtQ8kNs2rHiG0u"


class TestIsYoutubeUrl:
    """Принадлежность домена к YouTube."""

    def test_youtube_com(self) -> None:
        assert is_youtube_url("https://www.youtube.com/watch?v=abc")

    def test_youtu_be(self) -> None:
        assert is_youtube_url("https://youtu.be/abc")

    def test_upper_case_host(self) -> None:
        assert is_youtube_url("https://YOUTU.BE/abc")

    def test_foreign_domain(self) -> None:
        assert not is_youtube_url("https://example.com/watch?v=abc")

    def test_empty(self) -> None:
        assert not is_youtube_url("")


class TestValidateUrl:
    """Корректность и тексты ошибок."""

    def test_valid_youtube_com(self) -> None:
        assert validate_url("https://www.youtube.com/watch?v=abc123") is None

    def test_valid_youtu_be(self) -> None:
        assert validate_url(_YOUTU_BE_VIDEO) is None

    def test_empty_url(self) -> None:
        assert validate_url("") == "Ссылка пуста"

    def test_no_scheme(self) -> None:
        assert validate_url("youtube.com/watch?v=abc") == (
            "Ссылка должна начинаться с http:// или https://"
        )

    def test_foreign_domain(self) -> None:
        assert validate_url("https://example.com/watch?v=abc") == (
            "Ссылка должна вести на youtube.com или youtu.be"
        )

    def test_duplicated_domain(self) -> None:
        assert validate_url(
            "https://youtube.com/watch?v=aahttps://youtube.com/watch?v=bb"
        ) == "Обнаружено дублирование домена в ссылке"

    def test_missing_v_param(self) -> None:
        assert validate_url("https://youtube.com/watch") == (
            "Не указан ID видео (параметр v=)"
        )

    def test_missing_youtu_be_path(self) -> None:
        assert validate_url("https://youtu.be/") == "Не указан ID видео"


class TestIsPlaylistUrl:
    """Определение плейлиста по параметру ``list=``."""

    def test_youtube_com_playlist(self) -> None:
        url = "https://www.youtube.com/watch?v=abc&list=PL123&index=1"
        assert is_playlist_url(url)

    def test_youtu_be_playlist(self) -> None:
        assert is_playlist_url("https://youtu.be/abc?list=PL123")

    def test_plain_video_not_playlist(self) -> None:
        assert not is_playlist_url("https://youtube.com/watch?v=abc")

    def test_test_video_not_playlist(self) -> None:
        assert not is_playlist_url(_YOUTU_BE_VIDEO)

    def test_foreign_domain_not_playlist(self) -> None:
        assert not is_playlist_url("https://example.com/?list=PL123")
