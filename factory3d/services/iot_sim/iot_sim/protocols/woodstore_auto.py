"""Авто-завдання порталу STORETEQ на стенді (вау №19, td_iot_sim R-18, td_machine_connect R-31).

Раніше REST ``woodStore`` (P-03) віддавав лише завдання, які створив Odoo (``POST /jobs``) або ``/jobs`` API-33;
сама модель порталу (``models/gantry.py``) ставила ``feed`` у пам'яті, не показуючи їх по REST. Тому в Odoo без
ручного «Подати плиту» завдань порталу не було, а ланцюжок завдання → лист → карта розкрою → МО не мав даних.

``AutoFeed`` закриває цю прогалину: кожен РЦ розкрою (``SAW-1…3``, ``NEST-1``) у стані WORKING без завдання порталу
в черзі отримує ``feed``-завдання на кілька листів, ``external_ref`` = ``order`` активного завдання РЦ (назва МО, якою
Odoo зв'язує завдання порталу з МО й картою розкрою). Плита — з наявних стосів (за назвою МО, детерміновано).

``phase_state`` дає стану порталу фази циклу листа (moving → picking → moving → placing, пропорції 10:4:10:3 з R-18),
щоб ``GET /status`` не стояв на ``placing`` увесь час, поки завдання активне.

Вимикається ``SIM_WOODSTORE_AUTOFEED=0``. Свого стану, крім лічильника поданого за МО, не має.
"""

from __future__ import annotations

import contextlib
import json
import os
import zlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

from iot_sim.models.machine import WORKING

if TYPE_CHECKING:
    from iot_sim.protocols.woodstore_api import WoodStore

# Фази циклу листа (R-18): стос → захоплення → верстат → кладемо; частки сумують до 1.
PHASES = (("moving", 10.0), ("picking", 4.0), ("moving", 10.0), ("placing", 3.0))
_CYCLE = sum(d for _, d in PHASES)

MIN_SHEETS, MAX_SHEETS = 2, 5  # листів у одному авто-завданні
MAX_PER_REF = 12  # скільки листів авто-режим подає під одну МО (далі — лише за командою Odoo)
PRIORITY = 3  # нижче за замовчування Odoo (5): команда Odoo завжди обганяє авто-подачу


CATALOG_STACKS = Path(__file__).resolve().parents[2] / "catalog" / "woodstore_stacks.json"


def default_stacks(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Початкові стоси стенда з ``catalog/woodstore_stacks.json`` (27 місць PLT-01A…PLT-09C, 23 з листами — залишки
    демо-бази Odoo): коди стосів, товари й партії збігаються зі стосами ``td_machine_connect``. Немає файлу — ``[]``."""
    file = Path(path or os.environ.get("SIM_WOODSTORE_STACKS") or CATALOG_STACKS)
    if not file.is_file():
        return []
    return [
        dict(s)
        for s in json.loads(file.read_text("utf-8")).get("stacks", [])
        if str(s.get("id", "")).startswith("PLT-")
    ]


def enabled() -> bool:
    return os.environ.get("SIM_WOODSTORE_AUTOFEED", "1").strip().lower() not in ("0", "false", "no", "off", "")


def phase_state(elapsed: float, period: float) -> str:
    """Стан порталу через ``elapsed`` с після початку циклу листа тривалістю ``period`` с (останні 27 с — рух)."""
    if period <= 0:
        return "placing"
    # рух триває ``_CYCLE`` с наприкінці періоду листа; решту часу портал чекає біля верстата
    start = max(period - _CYCLE, 0.0)
    if elapsed < start:
        return "idle"
    x = (elapsed - start) / min(period, _CYCLE) * _CYCLE
    for name, dur in PHASES:
        if x < dur:
            return name
        x -= dur
    return "placing"


class AutoFeed:
    """Створює ``feed`` для РЦ розкрою у WORKING; викликається з ``WoodStore.on_tick`` до розбору черги."""

    def __init__(self, store: WoodStore, targets: tuple[str, ...], auto_feed: bool | None = None) -> None:
        self.store = store
        self.targets = targets
        self.auto_feed = auto_feed  # None — за SIM_WOODSTORE_AUTOFEED (умовчання: увімкнено)
        self.fed: dict[str, int] = {}  # назва МО → листів, поданих авто-режимом

    def _products(self) -> list[str]:
        st = self.store
        return sorted({s["product"] for s in st.stacks.values() if s["product"] and s["qty"] - s["reserved"] > 0})

    def _busy(self, target: str) -> bool:
        return any(j["target"] == target and j["state"] in ("queued", "active") for j in self.store.jobs.values())

    def on_tick(self, world: Any) -> None:
        if not (enabled() if self.auto_feed is None else self.auto_feed):
            return
        for target in self.targets:
            dev = world.devices.get(target)
            model = dev.model if dev else None
            if model is None or getattr(model, "current_state", None) != WORKING or self._busy(target):
                continue
            job = model.active_job() if hasattr(model, "active_job") else None
            ref = (job or {}).get("order") or None
            seed = zlib.crc32((ref or target).encode())
            if ref and self.fed.get(ref, 0) >= MAX_PER_REF:
                continue
            products = self._products()
            if not products:
                continue
            sheets = MIN_SHEETS + seed % (MAX_SHEETS - MIN_SHEETS + 1)
            order = products[seed % len(products) :] + products[: seed % len(products)]
            for product in order:
                free = sum(s["qty"] - s["reserved"] for s in self.store.available(product, None, None))
                n = min(sheets, free)
                if n < 1:
                    continue
                # ApiError (409/422) — не помилка стенда: наступний тік спробує знову
                with contextlib.suppress(Exception):
                    self.store.create_job(
                        {
                            "type": "feed",
                            "target": target,
                            "sheets": n,
                            "product": product,
                            "priority": PRIORITY,
                            "external_ref": ref,
                        }
                    )
                    if ref:
                        self.fed[ref] = self.fed.get(ref, 0) + n
                    break
