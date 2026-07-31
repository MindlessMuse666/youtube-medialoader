"""Главное окно приложения YouTube Medialoader.

Содержит класс :class:`MainWindow` - основной QMainWindow с неоновой
тeмной темой и всем необходимым для загрузки видео/аудио с YouTube.
"""

from __future__ import annotations

import html
import os
import re
from typing import Any
from urllib.parse import urlparse

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QEvent,
    QMimeData,
    QObject,
    QPropertyAnimation,
    QSettings,
    Qt,
    QThread,
    QTimer,
    QUrl,
)
from PySide6.QtGui import QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtGui import (
    QCloseEvent,
    QDragEnterEvent,
    QDropEvent,
    QFont,
    QIcon,
    QKeySequence,
    QResizeEvent,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.gui.animated_background import AnimatedBackground
from src.gui.download_queue import DownloadQueueWidget, QueueItem, QueueItemStatus
from src.gui.styles import get_main_qss, load_fonts
from src.gui.widgets import LoadingSpinner, NeonButton, NeonProgressBar, Toast
from src.gui.history_dialog import HistoryDialog
from src.gui.playlist_dialog import PlaylistDialog
from src.gui.worker import DownloadWorker, PlaylistWorker, VideoInfoWorker
from src.utils.file_utils import (
    assets_dir,
    resolve_filename,
    reveal_in_file_manager,
)
from src.utils.history import HistoryEntry, HistoryManager


# Press Start 2P не содержит глифов эмодзи: без явного шрифта-фолбэка Qt
# рисует эмодзи системным шрифтом в уменьшенном размере. Эти константы
# используются в :meth:`MainWindow.log_message`, чтобы эмодзи в логах
# были читабельными на фоне пиксельного текста.
_EMOJI_FONT_STYLE = (
    "font-family: 'Segoe UI Emoji', 'Apple Color Emoji', "
    "'Noto Color Emoji', sans-serif; font-size: 16px;"
)

_EMOJI_RE = re.compile(
    "["
    "\U0001F000-\U0001FAFF"     # основные блоки эмодзи (лица, жесты, объекты)
    "\U00002300-\U000023FF"     # технические символы (⏳, ⏹, ⌚)
    "\U000025A0-\U000027BF"     # геометрия, символы, дингбаты (✅, ⚠)
    "\U00002B00-\U00002BFF"     # разные символы (⭐, ➡)
    "\U0001F1E6-\U0001F1FF"     # региональные индикаторы (флаги)
    "]+"
)


class MainWindow(QMainWindow):
    """Главное окно приложения.

    Содержит поля для ввода ссылки, выбора типа/качества, папки сохранения,
    имени файла, блок предпросмотра информации, кнопки управления, прогресс-бар
    и область логов.
    """

    MIN_WIDTH = 700
    MIN_HEIGHT = 600

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("YouTube Medialoader")
        self.setMinimumSize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self.resize(780, 720)

        # Флаг: пользователь вводил имя файла вручную?
        self._is_custom_filename = False

        # Последнее полученное название видео (для дефолтного имени файла).
        # Эти два атрибута должны существовать ДО _load_settings(): смена
        # формата при восстановлении настроек вызывает _on_type_changed.
        self._current_video_title: str = ""

        # Загружаем шрифты один раз при старте
        load_fonts()

        # Центральный виджет и общий layout
        self._setup_central_widget()

        # Применяем QSS (с учeтом доступности пиксельного шрифта)
        self.setStyleSheet(get_main_qss())

        # Загружаем сохранeнные настройки (геометрия, папка, тип/качество)
        self._load_settings()

        # Клавиатурные шорткаты
        self._setup_shortcuts()

        # Стартовая анимация fade-in
        self._start_fade_in()

        # Отслеживаем последнюю папку для QSettings
        self._last_save_path: str = ""

        # Network manager для асинхронной загрузки миниатюр
        self._network_manager = QNetworkAccessManager(self)
        self._network_manager.finished.connect(self._on_thumbnail_loaded)

        # Кеш миниатюр (URL -> QPixmap)
        self._thumbnail_cache: dict[str, QPixmap] = {}
        self._last_thumbnail_url: str = ""

        # Менеджер истории загрузок
        self._history_manager = HistoryManager()

        # Системный трей
        self._tray_icon: QSystemTrayIcon | None = None
        # Путь к файлу, показанному в последнем системном уведомлении.
        # По клику на уведомление открываем именно этот файл, даже если
        # после него уже успела начаться новая загрузка.
        self._notify_path: str | None = None
        self._setup_tray()

        # Состояние раскрытия панели управления
        self._controls_expanded = False

        # Таймер дебаунса для предпросмотра (500 мс после ввода ссылки)
        self._fetch_timer = QTimer(self)
        self._fetch_timer.setSingleShot(True)
        self._fetch_timer.setInterval(500)
        self._fetch_timer.timeout.connect(self._on_fetch_timer_timeout)

        # Ссылка на текущий поток и worker предпросмотра
        self._info_thread: QThread | None = None
        self._info_worker: VideoInfoWorker | None = None

        # Ссылка на текущий поток и worker загрузки
        self._download_thread: QThread | None = None
        self._download_worker: DownloadWorker | None = None

        # Текущий элемент очереди (если загрузка из очереди)
        self._current_queue_item: QueueItem | None = None

        # Счeтчик для игнорирования устаревших результатов
        self._fetch_seq: int = 0

        # Таймаут запроса информации (60 сек) - защита от зависания yt-dlp
        self._fetch_timeout_timer = QTimer(self)
        self._fetch_timeout_timer.setSingleShot(True)
        self._fetch_timeout_timer.setInterval(60_000)
        self._fetch_timeout_timer.timeout.connect(self._on_fetch_timeout)

    # ------------------------------------------------------------------
    # Настройки и шорткаты
    # ------------------------------------------------------------------

    def _load_settings(self) -> None:
        """Загрузить сохранeнные настройки приложения.

        Восстанавливает геометрию окна, последнюю папку сохранения,
        выбранный тип/качество и список недавних ссылок.
        """
        settings = QSettings("MindlessMuse666", "YouTube-Medialoader")

        # Геометрия окна
        geo = settings.value("window/geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        state = settings.value("window/state")
        if state is not None:
            self.restoreState(state)

        # Папка сохранения
        save_dir = settings.value("save/directory", "", type=str)
        if save_dir:
            self.path_input.setText(save_dir)
            self._last_save_path = save_dir

        # Тип формата (0 = MP4, 1 = MP3)
        fmt_idx = settings.value("save/format_type", 0, type=int)
        if fmt_idx in (0, 1):
            self.type_combo.setCurrentIndex(fmt_idx)

        # Качество (0 = 1080p, 1 = 720p, 2 = 480p)
        qual_idx = settings.value("save/quality", 1, type=int)
        # None бывает при повреждённых/нечисловых настройках - пропускаем.
        if qual_idx is not None and 0 <= qual_idx <= 2:
            self.quality_combo.setCurrentIndex(qual_idx)

        # Недавние ссылки (последние 10) - сохраняем для автодополнения
        recent_urls = settings.value("urls/recent", [], type=list)
        if recent_urls:
            completer = self.url_input.completer()
            if completer is not None:
                from PySide6.QtCore import QStringListModel
                completer.setModel(QStringListModel(recent_urls))
                completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def _save_settings(self) -> None:
        """Сохранить текущие настройки приложения."""
        settings = QSettings("MindlessMuse666", "YouTube-Medialoader")
        settings.setValue("window/geometry", self.saveGeometry())
        settings.setValue("window/state", self.saveState())
        settings.setValue("save/directory", self.path_input.text())
        settings.setValue("save/format_type", self.type_combo.currentIndex())
        settings.setValue("save/quality", self.quality_combo.currentIndex())

    def _setup_shortcuts(self) -> None:
        """Настроить клавиатурные шорткаты."""
        # Ctrl+V - вставить ссылку из буфера обмена и запустить предпросмотр
        QShortcut(QKeySequence("Ctrl+V"), self, self._on_paste_url)

        # Enter/Return - начать загрузку (если поле ввода в фокусе)
        QShortcut(QKeySequence("Return"), self, self._on_enter_pressed)

        # Escape - отменить загрузку
        QShortcut(QKeySequence("Escape"), self, self._on_cancel_clicked)

        # Ctrl+O - открыть диалог выбора папки
        QShortcut(QKeySequence("Ctrl+O"), self, self._on_browse_clicked)

        # Ctrl+L - очистить логи
        QShortcut(QKeySequence("Ctrl+L"), self, self._on_clear_log_clicked)

    def _setup_tray(self) -> None:
        """Настроить иконку в системном трее.

        Создаeт ``QSystemTrayIcon`` с контекстным меню (Показать/Скрыть,
        Выход). Если системный трей не поддерживается, инициализация
        пропускается без ошибок.
        """
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self._tray_icon = None
            return

        icon = QIcon()
        # Пробуем загрузить собственную иконку приложения
        icon_path = str(assets_dir() / "icons" / "app_icon.png")
        if os.path.isfile(icon_path):
            icon = QIcon(icon_path)
        else:
            # Fallback - стандартная иконка приложения
            icon = QApplication.windowIcon()

        self._tray_icon = QSystemTrayIcon(icon, self)
        self._tray_icon.setToolTip("YouTube Medialoader")

        # Контекстное меню
        tray_menu = QMenu(self)

        show_action = tray_menu.addAction("Показать / Скрыть")
        show_action.triggered.connect(self._toggle_tray_window)

        tray_menu.addSeparator()

        quit_action = tray_menu.addAction("Выход")
        quit_action.triggered.connect(self._quit_app)

        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.messageClicked.connect(self._on_tray_message_clicked)

        self._tray_icon.show()

    def _toggle_tray_window(self) -> None:
        """Показать или скрыть главное окно из трея."""
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def _on_tray_activated(
        self, reason: QSystemTrayIcon.ActivationReason
    ) -> None:
        """Обработать клик по иконке в трее.

        Args:
            reason: Причина активации (двойной клик, одинарный и т.д.).
        """
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._toggle_tray_window()

    def _on_tray_message_clicked(self) -> None:
        """Открыть скачанный файл по клику на системное уведомление.

        Показывает файл в Explorer с выделением (как кнопка «Открыть
        папку»). Если файл уже удалeн - открывает содержащую папку.
        """
        path = self._notify_path
        if not path:
            return

        if os.path.isfile(path):
            reveal_in_file_manager(path)
            return

        folder = os.path.dirname(path)
        if folder and os.path.isdir(folder):
            reveal_in_file_manager(folder)

    def _quit_app(self) -> None:
        """Полный выход из приложения (включая скрытие в трей).
        Отменяет активные загрузки и завершает процесс.
        """
        if self._tray_icon is not None:
            self._tray_icon.hide()
        # Отменяем загрузку если активна
        if self._download_worker is not None and self._download_thread is not None:
            self._on_cancel_clicked()
            # Уничтожаем поток
            if self._download_thread is not None:
                self._download_thread.quit()
                self._download_thread.wait(1000)
        QApplication.quit()

    def _on_paste_url(self) -> None:
        """Вставить URL из буфера обмена в поле ввода и запустить предпросмотр."""
        clipboard = QApplication.clipboard()
        if clipboard is None:
            return
        text = clipboard.text().strip()
        if text:
            self.url_input.setText(text)
            # Принудительно запускаем предпросмотр (без ожидания дебаунса)
            self._fetch_timer.stop()
            self._on_fetch_timer_timeout()

    def _on_enter_pressed(self) -> None:
        """Начать загрузку при нажатии Enter, если поле ввода в фокусе."""
        focused = QApplication.focusWidget()
        if focused in (self.url_input, self.filename_input):
            self._on_download_clicked()

    def _remember_url(self, url: str) -> None:
        """Добавить URL в список недавних (для автодополнения).

        Args:
            url: Ссылка на YouTube-видео.
        """
        settings = QSettings("MindlessMuse666", "YouTube-Medialoader")
        recent: list[str] = settings.value("urls/recent", [], type=list)
        # Удаляем дубликат если уже есть, добавляем в начало
        if url in recent:
            recent.remove(url)
        recent.insert(0, url)
        # Храним не более 10
        settings.setValue("urls/recent", recent[:10])

    # ------------------------------------------------------------------
    # Установка интерфейса
    # ------------------------------------------------------------------

    def _setup_central_widget(self) -> None:
        """Создать центральный виджет с прокруткой и layout."""
        central = QWidget(self)
        self.setCentralWidget(central)

        # Анимированный фон - растягиваем на весь central widget
        self._bg = AnimatedBackground(central)
        self._bg.lower()

        scroll = QScrollArea(central)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        scroll_content = QWidget()
        scroll_content.setObjectName("scrollContent")
        scroll.setWidget(scroll_content)

        # Основной layout
        layout = QVBoxLayout(scroll_content)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(20)

        # --- Собираем интерфейс ---
        self._build_header(layout)
        self._build_url_input(layout)
        self._build_type_quality(layout)
        self._build_save_section(layout)
        self._build_info_preview(layout)
        self._build_controls_section(layout)
        self._build_download_queue(layout)
        self._build_log_section(layout)

        layout.addStretch()

        # Обeртка центрального виджета
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def _build_header(self, parent: QVBoxLayout) -> None:
        """Заголовок окна: название + подзаголовок."""
        title = QLabel("YouTube Medialoader")
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        parent.addWidget(title)

        subtitle = QLabel("v2.0-unstable | mp4 / mp3 / плейлисты")
        subtitle.setObjectName("subtitleLabel")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        parent.addWidget(subtitle)

        sep = QFrame()
        sep.setObjectName("separator")
        parent.addWidget(sep)

    def _build_url_input(self, parent: QVBoxLayout) -> None:
        """Поле ввода ссылки на YouTube."""
        row = QHBoxLayout()
        row.setSpacing(8)

        label = QLabel("Ссылка:")
        label.setObjectName("fixedLabel")
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(label)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(
            "https://youtube.com/watch?v=...  или  https://youtu.be/..."
        )
        self.url_input.textChanged.connect(self._on_url_changed)
        row.addWidget(self.url_input, 1)

        # Спиннер загрузки информации
        self._loading_spinner = LoadingSpinner()
        row.addWidget(self._loading_spinner)

        parent.addLayout(row)

    def _build_type_quality(self, parent: QVBoxLayout) -> None:
        """Строка выбора типа (mp4/mp3) и качества видео."""
        row = QHBoxLayout()
        row.setSpacing(16)

        # Тип
        type_layout = QHBoxLayout()
        type_layout.setSpacing(6)
        type_label = QLabel("Тип:")
        type_label.setObjectName("fixedLabel")
        type_label.setMinimumWidth(50)
        type_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        type_layout.addWidget(type_label)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["Видео (MP4)", "Аудио (MP3)"])
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        self._fix_combo_font(self.type_combo)
        type_layout.addWidget(self.type_combo, 1)
        row.addLayout(type_layout)

        # Качество
        quality_layout = QHBoxLayout()
        quality_layout.setSpacing(6)
        quality_label = QLabel("Качество:")
        quality_label.setObjectName("fixedLabel")
        quality_label.setMinimumWidth(100)
        quality_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        quality_layout.addWidget(quality_label)

        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["1080p", "720p", "480p"])
        self.quality_combo.setCurrentIndex(1)  # 720p по умолчанию
        self._fix_combo_font(self.quality_combo)
        quality_layout.addWidget(self.quality_combo, 1)
        row.addLayout(quality_layout)

        # Сохраняем ссылку на лейбл качества для _on_type_changed
        self._quality_label = quality_label

        parent.addLayout(row)

    def _build_save_section(self, parent: QVBoxLayout) -> None:
        """Группа полей: папка сохранения и имя файла."""
        group = QGroupBox("СОХРАНЕНИЕ")
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(8)

        # Папка + кнопка ОБЗОР
        path_row = QHBoxLayout()
        path_row.setSpacing(8)

        folder_label = QLabel("Папка:")
        folder_label.setObjectName("fixedLabel")
        folder_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        path_row.addWidget(folder_label)

        self.path_input = QLineEdit()
        self.path_input.setReadOnly(True)
        self.path_input.setPlaceholderText("Выберите папку для сохранения...")
        self.path_input.setObjectName("folderPath")
        self.path_input.installEventFilter(self)
        path_row.addWidget(self.path_input, 1)

        self.browse_btn = NeonButton("ОБЗОР")
        self.browse_btn.setObjectName("browseBtn")
        self.browse_btn.clicked.connect(self._on_browse_clicked)
        path_row.addWidget(self.browse_btn)
        group_layout.addLayout(path_row)

        # Имя файла
        name_row = QHBoxLayout()
        name_row.setSpacing(8)

        name_label = QLabel("Название:")
        name_label.setObjectName("fixedLabel")
        name_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        name_row.addWidget(name_label)

        self.filename_input = QLineEdit()
        self.filename_input.setPlaceholderText("untitled")
        self.filename_input.textChanged.connect(self._on_filename_changed)
        name_row.addWidget(self.filename_input, 1)
        group_layout.addLayout(name_row)

        parent.addWidget(group)

    def _build_info_preview(self, parent: QVBoxLayout) -> None:
        """Блок предпросмотра информации о видео (скрыт до загрузки данных).

        Содержит миниатюру слева и текстовую информацию справа.
        """
        self.info_group = QGroupBox("ИНФОРМАЦИЯ")

        # Горизонтальный layout: обложка | текст
        info_h_layout = QHBoxLayout(self.info_group)
        info_h_layout.setSpacing(16)

        # Миниатюра видео
        self._thumbnail_label = QLabel()
        self._thumbnail_label.setObjectName("thumbnail")
        self._thumbnail_label.setFixedSize(160, 90)
        self._thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumbnail_label.setStyleSheet("""
            QLabel#thumbnail {
                background-color: #1A1A1A;
                border: 1px solid #2A2A2A;
                border-radius: 4px;
            }
        """)
        info_h_layout.addWidget(self._thumbnail_label)

        # Текстовая информация (вертикально)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(6)

        self.video_title_label = QLabel("Название: -")
        self.video_title_label.setObjectName("videoTitle")
        self.video_title_label.setWordWrap(True)
        self.video_title_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        text_layout.addWidget(self.video_title_label)

        self.video_duration_label = QLabel("Длительность: -")
        self.video_duration_label.setObjectName("videoDetail")
        self.video_duration_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        text_layout.addWidget(self.video_duration_label)

        self.video_size_label = QLabel("Размер: -")
        self.video_size_label.setObjectName("videoDetail")
        self.video_size_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        text_layout.addWidget(self.video_size_label)

        # Заполнитель внизу текстового блока
        text_layout.addStretch()

        info_h_layout.addLayout(text_layout, 1)

        # Скрыт - показывается анимацией maximumHeight
        self.info_group.setVisible(False)
        self.info_group.setMaximumHeight(0)

        parent.addWidget(self.info_group)

    def _build_controls_section(self, parent: QVBoxLayout) -> None:
        """Прогресс-бар и кнопки управления, изначально свeрнуты.

        Показываются с анимацией только когда пользователь ввeл ссылку.
        """
        self._controls_container = QWidget()
        controls_layout = QVBoxLayout(self._controls_container)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(12)

        # Прогресс-бар
        self.progress_bar = NeonProgressBar()
        controls_layout.addWidget(self.progress_bar)

        # Статус загрузки (скорость, ETA, размер)
        self._progress_status_label = QLabel("")
        self._progress_status_label.setObjectName("progressStatus")
        controls_layout.addWidget(self._progress_status_label)

        # Кнопки
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.download_btn = NeonButton("СКАЧАТЬ")
        self.cancel_btn = NeonButton("ОТМЕНА", accent_color="#FF4081")
        self.cancel_btn.setVisible(False)
        self.open_folder_btn = NeonButton("ОТКРЫТЬ ПАПКУ")
        self.open_folder_btn.setVisible(False)

        btn_row.addStretch()
        btn_row.addWidget(self.download_btn)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.open_folder_btn)
        btn_row.addStretch()
        controls_layout.addLayout(btn_row)

        # Подключаем кнопки загрузки
        self.download_btn.clicked.connect(self._on_download_clicked)
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        self.open_folder_btn.clicked.connect(self._on_open_folder_clicked)

        parent.addWidget(self._controls_container)

        # Скрываем по умолчанию (схлопнуто)
        self._controls_container.setMaximumHeight(0)
        self._controls_container.setVisible(False)

    def _build_download_queue(self, parent: QVBoxLayout) -> None:
        """Виджет очереди загрузок (скрыт, пока нет элементов)."""
        self._queue_widget = DownloadQueueWidget()
        parent.addWidget(self._queue_widget)
        self._queue_widget.queue_changed.connect(self._on_queue_changed)

    def _build_log_section(self, parent: QVBoxLayout) -> None:
        """Область логов с кнопкой очистки."""
        group = QGroupBox("ЛОГИ")
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(10)

        self.log_area = QTextEdit()
        self.log_area.setObjectName("logArea")
        self.log_area.setReadOnly(True)
        self.log_area.setMinimumHeight(140)
        group_layout.addWidget(self.log_area)

        log_btn_row = QHBoxLayout()
        self.history_btn = QPushButton("ИСТОРИЯ")
        self.history_btn.setObjectName("historyBtn")
        self.history_btn.clicked.connect(self._on_open_history)
        log_btn_row.addWidget(self.history_btn)

        log_btn_row.addStretch()

        self.clear_log_btn = QPushButton("ОЧИСТИТЬ ЛОГИ")
        self.clear_log_btn.setObjectName("clearLogBtn")
        log_btn_row.addWidget(self.clear_log_btn)
        group_layout.addLayout(log_btn_row)

        self.clear_log_btn.clicked.connect(self._on_clear_log_clicked)

        parent.addWidget(group)

    # ------------------------------------------------------------------
    # Обработчики событий
    # ------------------------------------------------------------------

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        """Перехватить изменение состояния окна (свѐртывание в трей).

        Args:
            event: Событие изменения состояния.
        """
        if (
            event.type() == QEvent.Type.WindowStateChange
            and self.isMinimized()
            and self._tray_icon is not None
        ):
            # Прячем в трей вместо панели задач
            self.hide()
            event.ignore()
            return
        super().changeEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Перехватить закрытие окна: сохранить настройки и проверить загрузку.

        Если идeт активная загрузка или есть элементы в очереди,
        показать диалог подтверждения.
        """
        has_active = self._download_worker is not None
        has_queued = (
            not self._queue_widget.is_empty or self._queue_widget.has_pending()
        )

        if has_active or has_queued:
            msg = "Загрузка ещe выполняется.\nОтменить и закрыть?"
            if has_queued and not has_active:
                msg = "В очереди есть ожидающие загрузки.\nОтменить и закрыть?"

            reply = QMessageBox.warning(
                self,
                "YouTube Medialoader",
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                if has_active:
                    self._on_cancel_clicked()
                self._queue_widget._items.clear()
            else:
                event.ignore()
                return

        # Сохраняем настройки перед закрытием
        self._save_settings()
        super().closeEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        """Принять перетаскивание, если это текстовая ссылка на YouTube.

        Args:
            event: Событие перетаскивания.
        """
        mime: QMimeData | None = event.mimeData()
        if mime is not None and mime.hasText():
            text = mime.text().strip()
            if self._validate_url(text) is None:
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        """Обработать сброшенную ссылку: вставить в поле ввода и запустить предпросмотр.

        Args:
            event: Событие сброса.
        """
        mime: QMimeData | None = event.mimeData()
        if mime is not None and mime.hasText():
            text = mime.text().strip()
            if self._validate_url(text) is None:
                self.url_input.setText(text)
                # Принудительно запускаем предпросмотр
                self._fetch_timer.stop()
                self._on_fetch_timer_timeout()
                self._remember_url(text)
                event.acceptProposedAction()
                return
        event.ignore()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Обновить размер фона при изменении окна."""
        super().resizeEvent(event)
        if hasattr(self, "_bg"):
            self._bg.setGeometry(self.centralWidget().rect())

    def eventFilter(  # noqa: N802
        self, watched: QObject, event: QEvent
    ) -> bool:
        """Перехватить клик по path_input как аналог кнопки "ОБЗОР".

        Args:
            watched: Отслеживаемый объект.
            event: Событие.

        Returns:
            True если событие обработано, иначе результат родителя.
        """
        if watched == self.path_input and event.type() == QEvent.Type.MouseButtonRelease:
            self._on_browse_clicked()
            return True
        return super().eventFilter(watched, event)

    def _on_url_changed(self, text: str) -> None:
        """Обработать изменение ссылки: дебаунс 500 мс, управление видимостью.

        Args:
            text: Текущее содержимое поля ввода ссылки.
        """
        has_text = bool(text.strip())

        # Раскрыть/схлопнуть панель управления
        if has_text and not self._controls_expanded:
            self._expand_controls()
        elif not has_text and self._controls_expanded:
            self._collapse_controls()

        # Новая ссылка в поле: сбрасываем результат предыдущей загрузки,
        # если сейчас ничего не скачивается (иначе прогресс-бар будет
        # висеть на "ЗАВЕРШЕНО!" от предыдущего видео).
        if (
            has_text
            and self._download_thread is None
            and hasattr(self, "progress_bar")
        ):
            self.progress_bar.reset()
            self._progress_status_label.setText("")
            # Результат старой загрузки сброшен - кнопка «Открыть папку»
            # к прежнему файлу больше не нужна.
            self.open_folder_btn.setVisible(False)

        # Сбросить предпросмотр при пустом поле
        if not has_text:
            self._cancel_pending_fetch()
            self._hide_info_preview()
            self._current_video_title = ""
            return

        # Перезапустить таймер дебаунса 500 мс
        self._fetch_timer.start()

    def _on_type_changed(self, index: int) -> None:
        """Скрыть/показать выбор качества при переключении на MP3.

        Расширение больше не хранится в поле имени файла, поэтому при смене
        типа формат подставится автоматически уже при самой загрузке.

        Args:
            index: 0 - Видео (MP4), 1 - Аудио (MP3).
        """
        is_audio = index == 1  # Аудио (MP3)
        # hasattr-защита: сигнал может прийти раньше создания виджетов
        # (например, при addItems() в _build_type_quality).
        if hasattr(self, "quality_combo"):
            self.quality_combo.setEnabled(not is_audio)
            self.quality_combo.setVisible(not is_audio)
        if hasattr(self, "_quality_label"):
            self._quality_label.setVisible(not is_audio)

    # ------------------------------------------------------------------
    # Асинхронный предпросмотр (Этап 3)
    # ------------------------------------------------------------------

    @staticmethod
    def _fix_combo_font(combo: QComboBox) -> None:
        """Явно задать шрифт комбобоксу и его выпадающему списку.

        Убирает предупреждение ``QFont::setPointSize: Point size <= 0 (-1)``,
        которое возникает при клике на комбобокс, если шрифт резолвится
        через QSS (особенно с пиксельным шрифтом Press Start 2P).

        Args:
            combo: Экземпляр QComboBox.
        """
        font = QFont("Press Start 2P", 10)
        combo.setFont(font)
        try:
            view = combo.view()
            if view is not None:
                view.setFont(font)
        except Exception:
            pass

    def _cancel_pending_fetch(self) -> None:
        """Отменить ожидающий запрос (без блокировки GUI).

        Поток не дожидается принудительно - старый поток завершается
        в фоне и автоматически удаляется через сигнал ``finished``.
        """
        self._fetch_timer.stop()
        self._fetch_timeout_timer.stop()
        self._loading_spinner.stop()
        self._fetch_seq += 1  # инвалидируем устаревшие результаты

        thread = self._info_thread
        worker = self._info_worker
        self._info_thread = None
        self._info_worker = None

        if thread is not None:
            # Отключаем все старые обработчики сигнала finished
            try:
                thread.finished.disconnect(self._on_fetch_finished)
            except TypeError:
                pass
            thread.quit()
            # Ждeм 50 мс - поток может уже завершиться; если нет -
            # удалим при срабатывании finished
            if not thread.wait(50):
                thread.finished.connect(thread.deleteLater)
            else:
                thread.deleteLater()

        if worker is not None:
            try:
                worker.info_fetched.disconnect()
                worker.error_occurred.disconnect()
            except TypeError:
                pass
            worker.deleteLater()

    def _on_fetch_timer_timeout(self) -> None:
        """Таймер дебаунса сработал - запустить асинхронное получение информации."""
        url = self.url_input.text().strip()
        if not url:
            return

        # Валидация URL перед запуском потока
        error = self._validate_url(url)
        if error is not None:
            self.show_toast(f"Неверная ссылка: {error}", Toast.ERROR)
            return

        # Запоминаем URL в недавних (для автодополнения)
        self._remember_url(url)

        self._cancel_pending_fetch()
        self._loading_spinner.start()
        self._hide_info_preview()

        # Проверяем, является ли URL плейлистом
        if self._is_playlist_url(url):
            self._fetch_playlist(url)
        else:
            self._fetch_video_info(url)

    @staticmethod
    def _is_playlist_url(url: str) -> bool:
        """Проверить, является ли ссылка ссылкой на плейлист.

        Args:
            url: Ссылка для проверки.

        Returns:
            ``True`` если URL содержит ``list=`` параметр.
        """
        parsed = urlparse(url)
        if "youtube.com" in parsed.netloc and "list=" in parsed.query:
            return True
        # youtu.be ссылки с list параметром
        if "youtu.be" in parsed.netloc and "list=" in parsed.query:
            return True
        return False

    def _fetch_video_info(self, url: str) -> None:
        """Запустить асинхронное получение информации о видео.

        Args:
            url: Ссылка на YouTube-видео.
        """
        # Создаeм поток и worker
        self._info_thread = QThread(self)
        self._info_worker = VideoInfoWorker(url)
        self._info_worker._fetch_seq = self._fetch_seq
        self._info_worker.moveToThread(self._info_thread)

        # Подключаем сигналы
        self._info_thread.started.connect(self._info_worker.run)
        self._info_worker.info_fetched.connect(self._on_info_fetched)
        self._info_worker.error_occurred.connect(self._on_info_error)

        self._info_thread.finished.connect(self._on_fetch_finished)

        self._info_thread.start()
        self._fetch_timeout_timer.start()

    def _fetch_playlist(self, url: str) -> None:
        """Запустить асинхронное получение списка видео из плейлиста.

        Args:
            url: Ссылка на YouTube-плейлист.
        """
        self._info_thread = QThread(self)
        self._info_worker = PlaylistWorker(url)
        self._info_worker._fetch_seq = self._fetch_seq
        self._info_worker.moveToThread(self._info_thread)

        self._info_thread.started.connect(self._info_worker.run)
        self._info_worker.playlist_fetched.connect(self._on_playlist_fetched)
        self._info_worker.error_occurred.connect(self._on_playlist_error)

        self._info_thread.finished.connect(self._on_fetch_finished)

        self._info_thread.start()
        self._fetch_timeout_timer.start()

    def _complete_fetch(self) -> None:
        """Безопасно завершить поток получения информации.

        Вызывается из ``_on_info_fetched`` и ``_on_info_error`` ПОСЛЕ
        обработки результата, чтобы избежать гонки, когда ``quit()``
        обнуляет ``_info_worker`` до того, как обработчик сигнала
        успевает его прочитать.
        """
        self._fetch_timeout_timer.stop()
        self._loading_spinner.stop()
        if self._info_thread is not None:
            self._info_thread.quit()

    def _on_fetch_finished(self) -> None:
        """Очистить поток и worker после завершения запроса."""
        # Проверяем, что это не устаревший вызов
        if self._info_worker is None:
            return
        if self._info_worker._fetch_seq != self._fetch_seq:
            return

        if self._info_thread is not None:
            self._info_thread.deleteLater()
            self._info_thread = None
        if self._info_worker is not None:
            self._info_worker.deleteLater()
            self._info_worker = None
        self._fetch_timeout_timer.stop()
        self._loading_spinner.stop()

    def _on_fetch_timeout(self) -> None:
        """Таймаут запроса информации - остановить поток и показать ошибку.

        Срабатывает через 60 секунд после старта запроса, если yt-dlp
        завис (например, из-за сетевых проблем или блокировки YouTube).
        """
        self._cancel_pending_fetch()
        self.show_toast(
            "Таймаут получения информации. Проверьте подключение к интернету.",
            Toast.ERROR,
        )

    def _on_info_fetched(self, info: dict) -> None:
        """Обработать успешное получение информации о видео.

        Обновляет блок предпросмотра и устанавливает дефолтное имя файла.

        Args:
            info: Словарь метаданных видео.
        """
        # Игнорируем устаревший результат от отменeнного запроса
        worker_seq = self._info_worker._fetch_seq if self._info_worker is not None else -1
        if worker_seq != self._fetch_seq:
            self._complete_fetch()
            return

        title: str = info.get("title", "Untitled")
        duration_secs: int = info.get("duration", 0)
        filesize: int | None = info.get("filesize")

        self._current_video_title = title

        # Форматируем данные для отображения
        duration_str = self._format_duration(duration_secs)
        size_str = self._format_filesize(filesize) if filesize else "неизвестно"

        # Обновляем блок предпросмотра с анимацией
        self.video_title_label.setText(f"Название: {title}")
        self.video_duration_label.setText(f"Длительность: {duration_str}")
        self.video_size_label.setText(f"Размер: {size_str}")
        self._show_info_preview()

        # Загружаем миниатюру
        thumbnail_url: str = info.get("thumbnail", "")
        self._load_thumbnail(thumbnail_url)

        # Если пользователь не вводил своe имя - подставляем оригинальное
        # название видео: без расширения и без замены пробелов подчeркиваниями.
        # Нужное расширение добавится при загрузке (см. resolve_filename).
        if not self._is_custom_filename:
            self.filename_input.setText(title)

        self._complete_fetch()

    def _on_info_error(self, error_text: str) -> None:
        """Обработать ошибку получения информации о видео.

        Args:
            error_text: Текст ошибки.
        """
        # Игнорируем устаревший результат от отменeнного запроса
        worker_seq = self._info_worker._fetch_seq if self._info_worker is not None else -1
        if worker_seq != self._fetch_seq:
            self._complete_fetch()
            return

        self._loading_spinner.stop()
        self.show_toast(
            f"Не удалось получить информацию: {error_text}",
            Toast.ERROR,
        )
        self._complete_fetch()

    def _on_playlist_fetched(self, entries: list[dict]) -> None:
        """Обработать успешное получение списка видео из плейлиста.

        Показывает диалог выбора видео и добавляет выбранные
        в очередь загрузки.

        Args:
            entries: Список словарей с данными видео из плейлиста.
        """
        # Игнорируем устаревший результат
        worker_seq = self._info_worker._fetch_seq if self._info_worker is not None else -1
        if worker_seq != self._fetch_seq:
            self._complete_fetch()
            return

        self._loading_spinner.stop()
        self._fetch_timeout_timer.stop()

        if not entries:
            self.show_toast("Плейлист пуст или недоступен", Toast.WARNING)
            self._complete_fetch()
            return

        # Показываем диалог выбора видео
        dialog = PlaylistDialog(entries, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected = dialog.selected_entries
            if selected:
                output_path = self.path_input.text().strip()
                if not output_path:
                    output_path = "."
                    self.path_input.setText(output_path)

                format_type = "mp4" if self.type_combo.currentIndex() == 0 else "mp3"
                quality = self.quality_combo.currentText()

                count = 0
                for entry in selected:
                    filename = resolve_filename(
                        entry.get("title", "untitled"), format_type
                    )

                    item = QueueItem(
                        url=entry.get("url", ""),
                        output_path=output_path,
                        filename=filename,
                        format_type=format_type,
                        quality=quality,
                        title=entry.get("title", "untitled"),
                    )
                    self._queue_widget.add_item(item)
                    count += 1

                self.log_message(
                    f"📋 Добавлено {count} видео из плейлиста в очередь",
                    "#00E5FF",
                )

                # Запускаем обработку очереди
                self._process_queue()
            else:
                self.show_toast("Не выбрано ни одного видео", Toast.WARNING)

        self._complete_fetch()

    def _on_playlist_error(self, error_text: str) -> None:
        """Обработать ошибку получения плейлиста.

        Args:
            error_text: Текст ошибки.
        """
        worker_seq = self._info_worker._fetch_seq if self._info_worker is not None else -1
        if worker_seq != self._fetch_seq:
            self._complete_fetch()
            return

        self._loading_spinner.stop()
        self.show_toast(f"Ошибка плейлиста: {error_text}", Toast.ERROR)
        self._complete_fetch()

    def _hide_info_preview(self) -> None:
        """Скрыть блок предпросмотра без анимации."""
        self.info_group.setVisible(False)
        self.info_group.setMaximumHeight(0)

    def _show_info_preview(self) -> None:
        """Плавно показать блок предпросмотра анимацией раскрытия.

        Анимируется ``maximumHeight`` от 0 до натуральной высоты -
        это позволяет избежать артефактов ``QGraphicsOpacityEffect``
        при скролле.
        """
        self.info_group.setVisible(True)
        # Сначала даeм layout рассчитаться
        self.info_group.setMaximumHeight(2000)
        # Сохраняем натуральную высоту
        target = max(self.info_group.sizeHint().height(), 40)
        # Сбрасываем для анимации от 0
        self.info_group.setMaximumHeight(0)
        self.info_group.repaint()  # принудительный рендер перед анимацией

        anim = QPropertyAnimation(self.info_group, b"maximumHeight", self)
        anim.setEndValue(target)
        anim.setDuration(350)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.valueChanged.connect(self._on_info_anim_step)
        anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

    def _on_info_anim_step(self, value: int) -> None:  # noqa: ARG002
        """При каждом шаге анимации обновляем layout для корректного скролла.

        Без этого QScrollArea не пересчитывает размер контента во время
        анимации maximumHeight, из-за чего блок информации может
        наслаиваться на соседние элементы.

        Args:
            value: Текущее значение анимируемого свойства (не используется).
        """
        parent = self.info_group.parentWidget()
        if parent is not None:
            lay = parent.layout()
            if lay is not None:
                lay.activate()
        self.info_group.updateGeometry()

    # ------------------------------------------------------------------
    # Выбор папки и имя файла (Этап 3)
    # ------------------------------------------------------------------

    def _on_browse_clicked(self) -> None:
        """Открыть диалог выбора папки для сохранения."""
        current_dir = self.path_input.text().strip() or ""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Выберите папку для сохранения",
            current_dir,
            QFileDialog.Option.ShowDirsOnly,
        )
        if directory:
            self.path_input.setText(directory)

    def _on_filename_changed(self, text: str) -> None:
        """Отследить, вводил ли пользователь имя файла вручную.

        Флаг сбрасывается, если имя совпадает с дефолтным (оригинальное
        название видео), и устанавливается при любом ручном изменении.

        Args:
            text: Текущее содержимое поля имени файла.
        """
        self._is_custom_filename = bool(text) and text != self._current_video_title

    # ------------------------------------------------------------------
    # Валидация URL
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_url(url: str) -> str | None:
        """Проверить, что ссылка является корректным YouTube-URL.

        Args:
            url: Ссылка для проверки.

        Returns:
            ``None`` если URL корректен, иначе строка с описанием ошибки.
        """
        url = url.strip()
        if not url:
            return "Ссылка пуста"

        # Должна начинаться с http:// или https://
        if not url.startswith(("http://", "https://")):
            return "Ссылка должна начинаться с http:// или https://"

        # Проверяем дублирование - явный признак мусора
        if url.count("youtube.com") > 1 or url.count("youtu.be") > 1:
            return "Обнаружено дублирование домена в ссылке"

        # Должна содержать youtube.com или youtu.be
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        if "youtube.com" not in netloc and "youtu.be" not in netloc:
            return "Ссылка должна вести на youtube.com или youtu.be"

        # Для youtube.com - нужен параметр v (id видео)
        if "youtube.com" in netloc:
            if not parsed.query:
                return "Не указан ID видео (параметр v=)"
            params = dict(param.split("=", 1) for param in parsed.query.split("&") if "=" in param)
            video_id = params.get("v", "")
            if not video_id:
                return "Не указан ID видео (параметр v=)"

        # Для youtu.be - нужен path
        if "youtu.be" in netloc:
            path = parsed.path.strip("/")
            if not path:
                return "Не указан ID видео"

        return None

    # ------------------------------------------------------------------
    # Форматтеры
    # ------------------------------------------------------------------

    @staticmethod
    def _format_duration(seconds: int) -> str:
        """Преобразовать секунды в читаемый формат ``ЧЧ:ММ:СС`` или ``ММ:СС``.

        Args:
            seconds: Длительность в секундах.

        Returns:
            Отформатированная строка длительности.
        """
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    @staticmethod
    def _format_filesize(size_bytes: int) -> str:
        """Преобразовать байты в читаемый размер (КБ, МБ, ГБ).

        Args:
            size_bytes: Размер в байтах.

        Returns:
            Отформатированная строка размера.
        """
        if size_bytes < 1024:
            return f"{size_bytes} Б"
        elif size_bytes < 1024**2:
            return f"{size_bytes / 1024:.1f} КБ"
        elif size_bytes < 1024**3:
            return f"{size_bytes / 1024**2:.1f} МБ"
        else:
            return f"{size_bytes / 1024**3:.2f} ГБ"

    # ------------------------------------------------------------------
    # Загрузка миниатюры (thumbnail)
    # ------------------------------------------------------------------

    def _load_thumbnail(self, url: str) -> None:
        """Асинхронно загрузить миниатюру видео по URL.

        Кеширует загруженные изображения в ``_thumbnail_cache``,
        чтобы избежать повторных запросов при повторном вводе той же ссылки.

        Args:
            url: URL миниатюры с YouTube.
        """
        self._thumbnail_label.clear()
        self._thumbnail_label.setText("")  # сброс плейсхолдера
        if not url:
            return
        # Проверяем кеш
        if url in self._thumbnail_cache:
            pixmap = self._thumbnail_cache[url]
            scaled = pixmap.scaled(
                158, 88,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._thumbnail_label.setPixmap(scaled)
            return
        # Запрашиваем
        self._last_thumbnail_url = url
        request = QNetworkRequest(QUrl(url))
        self._network_manager.get(request)

    def _on_thumbnail_loaded(self, reply: QNetworkReply) -> None:
        """Обработать завершение загрузки миниатюры.

        Сохраняет загруженное изображение в кеш и отображает его
        в ``_thumbnail_label``.

        Args:
            reply: Ответ от сетевого менеджера.
        """
        if reply.error() == QNetworkReply.NetworkError.NoError:
            data = reply.readAll()
            pixmap = QPixmap()
            if pixmap.loadFromData(data):
                url = reply.url().toString()
                self._thumbnail_cache[url] = pixmap
                scaled = pixmap.scaled(
                    158, 88,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._thumbnail_label.setPixmap(scaled)
        reply.deleteLater()

    # ------------------------------------------------------------------
    # Анимация раскрытия панели управления
    # ------------------------------------------------------------------

    def _expand_controls(self) -> None:
        """Плавно раскрыть панель с прогресс-баром и кнопками."""
        self._controls_container.setVisible(True)
        # Временно даeм большую высоту, чтобы layout рассчитал натуральный размер
        self._controls_container.setMaximumHeight(2000)
        QTimer.singleShot(0, self._do_expand)

    def _do_expand(self) -> None:
        """Вторая фаза раскрытия - анимация до натуральной высоты."""
        if self._controls_expanded:
            return
        target = max(self._controls_container.sizeHint().height(), 40)
        # Сбрасываем на 0, чтобы анимация шла от 0 -> target
        self._controls_container.setMaximumHeight(0)
        anim = QPropertyAnimation(
            self._controls_container, b"maximumHeight", self
        )
        anim.setEndValue(target)
        anim.setDuration(300)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
        self._controls_expanded = True

    def _collapse_controls(self) -> None:
        """Плавно схлопнуть панель управления."""
        anim = QPropertyAnimation(
            self._controls_container, b"maximumHeight", self
        )
        anim.setEndValue(0)
        anim.setDuration(200)
        anim.setEasingCurve(QEasingCurve.Type.InCubic)
        anim.finished.connect(self._on_collapsed)
        anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
        self._controls_expanded = False

    def _on_collapsed(self) -> None:
        """Скрыть контейнер после завершения схлопывания."""
        self._controls_container.setVisible(False)

    # ------------------------------------------------------------------
    # Анимации
    # ------------------------------------------------------------------

    def _start_fade_in(self) -> None:
        """Fade-in анимация при запуске окна."""
        self._fade_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setDuration(400)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

    # ------------------------------------------------------------------
    # Очередь загрузок
    # ------------------------------------------------------------------

    def _on_queue_changed(self) -> None:
        """Обработать изменение очереди (показать/скрыть виджет)."""
        if self._queue_widget.is_empty:
            pass  # очередь сама скрывается

    def _on_download_clicked(self) -> None:
        """Добавить видео в очередь загрузки.

        Проверяет URL, папку и имя файла, затем добавляет элемент
        в очередь. Если в данный момент ничего не скачивается,
        запускает обработку очереди.
        """
        url = self.url_input.text().strip()
        if not url:
            self.show_toast("Введите ссылку на видео", Toast.WARNING)
            return

        error = self._validate_url(url)
        if error is not None:
            self.show_toast(f"Неверная ссылка: {error}", Toast.ERROR)
            return

        output_path = self.path_input.text().strip()
        if not output_path:
            self.show_toast("Выберите папку для сохранения", Toast.WARNING)
            return

        filename = self.filename_input.text().strip()
        if not filename:
            filename = "untitled"

        format_type = "mp4" if self.type_combo.currentIndex() == 0 else "mp3"
        quality = self.quality_combo.currentText()

        # Создаeм элемент очереди: имя получает расширение выбранного формата
        safe_name = resolve_filename(filename, format_type)
        item = QueueItem(
            url=url,
            output_path=output_path,
            filename=safe_name,
            format_type=format_type,
            quality=quality,
            title=self._current_video_title or filename,
        )

        # Добавляем в очередь
        self._queue_widget.add_item(item)
        self._last_download_path = os.path.join(output_path, safe_name)

        self.log_message(
            f"📋 Добавлено в очередь: {item.title[:50]}",
            "#00E5FF",
        )

        # Запускаем обработку очереди. Если загрузка уже идёт, _process_queue
        # сам дождётся еe завершения и запустит этот элемент следующим.
        self._process_queue()

    def _process_queue(self) -> None:
        """Обработать следующий элемент в очереди.

        Берeт следующий ожидающий элемент из очереди и запускает
        его загрузку в отдельном потоке. Если загрузка уже активна -
        ничего не делает: еe завершение (или отмена) само запустит
        следующий элемент.
        """
        # Если загрузка уже идёт - не запускаем вторую параллельно.
        if self._download_thread is not None:
            return

        item = self._queue_widget.next_pending()
        if item is None:
            # Очередь пуста - разблокируем UI
            self.download_btn.setVisible(True)
            self.cancel_btn.setVisible(False)
            self.type_combo.setEnabled(True)
            self.quality_combo.setEnabled(True)
            self.log_message("✅ Все загрузки завершены", "#00FF88")
            return

        # Отмечаем как скачиваемый
        self._queue_widget.mark_downloading(item)
        self._current_queue_item = item

        # Блокируем UI на время загрузки: кнопку "СКАЧАТЬ" прячем, чтобы
        # пользователь не мог запустить параллельную загрузку.
        self.download_btn.setVisible(False)
        self.cancel_btn.setVisible(True)
        self.open_folder_btn.setVisible(False)
        self.type_combo.setEnabled(False)
        self.quality_combo.setEnabled(False)
        self.progress_bar.reset()
        self._progress_status_label.setText("")

        self.log_message(
            f"⏳ [{item.title[:40]}]: начинаем загрузку...",
            "#00E5FF",
        )

        # Сохраняем полный путь для кнопки "Открыть папку"
        self._last_download_path = os.path.join(item.output_path, item.filename)

        # Создаeм поток и worker
        thread = QThread(self)
        worker = DownloadWorker(
            url=item.url,
            output_path=item.output_path,
            filename=item.filename,
            format_type=item.format_type,
            quality=item.quality,
        )
        worker.moveToThread(thread)

        # Подключаем сигналы
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_download_progress)
        worker.finished.connect(self._on_download_finished)
        worker.error_occurred.connect(self._on_download_error)
        # Уборку привязываем к конкретной паре (thread, worker): когда старый
        # поток завершается уже после старта следующего, его finished-сигнал
        # не заденет новый поток (иначе - QThread: Destroyed while running).
        thread.finished.connect(
            lambda t=thread, w=worker: self._cleanup_download(t, w)
        )

        self._download_thread = thread
        self._download_worker = worker

        thread.start()

        self.log_message(
            f"📥 Скачивание в: {item.output_path}",
            "#00E5FF",
        )

    def _on_cancel_clicked(self) -> None:
        """Отменить текущую загрузку.

        Устанавливает ``cancel_event`` (yt-dlp остановится на ближайшем
        progress-hook), помечает элемент очереди как отменённый и переходит
        к следующему элементу очереди.
        """
        worker = self._download_worker
        thread = self._download_thread
        if worker is None and thread is None:
            return

        self.cancel_btn.setVisible(False)
        self.download_btn.setVisible(True)
        self.open_folder_btn.setVisible(False)
        self.type_combo.setEnabled(True)
        self.quality_combo.setEnabled(True)
        self.progress_bar.reset()
        self._progress_status_label.setText("")

        # Отмечаем элемент очереди как отменённый
        item = self._current_queue_item
        self._current_queue_item = None
        if item is not None:
            self._queue_widget.mark_cancelled(item)
            title = item.title or "файл"
            self.log_message(f"⏹ [{title[:40]}]: загрузка отменена", "#FFC107")
        else:
            self.log_message("⏹ Отмена загрузки...", "#FFC107")
        self.show_toast("Отмена загрузки…", Toast.WARNING)

        # Просим yt-dlp остановиться
        if worker is not None:
            worker.cancel_event.set()

        # Освобождаем ссылки до запуска следующего элемента: старый поток
        # доработает в фоне, а его finished-сигнал вызовет _cleanup_download
        # с явными ссылками и не заденет новый поток.
        self._download_worker = None
        self._download_thread = None

        if thread is not None:
            thread.quit()
            thread.wait(1000)

        # Запускаем следующий элемент очереди
        self._process_queue()

    def _on_download_progress(self, data: dict) -> None:
        """Обновить прогресс-бар на основе данных от yt-dlp.

        Отображает скорость, ETA и размер файла в статус-лейбле.

        Args:
            data: Словарь прогресса от :class:`YouTubeDownloader`.
        """
        # Игнорируем устаревшие сигналы от worker'а, который больше
        # не является текущим (например, при отмене предыдущей загрузки).
        if self.sender() is not self._download_worker:
            return

        status = data.get("status", "")
        if status == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate", 0)
            downloaded = data.get("downloaded_bytes", 0)
            if total and total > 0:
                percent = int(downloaded / total * 100)
                self.progress_bar.animate_to(percent)

            # Форматируем скорость
            speed = data.get("speed", 0)
            speed_str = ""
            if speed:
                if speed > 1_000_000:
                    speed_str = f"{speed / 1_000_000:.1f} MB/s"
                elif speed > 1_000:
                    speed_str = f"{speed / 1_000:.0f} KB/s"
                else:
                    speed_str = f"{speed:.0f} B/s"

            # ETA
            eta = data.get("eta", 0)
            eta_str = ""
            if eta and eta > 0:
                hours, remainder = divmod(int(eta), 3600)
                minutes, secs = divmod(remainder, 60)
                if hours > 0:
                    eta_str = f"{hours}:{minutes:02d}:{secs:02d}"
                else:
                    eta_str = f"{minutes}:{secs:02d}"

            # Размеры файлов
            dl_str = self._format_filesize(downloaded) if downloaded else "?"
            total_str = self._format_filesize(total) if total else "?"

            # Собираем строку статуса
            parts = [f"{dl_str} / {total_str}"]
            if speed_str:
                parts.append(speed_str)
            if eta_str:
                parts.append(f"осталось {eta_str}")

            self._progress_status_label.setText("  |  ".join(parts))

        elif status == "finished":
            self.progress_bar.animate_to(100)

    def _on_download_finished(self) -> None:
        """Обработать успешное завершение загрузки.

        Отмечает элемент в очереди как завершeнный, показывает
        кнопку "Открыть папку" и запускает следующий элемент очереди.
        """
        # Игнорируем устаревшие сигналы от worker'а, который больше
        # не является текущим (например, при отмене предыдущей загрузки).
        if self.sender() is not self._download_worker:
            return

        self.progress_bar.complete()
        self.cancel_btn.setVisible(False)
        self.open_folder_btn.setVisible(True)
        self._progress_status_label.setText("")

        # Захватываем ссылки до их обнуления: завершившийся поток будет
        # прибран _cleanup_download(thread, worker), когда его finished-сигнал
        # дойдёт до GUI-потока (возможно, уже после старта следующей загрузки).
        item = self._current_queue_item
        self._current_queue_item = None
        thread = self._download_thread
        self._download_worker = None
        self._download_thread = None

        if item is not None:
            self._queue_widget.mark_completed(item)
            title = item.title or "файл"
            self.log_message(f"✅ [{title[:40]}]: загрузка завершена!", "#00FF88")
            self.show_toast(f"Загрузка завершена: {title[:30]}", Toast.SUCCESS)

            # Уведомление в системный трей. Запоминаем путь к файлу, чтобы
            # клик по уведомлению открыл именно его (см. _on_tray_message_clicked).
            if self._tray_icon is not None:
                self._notify_path = self._last_download_path
                self._tray_icon.showMessage(
                    "YouTube Medialoader",
                    f"Загрузка завершена: {title[:50]}",
                    QSystemTrayIcon.MessageIcon.Information,
                    4000,
                )

            # Записываем в историю
            file_size = 0
            if self._last_download_path and os.path.isfile(self._last_download_path):
                file_size = os.path.getsize(self._last_download_path)
            entry = HistoryEntry(
                title=item.title or title,
                url=item.url,
                format_type=item.format_type,
                quality=item.quality,
                file_path=self._last_download_path or "",
                file_size=file_size,
            )
            self._history_manager.add(entry)
        else:
            self.log_message("✅ Загрузка завершена!", "#00FF88")
            self.show_toast("Загрузка завершена!", Toast.SUCCESS)

        if thread is not None:
            thread.quit()

        # Запускаем следующий элемент очереди
        self._process_queue()

    def _on_open_folder_clicked(self) -> None:
        """Открыть папку с файлом и выделить сам файл в Explorer.

        Если файл был удалeн или перемещeн - открывает содержащую папку
        и показывает предупреждение.
        """
        path = self._last_download_path or ""
        if not path:
            return

        if os.path.isfile(path):
            reveal_in_file_manager(path)
            return

        folder = os.path.dirname(path)
        if folder and os.path.isdir(folder):
            reveal_in_file_manager(folder)
        self.show_toast("Файл был удалён или перемещён", Toast.WARNING)

    def _on_download_error(self, error_text: str) -> None:
        """Обработать ошибку загрузки.

        Отмечает элемент в очереди как ошибочный и запускает
        следующий элемент очереди.

        Args:
            error_text: Текст ошибки.
        """
        # Игнорируем устаревшие сигналы от worker'а, который больше
        # не является текущим.
        if self.sender() is not self._download_worker:
            return

        self.cancel_btn.setVisible(False)
        self.open_folder_btn.setVisible(False)
        self.progress_bar.reset()
        self._progress_status_label.setText("")

        item = self._current_queue_item
        self._current_queue_item = None
        thread = self._download_thread
        self._download_worker = None
        self._download_thread = None

        if item is not None:
            self._queue_widget.mark_error(item, error_text)
            title = item.title or "файл"
            self.log_message(f"❌ [{title[:40]}]: {error_text}", "#FF4081")
            self.show_toast(f"Ошибка: {title[:30]}", Toast.ERROR)
        else:
            self.log_message(f"❌ Ошибка: {error_text}", "#FF4081")
            self.show_toast(f"Ошибка загрузки: {error_text}", Toast.ERROR)

        if thread is not None:
            thread.quit()

        # Запускаем следующий элемент очереди
        self._process_queue()

    def _cleanup_download(self, thread: QThread, worker: DownloadWorker) -> None:
        """Освободить ресурсы конкретного потока и worker'а.

        Принимает явные ссылки на завершившийся поток и worker: уборка
        одного потока никогда не заденет уже запущенный следующий
        (иначе при последовательной загрузке из очереди возникает
        ``QThread: Destroyed while thread '' is still running``).

        Args:
            thread: Завершившийся :class:`QThread`.
            worker: Связанный с ним :class:`DownloadWorker`.
        """
        if thread is self._download_thread:
            self._download_thread = None
        if worker is self._download_worker:
            self._download_worker = None
        worker.deleteLater()
        thread.deleteLater()

    def _on_clear_log_clicked(self) -> None:
        """Очистить область логов."""
        self.log_area.clear()

    def _on_open_history(self) -> None:
        """Открыть диалог истории загрузок."""
        dialog = HistoryDialog(self._history_manager, self)
        dialog.exec()

    # ------------------------------------------------------------------
    # Публичные методы (для использования из Worker)
    # ------------------------------------------------------------------

    @staticmethod
    def _wrap_emoji(text: str) -> str:
        """Обернуть эмодзи в ``<span>`` с обычным шрифтом и увеличенным размером.

        Press Start 2P не содержит глифов эмодзи, поэтому без явного
        шрифта-фолбэка они рисуются системным шрифтом и выглядят слишком
        мелкими. Параметр *text* уже должен быть экранирован как HTML.

        Args:
            text: Экранированный HTML-текст сообщения.

        Returns:
            Текст с обёрнутыми в ``<span>`` эмодзи.
        """
        return _EMOJI_RE.sub(
            lambda m: f'<span style="{_EMOJI_FONT_STYLE}">{m.group(0)}</span>',
            text,
        )

    def log_message(self, message: str, color: str = "#CCCCCC") -> None:
        """Добавить цветное сообщение в область логов.

        Текст экранируется от HTML-инъекций, а эмодзи оборачиваются
        в span с обычным шрифтом (см. :meth:`_wrap_emoji`).

        Args:
            message: Текст сообщения.
            color: CSS-цвет (например, ``"#00E5FF"``).
        """
        content = self._wrap_emoji(html.escape(message))
        self.log_area.append(f'<span style="color: {color}">{content}</span>')

    def show_toast(
        self, text: str, border_color: str = Toast.INFO
    ) -> None:
        """Показать всплывающее уведомление.

        Args:
            text: Текст уведомления.
            border_color: Цвет обводки (``Toast.INFO`` / ``Toast.SUCCESS`` / …).
        """
        toast = Toast(text, border_color, parent=self)
        toast.show()

    def update_video_info(
        self, title: str, duration: str, size: str
    ) -> None:
        """Обновить блок предпросмотра информации о видео.

        Args:
            title: Название видео.
            duration: Длительность (отформатированная строка).
            size: Размер (отформатированная строка).
        """
        self.video_title_label.setText(f"Название: {title}")
        self.video_duration_label.setText(f"Длительность: {duration}")
        self.video_size_label.setText(f"Размер: {size}")
        self._show_info_preview()
