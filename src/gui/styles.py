"""QSS-стили и загрузка шрифтов для неоновой темы YouTube Medialoader.

Цветовая палитра берeтся из :mod:`src.utils.theme` - единого источника
HEX-цветов. В шаблоне :data:`_MAIN_QSS_TEMPLATE` вместо литералов стоят
плейсхолдеры ``{CYAN}``, ``{BG}`` и т.п., которые подставляются в
:func:`get_main_qss`.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFontDatabase

from src.utils.file_utils import assets_dir
from src.utils.theme import (
    BG,
    BG_BLACK,
    BG_HOVER,
    BORDER,
    CYAN,
    GRAY,
    GRAY_DARKER,
    GREEN,
    PINK,
    TEXT,
    WHITE,
    YELLOW,
)

# Семейство пиксельного шрифта - устанавливается в load_fonts()
# Если Press Start 2P не загрузился, используется fallback "monospace"
PIXEL_FONT_FAMILY: str = "monospace"


def _assets_dir() -> Path:
    """Вернуть путь к папке ``assets`` (общий хелпер, см. file_utils)."""
    return assets_dir()


def load_fonts() -> None:
    """Загрузить TTF/OTF-шрифты из ``assets/fonts/`` в QFontDatabase.

    После загрузки проверяет, доступен ли "Press Start 2P", и обновляет
    :data:`PIXEL_FONT_FAMILY`.
    """
    global PIXEL_FONT_FAMILY  # noqa: PLW0603

    fonts_dir = _assets_dir() / "fonts"
    if not fonts_dir.is_dir():
        PIXEL_FONT_FAMILY = "monospace"
        return

    for font_file in fonts_dir.iterdir():
        if font_file.suffix.lower() in (".ttf", ".otf"):
            try:
                QFontDatabase.addApplicationFont(str(font_file))
            except Exception:
                # Игнорируем проблемные шрифты - приложение работает и с
                # системными шрифтами, просто неоновая тема будет менее заметна
                pass

    # Проверяем, что пиксельный шрифт действительно зарегистрирован
    if "Press Start 2P" in QFontDatabase.families():
        PIXEL_FONT_FAMILY = '"Press Start 2P", monospace'
    else:
        PIXEL_FONT_FAMILY = "monospace"


# Плейсхолдеры цветов темы в шаблоне QSS: имя -> HEX из src.utils.theme.
# PIXEL_FONT подставляется отдельно (значение меняется в load_fonts).
_THEME_PLACEHOLDERS = {
    "CYAN": CYAN,
    "PINK": PINK,
    "GREEN": GREEN,
    "YELLOW": YELLOW,
    "WHITE": WHITE,
    "TEXT": TEXT,
    "GRAY": GRAY,
    "GRAY_DARKER": GRAY_DARKER,
    "BORDER": BORDER,
    "BG": BG,
    "BG_HOVER": BG_HOVER,
    "BG_BLACK": BG_BLACK,
}


def get_main_qss() -> str:
    """Вернуть QSS-строку с подставленными шрифтом и цветами темы.

    Подставляет :data:`PIXEL_FONT_FAMILY` и HEX-цвета из :mod:`theme`
    в шаблон ``_MAIN_QSS_TEMPLATE``, чтобы избежать предупреждения
    ``QFont::setPointSize``, если шрифт Press Start 2P не загружен.
    """
    result = _MAIN_QSS_TEMPLATE.replace("{PIXEL_FONT}", PIXEL_FONT_FAMILY)
    for name, color in _THEME_PLACEHOLDERS.items():
        result = result.replace(f"{{{name}}}", color)
    return result


_MAIN_QSS_TEMPLATE = """
/* === Глобальные настройки === */
QMainWindow {
    background-color: transparent;
}

QWidget {
    background-color: transparent;
    color: {WHITE};
    font-family: {PIXEL_FONT};
    font-size: 13px;
}

/* === Поля ввода === */
QLineEdit {
    background-color: {BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 12px;
    color: {WHITE};
    font-size: 13px;
    min-height: 20px;
}

QComboBox {
    background-color: {BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 12px;
    color: {WHITE};
    font-size: 13px;
    min-height: 20px;
}

QLineEdit:hover, QComboBox:hover {
    border: 1px solid {GRAY_DARKER};
    background-color: {BG_HOVER};
}

QLineEdit:focus, QComboBox:focus {
    border: 1px solid {CYAN};
}

/* QLineEdit#folderPath - стили по умолчанию */

QComboBox::drop-down {
    border: none;
    width: 30px;
}

QComboBox::down-arrow {
    image: none;
    border: none;
}

QComboBox QAbstractItemView {
    background-color: {BG};
    border: 1px solid {CYAN};
    outline: none;
    padding: 4px;
    font-size: 13px;
}

QComboBox QAbstractItemView::item {
    color: {WHITE};
    padding: 6px 10px;
    min-height: 24px;
    font-size: 13px;
}

QComboBox QAbstractItemView::item:selected {
    background-color: {CYAN};
    color: {BG_BLACK};
}

/* === Область логов === */
QTextEdit#logArea {
    background-color: {BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
    color: {TEXT};
    font-size: 12px;
    padding: 8px;
}

/* === Кнопки (глобальный bold) === */
QPushButton {
    font-weight: bold;
}

/* === Заголовок === */
QLabel#titleLabel {
    font-family: {PIXEL_FONT};
    font-size: 16pt;
    color: {CYAN};
    font-weight: bold;
}

QLabel#subtitleLabel {
    font-family: {PIXEL_FONT};
    font-size: 9pt;
    color: {PINK};
    font-weight: bold;
}

/* === Информационные метки === */
QLabel#infoLabel {
    color: {GRAY};
    font-size: 12px;
}

QLabel#videoTitle {
    font-size: 14px;
    font-weight: bold;
    color: {WHITE};
}

QLabel#videoDetail {
    font-size: 12px;
    color: {GRAY};
}

/* === Метка фиксированной ширины для выравнивания === */
QLabel#fixedLabel {
    color: {GRAY};
    font-size: 12px;
    min-width: 115px;
    max-width: 115px;
    font-weight: normal;
}

/* === Группы === */
QGroupBox {
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 32px;
    padding: 10px 12px 8px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    font-family: {PIXEL_FONT};
    font-size: 9pt;
    color: {CYAN};
    font-weight: bold;
}

/* === Кнопки "ОЧИСТИТЬ ЛОГИ" / "ОЧИСТИТЬ ЗАВЕРШЁННЫЕ" === */
QPushButton#clearLogBtn, QPushButton#queueClearBtn {
    background-color: transparent;
    border: none;
    color: {GRAY_DARKER};
    font-size: 11px;
    min-height: 30px;
    padding: 4px 8px;
    text-decoration: underline;
}

QPushButton#clearLogBtn:hover, QPushButton#queueClearBtn:hover {
    color: {PINK};
}

/* === Кнопка "ИСТОРИЯ" === */
QPushButton#historyBtn {
    background-color: transparent;
    border: 1px solid {GREEN};
    border-radius: 4px;
    padding: 4px 12px;
    min-height: 30px;
    color: {GREEN};
    font-size: 11px;
}

QPushButton#historyBtn:hover {
    background-color: rgba(0, 255, 136, 0.1);
    color: {GREEN};
}

QPushButton:disabled {
    font-weight: normal;
}

/* === Разделитель === */
QFrame#separator {
    background-color: {BORDER};
    max-height: 1px;
}

/* === Scroll area === */
QScrollArea {
    background: transparent;
    border: none;
}

/* === Статус прогресса (скорость, ETA) === */
/* Горизонтальное центрирование задаётся в коде (setAlignment) - значение
   enum в qproperty с кавычками не применялось бы. */
QLabel#progressStatus {
    color: {GRAY};
    font-size: 11px;
    padding: 0px;
    margin: 0px;
}
"""
