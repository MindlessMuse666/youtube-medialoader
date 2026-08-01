"""Тесты для модуля file_utils."""

import os

from src.utils.file_utils import (
    _shell_select_file,
    resolve_filename,
    resolve_output_path,
    reveal_in_file_manager,
    sanitize_filename,
)


class TestSanitizeFilename:
    """Тесты для :func:`sanitize_filename`."""

    def test_normal_text_preserved(self) -> None:
        """Обычные имена файлов должны проходить без изменений."""
        assert sanitize_filename("My Video") == "My Video"

    def test_underscores_preserved(self) -> None:
        """Подчeркивания допустимы и должны сохраняться."""
        assert sanitize_filename("my_video") == "my_video"

    def test_invalid_chars_replaced(self) -> None:
        """Недопустимые символы должны заменяться на подчeркивание."""
        result = sanitize_filename('video<>:"/\\|?*name')
        assert "<" not in result
        assert ">" not in result
        assert '"' not in result
        assert ":" not in result
        assert "/" not in result
        assert "\\" not in result
        assert "|" not in result
        assert "?" not in result
        assert "*" not in result

    def test_leading_trailing_dots_spaces(self) -> None:
        """Точки и пробелы по краям должны удаляться."""
        assert sanitize_filename("  video  ") == "video"
        # Точки по краям удаляются - на Windows имя не может заканчиваться точкой
        assert sanitize_filename("..video..") == "video"

    def test_empty_after_sanitize_returns_untitled(self) -> None:
        """Если после очистки имя пустое, вернуть 'untitled'."""
        assert sanitize_filename("") == "untitled"
        assert sanitize_filename("<>:|?") == "untitled"

    def test_truncation(self) -> None:
        """Длинные имена должны обрезаться до max_length."""
        long_name = "a" * 300
        result = sanitize_filename(long_name, max_length=50)
        assert len(result) == 50

    def test_with_extension(self) -> None:
        """Расширение должно сохраняться, а пробелы - оставаться."""
        result = sanitize_filename("video name.mp4")
        assert result == "video name.mp4"

    def test_original_title_keeps_spaces(self) -> None:
        """Оригинальное название сохраняет пробелы; заменяется только '/'."""
        result = sanitize_filename("승인해주세요 지니님! / 카사네 테토")
        assert result == "승인해주세요 지니님! _ 카사네 테토"

    def test_trailing_suffix_preserved(self) -> None:
        """Имя только с недопустимыми символами перед расширением."""
        result = sanitize_filename("<>:.mp4")
        assert result == "untitled.mp4"

    def test_collapse_spaces(self) -> None:
        """Несколько пробелов должны схлопнуться в один."""
        assert sanitize_filename("my   super   video") == "my super video"


class TestResolveOutputPath:
    """Тесты для :func:`resolve_output_path`."""

    def test_simple_join(self) -> None:
        """Директория и имя файла должны склеиваться в нормализованный путь."""
        result = resolve_output_path("/tmp", "video.mp4")
        assert result.endswith("video.mp4")
        assert os.sep in result  # путь содержит разделитель для текущей ОС


class TestResolveFilename:
    """Тесты для :func:`resolve_filename`."""

    def test_appends_extension(self) -> None:
        """К имени без расширения добавляется расширение формата."""
        assert resolve_filename("My Video", "mp4") == "My Video.mp4"
        assert resolve_filename("My Video", "mp3") == "My Video.mp3"

    def test_preserves_matching_extension(self) -> None:
        """Совпадающее расширение сохраняется как есть."""
        assert resolve_filename("My Video.mp4", "mp4") == "My Video.mp4"

    def test_replaces_wrong_extension(self) -> None:
        """Расширение, не совпадающее с форматом, заменяется."""
        assert resolve_filename("My Video.mp3", "mp4") == "My Video.mp4"

    def test_unknown_dot_not_treated_as_extension(self) -> None:
        """Точка внутри имени (не известное расширение) не теряется."""
        assert resolve_filename("ft.初音ミク", "mp4") == "ft.初音ミク.mp4"

    def test_original_title_sanitized(self) -> None:
        """Слеш в названии заменяется, пробелы сохраняются."""
        result = resolve_filename("승인해주세요 지니님! / 카사네", "mp3")
        assert result == "승인해주세요 지니님! _ 카사네.mp3"


class TestRevealInFileManager:
    """Тесты для :func:`reveal_in_file_manager`.

    Основной способ выделения файла/папки - Windows Shell API (устойчив
    к спецсимволам в имени). ``explorer.exe`` используется только как
    фолбэк. Проверяем оба пути: при доступном Shell API Explorer не
    запускается, а при недоступном - запускается с корректными аргументами.
    Запуск Explorer и вызовы Shell API мокаются.
    """

    def test_existing_file_selects_in_new_explorer_window(
        self, tmp_path, monkeypatch
    ) -> None:
        """Фолбэк: файл передаётся Explorer с ``/n,/select,`` (новое окно)."""
        monkeypatch.setattr("src.utils.file_utils.sys.platform", "win32")
        target = tmp_path / "video.mp4"
        target.write_bytes(b"data")
        calls: list[tuple] = []
        monkeypatch.setattr(
            "src.utils.file_utils.subprocess.Popen",
            lambda *args, **kwargs: calls.append(args) or True,
        )
        monkeypatch.setattr(
            "src.utils.file_utils._shell_select_file", lambda *_: False
        )

        assert reveal_in_file_manager(str(target))
        assert calls == [(["explorer", "/n,/select," + str(target)],)]

    def test_existing_file_uses_shell_api(self, tmp_path, monkeypatch) -> None:
        """Если Shell API доступен, explorer.exe не запускается."""
        monkeypatch.setattr("src.utils.file_utils.sys.platform", "win32")
        target = tmp_path / "video.mp4"
        target.write_bytes(b"data")
        calls: list[tuple] = []
        monkeypatch.setattr(
            "src.utils.file_utils.subprocess.Popen",
            lambda *args, **kwargs: calls.append(args) or True,
        )
        shell_calls: list[tuple] = []
        monkeypatch.setattr(
            "src.utils.file_utils._shell_select_file",
            lambda d, f: shell_calls.append((d, f)) or True,
        )

        assert reveal_in_file_manager(str(target))
        assert shell_calls == [(str(tmp_path), "video.mp4")]
        assert calls == []

    def test_existing_folder_opens_in_explorer(self, tmp_path, monkeypatch) -> None:
        """Фолбэк: папка передаётся Explorer как обычный аргумент пути."""
        monkeypatch.setattr("src.utils.file_utils.sys.platform", "win32")
        calls: list[tuple] = []
        monkeypatch.setattr(
            "src.utils.file_utils.subprocess.Popen",
            lambda *args, **kwargs: calls.append(args) or True,
        )
        monkeypatch.setattr(
            "src.utils.file_utils._shell_open_folder", lambda *_: False
        )

        assert reveal_in_file_manager(str(tmp_path))
        assert calls == [(["explorer", str(tmp_path)],)]

    def test_existing_folder_uses_shell_api(self, tmp_path, monkeypatch) -> None:
        """Папка тоже открывается через Shell API, Explorer не нужен."""
        monkeypatch.setattr("src.utils.file_utils.sys.platform", "win32")
        calls: list[tuple] = []
        monkeypatch.setattr(
            "src.utils.file_utils.subprocess.Popen",
            lambda *args, **kwargs: calls.append(args) or True,
        )
        monkeypatch.setattr(
            "src.utils.file_utils._shell_open_folder", lambda *_: True
        )

        assert reveal_in_file_manager(str(tmp_path))
        assert calls == []

    def test_missing_file_opens_parent_folder(self, tmp_path, monkeypatch) -> None:
        """Удалeнный файл: открывается его родительская папка."""
        monkeypatch.setattr("src.utils.file_utils.sys.platform", "win32")
        missing = tmp_path / "gone.mp4"
        calls: list[tuple] = []
        monkeypatch.setattr(
            "src.utils.file_utils.subprocess.Popen",
            lambda *args, **kwargs: calls.append(args) or True,
        )
        monkeypatch.setattr(
            "src.utils.file_utils._shell_open_folder", lambda *_: False
        )

        assert reveal_in_file_manager(str(missing))
        assert calls == [(["explorer", str(tmp_path)],)]

    def test_missing_file_with_missing_parent_returns_false(
        self, tmp_path, monkeypatch
    ) -> None:
        """Если и файла, и родительской папки нет - ничего не открываем."""
        monkeypatch.setattr("src.utils.file_utils.sys.platform", "win32")
        calls: list[tuple] = []
        monkeypatch.setattr(
            "src.utils.file_utils.subprocess.Popen",
            lambda *args, **kwargs: calls.append(args) or True,
        )

        missing = tmp_path / "no" / "such" / "file.mp4"
        assert reveal_in_file_manager(str(missing)) is False
        assert calls == []

    def test_non_windows_returns_false(self, monkeypatch) -> None:
        monkeypatch.setattr("src.utils.file_utils.sys.platform", "linux")
        assert reveal_in_file_manager("whatever") is False

    def test_file_select_without_create_no_window_flag(
        self, tmp_path, monkeypatch
    ) -> None:
        """Explorer (фолбэк) не должен запускаться с CREATE_NO_WINDOW (иначе открывает "Документы")."""
        monkeypatch.setattr("src.utils.file_utils.sys.platform", "win32")
        target = tmp_path / "video.mp4"
        target.write_bytes(b"data")
        calls: list[tuple] = []
        monkeypatch.setattr(
            "src.utils.file_utils.subprocess.Popen",
            lambda *args, **kwargs: calls.append((args, kwargs)) or True,
        )
        monkeypatch.setattr(
            "src.utils.file_utils._shell_select_file", lambda *_: False
        )

        reveal_in_file_manager(str(target))

        assert calls
        _, kwargs = calls[0]
        assert kwargs.get("creationflags") is None

    def test_special_chars_passed_verbatim_to_shell(
        self, tmp_path, monkeypatch
    ) -> None:
        """Имя со спецсимволами (&, —, CJK) передаётся в Shell API как есть."""
        monkeypatch.setattr("src.utils.file_utils.sys.platform", "win32")
        filename = "MASA WORKS DESIGN - 春またいつか ft.初音ミク&鏡音リン.mp4"
        target = tmp_path / filename
        target.write_bytes(b"data")
        shell_calls: list[tuple] = []
        monkeypatch.setattr(
            "src.utils.file_utils._shell_select_file",
            lambda d, f: shell_calls.append((d, f)) or False,
        )

        reveal_in_file_manager(str(target))

        assert shell_calls == [(str(tmp_path), filename)]

    def test_special_chars_fallback_to_explorer(
        self, tmp_path, monkeypatch
    ) -> None:
        """Фолбэк explorer получает имя со спецсимволами без изменений."""
        monkeypatch.setattr("src.utils.file_utils.sys.platform", "win32")
        filename = "Френдзона — Молодость.mp4"
        target = tmp_path / filename
        target.write_bytes(b"data")
        calls: list[tuple] = []
        monkeypatch.setattr(
            "src.utils.file_utils.subprocess.Popen",
            lambda *args, **kwargs: calls.append(args) or True,
        )
        monkeypatch.setattr(
            "src.utils.file_utils._shell_select_file", lambda *_: False
        )

        assert reveal_in_file_manager(str(target))
        assert calls == [(["explorer", "/n,/select," + str(target)],)]

    def test_shell_select_file_missing_path_returns_false(self) -> None:
        """Несуществующий путь: Shell API не открывает окно и возвращает False.

        На Windows ``SHParseDisplayName`` завершится ошибкой, на других
        платформах ``ctypes.windll`` недоступен - в обоих случаях ``False``.
        """
        assert _shell_select_file("C:/definitely/not/here", "x.mp4") is False
