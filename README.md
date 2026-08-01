<div align="center">
  <img src="assets/icons/app_icon.png" alt="youtube_medialoader_logo.png" width="200" height="200" />
   <h1>YouTube Medialoader 🎈</h1>
   <p><b><i>Десктоп-приложение для скачивания видео и аудио с YouTube </br>ヾ(＠⌒ー⌒＠)ノ</i></b></p>
   <a href="https://www.python.org"><img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python" alt="Python" height="35"></a>
   <a href="https://www.qt.io/qt-for-python"><img src="https://img.shields.io/badge/PySide6-6.11-41CD52?style=for-the-badge&logo=qt" alt="PySide6" height="35"></a>
   <a href="https://github.com/yt-dlp/yt-dlp"><img src="https://img.shields.io/badge/yt--dlp-2024.7-FF0000?style=for-the-badge&logo=youtube" alt="yt-dlp" height="35"></a>
   <br/>
   <a href="https://github.com/MindlessMuse666/yappari/blob/main/LICENSE.md"><img src="https://img.shields.io/badge/AGPLv3-yellow?style=for-the-badge&logo=readme&logoColor=white" alt="AGPL v3" height="35"></a>
   <a href="https://www.microsoft.com/windows"><img src="https://img.shields.io/badge/Windows%2010%2F11-0078D4?style=for-the-badge&logo=windows" alt="Windows" height="35"></a>
</div>

---

## Общее описание

**YouTube Medialoader** - это десктопное приложение для скачивания видео (MP4) и аудио (MP3) с YouTube. Предпросмотр меты, обложка видео, выбор качества, очередь загрузки, поддержка плейлистов - и всe локально ✨

---

## Возможности

| Функция | Описание |
| --- | --- |
| 🎥 **Видео MP4** | Скачивание видео в 1080p / 720p / 480p |
| 🎵 **Аудио MP3** | Извлечение аудиодорожки в лучшем качестве |
| 🔍 **Предпросмотр** | Название, длительность, размер файла, обложка видео до загрузки |
| 📋 **Плейлисты** | Обнаружение плейлистов, выбор видео для загрузки |
| 🗂 **Очередь загрузки** | Последовательная загрузка нескольких видео |
| 🖼 **Обложка видео** | Отображение миниатюры видео в блоке предпросмотра |
| 📜 **История загрузок** | Таблица завершенных загрузок с возможностью открыть папку |
| 🚀 **Фоновые потоки** | Загрузка и получение информации в отдельных QThread |
| ⏹ **Отмена** | Прерывание загрузки в любой момент с удалением временного файла |
| 🍪 **Поддержка кук** | Опциональные куки браузера или файла для обхода блокировок, автоповтор без них при ошибке |
| 📊 **Расширенный прогресс** | Скорость, ETA и размер файла в реальном времени |
| 🎨 **Неоновая тема** | Анимированный темный фон, голубые акценты `#00E5FF`, розовые `#FF4081` |
| ⌨️ **Шорткаты** | `Ctrl+V`, `Enter`, `Escape`, `Ctrl+O`, `Ctrl+L` |
| 🖱 **Drag & Drop** | Перетаскивание ссылки из браузера прямо в окно |
| 🗂 **Открыть папку** | Кнопка открытия папки с файлом после загрузки |
| 🧩 **Системный трей** | Сворачивание в трей, алерт о завершении, открытие файла по клику |
| 🔄 **Проверка обновлений** | Автоматическая проверка новой версии на GitHub при старте |
| 🪶 **Легкий** | Минимум зависимостей: Python + PySide6 + yt-dlp |

---

## Скриншоты

### 🏠 После указания ссылки

<img src="screenshots/link_pasted_v2.png" alt="link_pasted_v2.png" width="800" />

### 🎉 Медиа успешно скачано

<img src="screenshots/media_success_load_and_alert_v2.png" alt="media_success_load_and_alert_v2.png" width="800" />
<img src="screenshots/media_success_load_and_logs_v2.png" alt="media_success_load_and_logs_v2.png" width="800" />

---

## Стек технологий

### Backend / Core

- **Python 3.12+** - язык разработки
- **PySide6 6.11** - нативный GUI (Qt6 для Python)
- **yt-dlp** - движок загрузки с YouTube
- **QThread** - асинхронные задачи

### UI

- **QSS** - кастомные стили
- **Press Start 2P** - локальный `.ttf` шрифт
- **QPropertyAnimation** - плавные анимации (fade-in, слайд-ин, раскрытие)
- **Animated Background** - градиентные сферы для глубины фона
- **QSystemTrayIcon** - системный трей с уведомлениями
- **QNetworkAccessManager** - асинхронная загрузка обложек и проверка обновлений
- **Drag & Drop** - поддержка перетаскивания ссылок из браузера

### Desktop

- **PyInstaller** - сборка в standalone EXE

---

## Быстрый старт

### Требования

- Windows 10/11
- Python 3.12+
- [FFmpeg](https://ffmpeg.org/download.html) (для MP3-конвертации и слияния видео+аудио)

### Шаги запуска

```powershell
# 1. склонируй репозиторий
git clone https://github.com/MindlessMuse666/youtube-medialoader.git
cd youtube-medialoader

# 2. создай виртуальное окружение и установи зависимости
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 3. запусти приложение
py -m src.main
```

### Сборка EXE

```powershell
# 1. перейди в .venv
.venv\Scripts\activate

# 2. если pyinstaller еще не установлен, то сделай это
pip install pyinstaller

# 3. собери бинарь командой
.\.venv\Scripts\pyinstaller --noconfirm --clean --onefile --windowed --name "YouTube Medialoader" --icon "assets\icons\app_icon.ico" --add-data "assets;assets" --collect-all "yt_dlp" --optimize 2 --exclude-module tkinter --exclude-module unittest --exclude-module pydoc --hidden-import "src.gui" --hidden-import "src.utils" --hidden-import "src.gui.animated_background" --hidden-import "src.gui.styles" --hidden-import "src.gui.widgets" --hidden-import "src.gui.worker" --hidden-import "src.gui.download_queue" --hidden-import "src.gui.playlist_dialog" --hidden-import "src.gui.history_dialog" --hidden-import "src.utils.constants" --hidden-import "src.utils.theme" --hidden-import "src.utils.file_utils" --hidden-import "src.utils.formatters" --hidden-import "src.utils.url_utils" --hidden-import "src.utils.logger" --hidden-import "src.utils.history" --hidden-import "src.utils.update_checker" "src\main.py"
```

> Готовый `.exe` появится в папке `dist/`.

---

## Разработка

### Структура проекта

```text
youtube-medialoader/
├── src/                          # Исходный код
│   ├── main.py                   # Точка входа
│   ├── downloader.py             # Движок загрузки (yt-dlp wrapper)
│   ├── gui/
│   │   ├── main_window.py        # Главное окно (MainWindow)
│   │   ├── widgets.py            # NeonButton, Toast, ProgressBar, Spinner
│   │   ├── styles.py             # QSS-стили + загрузка шрифтов
│   │   ├── worker.py             # QThread-задачи (VideoInfoWorker, DownloadWorker, PlaylistWorker)
│   │   ├── animated_background.py  # Анимированные сферы на фоне
│   │   ├── download_queue.py     # Виджет очереди загрузки
│   │   ├── playlist_dialog.py    # Диалог выбора видео из плейлиста
│   │   └── history_dialog.py     # Диалог истории загрузок
│   └── utils/
│       ├── constants.py          # Общие константы (имя, версия, GitHub-репо)
│       ├── theme.py              # Палитра темы (единый источник цветов)
│       ├── file_utils.py         # Очистка имен файлов, пути
│       ├── formatters.py         # Форматирование длительности, размера, скорости, ETA
│       ├── url_utils.py          # Валидация URL, определение плейлистов
│       ├── logger.py             # Qt-логгер с сигналами
│       ├── history.py            # Менеджер истории (QSettings + JSON)
│       └── update_checker.py     # Проверка обновлений на GitHub
├── assets/
│   ├── fonts/                    # PressStart2P-Regular.ttf
│   └── icons/                    # app_icon.ico, app_icon.png
├── tests/
│   ├── test_downloader.py        # Тесты загрузчика (моки yt-dlp)
│   ├── test_download_queue.py    # Тесты очереди загрузок
│   ├── test_file_utils.py        # Тесты утилит
│   ├── test_formatters.py        # Тесты форматтеров (длительность, размер, скорость)
│   ├── test_history_dialog.py    # Тесты диалога истории
│   ├── test_history_manager.py   # Тесты менеджера истории (QSettings + JSON)
│   ├── test_integration.py       # Opt-in сетевые тесты (YML_INTEGRATION=1)
│   ├── test_main_window_queue.py # Тесты очереди и потоков главного окна
│   ├── test_playlist_dialog.py   # Тесты диалога выбора видео из плейлиста
│   ├── test_update_checker.py    # Тесты проверки обновлений
│   ├── test_url_utils.py         # Тесты валидации URL и определения плейлистов
│   ├── test_worker.py            # Тесты worker-ов
│   ├── test_widgets.py           # Тесты виджетов
│   └── conftest.py               # Фикстуры pytest
├── pyproject.toml                # Мета и конфиг
├── requirements.txt              # Зависимости
└── README.md                     # Этот файл
```

### Команды

| Команда                           | Описание                                    |
| --------------------------------- | ------------------------------------------- |
| `py -m src.main`                  | Запуск приложения                           |
| `pytest tests/ -v`                | Запуск тестов + подробный отчет             |
| `py -m pytest -q`                 | Запуск тестов + краткий отчет о прохождении |
| `pip install -r requirements.txt` | Установка зависимостей                      |

### Тестирование

Проект покрыт модульными тестами с моками (без сети).

Тесты охватывают движок загрузки (форматы, куки, имена файлов, cookie-фоллбек), очередь загрузок, жизненный цикл потоков главного окна, валидацию URL, форматтеры, проверку обновлений, менеджер истории, диалог плейлиста и неоновые виджеты:

```bash
pytest tests/ -v --tb=short
```

### Интеграционные тесты (opt-in)

Для реальной проверки метаданных с YouTube доступен сетевой тест. По умолчанию он пропускается; включить его можно переменной окружения `YML_INTEGRATION=1`:

```powershell
# включить и запустить
$env:YML_INTEGRATION = "1"; pytest tests/test_integration.py -v

# сбросить после проверки
Remove-Item Env:YML_INTEGRATION
```

---

## Лицензия

Проект распространяется под лицензией [GNU AGPL v3](LICENSE.md).

---

<div align="center">
  <img src="assets/icons/app_icon.png" alt="app_icon.png" width="100" height="100" />
  <br>
  <sub><b>YouTube Medialoader // Видео и аудио с YouTube</b></sub>
  <br>
  <sup><i>made with ❤️ by <a href="https://github.com/MindlessMuse666" target="_blank">MindlessMuse666</a></i></sup>
</div>
