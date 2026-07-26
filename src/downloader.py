"""Главный движок загрузки для YouTube Medialoader.

Предоставляет класс :class:`YouTubeDownloader`, который оборачивает `yt-dlp`
для получения метаданных видео и выполнения загрузки с возможностью отмены.
"""

import os
import threading
from typing import Any, Callable, Optional

import yt_dlp
from yt_dlp.utils import DownloadError

from src.utils.file_utils import sanitize_filename


class YouTubeDownloader:
    """Обёртка над yt-dlp для получения информации и загрузки видео с отменой.

    Пример использования::

        downloader = YouTubeDownloader()
        info = downloader.get_video_info("https://youtube.com/watch?v=...")
        downloader.download(
            url="...",
            output_path="./downloads",
            filename=info["title"],
            format_type="mp4",
            quality="720p",
            progress_callback=my_progress_fn,
            cancel_event=threading.Event(),
        )

    Attributes:
        DEFAULT_USER_AGENT: Стандартный User-Agent для обхода блокировок.
    """

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(self) -> None:
        """Инициализация загрузчика."""
        self._cancel_event: Optional[threading.Event] = None

    # ------------------------------------------------------------------
    # Публичное API
    # ------------------------------------------------------------------

    def get_video_info(self, url: str) -> dict[str, Any]:
        """Получить метаданные видео по ссылке YouTube.

        Использует `yt-dlp` в режиме без загрузки для извлечения названия,
        длительности, примерного размера файла и доступных форматов.

        Args:
            url: Ссылка на YouTube-видео (любой поддерживаемый формат).

        Returns:
            dict с ключами:
                - title (str): Название видео.
                - duration (int): Длительность в секундах.
                - filesize (int | None): Примерный размер файла в байтах.
                - formats (list[dict]): Доступные форматы с `format_id`,
                  `height`, `ext`, `filesize`, `tbr`.

        Raises:
            yt_dlp.utils.DownloadError: Если URL некорректен или недоступен.
        """
        opts: Any = {
            "quiet": True,
            "no_warnings": True,
            "nocheckcertificate": True,
            "user_agent": self.DEFAULT_USER_AGENT,
            "source_address": "0.0.0.0",
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        # Нормализуем возвращаемый словарь
        return {
            "title": info.get("title", "Untitled"),
            "duration": info.get("duration", 0),
            "filesize": self._estimate_filesize(info),
            "formats": self._clean_formats(info.get("formats") or []),
        }

    def download(
        self,
        url: str,
        output_path: str,
        filename: str,
        format_type: str = "mp4",
        quality: str = "720p",
        progress_callback: Optional[Callable[[Any], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> None:
        """Скачать видео или аудио с YouTube.

        Работает синхронно — запускайте в отдельном потоке, чтобы не блокировать
        интерфейс. Поддерживает отмену через *cancel_event*.

        Args:
            url: Ссылка на YouTube-видео.
            output_path: Папка для сохранения файла.
            filename: Желаемое имя файла (будет очищено от недопустимых символов).
            format_type: `"mp4"` для видео или `"mp3"` для аудио.
            quality: Желаемое качество — `"1080p"`, `"720p"` или `"480p"`.
                Игнорируется при *format_type* = `"mp3"`.
            progress_callback: Функция, вызываемая с словарем при каждом обновлении
                прогресса (те же ключи, что у `yt-dlp` progress hook). Вызывается
                из фонового потока.
            cancel_event: При установке этого события загрузка будет прервана,
                а частично скачанный файл удалён.

        Raises:
            yt_dlp.utils.DownloadError: При ошибках загрузки.
            ValueError: Если *format_type* или *quality* не поддерживаются.
        """
        self._cancel_event = cancel_event

        safe_name = sanitize_filename(filename)
        base, ext = os.path.splitext(safe_name)
        if not ext:
            ext = f".{format_type}" if format_type == "mp4" else ".mp3"
        safe_name = f"{base}{ext}"

        outtmpl = os.path.join(output_path, safe_name)

        ydl_opts: Any = self._build_opts(
            format_type=format_type,
            quality=quality,
            outtmpl=outtmpl,
            progress_callback=progress_callback,
        )

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                ydl.download([url])
            finally:
                # Если загрузка отменена — удаляем частичный файл
                if self._cancel_event and self._cancel_event.is_set():
                    # prepare_filename ожидает словарь с минимум 'id' и 'title'
                    partial = ydl.prepare_filename({
                        "id": "unknown",
                        "title": base,
                    })
                    if os.path.exists(partial):
                        os.remove(partial)

    # ------------------------------------------------------------------
    # Внутренние helpers
    # ------------------------------------------------------------------

    def _build_opts(
        self,
        format_type: str,
        quality: str,
        outtmpl: str,
        progress_callback: Optional[Callable[[Any], None]] = None,
    ) -> Any:
        """Собрать словарь опций для yt-dlp.

        Args:
            format_type: `"mp4"` или `"mp3"`.
            quality: `"1080p"`, `"720p"` или `"480p"`.
            outtmpl: Шаблон пути для сохранения файла.
            progress_callback: Опциональный колбэк прогресса.

        Returns:
            Словарь опций, готовый для :class:`yt_dlp.YoutubeDL`.

        Raises:
            ValueError: Если format_type или quality не поддерживаются.
        """
        if format_type not in ("mp4", "mp3"):
            raise ValueError(f"Неподдерживаемый format_type: {format_type!r}")

        opts: Any = {
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
            "nocheckcertificate": True,
            "user_agent": self.DEFAULT_USER_AGENT,
            "source_address": "0.0.0.0",
        }

        if progress_callback is not None:
            opts["progress_hooks"] = [self._make_progress_hook(progress_callback)]

        if self._cancel_event is not None:
            opts["hook"] = self._cancel_hook

        if format_type == "mp3":
            opts.update(self._audio_opts())
        else:
            opts.update(self._video_opts(quality))

        return opts

    def _audio_opts(self) -> Any:
        """Вернуть опции yt-dlp для извлечения MP3 в лучшем качестве."""
        return {
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "0",  # максимальное качество
                }
            ],
        }

    def _video_opts(self, quality: str) -> Any:
        """Вернуть опции yt-dlp для скачивания видео+аудио до *quality*.

        Args:
            quality: `"1080p"`, `"720p"` или `"480p"`.

        Returns:
            Опции формата для yt-dlp.

        Raises:
            ValueError: Если quality не поддерживается.
        """
        quality_map = {"1080p": 1080, "720p": 720, "480p": 480}
        height = quality_map.get(quality)
        if height is None:
            raise ValueError(
                f"Неподдерживаемое качество: {quality!r}. "
                f"Выберите из {list(quality_map)}"
            )

        return {
            "format": (
                f"bestvideo[height<={height}][ext=mp4]+"
                f"bestaudio[ext=m4a]/"
                f"best[height<={height}][ext=mp4]/"
                f"best"
            ),
            "merge_output_format": "mp4",
        }

    def _make_progress_hook(
        self, callback: Callable[[Any], None]
    ) -> Callable[[Any], None]:
        """Обернуть пользовательский колбэк в progress-hook для yt-dlp.

        Также проверяет событие отмены и выбрасывает исключение для остановки
        загрузки внутри yt-dlp.
        """

        def hook(d: Any) -> None:
            if self._cancel_event and self._cancel_event.is_set():
                raise DownloadError("Отменено пользователем")
            callback(d)

        return hook

    def _cancel_hook(self, d: Any) -> None:
        """Минимальный хук, проверяющий отмену (без прогресса)."""
        if self._cancel_event and self._cancel_event.is_set():
            raise DownloadError("Отменено пользователем")

    @staticmethod
    def _estimate_filesize(info: Any) -> Optional[int]:
        """Получить примерный размер файла из информации о видео.

        Сначала пытается взять суммарный размер из `requested_formats`,
        затем — наибольший размер среди всех форматов.
        """
        # Если yt-dlp уже вычислил общий размер
        if info.get("requested_formats"):
            total = sum(
                f.get("filesize", 0) or f.get("filesize_approx", 0) or 0
                for f in info["requested_formats"]
            )
            if total:
                return int(total)

        # Иначе ищем наибольший размер среди форматов
        formats = info.get("formats") or []
        sizes = [
            f.get("filesize") or f.get("filesize_approx") or 0
            for f in formats
        ]
        sizes = [s for s in sizes if s]
        return int(max(sizes)) if sizes else None

    @staticmethod
    def _clean_formats(raw_formats: Any) -> list[dict[str, Any]]:
        """Отфильтровать и нормализовать список форматов для внешнего использования.

        Оставляет только форматы с указанием format_id, убирает дубликаты.
        """
        cleaned: list[dict[str, Any]] = []
        seen: set[str] = set()
        for f in raw_formats:
            fid = f.get("format_id")
            if not fid or fid in seen:
                continue
            seen.add(fid)
            cleaned.append(
                {
                    "format_id": fid,
                    "ext": f.get("ext", ""),
                    "height": f.get("height"),
                    "width": f.get("width"),
                    "filesize": f.get("filesize") or f.get("filesize_approx"),
                    "tbr": f.get("tbr"),  # средний битрейт
                    "acodec": f.get("acodec"),
                    "vcodec": f.get("vcodec"),
                }
            )
        return cleaned
