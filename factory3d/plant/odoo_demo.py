"""Демо-дані «як із підключеної Odoo 19» для 3D-моделі.

Структура повторює моделі Odoo (stock.location / stock.quant, mrp.production / mrp.workorder,
mrp.workcenter, stock.picking, sale.order, purchase.order, quality.check, maintenance.request,
maintenance.equipment, hr.employee), а ключі — це коди об'єктів у 3D-сцені. Коли буде справжня
база, достатньо віддати JSON того самого формату (наприклад, скриптом через XML-RPC) — переглядач
не зміниться.

Запуск без Blender:  python -m plant.odoo_demo dist/odoo_demo.json
"""
import json
import sys
from datetime import datetime, timedelta

from .energy import IDLE_DEFAULT, IDLE_K, PROFILE, TARIFF, energy_data, passport_energy
from .evacuation import load as evac_load
from .fire import fire_data
from .infra import infra_data
from .lighting import layout as light_layout
from .lighting import load_lux_norms, panels_load
from .ventilation import ventilation_data
from .equipment import ROLE_BY_CODE, load_specs, passport
from .layout import (EDGE_LEVELS, EDGE_SECTIONS, EDGE_UNITS, FG_BAYS, FG_LEVELS, FG_PRODUCTS,
                     FG_ROWS, HW_LEVELS, HW_ROWS, HW_SECTIONS, MACHINES, SHEET_COLS_X, SHEET_ROWS_Y,
                     STATUS, ZONES, edge_slot, fg_slot, hw_state, sheet_slot)
from .layout import DOOR_Y, QC_STACKS, RACK_LEVELS, RACK_LINES, SHEET_DOORS, UNLOAD_STACKS, rack_bays, rack_slot

NOW = datetime(2026, 10, 12, 10, 30)
WH = "WH"


def ts(dt):
    return dt.strftime("%Y-%m-%d %H:%M")


def det(*xs, mod=1000):
    """Детермінований «випадковий» відгук без random — щоб дані не змінювались між збірками."""
    h = 2166136261
    for x in xs:
        for ch in str(x):
            h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return h % mod


# ---------------------------------------------------------------- довідники
SHEET_PRODUCTS = [("DSP16-SON", "ДСП 16 мм Дуб Сонома 2800×2070"),
                  ("DSP16-WHT", "ДСП 16 мм Білий 2800×2070"),
                  ("DSP16-ANT", "ДСП 16 мм Антрацит 2800×2070"),
                  ("DSP16-WNG", "ДСП 16 мм Венге 2800×2070"),
                  ("DSP18-CON", "ДСП 18 мм Бетон 2800×2070"),
                  ("MDF18-RAW", "МДФ 18 мм під фарбування 2800×2070"),
                  ("HDF3-WHT", "ХДФ 3 мм білий 2800×2070")]
EDGE_PRODUCTS = [("EB2-SON", "Крайка ПВХ 2×22 Дуб Сонома"), ("EB04-WHT", "Крайка ПВХ 0,4×19 Біла"),
                 ("EB2-ANT", "Крайка ПВХ 2×22 Антрацит"), ("EB2-WNG", "Крайка ПВХ 2×22 Венге"),
                 ("EB2-CON", "Крайка ПВХ 2×22 Бетон"), ("EB2-WHT", "Крайка ПВХ 2×22 Біла")]
HW_PRODUCTS = [
    ("FUR-HG-110", "Завіса накладна 110° з доводчиком", "шт", 400, 120),
    ("FUR-HG-110V", "Завіса вкладна 110°", "шт", 300, 80),
    ("FUR-HG-175", "Завіса для фальшпанелі 175°", "шт", 120, 30),
    ("FUR-SL-450", "Напрямні кулькові 450 мм", "компл", 120, 40),
    ("FUR-SL-500", "Напрямні кулькові 500 мм", "компл", 120, 40),
    ("FUR-TB-450", "Напрямні прихованого монтажу 450 мм", "компл", 80, 20),
    ("FUR-CF-750", "Конфірмат 7×50", "шт", 5000, 1500),
    ("FUR-EX-15", "Ексцентрик 15 мм", "шт", 3000, 800),
    ("FUR-EXS-34", "Шток ексцентрика 34 мм", "шт", 3000, 800),
    ("FUR-DW-830", "Шкант 8×30", "шт", 8000, 2000),
    ("FUR-HD-128B", "Ручка-скоба 128 мм, чорна", "шт", 300, 80),
    ("FUR-HD-160S", "Ручка-скоба 160 мм, сталь", "шт", 300, 80),
    ("FUR-GL-250", "Ручка-профіль 2,5 м", "шт", 60, 15),
    ("FUR-LG-100", "Опора регульована 100 мм", "шт", 800, 200),
    ("FUR-SP-5", "Полицетримач 5 мм", "шт", 4000, 1000),
    ("FUR-CP-OAK", "Заглушка конфірмата, дуб", "шт", 4000, 1000),
    ("FUR-CP-WHT", "Заглушка конфірмата, біла", "шт", 4000, 1000),
    ("FUR-SC-416", "Саморіз 4×16", "шт", 10000, 3000),
    ("FUR-GS-100", "Газліфт 100N", "шт", 150, 40),
    ("FUR-HN-ADJ", "Навіска регульована", "компл", 200, 60),
    ("FUR-AN-20", "Куточок меблевий 20×20", "шт", 2000, 500),
    ("FUR-DM-01", "Демпфер для дверей", "шт", 500, 150),
    ("FUR-PL-100", "Цоколь кухонний 100 мм, 4 м", "шт", 40, 10),
    ("FUR-MB-450", "Ящик-метабокс 450 мм", "компл", 60, 15),
]
FG_CODES = ["KC-B600", "KC-W800", "KC-T400", "OF-D3", "OF-T1400", "OF-C800", "BR-K4"]
FRONT_PRODUCTS = [("FR-PVC-WG", "Фасад МДФ у плівці ПВХ, білий глянець"),
                  ("FR-PNT-ANT", "Фасад МДФ фарбований, антрацит мат"),
                  ("FR-PNT-WHT", "Фасад МДФ фарбований, білий мат")]
OTHER_PRODUCTS = [("PK-FF1400", "Гофрокартон фанфолд 1400 мм", "м"),
                  ("PK-STR500", "Стрейч-плівка 500 мм", "рул"),
                  ("PK-COR50", "Кутик картонний 50×50", "шт"),
                  ("PAL-EUR", "Європалета 1200×800", "шт"),
                  ("LFM-PR", "Ґрунт ПУ білий", "кг"),
                  ("LFM-ENW", "Емаль ПУ біла матова", "кг"),
                  ("LFM-ENA", "Емаль ПУ антрацит матова", "кг"),
                  ("LFM-UV", "Лак УФ прозорий", "кг"),
                  ("LFM-GLUE", "Клей ПУР для мембранного пресу", "кг"),
                  ("PVC-WG", "Плівка ПВХ для фасадів, білий глянець", "м")]

SUPPLIERS = {"sheets": "Плитсервіс (демо)", "hw": "Фурнітура-Трейд (демо)", "edge": "Крайка-Профі (демо)",
             "paint": "ЛакоФарб (демо)", "pack": "ПакЦентр (демо)"}
CUSTOMERS = ["Кухні Плюс (демо)", "Меблі Дім (демо)", "ТОВ «Офіс-Простір» (демо)",
             "Готель «Карпати» (демо)", "Студія «Інтер'єр» (демо)", "Кухні Плюс (демо)",
             "Меблі Дім (демо)", "Школа № 12 (демо)"]
NAMES = ["Олег Мельник", "Ірина Коваль", "Андрій Бондар", "Наталія Ткачук", "Сергій Кравець",
         "Оксана Шевчук", "Віктор Поліщук", "Марина Литвин", "Дмитро Савчук", "Юлія Марченко",
         "Петро Онищенко", "Тетяна Руденко", "Роман Гнатюк", "Галина Мороз", "Василь Лисенко",
         "Олена Кузьменко", "Ігор Павленко", "Світлана Зінченко", "Максим Остапенко",
         "Людмила Гончар", "Богдан Ярошенко", "Катерина Бойко", "Євген Тимошенко",
         "Алла Демченко", "Степан Кушнір", "Валентина Чорна", "Артем Литвиненко",
         "Надія Сидоренко", "Олександр Федоренко", "Інна Карпенко"]


class Demo:
    def __init__(self):
        self.products = {}
        self.locations = {}
        self.pickings = []
        self.purchase = []
        self.sale = []
        self.productions = []
        self.workorders = {}
        self.workcenters = {}
        self.maintenance = []
        self.quality = []
        self.equipment = {}
        self.employees = {}
        self.docks = {}

    # ---------------------------------------------------------------- товари і залишки
    def product(self, code, name, uom, categ, **kw):
        self.products[code] = dict(default_code=code, name=name, uom=uom, categ=categ, **kw)

    def location(self, code, complete_name, quants, capacity=None, **kw):
        fill = None
        if capacity:
            fill = min(1.0, sum(q["qty"] for q in quants) / capacity) if quants else 0.0
        self.locations[code] = dict(complete_name=complete_name, quants=quants, capacity=capacity,
                                    fill=fill, **kw)

    def build_catalog(self):
        for code, name in SHEET_PRODUCTS:
            self.product(code, name, "арк", "Плитні матеріали", seller=SUPPLIERS["sheets"])
        for code, name in EDGE_PRODUCTS:
            self.product(code, name, "м", "Крайка", seller=SUPPLIERS["edge"])
        for code, name, uom, mx, mn in HW_PRODUCTS:
            self.product(code, name, uom, "Фурнітура", seller=SUPPLIERS["hw"])
        for code, name in zip(FG_CODES, FG_PRODUCTS):
            self.product(code, name, "шт", "Готова продукція")
        for code, name in FRONT_PRODUCTS:
            self.product(code, name, "шт", "Фасади (напівфабрикат)")
        for code, name, uom in OTHER_PRODUCTS:
            categ = "ЛФМ" if code.startswith(("LFM", "PVC")) else "Пакування"
            self.product(code, name, uom, categ,
                         seller=SUPPLIERS["paint" if categ == "ЛФМ" else "pack"])

    def build_stock(self):
        # портальний склад плит
        for j in range(len(SHEET_ROWS_Y)):
            for i in range(len(SHEET_COLS_X)):
                code, decor, n = sheet_slot(i, j)
                pcode = SHEET_PRODUCTS[decor][0]
                if pcode == "DSP18-CON":
                    n = min(n, 10)  # дефіцит бетону — через нього стоїть пакетний розкрій
                quants = [dict(product=pcode, qty=n, lot=f"{pcode}-{2609 + (i + j) % 5}-{100 + i * 14 + j}",
                               reserved=min(n, 10) if det(code, mod=4) == 0 else 0)] if n else []
                self.location(code, f"{WH}/Сировина/Плити/Портал/{code}", quants, capacity=60, kind="stack")
        # стелажі буфера (навантажувач поповнює з них портал через транспортери)
        for li, (line, _, _) in enumerate(RACK_LINES):
            for b in range(rack_bays(line)):
                for lv in range(len(RACK_LEVELS)):
                    code, decor, n = rack_slot(li, b, lv)
                    pcode = SHEET_PRODUCTS[decor][0]
                    if pcode == "DSP18-CON":
                        n = 0  # бетону немає й у стелажах — чекаємо P00414
                    lot = f"{pcode}-{2610 + (li + b) % 3}-{300 + li * 12 + b * 4 + lv}"
                    quants = [dict(product=pcode, qty=n, lot=lot)] if n else []
                    self.location(code, f"{WH}/Сировина/Плити/Стелажі/{line}/{code}", quants, capacity=55,
                                  kind="stack")
        # приймання плит: вивантаження біля воріт 1–3 (WH/Вхід) і площадки контролю (WH/Контроль якості)
        for k, _ in enumerate(SHEET_DOORS, 1):
            self.location(f"UNLOAD-{k}", f"{WH}/Вхід/Ворота {k}",
                          [dict(product=SHEET_PRODUCTS[d][0], qty=n) for n, d in UNLOAD_STACKS[k]], kind="area")
            n, d = QC_STACKS[k]
            self.location(f"QC-PLT-{k}", f"{WH}/Контроль якості/Плити {k}",
                          [dict(product=SHEET_PRODUCTS[d][0], qty=n)], kind="area")
        # фурнітура: правило поповнення на кожну комірку
        po_lines = []
        for ri in range(HW_ROWS):
            for s in range(1, HW_SECTIONS + 1):
                for li in range(1, HW_LEVELS + 1):
                    code = f"FUR-R{ri + 1}-S{s:02d}-L{li}"
                    pcode, _, _, mx, mn = HW_PRODUCTS[((ri * HW_SECTIONS + s - 1) * HW_LEVELS + li - 1)
                                                      % len(HW_PRODUCTS)]
                    bmax, bmin = max(4, mx // 6), max(2, mn // 6)
                    state = hw_state(ri, s, li)
                    r = det(code, mod=100) / 100
                    qty = {"ok": round(bmin * 1.5 + r * (bmax - bmin * 1.5)), "low": round(bmin * (0.2 + 0.6 * r)),
                           "out": 0}[state]
                    quants = [dict(product=pcode, qty=qty, reserved=round(qty * 0.2) if r > 0.7 else 0)] if qty else []
                    op = dict(product=pcode, min=bmin, max=bmax)
                    if state != "ok":
                        po_lines.append(dict(product=pcode, qty=bmax - qty, location=code))
                        op["purchase"] = None  # заповнимо назвою замовлення нижче
                    self.location(code, f"{WH}/Сировина/Фурнітура/{code}", quants, capacity=bmax,
                                  kind="bin", state=state, orderpoint=op)
        # закупівля для комірок нижче мінімуму — два замовлення постачальнику
        for k, chunk in enumerate((po_lines[: len(po_lines) // 2], po_lines[len(po_lines) // 2:])):
            name = f"P{412 + k:05d}"
            self.purchase.append(dict(name=name, partner=SUPPLIERS["hw"], state="purchase",
                                      date_order=ts(NOW - timedelta(days=2 - k)),
                                      date_planned=ts(NOW.replace(hour=11 + k * 3, minute=0)),
                                      lines=[dict(product=lin["product"], qty=lin["qty"]) for lin in chunk],
                                      locations=[lin["location"] for lin in chunk]))
            for lin in chunk:
                self.locations[lin["location"]]["orderpoint"]["purchase"] = name
        self.purchase.append(dict(name="P00414", partner=SUPPLIERS["sheets"], state="purchase",
                                  date_order=ts(NOW - timedelta(days=3)), date_planned=ts(NOW.replace(hour=13)),
                                  lines=[dict(product="DSP18-CON", qty=120), dict(product="DSP16-ANT", qty=60)],
                                  locations=[]))
        # крайка
        for ui in range(1, EDGE_UNITS + 1):
            for s in range(1, EDGE_SECTIONS + 1):
                for li in range(1, EDGE_LEVELS + 1):
                    code = f"EB-U{ui}-S{s}-L{li}"
                    decor, n = edge_slot(ui, s, li)
                    pcode = EDGE_PRODUCTS[decor][0]
                    quants = [dict(product=pcode, qty=n * 200, lot=f"{pcode}-R{ui}{s}{li}")] if n else []
                    self.location(code, f"{WH}/Сировина/Крайка/{code}", quants, capacity=11 * 200, kind="shelf")
        # склад готової продукції
        pack_no = 30000
        for ri in range(1, len(FG_ROWS) + 1):
            for b in range(1, FG_BAYS + 1):
                for li in range(1, FG_LEVELS + 1):
                    code = f"FG-R{ri}-B{b:02d}-L{li}"
                    n, l0, l1, pi = fg_slot(ri, b, li)
                    quants = []
                    for p, layers in zip(range(n), (l0, l1)):
                        pack_no += 1
                        quants.append(dict(product=FG_CODES[pi], qty=layers * 4, package=f"PACK{pack_no:07d}"))
                    self.location(code, f"{WH}/Готова продукція/{code}", quants, capacity=2, kind="pallet_cell")
                    self.locations[code]["fill"] = n / 2
        # інші місця
        self.location("PACK-STORE", f"{WH}/Сировина/Пакування", [
            dict(product="PK-FF1400", qty=4200), dict(product="PK-STR500", qty=48),
            dict(product="PK-COR50", qty=3600)], kind="area")
        for i in range(1, 4):
            self.location(f"PAL-{i}", f"{WH}/Сировина/Пакування/PAL-{i}", [dict(product="PAL-EUR", qty=14)],
                          capacity=14, kind="area")
        self.location("PAINT-STORE", f"{WH}/Сировина/ЛФМ", [
            dict(product="LFM-PR", qty=380, lot="PR-2609-07"), dict(product="LFM-ENW", qty=520, lot="ENW-2609-11"),
            dict(product="LFM-ENA", qty=140, lot="ENA-2608-30"), dict(product="LFM-UV", qty=260, lot="UV-2609-02"),
            dict(product="LFM-GLUE", qty=95, lot="GL-2609-15"), dict(product="PVC-WG", qty=1800)], kind="area")

    # ---------------------------------------------------------------- виробництво
    def build_production(self):
        routes = {
            "A": [("Розкрій", "SAW-1"), ("Крайкооблицювання", "EDGE-1"), ("Присадка", "CNC-1"),
                  ("Сортування", "SORT-1"), ("Збирання", "ASMLINE-1"), ("Пакування", "PACK-1")],
            "B": [("Розкрій", "SAW-2"), ("Крайкооблицювання", "EDGE-2"), ("Присадка", "CNC-2"),
                  ("Сортування", "SORT-1"), ("Збирання", "ASM-{a}"), ("Пакування", "PACK-2")],
            "C": [("Пакетний розкрій", "SAW-3"), ("Крайкооблицювання", "EDGE-3"),
                  ("Прохідна присадка", "BORE-1"), ("Шкантування", "DOWEL-1"), ("Сортування", "SORT-1"),
                  ("Збирання", "ASMLINE-1"), ("Термоусадка та обв'язка", "PACKLINE-1")],
            "D": [("Розкрій нестандарту", "{saw}"), ("Крайкооблицювання", "EDGE-3"), ("Присадка", "{cnc}"),
                  ("Сортування", "SORT-1"),
                  ("Збирання", "ASM-{a}"), ("Коробка під розмір", "BOX-1"), ("Пакування", "PACK-{p}")],
            # нестандарт облицьовують на лінії C, поки вона чекає на ДСП Бетон
            "F1": [("Нестинг МДФ", "NEST-1"), ("Шліфування", "SAND-1"), ("Нанесення клею", "GLUE-1"),
                   ("Облицювання плівкою", "PRESS-1"), ("Встановлення завіс", "HINGE-1")],
            "F2": [("Нестинг МДФ", "NEST-1"), ("Шліфування", "SAND-1"), ("Фарбування (автомат)", "AUTOSPRAY-1"),
                   ("Сушіння", "DRY-1"), ("УФ-лакування", "UV-1"), ("Встановлення завіс", "HINGE-1")],
            "F3": [("Нестинг МДФ", "NEST-1"), ("Шліфування", "SAND-1"), ("Фарбування (ручне)", "SPRAY-1"),
                   ("Сушіння", "DRY-1"), ("Встановлення завіс", "HINGE-1")],
        }
        # (маршрут, етап у роботі, параметри, стан МО) — у кожного працюючого верстата рівно одне
        # завдання в роботі; простої та зупинка пояснюються чергою
        plan = [
            ("A", 4, {}, "progress"), ("A", 2, {}, "progress"), ("A", 0, {}, "progress"), ("A", 1, {}, "progress"),
            ("A", 3, {}, "progress"), ("A", 5, {}, "progress"),
            ("B", 0, {"a": 1}, "progress"), ("B", 1, {"a": 2}, "progress"),
            ("B", 2, {"a": 5}, "progress"),  # CNC-2 зупинено — Збирання 5 чекає
            ("B", 4, {"a": 1}, "progress"), ("B", 4, {"a": 2}, "progress"), ("B", 5, {"a": 4}, "progress"),
            ("C", 2, {}, "progress"), ("C", 3, {}, "progress"), ("C", 6, {}, "progress"),
            ("C", 0, {}, "confirmed"),  # бракує ДСП 18 Бетон — пакетний розкрій і крайка C простоюють
            ("D", 0, {"saw": "SLIDE-1", "cnc": "CNC-3", "a": 3, "p": 1}, "progress"),
            ("D", 2, {"saw": "SLIDE-1", "cnc": "CNC-3", "a": 3, "p": 1}, "progress"),
            ("D", 2, {"saw": "SLIDE-1", "cnc": "CNC-4", "a": 4, "p": 2}, "progress"),
            ("D", 4, {"saw": "SLIDE-1", "cnc": "CNC-4", "a": 3, "p": 1}, "progress"),
            ("D", 4, {"saw": "VSAW-1", "cnc": "CNC-3", "a": 4, "p": 2}, "progress"),
            ("D", 4, {"saw": "SLIDE-1", "cnc": "CNC-4", "a": 6, "p": 2}, "progress"),
            ("D", 5, {"saw": "SLIDE-1", "cnc": "CNC-3", "a": 6, "p": 1}, "progress"),
            ("D", 0, {"saw": "VSAW-1", "cnc": "CNC-4", "a": 6, "p": 2}, "confirmed"),
            ("F1", 0, {}, "progress"), ("F2", 1, {}, "progress"), ("F1", 2, {}, "progress"),
            ("F1", 3, {}, "progress"), ("F2", 2, {}, "progress"), ("F3", 2, {}, "progress"),
            ("F2", 3, {}, "progress"), ("F1", 4, {}, "progress"),
        ]
        orders = []  # замовлення клієнтів
        for k in range(8):
            name = f"S{87 + k:05d}"
            orders.append(dict(name=name, partner=CUSTOMERS[k], state="sale",
                               date_order=ts(NOW - timedelta(days=6 + k)),
                               commitment_date=ts((NOW + timedelta(days=(k * 2) % 7)).replace(hour=16, minute=0)),
                               lines=[], productions=[], amount=0))
        mo_no, wo_no = 231, 1
        fg_price = [6400, 4800, 7900, 5600, 9800, 8700, 7400]
        for idx, (route, stage, params, mo_state) in enumerate(plan):
            ops = [(op, wc.format(**params)) for op, wc in routes[route]]
            front = route.startswith("F")
            if front:
                # F1 — плівка ПВХ, F2/F3 — фарбування
                pcode, pname = FRONT_PRODUCTS[0] if route == "F1" else FRONT_PRODUCTS[1 + idx % 2]
                qty = 12 + det(idx, mod=4) * 12
            else:
                pi = (idx * 3) % len(FG_CODES)
                pcode, pname = FG_CODES[pi], FG_PRODUCTS[pi]
                qty = (2 + det(idx, mod=5) * 2) if route == "D" else (8 + det(idx, mod=5) * 6)
            so = orders[idx % len(orders)]
            name = f"{WH}/MO/{mo_no:05d}"
            mo_no += 1
            start = NOW - timedelta(minutes=40 + stage * 75 + det(name, mod=40))
            wos = []
            t = start
            for k, (op, wc) in enumerate(ops):
                per_unit = {"Розкрій": 2.2, "Пакетний розкрій": 0.9, "Крайкооблицювання": 1.6,
                            "Присадка": 2.0, "Прохідна присадка": 0.8, "Шкантування": 1.0,
                            "Сортування": 0.5, "Збирання": 6.0, "Пакування": 3.0}.get(op, 1.5)
                expected = round(15 + per_unit * qty)
                if mo_state == "confirmed":
                    state = "waiting" if k == 0 else "pending"
                elif k < stage:
                    state = "done"
                elif k == stage:
                    state = "progress"
                else:
                    state = "ready" if k == stage + 1 else "pending"
                wo = dict(id=f"WO{wo_no:05d}", name=op, production=name, workcenter=wc, state=state,
                          sequence=k + 1, duration_expected=expected)
                wo_no += 1
                if state == "done":
                    wo.update(date_start=ts(t), date_finished=ts(t + timedelta(minutes=expected * 0.95)),
                              duration=round(expected * (0.85 + det(wo["id"], mod=30) / 100)), progress=1.0)
                    t += timedelta(minutes=expected)
                elif state == "progress":
                    prog = 0.15 + det(wo["id"], mod=70) / 100
                    wo.update(date_start=ts(NOW - timedelta(minutes=expected * prog)), progress=round(prog, 2),
                              duration=round(expected * prog),
                              date_planned_finished=ts(NOW + timedelta(minutes=expected * (1 - prog))))
                else:
                    wo.update(progress=0.0)
                if state == "progress" and STATUS.get(wc) == "stop":
                    wo["blocked"] = True
                self.workorders[wo["id"]] = wo
                wos.append(wo["id"])
            done_ops = sum(1 for w in wos if self.workorders[w]["state"] == "done")
            components = self.components(route, pcode, qty, name, idx)
            mo = dict(name=name, product=pcode, product_name=pname, qty=qty, uom="шт", state=mo_state,
                      origin=so["name"], route=route, workorders=wos,
                      date_start=ts(start), date_deadline=so["commitment_date"],
                      progress=round((done_ops + (self.workorders[wos[stage]].get("progress", 0)
                                                  if mo_state == "progress" else 0)) / len(wos), 2),
                      components=components)
            if mo_state == "confirmed":
                mo["reservation_state"] = "waiting"
            self.productions.append(mo)
            so["productions"].append(name)
            if not front:
                so["lines"].append(dict(product=pcode, qty=qty))
                so["amount"] += qty * fg_price[FG_CODES.index(pcode)]
        # фасади — дочірні МО до МО корпусів
        carc = [mo for mo in self.productions if not mo["route"].startswith("F")]
        for k, mo in enumerate(m for m in self.productions if m["route"].startswith("F")):
            parent = carc[(k * 3) % len(carc)]
            mo["origin"] = parent["name"]
            parent.setdefault("child_productions", []).append(mo["name"])
        self.sale = orders

    def components(self, route, pcode, qty, mo_name, idx):
        """Компоненти МО і де вони лежать (для підсвічування в 3D)."""
        if route.startswith("F"):
            items = [("MDF18-RAW", max(1, qty // 10))]
            items += [("PVC-WG", qty * 2), ("LFM-GLUE", round(qty * 0.3))] if route == "F1" else \
                     [("LFM-PR", round(qty * 0.4)), ("LFM-ENW", round(qty * 0.5))]
            items += [("FUR-HG-110", qty * 2)]
        else:
            decor = SHEET_PRODUCTS[[0, 1, 2, 3, 4][idx % 5]][0]
            items = [(decor, max(2, qty // 3)), ("HDF3-WHT", max(1, qty // 8)),
                     (EDGE_PRODUCTS[[0, 5, 2, 3, 4][idx % 5]][0], qty * 9),
                     ("FUR-CF-750", qty * 12), ("FUR-HG-110", qty * 2), ("FUR-LG-100", qty * 4),
                     ("PK-FF1400", qty * 3)]
        out = []
        for p, q in items:
            locs = [c for c, loc in self.locations.items() if any(x["product"] == p for x in loc["quants"])]
            have = sum(x["qty"] - x.get("reserved", 0) for c in locs for x in self.locations[c]["quants"]
                       if x["product"] == p)
            out.append(dict(product=p, qty=q, available=have >= q, locations=locs[:12]))
        return out

    def build_workcenters(self):
        loss_reasons = ["Налагодження", "Очікування матеріалу", "Заміна інструменту", "Перерва", "Поломка"]
        for mch in MACHINES:
            code, typ, name = mch[:3]
            st = STATUS[code]
            wos = [w for w in self.workorders.values() if w["workcenter"] == code]
            cur = next((w["id"] for w in wos if w["state"] == "progress"), None)
            queue = [w["id"] for w in sorted(wos, key=lambda w: (w["state"] != "ready", w["production"]))
                     if w["state"] in ("ready", "waiting", "pending")]
            oee = {"work": 0.74 + det(code, mod=18) / 100, "idle": 0.38 + det(code, mod=15) / 100,
                   "stop": 0.31}[st]
            losses = [dict(reason=loss_reasons[k], minutes=5 + det(code, k, mod=25))
                      for k in range(3) if det(code, k, mod=3)]
            if st == "stop":
                losses.append(dict(reason="Поломка", minutes=48))
            if st == "idle":
                losses.append(dict(reason="Очікування матеріалу", minutes=55 + det(code, mod=40)))
            self.workcenters[code] = dict(
                name=name, code=code, status=st,
                working_state={"work": "done", "idle": "normal", "stop": "blocked"}[st],
                oee=round(oee, 2), capacity=1, time_efficiency=1.0,
                productive_minutes=round(210 * oee), losses=losses, current_workorder=cur, queue=queue[:8])
        # чому стоять — щоб картка верстата пояснювала простій
        self.workcenters["SAW-3"]["idle_reason"] = \
            "Бракує ДСП 18 мм Бетон для WH/MO пакетного розкрою — приймання WH/IN/00131 о 13:00."
        self.workcenters["EDGE-3"]["idle_reason"] = "Чекає деталей із пакетного розкрою (лінія C)."
        self.workcenters["ASM-5"]["idle_reason"] = "Чекає деталей із «Присадка ЧПК B» — верстат зупинено."
        self.workcenters["VSAW-1"]["idle_reason"] = "Наступне завдання — після обіду, зміна 2."
        self.workcenters["UV-1"]["idle_reason"] = "Фасади ще в сушильній камері, вихід о 11:40."
        self.maintenance.append(dict(
            id="MR/00031", name="Помилка шпинделя осі Z, чекаємо сервісного інженера",
            equipment="CNC-2", maintenance_type="corrective", stage="В роботі", priority="3",
            request_date=ts(NOW.replace(hour=9, minute=42)), schedule_date=ts(NOW.replace(hour=12, minute=0)),
            technician="Наладчик зміни"))
        self.workcenters["CNC-2"]["maintenance_request"] = "MR/00031"

    # ---------------------------------------------------------------- логістика
    def build_logistics(self):
        w_docks = [f"DOCK-W{i}" for i in range(1, 8)]
        e_docks = [f"DOCK-E{i}" for i in range(1, 8)]
        hw_po = self.purchase[0]
        incoming = [
            # уже прийняті сьогодні: їхні вантажі ще біля воріт, на контролі або в карантині
            ("WH/IN/00123", "edge", "P00405", w_docks[4], None, "done", 1.0,
             [("EB2-ANT", 1200), ("EB04-WHT", 2400), ("EB2-WNG", 800)], NOW.replace(hour=7, minute=40)),
            ("WH/IN/00124", "paint", "P00406", w_docks[5], None, "done", 1.0,
             [("LFM-PR", 160), ("LFM-ENW", 120)], NOW.replace(hour=8, minute=10)),
            ("WH/IN/00125", "pack", "P00407", w_docks[6], None, "done", 1.0,
             [("PK-FF1400", 1500), ("PK-STR500", 12)], NOW.replace(hour=8, minute=50)),
            ("WH/IN/00126", "sheets", "P00403", w_docks[1], None, "done", 1.0,
             [("DSP16-ANT", 60)], NOW.replace(hour=7, minute=10)),
            ("WH/IN/00127", "sheets", "P00408", w_docks[1], None, "done", 1.0,
             [("DSP16-WNG", 45)], NOW.replace(hour=9, minute=45)),
            ("WH/IN/00128", "sheets", "P00409", w_docks[0], "TRUCK-IN-1", "assigned", 0.6,
             [("DSP16-SON", 120), ("DSP16-WHT", 80)], NOW.replace(hour=9, minute=30)),
            ("WH/IN/00129", "sheets", "P00410", w_docks[2], "TRUCK-IN-2", "assigned", 0.2,
             [("MDF18-RAW", 60), ("HDF3-WHT", 200)], NOW.replace(hour=10, minute=15)),
            ("WH/IN/00130", "hw", hw_po["name"], w_docks[3], "TRUCK-IN-3", "assigned", 0.4,
             [(lin["product"], lin["qty"]) for lin in hw_po["lines"][:8]], NOW.replace(hour=10, minute=40)),
            ("WH/IN/00131", "sheets", "P00414", w_docks[1], None, "assigned", 0.0,
             [("DSP18-CON", 120), ("DSP16-ANT", 60)], NOW.replace(hour=13, minute=0)),
            ("WH/IN/00132", "edge", "P00415", w_docks[4], None, "assigned", 0.0,
             [("EB2-SON", 2000), ("EB2-WHT", 1400)], NOW.replace(hour=14, minute=0)),
            ("WH/IN/00133", "paint", "P00416", w_docks[5], None, "assigned", 0.0,
             [("LFM-ENW", 200), ("LFM-UV", 120)], NOW.replace(hour=14, minute=30)),
            ("WH/IN/00134", "pack", "P00417", w_docks[6], None, "draft", 0.0,
             [("PK-FF1400", 3000), ("PK-STR500", 24)], (NOW + timedelta(days=1)).replace(hour=9, minute=0)),
        ]
        for name, sup, origin, dock, truck, state, done, lines, when in incoming:
            dest = {"sheets": "Вхід → контроль плит → стелажі", "hw": "Склад фурнітури", "edge": "Склад крайки",
                    "paint": "Склад ЛФМ", "pack": "Пакувальні матеріали"}[sup]
            self.pickings.append(dict(
                name=name, picking_type="Приймання", type="incoming", partner=SUPPLIERS[sup], origin=origin,
                state=state, scheduled_date=ts(when), dock=dock, truck=truck, location_dest=dest,
                progress=done, lines=[dict(product=p, qty=q, qty_done=round(q * done)) for p, q in lines]))
            self.docks[dock] = name
        # розміщення після контролю: площадка контролю → стелаж (крок 3)
        empty_rack = [c for c, loc in self.locations.items() if c.startswith("RCK-") and not loc["quants"]]
        for po in self.purchase:
            if po["name"] == "P00414":
                po["locations"] = empty_rack[:4]  # куди підуть плити з фури о 13:00
        putaway = [("WH/INT/00060", "done", 1.0, "QC-PLT-2", empty_rack[4], None, 2, 35, NOW.replace(hour=8, minute=5)),
                   ("WH/INT/00061", "assigned", 0.5, "QC-PLT-1", empty_rack[5], "FL-2", 1, 35,
                    NOW.replace(hour=10, minute=25))]
        for name, state, prog, src, dest, fl, decor, qty, when in putaway:
            self.pickings.append(dict(
                name=name, picking_type="Розміщення плит у стелажі", type="putaway", partner="",
                origin="QC/00413" if src == "QC-PLT-1" else "WH/IN/00126", state=state, scheduled_date=ts(when),
                progress=prog, source_locations=[src], location_dest=dest, vehicle=fl,
                lines=[dict(product=SHEET_PRODUCTS[decor][0], qty=qty, qty_done=round(qty * prog))],
                note="Контроль пройдено — стос їде в стелаж." if fl else
                "35 арк. пройшли контроль; 25 — у карантині (QC/00412)."))
        # поповнення під портал: стелаж → ряд під порталом цілим стосом (крок 4)
        by_prod = {}
        for c, loc in self.locations.items():
            if c.startswith("RCK-"):
                for q in loc["quants"]:
                    by_prod.setdefault(q["product"], []).append(c)
        repl = [("WH/INT/00071", "done", 1.0, "PLT-03A", "FL-6", 2, 40, NOW.replace(hour=9, minute=40)),
                ("WH/INT/00072", "assigned", 0.5, "PLT-07C", "FL-6", 3, 35, NOW.replace(hour=10, minute=20)),
                ("WH/INT/00073", "assigned", 0.0, "PLT-08A", None, 5, 30, NOW.replace(hour=11, minute=0))]
        for k, (name, state, prog, target, fl, decor, qty, when) in enumerate(repl):
            pcode = SHEET_PRODUCTS[decor][0]
            srcs = by_prod.get(pcode) or ["RCK-R1-1A"]
            self.pickings.append(dict(
                name=name, picking_type="Поповнення під портал", type="replenish", partner="",
                origin="Мінімальний запас під порталом", state=state, scheduled_date=ts(when), progress=prog,
                source_locations=[srcs[k % len(srcs)]], location_dest=target, vehicle=fl,
                lines=[dict(product=pcode, qty=qty, qty_done=round(qty * prog))],
                note={0: "Стос стоїть у ряду 3, портал бере з нього листи.",
                      1: "Навантажувач у проході 4 ставить стос у ряд 7; прохід заблоковано для порталу.",
                      2: "Наступне: МДФ для нестингу, ряд 8."}[k]))
        # вхідний контроль
        self.quality += [
            dict(name="QC/00412", title="Вхідний контроль плит", product="DSP16-ANT", lot="DSP16-ANT-2608-77",
                 state="fail", location="QC-1", picking="WH/IN/00126",
                 note="Товщина 16,6 мм при допуску ±0,3 мм. Стос у карантині, претензія постачальнику."),
            dict(name="QC/00413", title="Вхідний контроль плит", product="DSP16-SON", lot="DSP16-SON-2610-31",
                 state="pass", location="QC-PLT-1", picking="WH/IN/00128",
                 note="Товщина 16,1 мм у 4 точках, декор і кромки в нормі — у стелаж (WH/INT/00061)."),
            dict(name="QC/00415", title="Вхідний контроль плит", product=SHEET_PRODUCTS[QC_STACKS[2][1]][0],
                 state="none", location="QC-PLT-2", picking="WH/IN/00127", note="Контролер міряє товщину."),
            dict(name="QC/00416", title="Вхідний контроль плит", product=SHEET_PRODUCTS[QC_STACKS[3][1]][0],
                 state="none", location="QC-PLT-3", picking="WH/IN/00129", note="Чекає контролера."),
            dict(name="QC/00414", title="Контроль збирання", product=self.productions[0]["product"],
                 state="none", location="ASMLINE-1", production=self.productions[0]["name"],
                 note="Перевірка діагоналей і роботи фасадів — перед пакуванням."),
        ]
        # відвантаження: перед кожними східними воротами — замовлення клієнта
        fg_by_product = {}
        for code, loc in self.locations.items():
            if loc.get("kind") == "pallet_cell":
                for q in loc["quants"]:
                    fg_by_product.setdefault(q["product"], []).append(code)
        trucks = {1: "TRUCK-OUT-1", 4: "TRUCK-OUT-2", 6: "TRUCK-OUT-3"}
        taken = {}
        for k, so in enumerate(self.sale):  # кожне замовлення клієнта — своє відвантаження зі своїми рядками
            dock = e_docks[k % len(e_docks)]
            name = f"WH/OUT/{412 + k:05d}"
            later = k >= len(e_docks)  # друга машина до тих самих воріт — завтра
            loading = k in trucks
            state = "waiting" if k == 3 or later else "assigned"
            prog = {1: 0.7, 4: 0.3, 6: 0.1}.get(k, 0.0)
            lines, cells = [], []
            for j, ln in enumerate(so["lines"]):
                pcode, qty = ln["product"], ln["qty"]
                lines.append(dict(product=pcode, qty=qty, qty_done=round(qty * prog)))
                free = [c for c in fg_by_product.get(pcode, []) if c not in taken]
                for c in free[:2]:
                    taken[c] = name
                    cells.append(c)
                    for q in self.locations[c]["quants"]:
                        q["reserved"] = q["qty"]
                        q["reserved_for"] = name
            when = (NOW + timedelta(days=1)).replace(hour=9, minute=0) if later else \
                NOW.replace(hour=11 + k % 3, minute=0) if loading else None
            self.pickings.append(dict(
                name=name, picking_type="Відвантаження", type="outgoing", partner=so["partner"],
                origin=so["name"], state=state, scheduled_date=ts(when) if when else so["commitment_date"],
                dock=dock, truck=trucks.get(k), progress=prog, lines=lines, source_locations=cells,
                carrier="Власний транспорт" if k % 2 else "Нова Пошта Вантаж (демо)",
                note="Чекає завершення МО" if state == "waiting" else ""))
            so["delivery"] = name
            self.docks.setdefault(dock, name)
        # комплектація компонентів (WH/PC) у візки буфера
        for k in range(12):
            code = f"KIT-{k + 1:02d}"
            mo = self.productions[(k * 2) % len(self.productions)]
            hw = [c for c in mo["components"] if c["product"].startswith("FUR")]
            done = k != 11
            name = f"WH/PC/{311 + k:05d}"
            self.pickings.append(dict(
                name=name, picking_type="Комплектація компонентів", type="pick_components",
                partner="", origin=mo["name"], state="done" if done else "assigned",
                scheduled_date=ts(NOW - timedelta(minutes=30 * (12 - k))), location_dest=code,
                lines=[dict(product=c["product"], qty=c["qty"], qty_done=c["qty"] if done else 0) for c in hw],
                source_locations=[loc for c in hw for loc in c["locations"][:2]], progress=1.0 if done else 0))
            self.location(code, f"{WH}/Передвиробництво/{code}",
                          [dict(product=c["product"], qty=c["qty"]) for c in hw] if done else [],
                          kind="kit", production=mo["name"], picking=name)
        fronts = [m for m in self.productions if m["route"].startswith("F")]
        for k, mo in enumerate(fronts):  # окрема етажерка на кожне замовлення фасадів
            code = f"FRONTS-{k + 1}"
            done = round(mo["qty"] * (1.0 if mo["state"] == "done" else mo.get("progress", 0)))
            self.location(code, f"{WH}/Передвиробництво/Фасади/{code}",
                          [dict(product=mo["product"], qty=done)] if done else [], kind="kit",
                          production=mo.get("origin"), fronts_mo=mo["name"],
                          note=f"Фасади з {mo['name']}: готово {done} з {mo['qty']}")
        # розміщення готової продукції (WH/SFP) і зона виходу
        post = []
        for k in range(4):
            mo = self.productions[k]
            name = f"WH/SFP/{201 + k:05d}"
            post.append(dict(product=mo["product"], qty=12 + 4 * k, package=f"PACK{40001 + k:07d}"))
            self.pickings.append(dict(
                name=name, picking_type="Розміщення готової продукції", type="store_finished", partner="",
                origin=mo["name"], state="assigned", scheduled_date=ts(NOW + timedelta(minutes=20 * k)),
                location_dest="Склад готової продукції", lines=[dict(product=mo["product"], qty=12 + 4 * k,
                                                                   qty_done=0)], progress=0))
        self.location("POST-STAGE", f"{WH}/Пост-виробництво", post, kind="area")
        self.location("OUT-STAGE", f"{WH}/Відвантаження/Коридори", [
            dict(product=line["product"], qty=line["qty_done"], reserved_for=p["name"])
            for p in self.pickings if p["type"] == "outgoing" for line in p["lines"] if line["qty_done"]],
            kind="area")
        for k in range(4, len(DOOR_Y) + 1):  # вивантаження перед воротами 4–7: те, що вже зняли з фури
            self.location(f"UNLOAD-{k}", f"{WH}/Вхід/Ворота {k}", [
                dict(product=line["product"], qty=line["qty_done"], picking=p["name"])
                for p in self.pickings if p["type"] == "incoming" and p["dock"] == f"DOCK-W{k}"
                for line in p["lines"] if line["qty_done"]], kind="area")
        self.location("QC-1", f"{WH}/Приймання/Карантин", [
            dict(product="DSP16-ANT", qty=25, lot="DSP16-ANT-2608-77", quality="QC/00412")], kind="area")

    # ---------------------------------------------------------------- люди та обладнання
    def build_people_equipment(self):
        ni = 0
        for mch in MACHINES:
            code, typ, name = mch[:3]
            wc = self.workcenters[code]
            if wc["status"] == "idle" or typ in ("sortbot", "dry"):
                continue
            emp = f"OP-{code}"
            self.employees[emp] = dict(
                name=NAMES[ni % len(NAMES)], job="Налагоджувальник" if wc["status"] == "stop" else "Оператор",
                department="Виробництво", workcenter=code, shift="Зміна 1 (07:00–15:30)",
                current_workorder=wc["current_workorder"])
            ni += 1
        for emp, job, dep in (("OP-W1", "Комірник", "Склад сировини"), ("OP-W2", "Комірник", "Склад сировини"),
                              ("OP-W3", "Приймальник", "Логістика"), ("OP-W4", "Контролер ВТК", "Якість"),
                              ("OP-W5", "Оператор порталу", "Склад сировини"),
                              ("OP-W6", "Комірник ГП", "Склад ГП"), ("OP-W7", "Комплектувальник", "Склад ГП")):
            self.employees[emp] = dict(name=NAMES[ni % len(NAMES)], job=job, department=dep,
                                       shift="Зміна 1 (07:00–15:30)")
            ni += 1
        if "OP-CNC-2" in self.employees:
            for mr in self.maintenance:
                if mr["equipment"] == "CNC-2":
                    mr["technician"] = self.employees["OP-CNC-2"]["name"]
        fl = {"FL-1": ("Навантажувач ГП 1", 0.64, "WH/SFP/00201"), "FL-2": ("Навантажувач приймання", 0.41,
                                                                          "WH/IN/00128"),
              "FL-3": ("Навантажувач відвантаження", 0.78, "WH/OUT/00413"),
              "FL-4": ("Навантажувач ГП 2", 0.52, "WH/OUT/00416"),
              "FL-5": ("Навантажувач пакування", 0.88, "WH/SFP/00202"),
              "FL-C1": ("Навантажувач (резерв)", 0.23, None), "FL-C2": ("Навантажувач (резерв)", 0.57, None)}
        for code, (name, bat, task) in fl.items():
            self.equipment[code] = dict(name=name, category="Навантажувачі", serial=f"FL-{4100 + det(code, mod=900)}",
                                        battery=bat, hours=1800 + det(code, mod=3000),
                                        next_maintenance=ts((NOW + timedelta(days=3 + det(code, mod=20))).replace(
                                            hour=8, minute=0)),
                                        current_task=task, state="charging" if code.startswith("FL-C") else "busy")
        self.equipment["TUGGER-1"] = dict(name="Електротягач", category="Внутрішній транспорт", battery=0.71,
                                          hours=920, current_task="WH/PC/00322",
                                          next_maintenance=ts((NOW + timedelta(days=9)).replace(hour=8, minute=0)))
        self.equipment["GANTRY-1"] = dict(name="Портальний склад плит", category="Склад",
                                          cycles_today=214 + det("g", mod=40), vacuum_kpa=-72,
                                          next_maintenance=ts((NOW + timedelta(days=4)).replace(hour=7, minute=0)))
        self.equipment["COMPRESSOR"] = dict(name="Компресорна станція", category="Енергетика", pressure_bar=6.8,
                                            hours=17840, load=0.63,
                                            next_maintenance=ts((NOW + timedelta(days=8)).replace(hour=7, minute=0)))
        self.equipment["DUST-1"] = dict(name="Аспірація", category="Енергетика", filter_dp_kpa=1.4, airflow_m3h=29800,
                                        next_maintenance=ts((NOW + timedelta(days=6)).replace(hour=7, minute=0)))
        self.equipment["BOILER"] = dict(name="Котельня на відходах (2 × Kalvis K-500M)", category="Енергетика",
                                        boilers="К1 і К2 у гарячому резерві: тепло зараз дає когенераційна "
                                                "установка; К1 вмикається, коли КГУ не вистачає, К2 — понад 85 % К1",
                                        supply_c=78,
                                        silo_fill=0.62, briquettes_today_kg=860)
        self.equipment["CHARGING"] = dict(name="Зарядна станція", category="Енергетика", busy=2, total=3)
        self.equipment["SPRINKLERS"] = dict(name="Спринклерна система", category="Безпека",
                                            last_inspection="2026-09-30", pressure_bar=7.2)
        self.equipment["AIR-RING"] = dict(name="Пневмомагістраль", category="Енергетика", pressure_bar=6.4,
                                          leak_check="2026-10-05")
        self.maintenance += [
            dict(id="MR/00032", name="Заміна рукавів фільтра", equipment="DUST-1", maintenance_type="preventive",
                 stage="Новий", schedule_date=self.equipment["DUST-1"]["next_maintenance"]),
            dict(id="MR/00033", name="ТО на 18 000 мотогодин", equipment="COMPRESSOR",
                 maintenance_type="preventive", stage="Новий",
                 schedule_date=self.equipment["COMPRESSOR"]["next_maintenance"]),
            dict(id="MR/00034", name="Підтікає гідравлічний шланг щогли", equipment="FL-2",
                 maintenance_type="corrective", stage="Новий", request_date=ts(NOW.replace(hour=8, minute=15))),
        ]
        self.equipment["FL-2"]["maintenance_request"] = "MR/00034"

    # ---------------------------------------------------------------- електроенергія
    def build_energy(self, specs):
        """Лічильники на фідерах ГРЩ: поточна потужність, кВт·год за зміну на верстат і на замовлення."""
        en = energy_data(specs)
        cons = en["consumers"]
        typ = {m[0]: m[1] for m in MACHINES}
        shift_min = (NOW.hour - 7) * 60 + NOW.minute  # зміна з 07:00
        for code, c in cons.items():
            wc = self.workcenters.get(code)
            if wc and code in typ:
                kf = PROFILE.get(typ[code], (0.5, 0.86))[0]
                idle = IDLE_K.get(typ[code], IDLE_DEFAULT)
                prod = min(wc["productive_minutes"], shift_min)
                c["kwh_shift"] = round(c["p_inst"] * (kf * prod + idle * (shift_min - prod)) / 60, 1)
                wc["energy"] = dict(p_now=c["p_now"], line=c["line"])
            else:
                c["kwh_shift"] = round(c["p_now"] * shift_min / 60, 1)
        for mo in self.productions:
            kwh = 0.0
            for wid in mo["workorders"]:
                w = self.workorders[wid]
                c = cons.get(w["workcenter"])
                if not c or w["state"] not in ("done", "progress"):
                    continue
                kf = PROFILE.get(typ.get(w["workcenter"]), (0.5, 0.86))[0]
                kwh += c["p_inst"] * kf * (w.get("duration") or 0) / 60
            mo["energy_kwh"] = round(kwh, 1)
            mo["energy_cost"] = round(kwh * TARIFF)
        return en

    def evacuation(self, fire):
        ev = evac_load()
        if not ev:
            return None
        rules = load_evac_rules()
        ev.update(drill_origin="FA-CNC", drill_zone="Присадка", drill_detector="2.CNC.05",
                  norm_distance=rules.get("evac_distance_prod_B", {}).get("value"),
                  norm_ref=rules.get("evac_distance_prod_B", {}).get("ref"), norm_alt=50,
                  norm_alt_ref="ДБН В.2.2-27:2025 п. 8.2.11 — якщо стінові й покрівельні панелі з полімерним "
                               "утеплювачем; тупики — не довше 25 м (п. 8.2.9); ворота не рахуються виходами "
                               "(п. 8.2.6).")
        t = fire["totals"]
        ev["drill_steps"] = [
            dict(t=0, who="Пожежна сигналізація",
                 text="Сповіщувач 2.CNC.05 над присадкою: дим і тепло — тривога на приладі."),
            dict(t=3, who="Пожежна сигналізація", text=f"Увімкнено {t['sounders']} сирен-маяків по всьому цеху."),
            dict(t=3, who="Пульт", text="Сигнал «Пожежа» передано на пульт ДСНС і черговому."),
            dict(t=6, who="Вентиляція",
                 text="Зупинено дахові установки й приплив фасадів, щоб не роздувати вогонь."),
            dict(t=9, who="Димовидалення", text="Відкрито клапани димовидалення на покрівлі."),
            dict(t=12, who="Охорона й доступ",
                 text="Розблоковано двері з контролем доступу й турнікети, шлагбауми — вгору."),
            dict(t=15, who="Евакуація",
                 text="Люди йдуть зеленими маршрутами до найближчих виходів; збір — на паркуванні."),
            dict(t=20, who="Виробництво",
                 text="Аварійна зупинка верстатів у зоні пожежі; аспірація — іскрогасіння в готовності."),
        ]
        return ev

    # ---------------------------------------------------------------- зони та підсумки
    def mo_supply(self):
        """Для кожного МО — шлях його основної плити до першої операції: фура й ворота приймання →
        вхідний контроль → стелаж → стос під порталом (звідти портал кладе лист на стіл пили)."""
        sheet_codes = {c for c, _ in SHEET_PRODUCTS}
        incoming = [p for p in self.pickings if p["type"] == "incoming" and p["partner"] == SUPPLIERS["sheets"]]
        qc_by_pick = {q["picking"]: q for q in self.quality if q.get("picking")}

        def first(prefix, product):
            return next((c for c, loc in self.locations.items() if c.startswith(prefix)
                         and any(q["product"] == product and q["qty"] for q in loc["quants"])), None)
        for mo in self.productions:
            prod = next((c["product"] for c in mo["components"] if c["product"] in sheet_codes), None)
            if not prod:
                continue
            pick = next((p for p in incoming if any(ln["product"] == prod for ln in p["lines"])), None)
            door = int(pick["dock"][-1]) if pick else 1 + sum(map(ord, prod)) % 3
            gantry, rack = first("PLT-", prod), first("RCK-", prod)
            lot = next((q.get("lot") for q in self.locations[gantry]["quants"] if q["product"] == prod), None) \
                if gantry else None
            if pick and pick["truck"]:  # така сама плита саме розвантажується
                steps = [dict(code=pick["truck"], label="фура", doc=pick["name"],
                              note=f"Ворота {door} · {pick['name']} — ця плита зараз розвантажується")]
            elif pick and not rack:  # дефіцит — чекаємо фуру
                steps = [dict(code=f"DOCK-W{door}", label="фура о " + pick["scheduled_date"][11:16], doc=pick["name"],
                              note=f"Ворота {door} · {pick['name']}: фура ще в дорозі")]
            else:
                steps = [dict(code=f"DOCK-W{door}", label="ворота", note=f"Ворота {door} · прийнято раніше"
                              + (f", лот {lot}" if lot else ""))]
            steps.insert(0, dict(code="GATE-W", label="в'їзд", note="КПП приймання, реєстрація фури"))
            qc = qc_by_pick.get(pick["name"]) if pick and pick["truck"] else None
            steps += [dict(code=f"UNLOAD-{door}", label="вивантаження", note="звірка з накладною"),
                      dict(code=f"QC-PLT-{door}", label="контроль", doc=qc["name"] if qc else None,
                           note=(qc["note"] if qc else "вхідний контроль пройдено при прийманні"))]
            if rack:
                steps.append(dict(code=rack, label="стелаж", note=self.locations[rack]["complete_name"]))
            if gantry:
                steps.append(dict(code=gantry, label="під порталом",
                                  note=(f"лот {lot}" if lot else "") + " · портал кладе лист на стіл пили"))
            mo["supply"] = dict(product=prod, steps=steps, lot=lot,
                                warn=None if rack or gantry else "Плити немає ні в стелажах, ні під порталом",
                                note=None if rack else "У стелажах немає — під порталом останні аркуші; "
                                f"поповнення з {pick['name'] if pick else 'наступного приймання'}")

    def component_sources(self):
        """Шлях кожного матеріалу МО від в'їзду фури до верстата, що його споживає:
        плити й ХДФ — через контроль, стелажі й портал; фурнітура — контроль, зважування, етикетка,
        стелаж, комплект у візку, тягач; крайка, ЛФМ і плівка, пакматеріали — зі своїх складів."""
        door_of = {"FUR": 4, "EB": 5, "LFM": 6, "PVC": 6, "PK": 7}
        kind_of = {"FUR": "фурнітура", "EB": "крайка", "LFM": "ЛФМ", "PVC": "плівка ПВХ", "PK": "пакування"}
        incoming = sorted((p for p in self.pickings if p["type"] == "incoming"), key=lambda p: p["scheduled_date"])
        trucks = {int(p["dock"][-1]): p["truck"] for p in incoming if p.get("truck")}
        kits = {loc.get("production"): c for c, loc in self.locations.items() if c.startswith("KIT-")}

        def first(prefix, product):
            return next((c for c, loc in self.locations.items() if c.startswith(prefix)
                         and any(q["product"] == product and q["qty"] for q in loc["quants"])), None)
        for mo in self.productions:
            wcs = [self.workorders[w]["workcenter"] for w in mo["workorders"]]

            def wc(*pre):
                return next((w for w in wcs if w.startswith(pre)), None)
            for c in mo["components"]:
                prod = c["product"]
                pre = next((k for k in ("DSP", "MDF", "HDF", "FUR", "EB", "LFM", "PVC", "PK")
                            if prod.startswith(k)), "")
                rec = [p for p in incoming if any(ln["product"] == prod for ln in p["lines"])]
                got = [p for p in rec if p["progress"] > 0]  # уже розвантажене сьогодні
                pick = (got or rec or [None])[-1]
                c["door"] = int(pick["dock"][-1]) if pick else door_of.get(pre, 1 + sum(map(ord, prod)) % 3)
                if got:
                    c["receipt"] = got[-1]["name"]
                elif rec:  # на складі із залишку, наступна партія ще їде
                    c["expected"] = f"{rec[-1]['name']} о {rec[-1]['scheduled_date'][11:16]}"
                k = c["door"]
                path = [dict(code="GATE-W", label="в'їзд"),
                        dict(code=trucks.get(k) or f"DOCK-W{k}", label=f"ворота {k}"),
                        dict(code=f"UNLOAD-{k}", label="вивантаження")]
                if pre in ("DSP", "MDF", "HDF"):
                    c["kind"], c["to"] = "плита", wc("SAW", "NEST", "SLIDE", "VSAW")
                    path.append(dict(code=f"QC-PLT-{k}", label="контроль"))
                    for loc, lbl in ((first("RCK-", prod), "стелаж"), (first("PLT-", prod), "під порталом")):
                        if loc:
                            path.append(dict(code=loc, label=lbl))
                elif pre == "FUR":
                    c["kind"] = kind_of[pre]
                    c["to"] = wc("ASM", "ASMLINE") or wc("HINGE")
                    path += [dict(code="QC-1", label="контроль"), dict(code="SCALE-RCV", label="зважування"),
                             dict(code="PRN-RCV", label="етикетка партії")]
                    cell = first("FUR-", prod)
                    if cell:
                        path.append(dict(code=cell, label="стелаж фурнітури"))
                    if c["to"] and c["to"].startswith("ASM"):
                        path.append(dict(code=kits.get(mo["name"], "Z-PRE"), label="комплект WH/PC"
                                         if mo["name"] in kits else "буфер комплектів"))
                    path.append(dict(code="TUGGER-1", label="тягач"))
                elif pre == "EB":
                    c["kind"], c["to"] = kind_of[pre], wc("EDGE")
                    cell = first("EB-", prod)
                    if cell:
                        path.append(dict(code=cell, label="склад крайки"))
                elif pre in ("LFM", "PVC"):
                    c["kind"] = kind_of[pre]
                    c["to"] = (wc("PRESS") if pre == "PVC" else wc("GLUE") if prod == "LFM-GLUE"
                               else wc("AUTOSPRAY", "SPRAY", "UV")) or wc("GLUE", "SPRAY", "PRESS")
                    path.append(dict(code="PAINT-STORE", label="склад ЛФМ"))
                elif pre == "PK":
                    c["kind"], c["to"] = kind_of[pre], wc("BOX", "PACK")
                    path += [dict(code="PACK-STORE", label="пакматеріали"), dict(code="PAL-1", label="піддони")]
                    if c["to"] != "BOX-1":
                        path.append(dict(code="BOX-1", label="коробки з гофрокартону"))
                c["path"] = path

    def mo_delivery(self):
        """Для кожного МО на замовлення клієнта — шлях після пакування: вихід з пакування → комірка складу ГП
        → зона відвантаження перед воротами → ворота → машина клієнта."""
        pk = {p["name"]: p for p in self.pickings}
        sale = {so["name"]: so for so in self.sale}
        sfp = {p["origin"]: p["name"] for p in self.pickings if p["type"] == "store_finished"}
        fg = [c for c in self.locations if c.startswith("FG-R")]
        for mo in self.productions:
            so = sale.get(mo["origin"])
            if not so:  # фасади йдуть у буфер комплектів до свого корпусу
                continue
            out = pk.get(so.get("delivery"))
            if not out:
                continue
            k = out["dock"][-1]
            cell = next((c for c in out["source_locations"]
                         if any(q["product"] == mo["product"] for q in self.locations[c]["quants"])), None)
            cell = cell or next((c for c in fg if any(q["product"] == mo["product"]
                                                      for q in self.locations[c]["quants"])), None)
            cell = cell or next((c for c in fg if not self.locations[c]["quants"]), fg[0])
            last = self.workorders[mo["workorders"][-1]]["workcenter"]
            steps = [dict(code="PRN-PACK2" if last in ("PACK-2", "PACKLINE-1") else "PRN-PACK1",
                          label="етикетка SSCC", note="друк з Odoo через IoT Box")] if last.startswith("PACK") else []
            steps += [dict(code="POST-STAGE", label="вихід з пакування", doc=sfp.get(mo["name"]),
                          note="палета запакована, етикетка SSCC — чекає розміщення"),
                     dict(code=cell, label="склад ГП", note=self.locations[cell]["complete_name"]),
                     dict(code="SCALE-OUT1" if int(k) <= 4 else "SCALE-OUT2", label="зважування палети",
                          note="вага в документ відвантаження"),
                     dict(code=f"Z-OUT-{k}", label=f"відвантаження · ворота {k}", doc=out["name"],
                          note=f"комплектування {out['name']} для {so['partner']}"),
                     dict(code=out["dock"], label="ворота", note=f"Ворота відвантаження {k}")]
            if out.get("truck"):
                steps.append(dict(code=out["truck"], label="фура клієнта",
                                  note=f"{out.get('carrier') or ''} · завантаження {round(out['progress'] * 100)} %"))
            steps += [dict(code="TRUCK-SCALE", label="вагова", note="контрольне зважування машини на виїзді"),
                      dict(code="GATE-E", label="виїзд", note="через КПП відвантаження")]
            mo["delivery"] = dict(picking=out["name"], partner=so["partner"], steps=steps,
                                  note=None if out.get("truck") else
                                  f"Машину ще не подано — відвантаження {out['scheduled_date'][:16].replace('-', '.')}"
                                  + (" · чекає завершення МО" if out["state"] == "waiting" else ""))
        # фасади: буфер фасадів → складання свого корпусу → далі шлях корпусу до клієнта
        by_name = {m["name"]: m for m in self.productions}
        for mo in self.productions:
            parent = by_name.get(mo["origin"])
            if not parent or not parent.get("delivery"):
                continue
            buf = next((c for c, loc in self.locations.items() if c.startswith("FRONTS-")
                        and loc.get("fronts_mo") == mo["name"]), None)
            asm = next((self.workorders[w]["workcenter"] for w in parent["workorders"]
                        if self.workorders[w]["workcenter"].startswith("ASM")), None)
            steps = ([dict(code=buf, label="буфер фасадів", note=self.locations[buf]["complete_name"])] if buf else [])
            if asm:
                steps.append(dict(code=asm, label=f"складання {parent['name'][-5:]}",
                                  note=f"фасади ставлять на корпус {parent['name']}"))
            pd = parent["delivery"]
            mo["delivery"] = dict(picking=pd["picking"], partner=pd["partner"], via=parent["name"],
                                  steps=steps + pd["steps"], note=pd["note"])
        full = next((m for m in self.productions if m["state"] == "progress" and m.get("delivery")
                     and any(st["code"].startswith("TRUCK-OUT") for st in m["delivery"]["steps"])
                     and any(st["code"].startswith("TRUCK-IN") for st in m.get("supply", {}).get("steps", []))
                     and any(c["product"].startswith("FUR") and "KIT-" in str(c.get("path"))
                             for c in m["components"])), None)
        self.full_cycle_mo = full["name"] if full else self.productions[0]["name"]

    def material_paths(self):
        """Типовий шлях кожного виду матеріалу (з першого МО, де він є) — для вкладки «Логістика»."""
        out = {}
        for mo in self.productions:
            for c in mo["components"]:
                k = c.get("kind")
                if k and k not in out and c.get("to"):
                    out[k] = dict(kind=k, product=c["product"], mo=mo["name"],
                                  steps=c["path"] + [dict(code=c["to"], label=self.workcenters[c["to"]]["name"])])
        return list(out.values())

    def ship_chain(self):
        """Ланцюжок відвантаження від пакування до машини клієнта."""
        outs = [p for p in self.pickings if p["type"] == "outgoing"]
        fg = [c for c in self.locations if c.startswith("FG-R")]
        full = sum(1 for c in fg if self.locations[c]["quants"])
        steps = [
            dict(n=1, title="Пакування", codes=["PACK-1", "PACK-2", "PACKLINE-1"], stock="",
                 desc="Остання операція МО: палетообмотувачі й лінія термоусадки."),
            dict(n=2, title="Вихід з пакування", codes=["POST-STAGE"],
                 stock=f"{sum(1 for p in self.pickings if p['type'] == 'store_finished')} палети на розміщення",
                 desc="Палета з етикеткою SSCC чекає навантажувача (WH/SFP — розміщення готової продукції)."),
            dict(n=3, title="Склад готової продукції", codes=[f"FG-RACK-R{r}" for r in range(1, 6)],
                 stock=f"{full} з {len(fg)} комірок зайнято",
                 desc="Палетні стелажі; під кожне відвантаження резервуються комірки."),
            dict(n=4, title="Зона відвантаження перед воротами", codes=[f"Z-OUT-{k}" for k in range(1, 8)],
                 stock=f"{len(outs)} відвантажень сьогодні",
                 desc="Комплектування WH/OUT у коридорі перед своїми воротами."),
            dict(n=5, title="Фура клієнта", codes=[p["truck"] for p in outs if p.get("truck")],
                 stock=f"{sum(1 for p in outs if p.get('truck'))} машини біля воріт",
                 desc="Завантаження через докшелтер, документи — з Odoo."),
        ]
        return dict(steps=steps)

    def sheet_chain(self):
        """Ланцюжок плит від фури до пили: кроки з об'єктами сцени, документами Odoo й залишками."""
        def sheets(prefix):
            return sum(q["qty"] for c, loc in self.locations.items() if c.startswith(prefix) for q in loc["quants"])

        def stacks(prefix):
            n = sum(len(loc["quants"]) if c.startswith(("UNLOAD-", "QC-PLT-")) else 1  # біля воріт — по стосах
                    for c, loc in self.locations.items() if c.startswith(prefix) and loc["quants"])
            word = "стос" if n % 10 == 1 and n % 100 != 11 else \
                "стоси" if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else "стосів"
            return f"{n} {word}"
        PLT_DOORS = ("UNLOAD-1", "UNLOAD-2", "UNLOAD-3")  # ворота плит; 4–7 — фурнітура, крайка, ЛФМ, пакування
        pk = {p["name"]: p for p in self.pickings}
        put, rep = pk["WH/INT/00061"], pk["WH/INT/00072"]
        saw_mo = next((m["name"] for m in self.productions if m["state"] == "progress" and any(
            self.workorders[w]["workcenter"] == "SAW-1" and self.workorders[w]["state"] == "progress"
            for w in m["workorders"])), self.productions[0]["name"])
        steps = [
            dict(n=1, title="Вивантаження з фури", docs=["WH/IN/00128", "WH/IN/00129"],
                 codes=["TRUCK-IN-1", "UNLOAD-1", "TRUCK-IN-2", "UNLOAD-3", "UNLOAD-2"],
                 stock=f"{stacks(PLT_DOORS)} · {sheets(PLT_DOORS)} арк.",
                 desc="Стоси знімають із фури біля воріт 1–3 і звіряють із накладною (WH/IN → Вхід)."),
            dict(n=2, title="Приймання й контроль якості", docs=["QC/00413", "QC/00415", "QC/00416", "QC/00412"],
                 codes=["QC-PLT-1", "QC-PLT-2", "QC-PLT-3", "QC-1"],
                 stock=f"{stacks('QC-PLT-')} · {sheets('QC-PLT-')} арк.",
                 desc="Товщина, декор, кромки, вологість. Брак — у карантин біля воріт 4, решта — у стелажі."),
            dict(n=3, title="Склад плит · стелажі", docs=["WH/INT/00061", "WH/INT/00060"],
                 codes=["BOARD-RACKS", put["location_dest"], "FL-2"],
                 stock=f"{stacks('RCK-')} · {sheets('RCK-')} арк.",
                 desc="8 ліній стелажів по 4 яруси; навантажувач кладе стос із площадки контролю."),
            dict(n=4, title="Склад під порталом", docs=["WH/INT/00072", "WH/INT/00071", "WH/INT/00073"],
                 codes=["GANTRY-1", rep["location_dest"], "FL-6"],
                 stock=f"{stacks('PLT-')} · {sheets('PLT-')} арк.",
                 desc="Навантажувач ставить цілий стос у ряд під порталом через ворота з блокуванням зони."),
            dict(n=5, title="Виробництво", docs=[saw_mo],
                 codes=["SAW-1", "SAW-2", "SAW-3", "NEST-1"], stock="портал подає по одному листу",
                 desc="Портал кладе лист на підйомний стіл розкрійного центру чи нестингу."),
        ]
        path = [("TRUCK-IN-1", "1 · фура"), ("UNLOAD-1", "1 · вивантаження"), ("QC-PLT-1", "2 · контроль"),
                (put["location_dest"], "3 · стелаж"), (rep["location_dest"], "4 · під порталом"),
                ("SAW-1", "5 · розкрій")]
        return dict(steps=steps, path=[dict(code=c, label=lbl) for c, lbl in path])

    def build(self):
        self.build_catalog()
        self.build_stock()
        self.build_production()
        self.build_workcenters()
        self.build_logistics()
        self.mo_supply()
        self.component_sources()
        self.mo_delivery()
        self.build_people_equipment()
        specs = load_specs()
        for code, eq in self.equipment.items():  # модель і серійник — у maintenance.equipment
            pp = passport(code, specs)
            if pp:
                eq.update(manufacturer=pp["manufacturer"], model=pp["model"])
        for code, wc in self.workcenters.items():
            pp = passport(code, specs)
            if pp:
                wc.update(manufacturer=pp["manufacturer"], model=pp["model"])
        zones = {}
        prefix = {"Z-SHEETS": ("PLT-", "RCK-"), "Z-HW": ("FUR-",), "Z-EDGE": ("EB-",),
                  "Z-PKS": ("PACK-STORE", "PAL-"),
                  "Z-FG": ("FG-R",),
                  "Z-POST": ("POST-STAGE",), "Z-PRE": ("KIT-", "FRONTS-1", "FRONTS-2", "FRONTS-3",
                            "FRONTS-7", "FRONTS-8"),
                  "Z-FAC": ("PAINT-STORE", "FRONTS-4", "FRONTS-5", "FRONTS-6")}
        odoo_loc = {"Z-SHEETS": "WH/Сировина/Плити", "Z-HW": "WH/Сировина/Фурнітура", "Z-EDGE": "WH/Сировина/Крайка",
                    "Z-PKS": "WH/Сировина/Пакування", "Z-FG": "WH/Готова продукція",
                    "Z-POST": "WH/Пост-виробництво", "Z-PRE": "WH/Передвиробництво"}
        for k in range(1, len(DOOR_Y) + 1):  # окрема зона перед кожними воротами
            qc = (f"QC-PLT-{k}",) if k <= 3 else ("QC-1",) if k == 4 else ()
            prefix[f"Z-RCV-{k}"] = (f"UNLOAD-{k}",) + qc
            odoo_loc[f"Z-RCV-{k}"] = f"WH/Приймання/Ворота {k}"
            odoo_loc[f"Z-OUT-{k}"] = f"WH/Відвантаження/Ворота {k}"
        wc_zone = {}
        for mch in MACHINES:
            code, _, _, x, y = mch[:5]
            for zc, _, (x0, y0, x1, y1), _, _ in ZONES:
                if x0 <= x <= x1 and y0 <= y <= y1:
                    wc_zone.setdefault(zc, []).append(code)
                    break
        for zc, name, *_ in ZONES:
            locs = [c for c in self.locations if prefix.get(zc) and c.startswith(prefix[zc])]
            zones[zc] = dict(name=name, odoo_location=odoo_loc.get(zc), locations=locs,
                             workcenters=wc_zone.get(zc, []))
        for p in self.pickings:
            if p.get("dock"):
                side, k = p["dock"][5], p["dock"][6:]
                zones[f"Z-{'RCV' if side == 'W' else 'OUT'}-{k}"].setdefault("pickings", []).append(p["name"])
        energy = self.build_energy(specs)
        lux_norms = load_lux_norms()
        groups = light_layout(specs, lux_norms)
        lighting = dict(groups={k: {kk: vv for kk, vv in g.items() if kk != "fixtures"} for k, g in groups.items()},
                        panels=panels_load(groups), uf=0.7, mf=0.8,
                        norms_ref={k: v.get("ref") for k, v in lux_norms.items()})
        infra = infra_data(specs, energy, ventilation_data(specs))
        it = infra["totals"]
        energy["totals"].update(pv_kw=it["pv_now"], grid_kw=it["grid_kw"], pv_today=it["pv_today"],
                                chp_kw=it["chp_kw"], export_kw=it["export_kw"], bess_kw=it["bess_kw"])
        fire = fire_data(specs)
        evac = self.evacuation(fire)
        self.maintenance.append(dict(id="MR/00036", name="Очистити сповіщувач 2.FAC.07 (запиленість 82 %)",
                                     equipment="FA-FAC", maintenance_type="corrective", stage="Новий",
                                     request_date=ts(NOW.replace(hour=9, minute=58))))
        fire["groups"]["FA-FAC"]["maintenance_request"] = "MR/00036"
        vent = ventilation_data(specs)
        vent["units"]["RV-05"]["maintenance_request"] = "MR/00035"
        self.maintenance.append(dict(id="MR/00035", name="Заміна фільтрів: перепад тиску 285 Па при нормі до 250",
                                     equipment="RV-05", maintenance_type="preventive", stage="Новий",
                                     request_date=ts(NOW.replace(hour=6, minute=50))))
        return dict(
            meta=dict(source="Odoo 19 · демо-дані", database="mebli-demo", company="Меблева фабрика (демо)",
                      warehouse=WH, now=ts(NOW), note="Згенеровано скриптом plant/odoo_demo.py; "
                      "формат повторює моделі Odoo, ключі — коди об'єктів 3D-сцени."),
            products=self.products, locations=self.locations, workcenters=self.workcenters,
            productions=self.productions, workorders=self.workorders, sale_orders=self.sale,
            purchase_orders=self.purchase, pickings=self.pickings, quality_checks=self.quality,
            maintenance_requests=self.maintenance, equipment=self.equipment, employees=self.employees,
            docks=self.docks, zones=zones, energy=energy, lighting=lighting, ventilation=vent, fire=fire, infra=infra,
            evacuation=evac, sheet_chain=self.sheet_chain(), ship_chain=self.ship_chain(),
            material_paths=self.material_paths(),
            full_cycle_mo=self.full_cycle_mo,
            passports={**{c: pp for c in ROLE_BY_CODE if (pp := passport(c, specs))}, **passport_energy(specs)})


def load_evac_rules():
    import os
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evac_rules.json")
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def generate():
    return Demo().build()


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "odoo_demo.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(generate(), f, ensure_ascii=False, separators=(",", ":"))
    print(out)
