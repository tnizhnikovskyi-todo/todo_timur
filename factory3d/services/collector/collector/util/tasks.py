"""Обмежені в часі скасування задач і виклики: зупинка не залежить від зависань (плагіни, бібліотеки пристроїв)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine, Iterable
from typing import Any

log = logging.getLogger("collector.tasks")


async def cancel_tasks(tasks: Iterable[asyncio.Task], timeout: float | None, what: str = "task") -> list[asyncio.Task]:
    """Скасовує задачі й чекає не довше `timeout` с. Задачі, що ігнорують скасування (бібліотека пристрою ковтає
    `CancelledError` у циклі перепідключення), лишаються працювати «в сирітстві»: це логується, повертаються вони
    списком, а зупинка триває. (`asyncio.gather`/`wait_for` у такому разі чекали б вічно.)"""
    live = [t for t in tasks if not t.done()]
    for t in live:
        t.cancel()
    if not live:
        return []
    done, pending = await asyncio.wait(live, timeout=timeout)
    for t in done:
        if not t.cancelled():
            t.exception()  # забрати виняток, щоб asyncio не писав «exception was never retrieved»
    for t in pending:
        log.error("%s %s ignored cancellation for %.1f s: abandoned", what, t.get_name(), timeout or 0.0)
    return list(pending)


async def run_bounded(coro: Coroutine[Any, Any, Any], timeout: float, what: str) -> bool:
    """Виконує `coro` не довше `timeout` с; True — завершилась без помилки. Після таймауту задачу скасовано і
    покинуто (навіть якщо вона ігнорує скасування), помилки не піднімаються: зупинка має дійти до кінця."""
    task = asyncio.ensure_future(coro)
    task.set_name(what)
    done, _ = await asyncio.wait({task}, timeout=timeout)
    if not done:
        task.cancel()
        log.error("%s did not finish within %.1f s: abandoned", what, timeout)
        return False
    if task.cancelled():
        return False
    exc = task.exception()
    if exc is not None:
        log.warning("%s failed: %s", what, exc)
        return False
    return True


async def wait_bounded(tasks: Iterable[asyncio.Task], timeout: float, what: str = "task") -> list[asyncio.Task]:
    """Чекає на задачі не довше `timeout` с; ті, що не вкладись, скасовуються і покидаються (повертаються списком)."""
    live = [t for t in tasks if not t.done()]
    if live:
        await asyncio.wait(live, timeout=timeout)
    for t in tasks:
        if t.done() and not t.cancelled():
            t.exception()
    pending = [t for t in live if not t.done()]
    for t in pending:
        t.cancel()
        log.error("%s %s did not finish within %.1f s: abandoned", what, t.get_name(), timeout)
    return pending
