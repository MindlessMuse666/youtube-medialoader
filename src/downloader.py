"""Главный движок загрузки для YouTube Medialoader.

Предоставляет класс :class:`YouTubeDownloader`, который оборачивает `yt-dlp`
для получения метаданных видео и выполнения загрузки с возможностью отмены.
"""

import os
import re
import shutil
import threading
from typing import Any, Callable, Optional

import yt_dlp
from yt_dlp.utils import DownloadError

from src.utils.file_utils import (
    _split_ext,
    resolve_filename,
    sanitize_filename,
)


class YouTubeDownloader:
    """Обeртка над yt-dlp для получения информации и загрузки видео с отменой.

    Куки **не используются по умолчанию**. Если запрос к YouTube не удался
    при использовании кук, движок автоматически повторяет попытку без них.
    Если куки не использовались - ошибка пробрасывается сразу.
    Специфичные куки можно передать явно через параметры
    ``cookies_from_browser`` / ``cookies_file``.

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

    def __init__(
        self,
        cookies_from_browser: Optional[tuple[str, ...]] = None,
        cookies_file: Optional[str] = None,
    ) -> None:
        """Инициализация загрузчика.

        Куки **не используются по умолчанию** (``None``). Передайте явные
        браузеры или файл кук только если вы уверены, что YouTube блокирует
        запросы без них.

        Args:
            cookies_from_browser: Кортеж имeн браузеров для извлечения кук
                (``("chrome",)``, ``("firefox",)``, и т.д.). Если запрос с
                куками не удался, будет автоматически повторeн без них.
                ``None`` (по умолчанию) - не использовать куки из браузера.
            cookies_file: Путь к файлу кук в формате Netscape.
                ``None`` (по умолчанию) - не использовать файл кук.
        """
        self._cancel_event: Optional[threading.Event] = None
        self._cookies_from_browser = cookies_from_browser
        self._cookies_file = cookies_file

    # ------------------------------------------------------------------
    # Публичное API
    # ------------------------------------------------------------------

    def get_video_info(
        self,
        url: str,
        cookies_from_browser: Optional[tuple[str, ...]] = None,
        cookies_file: Optional[str] = None,
    ) -> dict[str, Any]:
        """Получить метаданные видео по ссылке YouTube.

        Использует `yt-dlp` в режиме без загрузки для извлечения названия,
        длительности, примерного размера файла и доступных форматов.

    Поведение при ошибке:
        1. Первая попытка - с переданными куками (если указаны).
        2. Если использовались куки и запрос упал -> повтор без кук.
        3. Если всe упало - исключение ``DownloadError``.

        Args:
            url: Ссылка на YouTube-видео (любой поддерживаемый формат).
            cookies_from_browser: Браузеры для извлечения кук
                (переопределяет значение из конструктора).
            cookies_file: Путь к файлу кук
                (переопределяет значение из конструктора).

        Returns:
            dict с ключами:
                - title (str): Название видео.
                - duration (int): Длительность в секундах.
                - filesize (int | None): Примерный размер файла в байтах.
                - formats (list[dict]): Доступные форматы с `format_id`,
                  `height`, `ext`, `filesize`, `tbr`.

        Raises:
            yt_dlp.utils.DownloadError: Если URL некорректен или видео
                недоступно.
        """
        cookie_browsers, cookie_file = self._resolve_cookies(
            cookies_from_browser, cookies_file
        )

        opts = self._base_opts()
        had_cookies = bool(cookie_browsers or cookie_file)
        if had_cookies:
            self._apply_cookie_opts(opts, cookie_browsers, cookie_file)

        info = self._extract_with_cookie_fallback(url, opts, had_cookies)

        return self._normalize_info(info)

    def get_playlist_info(
        self,
        url: str,
    ) -> list[dict[str, Any]]:
        """Получить список видео из плейлиста YouTube.

        Извлекает метаданные каждого видео в плейлисте:
        название, URL, длительность, обложку.

        Args:
            url: Ссылка на YouTube-плейлист (содержит ``list=``).

        Returns:
            Список словарей, каждый с ключами:
            ``title``, ``url``, ``duration``, ``thumbnail``, ``index``.

        Raises:
            yt_dlp.utils.DownloadError: Если URL некорректен или плейлист
                недоступен.
        """
        opts: Any = self._base_opts()
        opts["extract_flat"] = True  # не качаем полную инфу о каждом видео
        opts["noplaylist"] = False

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        entries = info.get("entries") or []
        results: list[dict[str, Any]] = []
        for entry in entries:
            if entry is None:
                continue
            results.append({
                "title": entry.get("title", "Untitled"),
                "url": entry.get("url") or entry.get("webpage_url", ""),
                "duration": entry.get("duration", 0),
                "thumbnail": entry.get("thumbnail", ""),
                "index": entry.get("playlist_index", len(results) + 1),
            })

        return results

    def download(
        self,
        url: str,
        output_path: str,
        filename: str,
        format_type: str = "mp4",
        quality: str = "720p",
        progress_callback: Optional[Callable[[Any], None]] = None,
        cancel_event: Optional[threading.Event] = None,
        cookies_from_browser: Optional[tuple[str, ...]] = None,
        cookies_file: Optional[str] = None,
    ) -> None:
        """Скачать видео или аудио с YouTube.

        Работает синхронно - запускайте в отдельном потоке, чтобы не
        блокировать интерфейс. Поддерживает отмену через *cancel_event*.

    Поведение при ошибке - то же, что у :meth:`get_video_info`:
        сначала попытка с переданными куками, затем без кук.

        Args:
            url: Ссылка на YouTube-видео.
            output_path: Папка для сохранения файла.
            filename: Желаемое имя файла (будет очищено от недопустимых
                символов).
            format_type: ``"mp4"`` для видео или ``"mp3"`` для аудио.
            quality: Желаемое качество - ``"1080p"``, ``"720p"`` или
            ``"480p"``.
                Игнорируется при *format_type* = ``"mp3"``.
            progress_callback: Функция, вызываемая с словарeм при каждом
                обновлении прогресса (те же ключи, что у `yt-dlp` progress
                hook). Вызывается из фонового потока.
            cancel_event: При установке этого события загрузка будет
                прервана, а частично скачанный файл удалeн.
            cookies_from_browser: Браузеры для извлечения кук
                (переопределяет значение из конструктора).
            cookies_file: Путь к файлу кук
                (переопределяет значение из конструктора).

        Raises:
            yt_dlp.utils.DownloadError: При ошибках загрузки.
            ValueError: Если *format_type* или *quality* не поддерживаются.
        """
        self._cancel_event = cancel_event

        # outtmpl собираем с учeтом постобработки: для mp3 расширение в
        # шаблоне НЕ указываем - иначе FFmpegExtractAudio заменит уже
        # существующее ".mp3" на ".mp3" и файл получится "<имя>.mp3.mp3".
        out_name = self._resolve_out_name(filename, format_type)
        outtmpl = os.path.join(output_path, out_name)

        cookie_browsers, cookie_file = self._resolve_cookies(
            cookies_from_browser, cookies_file
        )

        ydl_opts = self._build_opts(
            format_type=format_type,
            quality=quality,
            outtmpl=outtmpl,
            progress_callback=progress_callback,
        )

        had_cookies = bool(cookie_browsers or cookie_file)
        if had_cookies:
            self._apply_cookie_opts(ydl_opts, cookie_browsers, cookie_file)

        try:
            self._download_once(ydl_opts, url)
        except DownloadError:
            if self._cancel_event and self._cancel_event.is_set():
                # yt-dlp оставляет .part-файлы для возобновления (resume);
                # при явной отмене пользователем они не нужны.
                self._cleanup_partial_files(outtmpl)
                raise

            # Если использовали куки - пробуем без них. Повтор идёт с копией
            # словаря опций, чтобы не мутировать исходный ydl_opts.
            if had_cookies:
                retry_opts = dict(ydl_opts)
                self._remove_cookie_opts(retry_opts)
                self._download_once(retry_opts, url)
            else:
                # Без кук - нечего повторять, пробрасываем исходную ошибку
                raise

    # ------------------------------------------------------------------
    # Внутренние helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_out_name(filename: str, format_type: str) -> str:
        """Определить имя для шаблона вывода ``outtmpl``.

        Для ``mp3`` расширение в шаблоне **не** указывается: промежуточный
        файл (``m4a``/``webm``) получит расширение автоматически, а
        ``FFmpegExtractAudio`` при постобработке заменит его на ``.mp3``.
        Если же расширение оставить в шаблоне - замена даст двойное
        расширение (``<имя>.mp3.mp3``). Для ``mp4`` имя фиксируется с
        расширением ``.mp4`` (совпадает с ``merge_output_format``).

        Args:
            filename: Желаемое имя файла (может содержать расширение).
            format_type: ``"mp4"`` или ``"mp3"``.

        Returns:
            Имя для шаблона вывода без абсолютного пути.
        """
        safe = sanitize_filename(filename)
        if format_type == "mp3":
            base, _ext = _split_ext(safe)
            return base
        return resolve_filename(filename, "mp4")

    @staticmethod
    def _cleanup_partial_files(outtmpl: str) -> None:
        """Удалить временные файлы yt-dlp, оставшиеся после отмены.

        При прерывании загрузки yt-dlp **не** удаляет частично скачанные
        файлы - они нужны ему для возобновления (resume). После явной отмены
        пользователем такие файлы не нужны, поэтому удаляем всё, что yt-dlp
        мог оставить для шаблона *outtmpl*:

          - ``<имя>.part`` — файл или каталог фрагментов;
          - ``<имя>.f<id>.<ext>`` — промежуточные файлы слияния форматов;
          - ``<имя>.ytdl`` — файл состояния возобновляемой загрузки.

        Готовый файл (``<имя>.mp4``/``<имя>.mp3``) при этом не затрагивается:
        для ``mp3`` шаблон задаётся без расширения, поэтому ``<имя>.mp3`` от
        прошлой успешной загрузки останется на месте.

        Args:
            outtmpl: Шаблон пути вывода, переданный yt-dlp в ``outtmpl``.
        """
        directory = os.path.dirname(outtmpl) or "."
        base = os.path.basename(outtmpl)
        if not base:
            return

        # Промежуточные файлы слияния: "<имя>.f<числовой id>.<ext>"
        intermediate_re = re.compile(
            rf"^{re.escape(base)}\.f\d+(?:\.[a-zA-Z0-9]+)?$"
        )

        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    name = entry.name
                    if not name.startswith(base + "."):
                        continue
                    is_temp = (
                        name.endswith(".part")
                        or name.endswith(".ytdl")
                        or intermediate_re.match(name) is not None
                    )
                    if not is_temp:
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        shutil.rmtree(entry.path, ignore_errors=True)
                    else:
                        try:
                            os.remove(entry.path)
                        except OSError:
                            pass
        except OSError:
            pass

    def _resolve_cookies(
        self,
        cookies_from_browser: Optional[tuple[str, ...]],
        cookies_file: Optional[str],
    ) -> tuple[Optional[tuple[str, ...]], Optional[str]]:
        """Выбрать куки: явные параметры или значения из конструктора.

        Явно переданные в вызов аргументы имеют приоритет над значениями
        из конструктора (``None`` означает "не переопределяли").

        Args:
            cookies_from_browser: Браузеры из аргументов вызова.
            cookies_file: Путь к файлу кук из аргументов вызова.

        Returns:
            Кортеж ``(cookie_browsers, cookie_file)``, готовый к использованию.
        """
        return (
            (
                cookies_from_browser
                if cookies_from_browser is not None
                else self._cookies_from_browser
            ),
            (
                cookies_file
                if cookies_file is not None
                else self._cookies_file
            ),
        )

    @staticmethod
    def _remove_cookie_opts(opts: dict[str, Any]) -> None:
        """Убрать опции кук из словаря опций yt-dlp (in-place).

        Используется для повторной попытки без кук, когда запрос с куками
        упал (см. :meth:`_extract_with_cookie_fallback`).

        Args:
            opts: Словарь опций yt-dlp.
        """
        opts.pop("cookiesfrombrowser", None)
        opts.pop("cookiefile", None)

    def _extract_with_cookie_fallback(
        self,
        url: str,
        opts: dict[str, Any],
        had_cookies: bool,
    ) -> Any:
        """Извлечь информацию, повторив попытку без кук при ошибке.

        Если куки использовались и запрос упал - удаляет опции кук и
        пробует ещё раз. Без кук ошибка пробрасывается сразу.

        Args:
            url: Ссылка на видео.
            opts: Словарь опций для YoutubeDL.
            had_cookies: Использовались ли куки в первой попытке.

        Returns:
            Информация о видео от yt-dlp.

        Raises:
            yt_dlp.utils.DownloadError: Если обе попытки не удались.
        """
        try:
            return self._extract(url, opts)
        except DownloadError:
            if not had_cookies:
                raise
            # Повтор идёт с копией словаря, чтобы не мутировать исходный opts
            # (первая попытка должна сохранить опции кук для проверок/логов).
            retry_opts = dict(opts)
            self._remove_cookie_opts(retry_opts)
            return self._extract(url, retry_opts)

    @staticmethod
    def _extract(url: str, opts: Any) -> Any:
        """Извлечь информацию о видео через yt-dlp.

        yt-dlp принимает произвольный словарь опций (включая динамические
        ключи вроде ``cookiesfrombrowser``), поэтому тип ``opts`` - ``Any``.

        Args:
            url: Ссылка на видео.
            opts: Словарь опций для YoutubeDL.

        Returns:
            Информация о видео от yt-dlp.

        Raises:
            yt_dlp.utils.DownloadError: Если запрос не удался.
        """
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

    @staticmethod
    def _download_once(opts: Any, url: str) -> None:
        """Выполнить один проход загрузки через yt-dlp.

        Args:
            opts: Словарь опций для YoutubeDL.
            url: Ссылка на видео.

        Raises:
            yt_dlp.utils.DownloadError: Если загрузка не удалась.
        """
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

    @staticmethod
    def _base_opts() -> dict[str, Any]:
        """Базовые опции для любого запроса к yt-dlp.

        Returns:
            Словарь опций с User-Agent, таймаутом, отключением
            проверки сертификата и тихим режимом.
        """
        return {
            "quiet": True,
            "no_warnings": True,
            "nocheckcertificate": True,
            "socket_timeout": 60,
            "user_agent": YouTubeDownloader.DEFAULT_USER_AGENT,
            "source_address": "0.0.0.0",
            "extractor_retries": 5,
            "noplaylist": True,
            "extractor_args": {"youtube": {"skip": ["dash", "hls"]}},
        }

    @staticmethod
    def _apply_cookie_opts(
        opts: dict[str, Any],
        cookies_from_browser: Optional[tuple[str, ...]] = None,
        cookies_file: Optional[str] = None,
    ) -> None:
        """Добавить опции кук в словарь опций yt-dlp.

        Вызывает ``--cookies-from-browser`` и/или ``--cookies``
        для аутентификации на YouTube.

        Args:
            opts: Словарь опций yt-dlp (изменяется in-place).
            cookies_from_browser: Браузеры для извлечения кук
                (``("chrome",)``, ``("firefox",)``, и т.д.).
            cookies_file: Путь к файлу кук в формате Netscape.
        """
        if cookies_file:
            opts["cookiefile"] = cookies_file
        if cookies_from_browser:
            opts["cookiesfrombrowser"] = cookies_from_browser

    def _build_opts(
        self,
        format_type: str,
        quality: str,
        outtmpl: str,
        progress_callback: Optional[Callable[[Any], None]] = None,
    ) -> Any:
        """Собрать словарь опций для yt-dlp (без кук).

        yt-dlp использует внутренний ``_Params`` TypedDict, которому
        не соответствует наш динамический словарь (``cookiesfrombrowser``,
        ``postprocessors``, ``hook`` и т.д.), поэтому тип возврата - ``Any``.

        Args:
            format_type: ``"mp4"`` или ``"mp3"``.
            quality: ``"1080p"``, ``"720p"`` или ``"480p"``.
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
            **self._base_opts(),
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

    def _audio_opts(self) -> dict[str, Any]:
        """Вернуть опции yt-dlp для извлечения MP3 в лучшем качестве."""
        return {
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "0",
                },
            ],
        }

    def _video_opts(self, quality: str) -> dict[str, Any]:
        """Вернуть опции yt-dlp для скачивания видео+аудио до *quality*.

        Args:
            quality: ``"1080p"``, ``"720p"`` или ``"480p"``.

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
                f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/"
                f"bestvideo[height<={height}][ext=mp4]+bestaudio/"
                f"best[height<={height}][ext=mp4]/"
                f"best[height<={height}]/"
                f"best"
            ),
            "merge_output_format": "mp4",
        }

    def _make_progress_hook(
        self, callback: Callable[[Any], None]
    ) -> Callable[[Any], None]:
        """Обернуть пользовательский колбэк в progress-hook для yt-dlp.

        Также проверяет событие отмены и выбрасывает исключение для
        остановки загрузки внутри yt-dlp.
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
    def _normalize_info(info: Any) -> dict[str, Any]:
        """Нормализовать сырой словарь от yt-dlp в единый формат.

        Args:
            info: Сырая информация о видео от yt-dlp.

        Returns:
            Нормализованный словарь с ключами title, duration, filesize,
            formats.
        """
        return {
            "title": info.get("title", "Untitled"),
            "duration": info.get("duration", 0),
            "filesize": YouTubeDownloader._estimate_filesize(info),
            "thumbnail": info.get("thumbnail", ""),
            "formats": YouTubeDownloader._clean_formats(
                info.get("formats") or []
            ),
        }

    @staticmethod
    def _estimate_filesize(info: Any) -> Optional[int]:
        """Получить примерный размер файла из информации о видео.

        Сначала пытается взять суммарный размер из ``requested_formats``,
        затем - наибольший размер среди всех форматов.
        """
        if info.get("requested_formats"):
            total = sum(
                f.get("filesize", 0) or f.get("filesize_approx", 0) or 0
                for f in info["requested_formats"]
            )
            if total:
                return int(total)

        formats = info.get("formats") or []
        sizes = [
            f.get("filesize") or f.get("filesize_approx") or 0
            for f in formats
        ]
        sizes = [s for s in sizes if s]
        return int(max(sizes)) if sizes else None

    @staticmethod
    def _clean_formats(
        raw_formats: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Отфильтровать и нормализовать список форматов.

        Оставляет только форматы с указанием format_id, убирает дубликаты.
        """
        cleaned: list[dict[str, Any]] = []
        seen: set[str] = set()
        for f in raw_formats:
            fid = f.get("format_id")
            if not fid or fid in seen:
                continue
            seen.add(fid)
            cleaned.append({
                "format_id": fid,
                "ext": f.get("ext", ""),
                "height": f.get("height"),
                "width": f.get("width"),
                "filesize": f.get("filesize") or f.get("filesize_approx"),
                "tbr": f.get("tbr"),
                "acodec": f.get("acodec"),
                "vcodec": f.get("vcodec"),
            })
        return cleaned
