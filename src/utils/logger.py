"""Логирование с Qt-сигналами для YouTube Medialoader.

Предоставляет потокобезопасный логгер, который отправляет сообщения
через Qt-сигналы для отображения в GUI в реальном времени.
"""

import enum
import logging
from typing import Optional

from PySide6.QtCore import QObject, Signal


class LogLevel(enum.Enum):
    """Уровни логирования, сопоставленные с цветовой схемой GUI."""

    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"


class LogSignal(QObject):
    """Qt-объект, передающий записи лога между потоками.

    Подключите отображение логов в GUI к сигналу :attr:`message_emitted`.
    """

    message_emitted = Signal(str, str)  # (level_name, text)


# Модульный singleton-сигнал
_log_signal = LogSignal()


def get_log_signal() -> LogSignal:
    """Вернуть модульный экземпляр сигнала лога."""
    return _log_signal


class QtLogHandler(logging.Handler):
    """Обработчик `logging.Handler`, пересылающий записи через Qt-сигнал.

    Подключите к стандартному Python-логгеру, чтобы перенаправить все
    логи в GUI-виджет на главном потоке.
    """

    def __init__(self, log_signal: Optional[LogSignal] = None) -> None:
        super().__init__()
        self._signal = log_signal or _log_signal

    def emit(self, record: logging.LogRecord) -> None:
        """Отправить запись лога через Qt-сигнал."""
        try:
            level = LogLevel.INFO
            if record.levelno >= logging.ERROR:
                level = LogLevel.ERROR
            elif record.levelno >= logging.WARNING:
                level = LogLevel.WARNING
            self._signal.message_emitted.emit(
                level.value, self.format(record)
            )
        except Exception:
            self.handleError(record)
