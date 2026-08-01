"""Модульные тесты для виджета очереди загрузок (download_queue.py).

Покрывают жизненный цикл очереди (добавление, смена статусов, очистка,
отмена) и авто-высоту списка - динамический размер контейнера вместо
фиксированного скролла.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLabel, QWidget

from src.gui.download_queue import (
    DownloadQueueWidget,
    QueueItem,
    QueueItemStatus,
    _format_details,
)


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
def queue(qapp) -> DownloadQueueWidget:
    """Новый виджет очереди под скрытым родителем (без реального окна).

    Родитель скрыт, поэтому ``isVisible()`` всегда ``False`` и авто-высота
    применяется без анимации - тесты получают детерминированный размер.
    """
    parent = QWidget()
    parent.hide()
    widget = DownloadQueueWidget(parent)
    # Держим родителя живым через ссылку на самом виджете: если обёртку
    # родителя соберёт сборщик мусора, его C++-объект удалится вместе с
    # дочерним виджетом, и тесты получат "Internal C++ object already deleted".
    setattr(widget, "_hidden_parent", parent)
    return widget


class TestQueueLifecycle:
    """Добавление элементов и смена статусов."""

    def test_new_widget_is_empty(self, queue: DownloadQueueWidget) -> None:
        assert queue.is_empty
        assert queue.title() == "ОЧЕРЕДЬ: 0"

    def test_add_item_updates_title_and_becomes_visible(
        self, queue: DownloadQueueWidget
    ) -> None:
        queue.add_item(make_item())
        assert queue.title() == "ОЧЕРЕДЬ: 1"
        assert not queue.isHidden()  # add_item вызывает setVisible(True)
        assert queue.next_pending() is not None

    def test_next_pending_returns_first_pending_in_order(
        self, queue: DownloadQueueWidget
    ) -> None:
        first = make_item(filename="a.mp4")
        second = make_item(filename="b.mp4")
        queue.add_item(first)
        queue.add_item(second)
        assert queue.next_pending() is first

    def test_next_pending_none_after_all_completed(
        self, queue: DownloadQueueWidget
    ) -> None:
        item = make_item()
        queue.add_item(item)
        queue.mark_completed(item)
        assert queue.next_pending() is None
        assert queue.is_empty

    def test_mark_downloading(self, queue: DownloadQueueWidget) -> None:
        item = make_item()
        queue.add_item(item)
        queue.mark_downloading(item)
        assert item.status is QueueItemStatus.DOWNLOADING
        assert not queue.has_pending()

    def test_mark_completed(self, queue: DownloadQueueWidget) -> None:
        item = make_item()
        queue.add_item(item)
        queue.mark_completed(item)
        assert item.status is QueueItemStatus.COMPLETED

    def test_mark_error_stores_message(self, queue: DownloadQueueWidget) -> None:
        item = make_item()
        queue.add_item(item)
        queue.mark_error(item, "boom")
        assert item.status is QueueItemStatus.ERROR
        assert item.error_text == "boom"

    def test_mark_cancelled(self, queue: DownloadQueueWidget) -> None:
        """Отмена помечает элемент как CANCELLED и убирает его из pending."""
        item = make_item()
        queue.add_item(item)
        queue.mark_cancelled(item)
        assert item.status is QueueItemStatus.CANCELLED
        assert queue.next_pending() is None
        assert queue.is_empty

    def test_clear_completed_keeps_pending(self, queue: DownloadQueueWidget) -> None:
        done = make_item(filename="a.mp4")
        pending = make_item(filename="b.mp4")
        queue.add_item(done)
        queue.add_item(pending)
        queue.mark_completed(done)
        queue._clear_completed()
        assert pending in queue._items
        assert done not in queue._items
        assert queue.title() == "ОЧЕРЕДЬ: 1"

    def test_clear_completed_hides_when_empty(self, queue: DownloadQueueWidget) -> None:
        item = make_item()
        queue.add_item(item)
        queue.mark_cancelled(item)
        queue._clear_completed()
        assert queue.title() == "ОЧЕРЕДЬ: 0"
        assert queue.is_empty


class TestQueueDynamicHeight:
    """Авто-высота списка: растёт с содержимым и ограничена максимумом.

    Высота читается через ``maximumHeight()``: у непоказанного виджета Qt не
    пересчитывает геометрию, поэтому ``height()`` мог бы вернуть старую
    (нераскладку) величину. ``setFixedHeight`` в ``_update_scroll_height``
    выставляет минимум и максимум равными цели - их и проверяем.
    """

    def test_scroll_height_grows_with_items(self, queue: DownloadQueueWidget) -> None:
        queue.add_item(make_item())
        height_1 = queue._scroll.maximumHeight()
        for _ in range(3):
            queue.add_item(make_item())
        height_4 = queue._scroll.maximumHeight()
        assert height_4 > height_1
        assert height_4 <= queue.MAX_HEIGHT

    def test_scroll_height_capped_at_max(self, queue: DownloadQueueWidget) -> None:
        for _ in range(30):
            queue.add_item(make_item())
        assert queue._scroll.maximumHeight() == queue.MAX_HEIGHT

    def test_scroll_height_at_least_min(self, queue: DownloadQueueWidget) -> None:
        queue.add_item(make_item())
        assert queue._scroll.maximumHeight() >= queue.MIN_HEIGHT

    def test_scroll_height_unchanged_when_count_stable(
        self, queue: DownloadQueueWidget
    ) -> None:
        """Смена статуса не меняет высоту - влияет только количество элементов."""
        item = make_item()
        queue.add_item(item)
        height_before = queue._scroll.maximumHeight()
        queue.mark_downloading(item)
        queue.mark_completed(item)
        assert queue._scroll.maximumHeight() == height_before


class TestQueueVerticalCentering:
    """Блок строк очереди центрируется по вертикали между двумя упорами."""

    def test_rows_sandwiched_between_stretches(
        self, queue: DownloadQueueWidget
    ) -> None:
        """Строки лежат между двумя упорами (индекс 0 и последний)."""
        queue.add_item(make_item())
        queue.add_item(make_item())
        layout = queue._list_layout
        assert layout.count() == 4
        assert layout.itemAt(0).spacerItem() is not None
        assert layout.itemAt(1).widget() is not None
        assert layout.itemAt(2).widget() is not None
        assert layout.itemAt(3).spacerItem() is not None

    def test_clear_keeps_two_stretches(self, queue: DownloadQueueWidget) -> None:
        """После очистки завершённых упоры сохраняются."""
        item = make_item()
        queue.add_item(item)
        queue.mark_completed(item)
        queue._clear_completed()
        layout = queue._list_layout
        assert layout.count() == 2
        assert layout.itemAt(0).spacerItem() is not None
        assert layout.itemAt(1).spacerItem() is not None


class TestQueueItemDetails:
    """Строка деталей формата/качества в записи очереди.

    Качество отображается только для видео: для MP3 выводится лишь
    расширение, без бессмысленного ``| 720p``.
    """

    def test_mp4_shows_quality(self) -> None:
        assert _format_details("mp4", "1080p") == "MP4 | 1080p"

    def test_mp3_omits_quality(self) -> None:
        assert _format_details("mp3", "720p") == "MP3"

    def test_format_type_case_insensitive(self) -> None:
        assert _format_details("MP3", "1080p") == "MP3"
        assert _format_details("MP4", "720p") == "MP4 | 720p"

    def test_mp3_widget_hides_quality(self, queue: DownloadQueueWidget) -> None:
        """В записи MP3 качество не отображается."""
        queue.add_item(make_item(format_type="mp3", quality="720p"))
        # itemAt(1): первая строка между двумя упорами (см. TestQueueVerticalCentering)
        labels = [
            lbl.text()
            for lbl in queue._list_layout.itemAt(1).widget().findChildren(QLabel)
        ]
        assert "720p" not in " ".join(labels)

    def test_mp4_widget_shows_quality(self, queue: DownloadQueueWidget) -> None:
        """В записи MP4 качество отображается."""
        queue.add_item(make_item(format_type="mp4", quality="1080p"))
        labels = [
            lbl.text()
            for lbl in queue._list_layout.itemAt(1).widget().findChildren(QLabel)
        ]
        assert "1080p" in " ".join(labels)
