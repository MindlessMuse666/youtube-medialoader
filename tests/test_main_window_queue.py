"""Тесты жизненного цикла очереди и потоков загрузки (main_window.py).

Покрывают исправление бага ``QThread: Destroyed while thread '' is still
running``: уборка завершившегося потока не должна задевать уже запущенный
следующий, а устаревшие сигналы старого worker'а должны игнорироваться.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QObject, Qt, QThread, Signal

from src.gui.download_queue import QueueItem, QueueItemStatus

_URL = "https://youtube.com/watch?v=test"


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
    """Кнопка "СКАЧАТЬ" скрывается на время активной загрузки."""

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
        main_window.url_input.setText(_URL)
        main_window._current_video_title = "Test Video"
        main_window._current_video_url = _URL
        main_window._process_queue()
        assert not main_window.download_btn.isHidden()


class TestOpenFolderButtonReset:
    """Кнопка "ОТКРЫТЬ ПАПКУ" должна скрываться при вводе новой ссылки."""

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
        """Путь для уведомления берётся из завершённого элемента очереди.

        Глобальный ``_last_download_path`` к моменту завершения мог быть
        перезаписан новым "СКАЧАТЬ"/стартом следующего элемента - поэтому
        путь считается из самого элемента (баг 3).
        """
        target = tmp_path / "video.mp4"
        target.write_bytes(b"data")
        main_window._process_queue = MagicMock()
        item = make_item(output_path=str(tmp_path), filename="video.mp4")
        main_window._queue_widget.add_item(item)
        main_window._current_queue_item = item
        worker = FakeWorker()
        main_window._download_worker = worker
        main_window._download_thread = None
        # "Загрязняем" глобальный путь: его перезаписала предыдущая загрузка.
        main_window._last_download_path = str(tmp_path / "other.mp4")
        tray = MagicMock()
        main_window._tray_icon = tray

        worker.finished.connect(main_window._on_download_finished)
        worker.finished.emit()

        tray.showMessage.assert_called_once()
        assert main_window._notify_path == str(target)

    def test_open_folder_uses_last_completed_path(
        self, main_window: MainWindow, tmp_path
    ) -> None:
        """Кнопка "ОТКРЫТЬ ПАПКУ" открывает последний завершённый файл.

        Путь не должен перезаписываться следующим элементом очереди.
        """
        target = tmp_path / "video.mp4"
        target.write_bytes(b"data")
        main_window._process_queue = MagicMock()
        item = make_item(output_path=str(tmp_path), filename="video.mp4")
        main_window._queue_widget.add_item(item)
        main_window._current_queue_item = item
        worker = FakeWorker()
        main_window._download_worker = worker
        main_window._download_thread = None
        main_window._last_download_path = str(tmp_path / "other.mp4")
        main_window._tray_icon = None

        worker.finished.connect(main_window._on_download_finished)
        worker.finished.emit()

        with patch("src.gui.main_window.reveal_in_file_manager") as mock_reveal:
            main_window._on_open_folder_clicked()
        mock_reveal.assert_called_once_with(str(target))

    def test_history_records_completed_path(
        self, main_window: MainWindow, tmp_path
    ) -> None:
        """В историю попадает путь завершённого файла, а не глобальный."""
        target = tmp_path / "song.mp3"
        target.write_bytes(b"data")
        main_window._process_queue = MagicMock()
        item = make_item(
            output_path=str(tmp_path),
            filename="song.mp3",
            format_type="mp3",
            title="Song",
        )
        main_window._queue_widget.add_item(item)
        main_window._current_queue_item = item
        worker = FakeWorker()
        main_window._download_worker = worker
        main_window._download_thread = None
        main_window._last_download_path = str(tmp_path / "other.mp3")
        main_window._tray_icon = None

        worker.finished.connect(main_window._on_download_finished)
        worker.finished.emit()

        entry = main_window._history_manager.add.call_args[0][0]
        assert entry.file_path == str(target)

    def test_queue_start_does_not_overwrite_last_completed_path(
        self, main_window: MainWindow
    ) -> None:
        """Старт новой загрузки не трогает путь последнего завершённого файла."""
        main_window._last_download_path = "C:/Downloads/done.mp4"
        with (
            patch("src.gui.main_window.QThread") as mock_thread_cls,
            patch("src.gui.main_window.DownloadWorker") as mock_worker_cls,
        ):
            mock_thread_cls.return_value = MagicMock()
            mock_worker_cls.return_value = MagicMock()
            main_window._queue_widget.add_item(
                make_item(output_path="C:/Downloads", filename="next.mp4")
            )
            main_window._download_thread = None
            main_window._process_queue()

        assert main_window._last_download_path == "C:/Downloads/done.mp4"


class TestProgressStatusLabel:
    """Строка статуса под прогресс-баром (баг "стили прогресс-бара съехали").

    Пустая метка скрывается, чтобы не резервировать строку между прогресс-баром
    и кнопками; непустая - показывается и центрируется по горизонтали, как
    текст самого прогресс-бара.
    """

    def test_empty_status_hides_label(self, main_window: MainWindow) -> None:
        """Пустая строка статуса прячет метку - она не занимает места."""
        main_window._set_progress_status("")
        assert main_window._progress_status_label.isHidden()

    def test_nonempty_status_shows_label(self, main_window: MainWindow) -> None:
        """Во время загрузки строка статуса появляется со своим текстом."""
        text = "10.0MB / 100.0MB  |  5MB/s  |  осталось 00:30"
        main_window._set_progress_status(text)
        assert not main_window._progress_status_label.isHidden()
        assert main_window._progress_status_label.text() == text

    def test_status_hidden_again_after_clear(self, main_window: MainWindow) -> None:
        """После очистки метка снова скрывается (кнопки прижимаются к бару)."""
        main_window._set_progress_status("что-то")
        main_window._set_progress_status("")
        assert main_window._progress_status_label.isHidden()

    def test_label_centered_horizontally(self, main_window: MainWindow) -> None:
        """Текст статуса центрируется, как и текст прогресс-бара."""
        flags = main_window._progress_status_label.alignment()
        assert flags & Qt.AlignmentFlag.AlignHCenter

    def test_label_hidden_by_default(self, main_window: MainWindow) -> None:
        """При старте пустая метка скрыта - кнопки не съезжают вниз."""
        assert main_window._progress_status_label.isHidden()


class TestDownloadButtonHiddenAfterSuccess:
    """Кнопка "СКАЧАТЬ" скрывается после успешной загрузки до смены параметров.

    Скачанный файл незачем качать повторно: кнопка не появляется, пока входные
    параметры (ссылка, тип, качество) не изменились.
    """

    def _finish_download(self, main_window: MainWindow) -> None:
        """Довести одну загрузку до успешного завершения (сигнал finished)."""
        main_window._process_queue = MagicMock()
        item = make_item()
        main_window._queue_widget.add_item(item)
        main_window._current_queue_item = item
        worker = FakeWorker()
        main_window._download_worker = worker
        main_window._download_thread = None
        main_window._tray_icon = None
        worker.finished.connect(main_window._on_download_finished)
        worker.finished.emit()

    def test_success_hides_button_even_with_info(
        self, main_window: MainWindow
    ) -> None:
        """После успеха кнопка скрыта, хотя информация для ссылки есть."""
        main_window.url_input.setText(_URL)
        main_window._current_video_title = "Test Video"
        main_window._current_video_url = _URL
        main_window._update_download_btn()
        assert not main_window.download_btn.isHidden()

        self._finish_download(main_window)
        main_window._update_download_btn()

        assert main_window._last_download_succeeded
        assert main_window.download_btn.isHidden()
        assert main_window._can_enable_download() is False

    def test_url_change_resets_flag(self, main_window: MainWindow) -> None:
        """Смена ссылки сбрасывает флаг и снова показывает кнопку."""
        main_window.url_input.setText(_URL)
        main_window._current_video_title = "Test Video"
        main_window._current_video_url = _URL
        self._finish_download(main_window)
        assert main_window._last_download_succeeded

        new_url = "https://youtube.com/watch?v=other"
        main_window.url_input.setText(new_url)
        assert main_window._last_download_succeeded is False

        main_window._current_video_title = "Other Video"
        main_window._current_video_url = new_url
        main_window._update_download_btn()
        assert not main_window.download_btn.isHidden()

    def test_type_change_shows_button(self, main_window: MainWindow) -> None:
        """Смена типа (MP4/MP3) сбрасывает флаг и показывает кнопку."""
        main_window.url_input.setText(_URL)
        main_window._current_video_title = "Test Video"
        main_window._current_video_url = _URL
        self._finish_download(main_window)
        main_window._update_download_btn()
        assert main_window.download_btn.isHidden()

        main_window._on_type_changed(0)  # Видео (MP4)

        assert main_window._last_download_succeeded is False
        assert not main_window.download_btn.isHidden()

    def test_quality_change_shows_button(self, main_window: MainWindow) -> None:
        """Смена качества сбрасывает флаг и показывает кнопку."""
        main_window.url_input.setText(_URL)
        main_window._current_video_title = "Test Video"
        main_window._current_video_url = _URL
        self._finish_download(main_window)
        main_window._update_download_btn()
        assert main_window.download_btn.isHidden()

        main_window._on_quality_changed()

        assert main_window._last_download_succeeded is False
        assert not main_window.download_btn.isHidden()

    def test_error_does_not_set_success_flag(
        self, main_window: MainWindow
    ) -> None:
        """Ошибка загрузки не прячет кнопку - можно повторить."""
        main_window.url_input.setText(_URL)
        main_window._current_video_title = "Test Video"
        main_window._current_video_url = _URL
        main_window._process_queue = MagicMock()
        item = make_item()
        main_window._queue_widget.add_item(item)
        main_window._current_queue_item = item
        worker = FakeWorker()
        main_window._download_worker = worker
        main_window._download_thread = None
        worker.error_occurred.connect(main_window._on_download_error)
        worker.error_occurred.emit("boom")

        assert main_window._last_download_succeeded is False
        main_window._update_download_btn()
        assert not main_window.download_btn.isHidden()
