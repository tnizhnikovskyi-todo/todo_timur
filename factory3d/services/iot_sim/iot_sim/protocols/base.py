"""Базовий протокольний сервер (SPEC §8.1.1): start()/stop()/health()."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ProtocolServer(ABC):
    name: str = "base"

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    def health(self) -> dict[str, Any]:
        """Стан сервера: {"proto": name, "up": bool, ...}."""
