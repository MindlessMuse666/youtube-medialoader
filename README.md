<div align="center">
  <img src="assets/icons/app_icon.png" alt="youtube_medialoader_logo.png" width="200" height="200" />
   <h1>YouTube Medialoader 🎬</h1>
   <p><b><i>Десктоп-приложение для скачивания видео и аудио с YouTube ( ͡° ͜ʖ ͡°)</i></b></p>
   <a href="https://www.python.org"><img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python" alt="Python" height="35"></a>
   <a href="https://www.qt.io/qt-for-python"><img src="https://img.shields.io/badge/PySide6-6.11-41CD52?style=for-the-badge&logo=qt" alt="PySide6" height="35"></a>
   <a href="https://github.com/yt-dlp/yt-dlp"><img src="https://img.shields.io/badge/yt--dlp-2024.7-FF0000?style=for-the-badge&logo=youtube" alt="yt-dlp" height="35"></a>
   <br/>
   <a href="https://github.com/MindlessMuse666/yappari/blob/main/LICENSE.md"><img src="https://img.shields.io/badge/AGPLv3-yellow?style=for-the-badge&logo=readme&logoColor=white" alt="AGPL v3" height="35"></a>
   <a href="https://www.microsoft.com/windows"><img src="https://img.shields.io/badge/Windows%2010%2F11-0078D4?style=for-the-badge&logo=windows" alt="Windows" height="35"></a>
</div>

---

## Общее описание

**YouTube Medialoader** - это десктопное приложение для скачивания видео (MP4) и аудио (MP3) с YouTube. Быстрый предпросмотр метаданных, выбор качества - всe локально ✨

---

## Возможности

| Функция | Описание |
| ------- | -------- |
| 🎥 **Видео MP4** | Скачивание видео в 1080p / 720p / 480p |
| 🎵 **Аудио MP3** | Извлечение аудиодорожки в лучшем качестве |
| 🔍 **Предпросмотр** | Название, длительность, размер файла до загрузки |
| 🚀 **Фоновые потоки** | Загрузка и получение информации в отдельных QThread |
| ⏹ **Отмена** | Прерывание загрузки в любой момент с удалением временного файла |
| 🎨 **Неоновая тема** | Анимированный тeмный фон, голубые акценты `#00E5FF`, розовые `#FF4081` |
| ⌨️ **Простой UI** | Интуитивный интерфейс: ссылка -> предпросмотр -> скачивание |
| 🪶 **Лeгкий** | Минимум зависимостей: Python + PySide6 + yt-dlp |

---

## Скриншоты

### 🏠 После указания ссылки

<img src="screenshots/link_pasted_v1.png" alt="link_pasted_v1.png" width="800" />

### 🎉 Медиа успешно скачано

<img src="screenshots/media_success_load_v1.png" alt="media_success_load_v1.png" width="800" />

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

### Desktop

- **Nuitka** - сборка в standalone EXE

---

## Быстрый старт

### Требования

- Windows 10/11
- Python 3.12+
- [FFmpeg](https://ffmpeg.org/download.html) (для MP3-конвертации и слияния видео+аудио)

### Шаги запуска

```bash
# 1. склонируй репозиторий
git clone https://github.com/MindlessMuse666/youtube-medialoader.git
cd youtube-medialoader

# 2. создай виртуальное окружение и установи зависимости
py -m venv .venv
source .venv/bin/activate         # Linux/macOS
.venv\Scripts\activate            # Windows
pip install -r requirements.txt

# 3. запусти приложение
py -m src.main
```

### Сборка EXE (nuitka)

```bash
pip install nuitka
nuitka `
    --standalone `
    --onefile `
    --windows-console-mode=disable `
    --enable-plugin=pyside6 `
    --include-data-dir=assets=assets `
    --output-dir=build `
    src/main.py
```

> Готовый `.exe` появится в папке `dist/`.

---

## Разработка

### Структура проекта

```text
youtube-medialoader/
├── src/                       # Исходный код
│   ├── main.py                # Точка входа
│   ├── downloader.py          # Движок загрузки (yt-dlp wrapper)
│   ├── gui/
│   │   ├── main_window.py     # Главное окно (MainWindow)
│   │   ├── widgets.py         # NeonButton, Toast, ProgressBar, Spinner
│   │   ├── styles.py          # QSS-стили + загрузка шрифтов
│   │   ├── worker.py          # QThread-задачи (VideoInfoWorker, DownloadWorker)
│   │   └── animated_background.py  # Анимированные сферы на фоне
│   └── utils/
│       ├── file_utils.py      # Очистка имeн файлов, пути
│       └── logger.py          # Qt-логгер с сигналами
├── assets/
│   ├── fonts/                 # PressStart2P-Regular.ttf
│   └── icons/                 # app_icon.ico, app_icon.png
├── tests/
│   ├── test_downloader.py     # Тесты загрузчика (моки yt-dlp)
│   ├── test_file_utils.py     # Тесты утилит
│   ├── test_worker.py         # Тесты worker-ов
│   └── conftest.py            # Фикстуры pytest
├── pyproject.toml             # Метаданные и конфигурация
├── requirements.txt           # Зависимости
├── BUILD.md                   # Гайд по сборке EXE
└── README.md                  # Этот файл
```

### Команды

| Команда                           | Описание               |
| --------------------------------- | ---------------------- |
| `py -m src.main`                  | Запуск приложения      |
| `pytest tests/ -v`                | Запуск тестов          |
| `pip install -r requirements.txt` | Установка зависимостей |

### Тестирование

Проект покрыт модульными тестами с моками - никаких реальных сетевых запросов:

```bash
pytest tests/ -v --tb=short
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
