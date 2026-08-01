"""Модульные тесты для кастомных виджетов (widgets.py).

Покрывают состояния NeonProgressBar: обычное заполнение, режим завершения
(``complete()`` -> "ЗАВЕРШЕНО!" + морф заливки в ``#FF4081``) и сброс.
Проверяются состояния-переходы без ожидания таймингов анимаций.
"""

from __future__ import annotations

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from src.gui.widgets import NeonProgressBar


@pytest.fixture
def progress(qapp) -> NeonProgressBar:
    """Прогресс-бар под скрытым родителем (без реального окна)."""
    parent = QWidget()
    parent.hide()
    widget = NeonProgressBar(parent)
    # Держим родителя живым: иначе сборщик мусора удалит его C++-объект
    # вместе с дочерним виджетом (Internal C++ object already deleted).
    setattr(widget, "_hidden_parent", parent)
    return widget


class TestNeonProgressBar:
    """Переходы состояний прогресс-бара."""

    def test_initial_state(self, progress: NeonProgressBar) -> None:
        assert progress.value() == 0
        assert progress._completed is False
        assert progress._mix == 0.0

    def test_set_value_no_animation(self, progress: NeonProgressBar) -> None:
        progress.setValue(42)
        assert progress.value() == 42

    def test_complete_sets_completed_and_targets(
        self, progress: NeonProgressBar
    ) -> None:
        """complete() включает режим завершения и цели анимаций."""
        progress.complete()
        assert progress._completed is True
        assert progress._fill_anim is not None
        assert progress._fill_anim.endValue() == 100.0
        assert progress._mix_anim is not None
        assert progress._mix_anim.endValue() == 1.0

    def test_animate_to_resets_completed(self, progress: NeonProgressBar) -> None:
        """Обычная заливка снимает режим завершения и его анимацию."""
        progress.complete()
        progress.animate_to(50)
        assert progress._completed is False
        assert progress._mix == 0.0
        assert progress._mix_anim is None
        assert progress._fill_anim is not None
        assert progress._fill_anim.endValue() == 50.0

    def test_reset_clears_all_state(self, progress: NeonProgressBar) -> None:
        """Сброс убирает и заливку, и режим завершения."""
        progress.complete()
        progress.reset()
        assert progress.value() == 0
        assert progress._completed is False
        assert progress._mix == 0.0
        assert progress._fill_anim is None
        assert progress._mix_anim is None

    def test_complete_after_natural_finish(self, progress: NeonProgressBar) -> None:
        """complete() не падает, если предыдущая анимация завершилась сама.

        Регрессия: с политикой ``DeleteWhenStopped`` C++-объект анимации
        удаляется после естественного завершения, а Python-атрибут
        ``_fill_anim`` держит ссылку на удалeнный объект -> следующий вызов
        ``_stop_anims()`` падал с ``RuntimeError``. Event loop здесь крутится
        реально (``QTest.qWait``), чтобы анимация успела завершиться.
        """
        progress.animate_to(100)
        QTest.qWait(600)  # заполнение доходит до конца и удаляется C++ стороной
        progress.complete()  # раньше: RuntimeError в _stop_anims()
        assert progress._completed is True
        assert progress._fill_anim is not None
        assert progress._fill_anim.endValue() == 100.0

    def test_reset_after_natural_finish(self, progress: NeonProgressBar) -> None:
        """reset() не падает, если предыдущая анимация завершилась сама."""
        progress.animate_to(100)
        QTest.qWait(600)
        progress.reset()
        assert progress.value() == 0
        assert progress._completed is False
        assert progress._fill_anim is None
        assert progress._mix_anim is None
