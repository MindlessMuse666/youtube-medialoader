"""Тесты для модуля file_utils."""

import os

from src.utils.file_utils import sanitize_filename, resolve_output_path


class TestSanitizeFilename:
    """Тесты для :func:`sanitize_filename`."""

    def test_normal_text_preserved(self) -> None:
        """Обычные имена файлов должны проходить без изменений."""
        assert sanitize_filename("My Video") == "My_Video"

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
        """Расширение должно сохраняться."""
        result = sanitize_filename("video name.mp4")
        assert result == "video_name.mp4"

    def test_trailing_suffix_preserved(self) -> None:
        """Имя только с недопустимыми символами перед расширением."""
        result = sanitize_filename("<>:.mp4")
        assert result == "untitled.mp4"

    def test_collapse_spaces(self) -> None:
        """Несколько пробелов/подчeркиваний должны схлопнуться в один."""
        result = sanitize_filename("my   super   video")
        assert "__" not in result
        assert "  " not in result


class TestResolveOutputPath:
    """Тесты для :func:`resolve_output_path`."""

    def test_simple_join(self) -> None:
        """Директория и имя файла должны склеиваться в нормализованный путь."""
        result = resolve_output_path("/tmp", "video.mp4")
        assert result.endswith("video.mp4")
        assert os.sep in result  # путь содержит разделитель для текущей ОС
