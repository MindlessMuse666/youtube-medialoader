"""Потокобезопасные рабочие задачи (QThread) для YouTube Medialoader.

Содержит базовый класс :class:`_BaseWorker` (Template Method) и три
наследника:
  - VideoInfoWorker - асинхронное получение информации о видео
  - DownloadWorker - асинхронная загрузка видео/аудио с прогрессом
  - PlaylistWorker - асинхронное получение списка видео из плейлиста
"""

from __future__ import annotations

import threading
from typing import Any

from PySide6.QtCore import QObject, Signal

from src.downloader import YouTubeDownloader


class _BaseWorker(QObject):
    """Базовый рабочий объект, выполняющийся в отдельном QThread.

    Реализует шаблонный метод :meth:`run`: оборачивает :meth:`_perform`
    в try/except и сообщает об ошибке через сигнал :attr:`error_occurred`.
    Наследники реализуют только полезную работу в :meth:`_perform` и
    (при необходимости) подавляют ошибку через :meth:`_should_report_error`
    (например, отмену загрузки пользователем).

    Сигналы:
        error_occurred: Срабатывает при ошибке. Передаeт текст ошибки.
    """

    error_occurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._downloader = YouTubeDownloader()

    def _perform(self) -> None:
        """Выполнить полезную работу worker'а (реализуется наследником)."""
        raise NotImplementedError

    def _should_report_error(self) -> bool:
        """Нужно ли сообщать об ошибке (``True`` по умолчанию)."""
        return True

    def run(self) -> None:
        """Запустить работу в фоновом потоке.

        Вызывается из QThread.started. Результат отправляется через сигналы.
        """
        try:
            self._perform()
        except Exception as exc:
            if self._should_report_error():
                self.error_occurred.emit(str(exc))


class VideoInfoWorker(_BaseWorker):
    """Асинхронное получение информации о видео в фоновом потоке.

    Запускается в отдельном QThread. Результат или ошибка возвращаются
    через Qt-сигналы, что гарантирует потокобезопасное обновление GUI.

    Сигналы:
        info_fetched: Срабатывает при успешном получении данных.
                      Передаeт словарь метаданных видео.
        error_occurred: Срабатывает при ошибке. Передаeт текст ошибки.
    """

    info_fetched = Signal(dict)

    # Счeтчик последовательности для детекции устаревших результатов запроса
    _fetch_seq: int = 0

    def __init__(self, url: str, parent: QObject | None = None) -> None:
        """Инициализация рабочего объекта.

        Args:
            url: Ссылка на YouTube-видео.
            parent: Родительский QObject (опционально).
        """
        super().__init__(parent)
        self._url = url

    def _perform(self) -> None:
        info = self._downloader.get_video_info(self._url)
        self.info_fetched.emit(info)


class DownloadWorker(_BaseWorker):
    """Асинхронная загрузка видео/аудио в фоновом потоке.

    Предоставляет сигналы прогресса, завершения и ошибки. Поддерживает
    отмену загрузки через :attr:`cancel_event`.

    Сигналы:
        progress: Обновление прогресса загрузки.
                  Передаeт словарь (status, downloaded_bytes, total_bytes, …).
        finished: Срабатывает при успешном завершении загрузки.
        error_occurred: Срабатывает при ошибке. Передаeт текст ошибки.
    """

    progress = Signal(dict)
    finished = Signal()

    def __init__(
        self,
        url: str,
        output_path: str,
        filename: str,
        format_type: str = "mp4",
        quality: str = "720p",
        parent: QObject | None = None,
    ) -> None:
        """Инициализация рабочего объекта загрузки.

        Args:
            url: Ссылка на YouTube-видео.
            output_path: Папка для сохранения файла.
            filename: Имя файла для сохранения.
            format_type: ``"mp4"`` для видео или ``"mp3"`` для аудио.
            quality: Качество видео (``"1080p"``, ``"720p"``, ``"480p"``).
                Игнорируется при *format_type* = ``"mp3"``.
            parent: Родительский QObject (опционально).
        """
        super().__init__(parent)
        self._url = url
        self._output_path = output_path
        self._filename = filename
        self._format_type = format_type
        self._quality = quality
        self._cancel_event = threading.Event()

    @property
    def cancel_event(self) -> threading.Event:
        """Вернуть threading.Event для отмены загрузки.

        Вызов ``cancel_event.set()`` из GUI-потока прервeт загрузку.
        """
        return self._cancel_event

    def _perform(self) -> None:
        self._downloader.download(
            url=self._url,
            output_path=self._output_path,
            filename=self._filename,
            format_type=self._format_type,
            quality=self._quality,
            progress_callback=self._on_progress,
            cancel_event=self._cancel_event,
        )
        if not self._cancel_event.is_set():
            self.finished.emit()

    def _should_report_error(self) -> bool:
        # При отмене пользователем никаких сигналов: ни finished, ни error.
        return not self._cancel_event.is_set()

    def _on_progress(self, data: dict[str, Any]) -> None:
        """Пробросить обновление прогресса через Qt-сигнал.

        Args:
            data: Словарь прогресса от yt-dlp.
        """
        self.progress.emit(data)


class PlaylistWorker(_BaseWorker):
    """Асинхронное получение списка видео из плейлиста YouTube.

    Запускается в отдельном QThread. Возвращает список видео через
    сигнал :attr:`playlist_fetched`.

    Сигналы:
        playlist_fetched: Срабатывает при успешном получении списка.
            Передаeт список словарей с ключами:
            ``title``, ``url``, ``duration``, ``thumbnail``, ``index``.
        error_occurred: Срабатывает при ошибке. Передаeт текст ошибки.
    """

    playlist_fetched = Signal(list)

    def __init__(self, url: str, parent: QObject | None = None) -> None:
        """Инициализация рабочего объекта плейлиста.

        Args:
            url: Ссылка на YouTube-плейлист.
            parent: Родительский QObject (опционально).
        """
        super().__init__(parent)
        self._url = url

    def _perform(self) -> None:
        entries = self._downloader.get_playlist_info(self._url)
        self.playlist_fetched.emit(entries)
