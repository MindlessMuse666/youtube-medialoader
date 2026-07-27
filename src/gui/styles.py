"""QSS-стили и загрузка шрифтов для неоновой темы YouTube Medialoader.

Цветовая палитра:
  - Фон: #0A0A0A
  - Акцент-голубой: #00E5FF
  - Акцент-розовый: #FF4081
  - Текст: #FFFFFF
  - Серый: #2A2A2A
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QFontDatabase


def _assets_dir() -> Path:
    """Вернуть путь к папке ``assets``.

    В режиме разработки — относительно этого файла,
    в собранном PyInstaller — относительно ``sys._MEIPASS``.
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "assets"  # type: ignore[arg-type]
    return Path(__file__).resolve().parent.parent.parent / "assets"


def load_fonts() -> None:
    """Загрузить TTF/OTF-шрифты из ``assets/fonts/`` в QFontDatabase."""
    fonts_dir = _assets_dir() / "fonts"
    if not fonts_dir.is_dir():
        return

    for font_file in fonts_dir.iterdir():
        if font_file.suffix.lower() in (".ttf", ".otf"):
            QFontDatabase.addApplicationFont(str(font_file))


MAIN_QSS = """
/* === Глобальные настройки === */
QMainWindow {
    background-color: transparent;
}

QWidget {
    background-color: transparent;
    color: #FFFFFF;
    font-family: "Inter", "NotoSansJP", sans-serif;
    font-size: 13px;
}

/* === Поля ввода === */
QLineEdit, QComboBox {
    background-color: #1A1A1A;
    border: 1px solid #2A2A2A;
    border-radius: 6px;
    padding: 8px 12px;
    color: #FFFFFF;
    font-size: 13px;
    min-height: 20px;
}

QLineEdit:hover, QComboBox:hover {
    border: 1px solid #555555;
    background-color: #1E1E1E;
}

QLineEdit:focus, QComboBox:focus {
    border: 1px solid #00E5FF;
}

QComboBox::drop-down {
    border: none;
    width: 30px;
}

QComboBox::down-arrow {
    image: none;
    border: none;
}

QComboBox QAbstractItemView {
    background-color: #1A1A1A;
    border: 1px solid #00E5FF;
    outline: none;
    padding: 4px;
}

QComboBox QAbstractItemView::item {
    color: #FFFFFF;
    padding: 6px 10px;
    min-height: 24px;
}

QComboBox QAbstractItemView::item:selected {
    background-color: #00E5FF;
    color: #0A0A0A;
}

/* === Прогресс-бар === */
QProgressBar {
    background-color: #1A1A1A;
    border: 1px solid #2A2A2A;
    border-radius: 4px;
    text-align: center;
    color: #FFFFFF;
    font-size: 12px;
    min-height: 28px;
}

QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #00E5FF, stop:1 #FF4081);
    border-radius: 3px;
}

/* === Область логов === */
QTextEdit#logArea {
    background-color: #1A1A1A;
    border: 1px solid #2A2A2A;
    border-radius: 6px;
    color: #CCCCCC;
    font-family: "Inter", monospace;
    font-size: 12px;
    padding: 8px;
}

/* === Заголовок === */
QLabel#titleLabel {
    font-family: "Press Start 2P";
    font-size: 18px;
    color: #00E5FF;
}

QLabel#subtitleLabel {
    font-family: "Press Start 2P";
    font-size: 9px;
    color: #FF4081;
}

/* === Информационные метки === */
QLabel#infoLabel {
    color: #AAAAAA;
    font-size: 12px;
}

QLabel#videoTitle {
    font-size: 14px;
    font-weight: bold;
    color: #FFFFFF;
}

QLabel#videoDetail {
    font-size: 12px;
    color: #AAAAAA;
}

/* === Метка фиксированной ширины для выравнивания === */
QLabel#fixedLabel {
    color: #AAAAAA;
    font-size: 12px;
    min-width: 75px;
}

/* === Группы === */
QGroupBox {
    border: 1px solid #2A2A2A;
    border-radius: 8px;
    margin-top: 24px;
    padding: 24px 12px 12px 12px;
    font-size: 13px;
    font-weight: normal;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    font-family: "Press Start 2P";
    font-size: 11px;
    color: #00E5FF;
}

/* === Кнопка "Очистить логи" === */
QPushButton#clearLogBtn {
    background-color: transparent;
    border: none;
    color: #555555;
    font-size: 11px;
    text-decoration: underline;
}

QPushButton#clearLogBtn:hover {
    color: #FF4081;
}

/* === Разделитель === */
QFrame#separator {
    background-color: #2A2A2A;
    max-height: 1px;
}

/* === Scroll area === */
QScrollArea {
    background: transparent;
    border: none;
}
"""
