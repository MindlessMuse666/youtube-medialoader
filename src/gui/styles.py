"""QSS-стили и загрузка шрифтов для неоновой темы YouTube Medialoader.

Цветовая палитра:
  - Фон: #0A0A0A
  - Акцент-голубой: #00E5FF
  - Акцент-розовый: #FF4081
  - Текст: #FFFFFF
  - Серый: #2A2A2A
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFontDatabase

from src.utils.file_utils import assets_dir

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


def get_main_qss() -> str:
    """Вернуть QSS-строку с корректным семейством пиксельного шрифта.

    Подставляет :data:`PIXEL_FONT_FAMILY` в шаблон ``MAIN_QSS``,
    чтобы избежать предупреждения ``QFont::setPointSize``, если
    шрифт Press Start 2P не загружен.
    """
    return _MAIN_QSS_TEMPLATE.replace("{PIXEL_FONT}", PIXEL_FONT_FAMILY)


_MAIN_QSS_TEMPLATE = """
/* === Глобальные настройки === */
QMainWindow {
    background-color: transparent;
}

QWidget {
    background-color: transparent;
    color: #FFFFFF;
    font-family: {PIXEL_FONT};
    font-size: 13px;
}

/* === Поля ввода === */
QLineEdit {
    background-color: #1A1A1A;
    border: 1px solid #2A2A2A;
    border-radius: 6px;
    padding: 8px 12px;
    color: #FFFFFF;
    font-size: 13px;
    min-height: 20px;
}

QComboBox {
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
    background-color: #1A1A1A;
    border: 1px solid #00E5FF;
    outline: none;
    padding: 4px;
    font-size: 13px;
}

QComboBox QAbstractItemView::item {
    color: #FFFFFF;
    padding: 6px 10px;
    min-height: 24px;
    font-size: 13px;
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
    color: #00E5FF;
    font-weight: bold;
}

QLabel#subtitleLabel {
    font-family: {PIXEL_FONT};
    font-size: 9pt;
    color: #FF4081;
    font-weight: bold;
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
    min-width: 115px;
    max-width: 115px;
    font-weight: normal;
}

/* === Группы === */
QGroupBox {
    border: 1px solid #2A2A2A;
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
    color: #00E5FF;
    font-weight: bold;
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

/* === Кнопка "История" === */
QPushButton#historyBtn {
    background-color: transparent;
    border: 1px solid #00FF88;
    border-radius: 4px;
    padding: 4px 10px;
    color: #00FF88;
    font-size: 11px;
}

QPushButton#historyBtn:hover {
    background-color: rgba(0, 255, 136, 0.1);
    color: #00FF88;
}

QPushButton:disabled {
    font-weight: normal;
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

/* === Статус прогресса (скорость, ETA) === */
QLabel#progressStatus {
    color: #AAAAAA;
    font-size: 11px;
    padding: 0px;
    margin: 0px;
    qproperty-alignment: 'AlignCenter';
}
"""
