"""Модульные тесты для PlaylistDialog (выбор видео из плейлиста).

Проверяют выбор/снятие всех, счётчик и фильтрацию при подтверждении.
"""

from __future__ import annotations

from src.gui.playlist_dialog import PlaylistDialog


def make_entries(n: int = 3) -> list[dict[str, object]]:
    """Хелпер: список словарей-видео, как возвращает downloader."""
    return [
        {
            "title": f"Video {i}",
            "url": f"https://youtube.com/watch?v={i}",
            "duration": 60 * i,
            "thumbnail": "",
            "index": i + 1,
        }
        for i in range(n)
    ]


class TestPlaylistSelection:
    """Выбор/снятие и обновление счётчика."""

    def test_all_selected_by_default(self, qapp) -> None:
        dialog = PlaylistDialog(make_entries(4))
        assert dialog._count_label.text() == "Выбрано: 4"
        dialog.close()

    def test_deselect_all_updates_counter(self, qapp) -> None:
        dialog = PlaylistDialog(make_entries(4))
        dialog._deselect_all()
        assert dialog._count_label.text() == "Выбрано: 0"
        dialog.close()

    def test_select_all_restores_counter(self, qapp) -> None:
        dialog = PlaylistDialog(make_entries(4))
        dialog._deselect_all()
        dialog._select_all()
        assert dialog._count_label.text() == "Выбрано: 4"
        dialog.close()

    def test_accept_selected_returns_only_checked(self, qapp) -> None:
        dialog = PlaylistDialog(make_entries(3))
        # Отмечаем только первое видео
        for widget in dialog._item_widgets[1:]:
            widget.is_checked = False
        dialog._update_count()

        dialog._accept_selected()

        assert [e["title"] for e in dialog.selected_entries] == ["Video 0"]
        assert dialog.result() == PlaylistDialog.DialogCode.Accepted

    def test_deselected_all_yields_empty_selection(self, qapp) -> None:
        dialog = PlaylistDialog(make_entries(3))
        dialog._deselect_all()

        dialog._accept_selected()

        assert dialog.selected_entries == []
