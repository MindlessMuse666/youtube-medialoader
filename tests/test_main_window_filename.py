"""Тесты исправления "устаревшего имени файла" (баг 2).

Если после успешной обработки одного видео ввести новую ссылку и быстро
нажать "СКАЧАТЬ" (до того, как yt-dlp вернёт информацию), для нового видео
не должно подхватываться название предыдущего.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from src.gui.main_window import MainWindow

_OLD_URL = "https://youtube.com/watch?v=old"
_NEW_URL = "https://youtube.com/watch?v=new"


class _FakeInfoWorker:
    """Минимальный объект, имитирующий VideoInfoWorker для обработчиков."""

    def __init__(self, url: str, seq: int) -> None:
        self._url = url
        self._fetch_seq = seq


def _simulate_processed_video(main_window: MainWindow) -> None:
    """Состояние окна после успешной обработки первого видео."""
    main_window._current_video_title = "Старое видео"
    main_window._current_video_url = _OLD_URL
    main_window._is_custom_filename = False
    main_window.filename_input.setText("Старое видео")


class TestStaleFilename:
    """Смена ссылки не должна оставлять устаревшее имя файла."""

    def test_new_url_clears_auto_filled_name(self, main_window: MainWindow) -> None:
        """Ввод новой ссылки очищает автоподставленное имя предыдущего видео."""
        _simulate_processed_video(main_window)

        main_window.url_input.setText(_NEW_URL)

        assert main_window.filename_input.text() == ""
        assert main_window._current_video_title == ""

    def test_same_url_keeps_auto_filled_name(self, main_window: MainWindow) -> None:
        """Повторный ввод той же ссылки не очищает имя."""
        _simulate_processed_video(main_window)

        main_window.url_input.setText(_OLD_URL)

        assert main_window.filename_input.text() == "Старое видео"

    def test_custom_filename_preserved_on_new_url(self, main_window: MainWindow) -> None:
        """Имя, введённое пользователем вручную, сохраняется при смене ссылки."""
        _simulate_processed_video(main_window)
        main_window._is_custom_filename = True
        main_window.filename_input.setText("Моё имя")

        main_window.url_input.setText(_NEW_URL)

        assert main_window.filename_input.text() == "Моё имя"

    def test_quick_download_blocked_without_info(
        self, main_window: MainWindow
    ) -> None:
        """Быстрая загрузка новой ссылки без блока "ИНФОРМАЦИЯ" ничего не даёт.

        Кнопка "СКАЧАТЬ" скрыта, пока информация не получена: иначе для
        нового видео подхватилось бы старое имя или файл сохранился бы как
        ``untitled``.
        """
        _simulate_processed_video(main_window)
        main_window.path_input.setText("C:/Downloads")
        main_window.type_combo.setCurrentIndex(0)
        main_window._process_queue = MagicMock()

        main_window.url_input.setText(_NEW_URL)
        main_window._on_download_clicked()

        assert main_window._queue_widget.is_empty
        main_window._process_queue.assert_not_called()

    def test_fetch_restores_name_after_clear(self, main_window: MainWindow) -> None:
        """После получения информации для новой ссылки имя подставляется снова."""
        main_window._fetch_seq = 1
        main_window._info_worker = _FakeInfoWorker(_NEW_URL, seq=1)
        main_window._info_thread = None
        main_window._is_custom_filename = False
        main_window._complete_fetch = MagicMock()

        main_window._on_info_fetched(
            {"title": "Новое видео", "duration": 60, "filesize": 1000, "thumbnail": ""}
        )

        assert main_window.filename_input.text() == "Новое видео"
        assert main_window._current_video_url == _NEW_URL


class TestDownloadButtonGate:
    """Кнопка "СКАЧАТЬ" видна только после появления блока "ИНФОРМАЦИЯ"."""

    def test_button_hidden_before_info(self, main_window: MainWindow) -> None:
        """После ввода новой ссылки (без инфы) кнопка скрыта."""
        main_window.download_btn.setVisible(True)
        main_window.url_input.setText(_NEW_URL)

        assert main_window.download_btn.isHidden()

    def test_button_visible_after_info(self, main_window: MainWindow) -> None:
        """После получения информации кнопка появляется."""
        main_window.url_input.setText(_NEW_URL)
        main_window._fetch_seq = 1
        main_window._info_worker = _FakeInfoWorker(_NEW_URL, seq=1)
        main_window._info_thread = None
        main_window._is_custom_filename = False

        main_window._on_info_fetched(
            {"title": "Новое видео", "duration": 60, "filesize": 1000, "thumbnail": ""}
        )

        assert not main_window.download_btn.isHidden()

    def test_button_hidden_after_url_change(self, main_window: MainWindow) -> None:
        """Смена ссылки после инфы снова прячет кнопку."""
        main_window.url_input.setText(_OLD_URL)
        main_window._fetch_seq = 1
        main_window._info_worker = _FakeInfoWorker(_OLD_URL, seq=1)
        main_window._info_thread = None
        main_window._is_custom_filename = False
        main_window._on_info_fetched(
            {"title": "Старое видео", "duration": 60, "filesize": 1000, "thumbnail": ""}
        )
        assert not main_window.download_btn.isHidden()

        main_window.url_input.setText(_NEW_URL)

        assert main_window.download_btn.isHidden()

    def test_button_hidden_on_info_error(self, main_window: MainWindow) -> None:
        """Ошибка получения информации оставляет кнопку скрытой."""
        main_window.url_input.setText(_NEW_URL)
        main_window.download_btn.setVisible(True)
        main_window._fetch_seq = 1
        main_window._info_worker = _FakeInfoWorker(_NEW_URL, seq=1)
        main_window._info_thread = None

        main_window._on_info_error("плохая ссылка")

        assert main_window.download_btn.isHidden()

    def test_download_click_allowed_after_info(
        self, main_window: MainWindow
    ) -> None:
        """С информацией загрузка проходит, имя файла - из настоящего названия."""
        main_window.url_input.setText(_NEW_URL)
        main_window.path_input.setText("C:/Downloads")
        main_window.type_combo.setCurrentIndex(0)
        main_window._process_queue = MagicMock()
        main_window._fetch_seq = 1
        main_window._info_worker = _FakeInfoWorker(_NEW_URL, seq=1)
        main_window._info_thread = None
        main_window._is_custom_filename = False
        main_window._on_info_fetched(
            {"title": "Новое видео", "duration": 60, "filesize": 1000, "thumbnail": ""}
        )

        main_window._on_download_clicked()

        item = main_window._queue_widget._items[-1]
        assert item.filename == "Новое видео.mp4"
        assert "Старое видео" not in item.filename
