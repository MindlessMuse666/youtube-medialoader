"""Главное окно приложения YouTube Medialoader.

Содержит класс :class:`MainWindow` — основной QMainWindow с неоновой
тёмной темой и всем необходимым для загрузки видео/аудио с YouTube.
"""

from __future__ import annotations

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    QTimer,
)
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.gui.animated_background import AnimatedBackground
from src.gui.styles import MAIN_QSS, load_fonts
from src.gui.widgets import NeonButton, NeonProgressBar, Toast


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

        # Загружаем шрифты один раз при старте
        load_fonts()

        # Центральный виджет и общий layout
        self._setup_central_widget()

        # Применяем QSS
        self.setStyleSheet(MAIN_QSS)

        # Стартовая анимация fade-in
        self._start_fade_in()

        # Состояние раскрытия панели управления
        self._controls_expanded = False

    # ------------------------------------------------------------------
    # Установка интерфейса
    # ------------------------------------------------------------------

    def _setup_central_widget(self) -> None:
        """Создать центральный виджет с прокруткой и layout."""
        central = QWidget(self)
        self.setCentralWidget(central)

        # Анимированный фон — растягиваем на весь central widget
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
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # --- Собираем интерфейс ---
        self._build_header(layout)
        self._build_url_input(layout)
        self._build_type_quality(layout)
        self._build_save_section(layout)
        self._build_info_preview(layout)
        self._build_controls_section(layout)
        self._build_log_section(layout)

        layout.addStretch()

        # Обёртка центрального виджета
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def _build_header(self, parent: QVBoxLayout) -> None:
        """Заголовок окна: название + подзаголовок."""
        title = QLabel("YouTube Medialoader")
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        parent.addWidget(title)

        subtitle = QLabel("v0.1.0  |  mp4 / mp3")
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
        type_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        type_layout.addWidget(type_label)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["Видео (MP4)", "Аудио (MP3)"])
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        type_layout.addWidget(self.type_combo, 1)
        row.addLayout(type_layout)

        # Качество
        quality_layout = QHBoxLayout()
        quality_layout.setSpacing(6)
        quality_label = QLabel("Качество:")
        quality_label.setObjectName("fixedLabel")
        quality_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        quality_layout.addWidget(quality_label)

        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["1080p", "720p", "480p"])
        self.quality_combo.setCurrentIndex(1)  # 720p по умолчанию
        quality_layout.addWidget(self.quality_combo, 1)
        row.addLayout(quality_layout)

        parent.addLayout(row)

    def _build_save_section(self, parent: QVBoxLayout) -> None:
        """Группа полей: папка сохранения и имя файла."""
        group = QGroupBox("Сохранение")
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(8)

        # Папка + кнопка Обзор
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
        path_row.addWidget(self.path_input, 1)

        self.browse_btn = NeonButton("Обзор")
        self.browse_btn.setObjectName("browseBtn")
        path_row.addWidget(self.browse_btn)
        group_layout.addLayout(path_row)

        # Имя файла
        name_row = QHBoxLayout()
        name_row.setSpacing(8)

        name_label = QLabel("Имя файла:")
        name_label.setObjectName("fixedLabel")
        name_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        name_row.addWidget(name_label)

        self.filename_input = QLineEdit()
        self.filename_input.setPlaceholderText("untitled")
        name_row.addWidget(self.filename_input, 1)
        group_layout.addLayout(name_row)

        parent.addWidget(group)

    def _build_info_preview(self, parent: QVBoxLayout) -> None:
        """Блок предпросмотра информации о видео (скрыт до загрузки данных)."""
        self.info_group = QGroupBox("Информация")
        info_layout = QVBoxLayout(self.info_group)
        info_layout.setSpacing(4)

        self.video_title_label = QLabel("Название: —")
        self.video_title_label.setObjectName("videoTitle")
        info_layout.addWidget(self.video_title_label)

        self.video_duration_label = QLabel("Длительность: —")
        self.video_duration_label.setObjectName("videoDetail")
        info_layout.addWidget(self.video_duration_label)

        self.video_size_label = QLabel("Размер: —")
        self.video_size_label.setObjectName("videoDetail")
        info_layout.addWidget(self.video_size_label)

        # По умолчанию скрыт — показывается после получения данных
        self.info_group.setVisible(False)
        parent.addWidget(self.info_group)

    def _build_controls_section(self, parent: QVBoxLayout) -> None:
        """Прогресс-бар и кнопки управления, изначально свёрнуты.

        Показываются с анимацией только когда пользователь ввёл ссылку.
        """
        self._controls_container = QWidget()
        controls_layout = QVBoxLayout(self._controls_container)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(12)

        # Прогресс-бар
        self.progress_bar = NeonProgressBar()
        controls_layout.addWidget(self.progress_bar)

        # Кнопки
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.download_btn = NeonButton("СКАЧАТЬ")
        self.cancel_btn = NeonButton("ОТМЕНА")
        self.cancel_btn.setEnabled(False)

        btn_row.addStretch()
        btn_row.addWidget(self.download_btn)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addStretch()
        controls_layout.addLayout(btn_row)

        parent.addWidget(self._controls_container)

        # Скрываем по умолчанию (схлопнуто)
        self._controls_container.setMaximumHeight(0)
        self._controls_container.setVisible(False)

    def _build_log_section(self, parent: QVBoxLayout) -> None:
        """Область логов с кнопкой очистки."""
        group = QGroupBox("Логи")
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(6)

        self.log_area = QTextEdit()
        self.log_area.setObjectName("logArea")
        self.log_area.setReadOnly(True)
        self.log_area.setMinimumHeight(140)
        group_layout.addWidget(self.log_area)

        log_btn_row = QHBoxLayout()
        log_btn_row.addStretch()
        self.clear_log_btn = QPushButton("Очистить логи")
        self.clear_log_btn.setObjectName("clearLogBtn")
        log_btn_row.addWidget(self.clear_log_btn)
        group_layout.addLayout(log_btn_row)

        parent.addWidget(group)

    # ------------------------------------------------------------------
    # Обработчики событий
    # ------------------------------------------------------------------

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Обновить размер фона при изменении окна."""
        super().resizeEvent(event)
        if hasattr(self, "_bg"):
            self._bg.setGeometry(self.centralWidget().rect())

    def _on_url_changed(self, text: str) -> None:
        """Раскрыть/схлопнуть панель управления при вводе ссылки.

        Args:
            text: Текущее содержимое поля ввода ссылки.
        """
        has_text = bool(text.strip())
        if has_text and not self._controls_expanded:
            self._expand_controls()
        elif not has_text and self._controls_expanded:
            self._collapse_controls()

    def _on_type_changed(self, index: int) -> None:
        """Скрыть/показать выбор качества при переключении на MP3.

        Args:
            index: 0 — Видео (MP4), 1 — Аудио (MP3).
        """
        is_audio = index == 1  # Аудио (MP3)
        self.quality_combo.setEnabled(not is_audio)
        self.quality_combo.setVisible(not is_audio)
        # Находим лейбл качества (идущий перед комбобоксом)
        parent_widget = self.quality_combo.parent()
        if parent_widget is not None:
            for lbl in parent_widget.findChildren(QLabel):
                if lbl.text() == "Качество:":
                    lbl.setVisible(not is_audio)
                    break

    # ------------------------------------------------------------------
    # Анимация раскрытия панели управления
    # ------------------------------------------------------------------

    def _expand_controls(self) -> None:
        """Плавно раскрыть панель с прогресс-баром и кнопками."""
        self._controls_container.setVisible(True)
        # Временно даём большую высоту, чтобы layout рассчитал натуральный размер
        self._controls_container.setMaximumHeight(2000)
        QTimer.singleShot(0, self._do_expand)

    def _do_expand(self) -> None:
        """Вторая фаза раскрытия — анимация до натуральной высоты."""
        if self._controls_expanded:
            return
        target = max(self._controls_container.sizeHint().height(), 40)
        # Сбрасываем на 0, чтобы анимация шла от 0 → target
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
    # Публичные методы (для использования из Worker)
    # ------------------------------------------------------------------

    def log_message(self, message: str, color: str = "#CCCCCC") -> None:
        """Добавить цветное сообщение в область логов.

        Args:
            message: Текст сообщения.
            color: CSS-цвет (например, ``"#00E5FF"``).
        """
        self.log_area.append(f'<span style="color: {color}">{message}</span>')

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
        self.info_group.setVisible(True)
