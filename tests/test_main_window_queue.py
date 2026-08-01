"""Тесты жизненного цикла очереди и потоков загрузки (main_window.py).

Покрывают исправление бага ``QThread: Destroyed while thread '' is still
running``: уборка завершившегося потока не должна задевать уже запущенный
следующий, а устаревшие сигналы старого worker'а должны игнорироваться.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QSystemTrayIcon

from src.gui.download_queue import QueueItem, QueueItemStatus
from src.gui.main_window import MainWindow


class FakeWorker(QObject):
    """Минимальный QObject, имитирующий DownloadWorker для тестов сигналов."""

    progress = Signal(dict)
    finished = Signal()
    error_occurred = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.cancel_event = threading.Event()


def make_item(**overrides: object) -> QueueItem:
    """Хелпер: создать элемент очереди с дефолтными полями."""
    data: dict[str, object] = {
        "url": "https://youtube.com/watch?v=test",
        "output_path": "/tmp",
        "filename": "video.mp4",
        "format_type": "mp4",
        "quality": "720p",
        "title": "Test Video",
    }
    data.update(overrides)
    return QueueItem(**data)  # type: ignore[arg-type]


@pytest.fixture
def main_window(qapp) -> MainWindow:
    """MainWindow с изолированными настройками и без побочных эффектов.

    Патчи сохраняются на время теста: QSettings возвращает пустые настройки,
    трей и анимированный фон отключены, тосты заглушены, история - мок.
    """
    with (
        patch("src.gui.main_window.QSettings") as mock_settings,
        patch.object(QSystemTrayIcon, "isSystemTrayAvailable", return_value=False),
        patch("src.gui.main_window.AnimatedBackground"),
        patch.object(MainWindow, "show_toast"),
    ):
        settings = MagicMock()
        settings.value.return_value = None
        mock_settings.return_value = settings

        window = MainWindow()
        window._history_manager = MagicMock()  # не пишем в реальный файл истории
        yield window
        window.deleteLater()
        qapp.processEvents()


class TestCleanupDownload:
    """_cleanup_download должен прибирать только завершившийся поток."""

    def test_stale_cleanup_does_not_touch_current(self, main_window: MainWindow) -> None:
        """Уборка старого потока не задевает уже запущенную новую загрузку."""
        old_thread = QThread(main_window)
        old_worker = FakeWorker()
        current_thread = QThread(main_window)
        current_worker = FakeWorker()

        main_window._download_thread = current_thread
        main_window._download_worker = current_worker

        # finished-сигнал старого потока, дошедший после старта нового
        main_window._cleanup_download(old_thread, old_worker)

        assert main_window._download_thread is current_thread
        assert main_window._download_worker is current_worker

    def test_cleanup_current_thread_nulls_refs(self, main_window: MainWindow) -> None:
        """Уборка текущего завершившегося потока освобождает ссылки."""
        thread = QThread(main_window)
        worker = FakeWorker()
        main_window._download_thread = thread
        main_window._download_worker = worker

        main_window._cleanup_download(thread, worker)

        assert main_window._download_thread is None
        assert main_window._download_worker is None


class TestStaleSignalsIgnored:
    """Сигналы старого worker'а не должны влиять на текущую загрузку."""

    def test_stale_finished_ignored(self, main_window: MainWindow) -> None:
        current = FakeWorker()
        stale = FakeWorker()
        main_window._download_worker = current
        main_window._download_thread = None

        stale.finished.connect(main_window._on_download_finished)
        stale.finished.emit()

        # Текущий worker не обнулён и не задет
        assert main_window._download_worker is current

    def test_stale_error_ignored(self, main_window: MainWindow) -> None:
        current = FakeWorker()
        stale = FakeWorker()
        main_window._download_worker = current
        main_window._download_thread = None

        stale.error_occurred.connect(main_window._on_download_error)
        stale.error_occurred.emit("boom")

        assert main_window._download_worker is current

    def test_stale_progress_ignored(self, main_window: MainWindow) -> None:
        current = FakeWorker()
        stale = FakeWorker()
        main_window._download_worker = current
        main_window._download_thread = None

        stale.progress.connect(main_window._on_download_progress)
        stale.progress.emit({"status": "downloading", "downloaded_bytes": 1})

        assert main_window._download_worker is current

    def test_current_finished_marks_item_completed(
        self, main_window: MainWindow
    ) -> None:
        """Сигнал текущего worker'а обрабатывается: элемент помечается готовым."""
        main_window._process_queue = MagicMock()
        item = make_item()
        main_window._queue_widget.add_item(item)
        main_window._current_queue_item = item
        worker = FakeWorker()
        main_window._download_worker = worker
        main_window._download_thread = None
        main_window._last_download_path = ""

        worker.finished.connect(main_window._on_download_finished)
        worker.finished.emit()

        assert item.status is QueueItemStatus.COMPLETED
        assert main_window._download_worker is None
        assert main_window._download_thread is None
        main_window._process_queue.assert_called_once()

    def test_current_error_marks_item_error(self, main_window: MainWindow) -> None:
        """Сигнал ошибки текущего worker'а помечает элемент как ошибочный."""
        main_window._process_queue = MagicMock()
        item = make_item()
        main_window._queue_widget.add_item(item)
        main_window._current_queue_item = item
        worker = FakeWorker()
        main_window._download_worker = worker
        main_window._download_thread = None

        worker.error_occurred.connect(main_window._on_download_error)
        worker.error_occurred.emit("boom")

        assert item.status is QueueItemStatus.ERROR
        assert item.error_text == "boom"
        assert main_window._download_worker is None
        main_window._process_queue.assert_called_once()


class TestCancelHandling:
    """Отмена загрузки корректно помечает элемент очереди."""

    def test_cancel_marks_item_cancelled(self, main_window: MainWindow) -> None:
        item = make_item()
        main_window._queue_widget.add_item(item)
        main_window._current_queue_item = item
        main_window._download_worker = FakeWorker()
        main_window._download_thread = None

        main_window._on_cancel_clicked()

        assert item.status is QueueItemStatus.CANCELLED
        assert main_window._current_queue_item is None
        assert main_window._download_worker is None

    def test_cancel_starts_next_pending(self, main_window: MainWindow) -> None:
        item = make_item()
        main_window._queue_widget.add_item(item)
        main_window._current_queue_item = item
        main_window._download_worker = FakeWorker()
        main_window._download_thread = None
        main_window._process_queue = MagicMock()

        main_window._on_cancel_clicked()

        main_window._process_queue.assert_called_once()

    def test_cancel_without_active_download_is_noop(self, main_window: MainWindow) -> None:
        main_window._download_worker = None
        main_window._download_thread = None
        # Не должно падать
        main_window._on_cancel_clicked()


class TestProcessQueueGuard:
    """_process_queue не должен запускать параллельную загрузку."""

    def test_process_queue_skips_when_download_active(
        self, main_window: MainWindow
    ) -> None:
        active_thread = QThread(main_window)
        main_window._download_thread = active_thread
        main_window._queue_widget.add_item(make_item())

        main_window._process_queue()

        assert main_window._download_thread is active_thread
        assert main_window._download_worker is None


class TestProgressResetOnNewDownload:
    """Прогресс-бар сбрасывается к 0 при указании следующей ссылки."""

    def test_url_entry_resets_progress_bar(self, main_window: MainWindow) -> None:
        """Ввод новой ссылки после завершeнной загрузки сбрасывает бар к 0."""
        main_window.progress_bar.setValue(100)
        main_window.progress_bar._completed = True
        main_window._download_thread = None

        main_window._on_url_changed("https://youtube.com/watch?v=second")

        assert main_window.progress_bar.value() == 0
        assert main_window.progress_bar._completed is False

    def test_second_download_starts_with_reset_bar(
        self, main_window: MainWindow
    ) -> None:
        """Старт второй загрузки сбрасывает прогресс-бар к 0."""
        main_window.progress_bar.setValue(100)
        main_window.progress_bar._completed = True

        with (
            patch("src.gui.main_window.QThread") as mock_thread_cls,
            patch("src.gui.main_window.DownloadWorker") as mock_worker_cls,
        ):
            mock_thread_cls.return_value = MagicMock()
            mock_worker_cls.return_value = MagicMock()
            main_window._queue_widget.add_item(make_item())
            main_window._download_thread = None

            main_window._process_queue()

        assert main_window.progress_bar.value() == 0
        assert main_window.progress_bar._completed is False


class TestDownloadButtonVisibility:
    """Кнопка «СКАЧАТЬ» скрывается на время активной загрузки."""

    def test_download_btn_hidden_during_download(
        self, main_window: MainWindow
    ) -> None:
        with (
            patch("src.gui.main_window.QThread") as mock_thread_cls,
            patch("src.gui.main_window.DownloadWorker") as mock_worker_cls,
        ):
            mock_thread_cls.return_value = MagicMock()
            mock_worker_cls.return_value = MagicMock()
            main_window._queue_widget.add_item(make_item())
            main_window._download_thread = None

            main_window._process_queue()

        assert main_window.download_btn.isHidden()
        assert main_window.download_btn.isEnabled()  # скрыт, а не заблокирован
        assert not main_window.cancel_btn.isHidden()

    def test_download_btn_shown_when_queue_empty(self, main_window: MainWindow) -> None:
        main_window.download_btn.setVisible(False)  # как будто шла загрузка
        main_window._process_queue()
        assert not main_window.download_btn.isHidden()


class TestOpenFolderButtonReset:
    """Кнопка «ОТКРЫТЬ ПАПКУ» должна скрываться при вводе новой ссылки."""

    def test_url_entry_hides_open_folder_button(
        self, main_window: MainWindow
    ) -> None:
        """Ввод новой ссылки после загрузки прячет кнопку открытия папки."""
        main_window.open_folder_btn.setVisible(True)
        main_window._download_thread = None

        main_window._on_url_changed("https://youtube.com/watch?v=second")

        assert main_window.open_folder_btn.isHidden()

    def test_url_entry_with_active_download_keeps_button(
        self, main_window: MainWindow
    ) -> None:
        """Во время активной загрузки ввод ссылки не трогает кнопку."""
        main_window.open_folder_btn.setVisible(True)
        main_window._download_thread = QThread(main_window)

        main_window._on_url_changed("https://youtube.com/watch?v=second")

        assert not main_window.open_folder_btn.isHidden()


class TestTrayMessageOpen:
    """Клик по системному уведомлению открывает скачанный файл."""

    def test_tray_click_reveals_notified_file(
        self, main_window: MainWindow, tmp_path
    ) -> None:
        target = tmp_path / "video.mp4"
        target.write_bytes(b"data")
        main_window._notify_path = str(target)

        with patch("src.gui.main_window.reveal_in_file_manager") as mock_reveal:
            main_window._on_tray_message_clicked()

        mock_reveal.assert_called_once_with(str(target))

    def test_tray_click_missing_file_reveals_parent_folder(
        self, main_window: MainWindow, tmp_path
    ) -> None:
        missing = tmp_path / "gone.mp4"
        main_window._notify_path = str(missing)

        with patch("src.gui.main_window.reveal_in_file_manager") as mock_reveal:
            main_window._on_tray_message_clicked()

        mock_reveal.assert_called_once_with(str(tmp_path))

    def test_tray_click_without_path_is_noop(
        self, main_window: MainWindow
    ) -> None:
        main_window._notify_path = None

        with patch("src.gui.main_window.reveal_in_file_manager") as mock_reveal:
            main_window._on_tray_message_clicked()

        mock_reveal.assert_not_called()

    def test_finished_captures_notify_path(
        self, main_window: MainWindow, tmp_path
    ) -> None:
        """После успешной загрузки путь сохраняется для клика по уведомлению."""
        target = tmp_path / "video.mp4"
        target.write_bytes(b"data")
        main_window._process_queue = MagicMock()
        item = make_item()
        main_window._queue_widget.add_item(item)
        main_window._current_queue_item = item
        worker = FakeWorker()
        main_window._download_worker = worker
        main_window._download_thread = None
        main_window._last_download_path = str(target)
        tray = MagicMock()
        main_window._tray_icon = tray

        worker.finished.connect(main_window._on_download_finished)
        worker.finished.emit()

        tray.showMessage.assert_called_once()
        assert main_window._notify_path == str(target)
