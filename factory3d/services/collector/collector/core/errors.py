"""Винятки ядра колектора (SPEC §8.3.2). Тексти — без секретів."""

from __future__ import annotations


class CollectorError(Exception):
    """Базовий виняток колектора."""


class ConnectError(CollectorError):
    """Не вдалося відкрити з'єднання з пристроєм/брокером."""


class PollError(CollectorError):
    """Опитування не вдалося повністю."""


class WriteError(CollectorError):
    """Запис у пристрій відхилено або не вдався."""


class NotSupported(CollectorError):
    """Операція не підтримується плагіном."""


class AllowlistDenied(CollectorError):
    """Хост поза F3D_ALLOW_HOSTS."""
