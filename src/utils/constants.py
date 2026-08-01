"""Централизованные константы приложения YouTube Medialoader.

Единый источник правды для названий, версии и ключей настроек. Убирает
разбросанные по коду магические строки ``"MindlessMuse666"`` и
``"YouTube-Medialoader"``.
"""

from __future__ import annotations

# Версия текущего релиза. Числовой формат обязателен: его сравнивает
# :mod:`src.utils.update_checker` (теги ``v2.x-stable`` парсятся как 2.x).
APP_VERSION = "2.3.0"

# Строка релиза, показываемая в подзаголовке окна и используемая для тегов.
RELEASE_TAG = "v2.3-stable"

# Метаданные приложения (совпадают с GitHub-репозиторием).
APP_NAME = "YouTube Medialoader"
ORG_NAME = "MindlessMuse666"

# Ключ приложения для QSettings (историческая схема org/app).
SETTINGS_APP = "YouTube-Medialoader"

# Репозиторий для проверки обновлений (owner/name).
GITHUB_REPO = "MindlessMuse666/youtube-medialoader"
