"""Модульные тесты для update_checker.py (проверка обновлений).

GitHub API мокается - реальных сетевых запросов нет. Основной фокус -
корректное сравнение версий с суффиксами в тегах (``v2.4-stable``).
"""

from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtNetwork import QNetworkReply

from src.utils.update_checker import UpdateChecker


class TestIsNewerVersion:
    """Сравнение версий, устойчивое к суффиксам тегов."""

    def test_newer_major(self, qapp) -> None:
        assert UpdateChecker("2.3.0")._is_newer_version("v3.0-stable")

    def test_newer_minor(self, qapp) -> None:
        """Баг-фикс: ``v2.4-stable`` больше ``2.3.0`` (раньше падало)."""
        assert UpdateChecker("2.3.0")._is_newer_version("v2.4-stable")

    def test_same_minor_is_not_newer(self, qapp) -> None:
        assert not UpdateChecker("2.3.0")._is_newer_version("v2.3-stable")

    def test_older(self, qapp) -> None:
        assert not UpdateChecker("2.3.0")._is_newer_version("v1.9-stable")

    def test_equal_plain_version(self, qapp) -> None:
        assert not UpdateChecker("2.3.0")._is_newer_version("2.3.0")

    def test_patch_upgrade_detected(self, qapp) -> None:
        assert UpdateChecker("2.3.0")._is_newer_version("2.3.1")

    def test_garbage_tag(self, qapp) -> None:
        assert not UpdateChecker("2.3.0")._is_newer_version("totally-not-a-version")

    def test_empty_tag(self, qapp) -> None:
        assert not UpdateChecker("2.3.0")._is_newer_version("")


class TestExtractNumericVersion:
    """Выделение числовой части из тега/версии."""

    def test_suffixed_tag(self, qapp) -> None:
        assert UpdateChecker._extract_numeric_version("v2.4-stable") == "2.4"

    def test_plain_version(self, qapp) -> None:
        assert UpdateChecker._extract_numeric_version("2.3.0") == "2.3.0"

    def test_no_number(self, qapp) -> None:
        assert UpdateChecker._extract_numeric_version("stable") == ""

    def test_none_input(self, qapp) -> None:
        assert UpdateChecker._extract_numeric_version(None) == ""


class TestOnReplyFinished:
    """Обработка ответа GitHub API."""

    def test_valid_json(self, qapp) -> None:
        checker = UpdateChecker("2.3.0")
        reply = MagicMock()
        reply.error.return_value = QNetworkReply.NetworkError.NoError
        reply.readAll.return_value = b'{"tag_name": "v2.4-stable"}'
        checker._reply = reply

        results: list[tuple[str, bool]] = []
        checker.on_result = lambda tag, newer: results.append((tag, newer))
        checker._on_reply_finished()

        assert results == [("v2.4-stable", True)]

    def test_network_error(self, qapp) -> None:
        checker = UpdateChecker("2.3.0")
        reply = MagicMock()
        reply.error.return_value = QNetworkReply.NetworkError.ConnectionRefusedError
        checker._reply = reply

        results: list[tuple[str, bool]] = []
        checker.on_result = lambda tag, newer: results.append((tag, newer))
        checker._on_reply_finished()

        assert results == [("", False)]

    def test_invalid_json(self, qapp) -> None:
        checker = UpdateChecker("2.3.0")
        reply = MagicMock()
        reply.error.return_value = QNetworkReply.NetworkError.NoError
        reply.readAll.return_value = b"not-json {"
        checker._reply = reply

        results: list[tuple[str, bool]] = []
        checker.on_result = lambda tag, newer: results.append((tag, newer))
        checker._on_reply_finished()

        assert results == [("", False)]
