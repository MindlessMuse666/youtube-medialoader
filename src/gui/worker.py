"""Потокобезопасные рабочие задачи (QThread) для YouTube Medialoader.

Содержит классы:
  - VideoInfoWorker - асинхронное получение информации о видео
  - DownloadWorker - асинхронная загрузка видео/аудио с прогрессом
"""

from __future__ import annotations

import threading
from typing import Any

from PySide6.QtCore import QObject, Signal

from src.downloader import YouTubeDownloader


class VideoInfoWorker(QObject):
    """Асинхронное получение информации о видео в фоновом потоке.

    Запускается в отдельном QThread. Результат или ошибка возвращаются
    через Qt-сигналы, что гарантирует потокобезопасное обновление GUI.

    Сигналы:
        info_fetched: Срабатывает при успешном получении данных.
                      Передаeт словарь метаданных видео.
        error_occurred: Срабатывает при ошибке. Передаeт текст ошибки.
    """

    info_fetched = Signal(dict)
    error_occurred = Signal(str)

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
        self._downloader = YouTubeDownloader()

    def run(self) -> None:
        """Запустить получение информации о видео.

        Вызывается из QThread.started. Отправляет результат через сигналы.
        """
        try:
            info = self._downloader.get_video_info(self._url)
            self.info_fetched.emit(info)
        except Exception as exc:
            self.error_occurred.emit(str(exc))


class DownloadWorker(QObject):
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
    error_occurred = Signal(str)

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
        self._downloader = YouTubeDownloader()

    @property
    def cancel_event(self) -> threading.Event:
        """Вернуть threading.Event для отмены загрузки.

        Вызов ``cancel_event.set()`` из GUI-потока прервeт загрузку.
        """
        return self._cancel_event

    def run(self) -> None:
        """Запустить загрузку в фоновом потоке.

        Вызывается из QThread.started. Результат отправляется через сигналы.
        """
        try:
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
        except Exception as exc:
            if not self._cancel_event.is_set():
                self.error_occurred.emit(str(exc))

    def _on_progress(self, data: dict[str, Any]) -> None:
        """Пробросить обновление прогресса через Qt-сигнал.

        Args:
            data: Словарь прогресса от yt-dlp.
        """
        self.progress.emit(data)


class PlaylistWorker(QObject):
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
    error_occurred = Signal(str)

    def __init__(self, url: str, parent: QObject | None = None) -> None:
        """Инициализация рабочего объекта плейлиста.

        Args:
            url: Ссылка на YouTube-плейлист.
            parent: Родительский QObject (опционально).
        """
        super().__init__(parent)
        self._url = url
        self._downloader = YouTubeDownloader()

    def run(self) -> None:
        """Запустить получение информации о плейлисте.

        Вызывается из QThread.started. Отправляет результат через сигналы.
        """
        try:
            entries = self._downloader.get_playlist_info(self._url)
            self.playlist_fetched.emit(entries)
        except Exception as exc:
            self.error_occurred.emit(str(exc))
