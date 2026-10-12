"""Меблеве підприємство: виробництво та склади — процедурна 3D-сцена.

Запуск (Blender як Python-модуль, pip install bpy):
    python build_scene.py dist/
або у Blender:
    blender -b -P build_scene.py -- dist/

Результат: factory.glb, factory.usdz, factory.blend, index.html, factory_viewer.html.

Координати в метрах. Осі Blender: X — уздовж будівлі (потік матеріалу зліва
направо), Y — поперек, Z — угору. При експорті в glTF вісь Y стає вертикальною.

Структура сцени:
  FACTORY                 корінь (extras: dims — габарити будівлі)
    LAYER_<key>           порожній об'єкт-шар (у переглядачі — перемикач шару)
      <об'єкт>            у кожного клікабельного об'єкта є властивості
                          code / kind / label / desc (у glTF це extras)

Однакові об'єкти (верстати одного типу, стелажі, палети, комірки) посилаються
на спільний меш — у glTF він зберігається один раз, тому файл лишається малим.
"""
import base64
import json
import math
import os
import shutil
import sys

import bpy  # noqa: I001 — bpy має імпортуватися раніше за bmesh/mathutils
import bmesh
from mathutils import Euler, Matrix, Vector

# --------------------------------------------------------------------------
# Планування
# --------------------------------------------------------------------------
W, D, H = 120.0, 72.0, 9.0  # будівля: довжина, ширина, висота

LAYERS = [
    ("building", "Будівля"),
    ("roof", "Покрівля, ферми, світло"),
    ("zones", "Розмітка зон"),
    ("receiving", "Приймання та ВТК"),
    ("sheets", "Склад плит"),
    ("hardware", "Склад фурнітури"),
    ("edge", "Склад крайки"),
    ("buffer", "Буфер комплектів"),
    ("line", "Виробничі дільниці"),
    ("facade", "Дільниця фасадів МДФ"),
    ("dust", "Аспірація"),
    ("utilities", "Інженерні системи"),
    ("fg", "Склад готової продукції"),
    ("shipping", "Відвантаження"),
    ("transport", "Транспорт"),
    ("people", "Персонал"),
    ("flow", "Маршрут виробу"),
]

# code, назва, (x0, y0, x1, y1), колір заливки, опис
ZONES = [
    ("Z-RCV", "Приймання", (0.6, 0.6, 15.4, 25.4), "#8fb9d6",
     "Розвантаження фур із плитою та фурнітурою, звірка з накладною. Троє воріт."),
    ("Z-QC", "Вхідний контроль", (0.6, 26.0, 15.4, 35.4), "#c3a6d1",
     "Перевірка декору, товщини й геометрії плит перед розміщенням."),
    ("Z-EDGE", "Склад крайки", (0.6, 36.0, 15.4, 59.4), "#efcfae",
     "Рулони крайки ПВХ за декорами й товщинами."),
    ("Z-SHEETS", "Склад плит", (16.0, 0.6, 44.4, 30.4), "#d2c0dc",
     "Автоматизований склад: портал із вакуумним захопленням подає плити на розкрій."),
    ("Z-HW", "Склад фурнітури", (16.0, 31.0, 44.4, 59.4), "#b1d8bf",
     "Шість стелажів з комірками: завіси, напрямні, кріплення, ручки."),
    ("Z-PRE", "Буфер комплектів", (45.0, 26.0, 49.4, 59.4), "#eadf9f",
     "Візки з фурнітурою під замовлення для дільниці збирання."),
    ("Z-CUT", "Розкрій", (50.0, 0.6, 61.6, 44.4), "#b9d3e6",
     "Три розкрійні центри та нестинг-ЧПК для МДФ."),
    ("Z-EB", "Крайкооблицювання", (62.0, 0.6, 78.4, 25.4), "#b9d3e6",
     "Три прохідні крайкооблицювальні верстати."),
    ("Z-CNC", "Присадка ЧПК", (79.0, 0.6, 98.4, 25.4), "#b9d3e6",
     "Чотири портальні обробні центри та візки сортування деталей."),
    ("Z-ASM", "Збирання", (62.0, 26.0, 90.4, 44.4), "#c6dcc0",
     "Шість збиральних дільниць із корпусними ваймами."),
    ("Z-PACK", "Пакування", (90.8, 26.0, 98.4, 44.4), "#e3d3b4",
     "Пакувальні столи й палетообмотувачі."),
    ("Z-OFFICE", "Офіс", (50.0, 45.0, 63.6, 59.4), "#d5d8dc",
     "Майстри дільниць, технологи, планування змін."),
    ("Z-MAINT", "Ремонтна дільниця", (64.0, 45.0, 80.4, 59.4), "#d5d8dc",
     "Обслуговування верстатів, заточування та заміна інструменту."),
    ("Z-SOC", "Побутові приміщення", (80.8, 45.0, 98.4, 59.4), "#d5d8dc",
     "Роздягальні, їдальня, медпункт."),
    ("Z-POST", "Вихід з лінії", (99.0, 24.6, 119.4, 30.4), "#eadf9f",
     "Запаковані вироби чекають на розміщення на складі."),
    ("Z-FG", "Склад готової продукції", (99.0, 31.0, 119.4, 59.4), "#b4dfc1",
     "Вісім рядів палетних стелажів, 4 яруси."),
    ("Z-OUT", "Відвантаження", (99.0, 0.6, 119.4, 24.0), "#ecbdb7",
     "Комплектування відвантажень за замовленнями, четверо воріт."),
    ("Z-PKS", "Склад пакувальних матеріалів", (0.6, 60.6, 39.4, 71.4), "#e3d3b4",
     "Гофрокартон, стрейч-плівка, порожні палети."),
    ("Z-PNT", "Склад ЛФМ", (39.8, 60.6, 49.4, 71.4), "#ecbdb7",
     "Фарби, лаки, клей. Вогнестійке приміщення."),
    ("Z-FAC", "Дільниця фасадів МДФ", (49.8, 60.6, 98.4, 71.4), "#d9c7e8",
     "Шліфування → клей → мембранний прес або фарбування → сушіння → УФ-лак."),
    ("Z-CMP", "Компресорна", (98.8, 60.6, 109.4, 71.4), "#d5d8dc",
     "Гвинтові компресори, ресивер, осушувач."),
    ("Z-CHG", "Зарядна станція", (109.8, 60.6, 119.4, 71.4), "#d5d8dc",
     "Заряджання тягових акумуляторів навантажувачів."),
]

# Ворота: стіна, центр по Y, ширина
DOORS = [("W", 5.0, 3.4), ("W", 11.0, 3.4), ("W", 17.0, 3.4),
         ("E", 4.0, 3.4), ("E", 9.5, 3.4), ("E", 15.0, 3.4), ("E", 20.5, 3.4)]
DOOR_H = 4.5

SHEET_DECORS = [
    ("ДСП 16 мм Дуб Сонома", "#c9a46f"),
    ("ДСП 16 мм Білий", "#efede6"),
    ("ДСП 16 мм Антрацит", "#45484c"),
    ("ДСП 16 мм Венге", "#4b3426"),
    ("ДСП 18 мм Бетон", "#a7a39b"),
    ("МДФ 18 мм під фарбування", "#b08a5a"),
    ("ХДФ 3 мм білий", "#e8e4da"),
]
# Портальний склад плит: сітка стосів 7 × 6
SHEET_COLS_X = [18.6 + 3.3 * i for i in range(7)]
SHEET_ROWS_Y = [3.0 + 3.0 * j for j in range(6)]

MACHINES = [
    # code, тип, назва, x, y, опис
    ("SAW-1", "saw", "Розкрій 1", 55.8, 5.0,
     "Розкрійний центр із притискною балкою та програмним штовхачем. Ріже плиту 2800×2070 "
     "на деталі за картою розкрою."),
    ("SAW-2", "saw", "Розкрій 2", 55.8, 14.5, "Розкрійний центр, ДСП 16–18 мм."),
    ("SAW-3", "saw_book", "Пакетний розкрій", 55.8, 24.0,
     "Розкрійний центр для пакетного розкрою: ріже «книгу» плит висотою до 150 мм."),
    ("NEST-1", "nest", "Нестинг ЧПК", 55.8, 35.0,
     "Фрезерний центр для нестингу: розкрій МДФ-фасадів і криволінійних деталей, "
     "автоматичне завантаження та вивантаження."),
    ("EDGE-1", "edge_robot", "Крайкооблицювання 1", 70.2, 4.0,
     "Прохідний крайкооблицювальний верстат із лазерним агрегатом (шов без клею), торцювання, "
     "фрезерування звисів, циклювання. Робот повертає деталі на повертальний конвеєр."),
    ("EDGE-2", "edge", "Крайкооблицювання 2", 70.2, 11.0, "Прохідний верстат, крайка 0,4–2 мм."),
    ("EDGE-3", "edge", "Крайкооблицювання 3", 70.2, 18.0, "Прохідний верстат, PUR-клей."),
    ("CNC-1", "cnc", "Присадка ЧПК 1", 84.0, 5.0,
     "Портальний обробний центр із ЧПК: свердлильна голова, магазин інструменту, "
     "вакуумні присоски на консолях."),
    ("CNC-2", "cnc", "Присадка ЧПК 2", 84.0, 13.5, "Портальний обробний центр."),
    ("CNC-3", "cnc", "Присадка ЧПК 3", 93.0, 5.0, "Портальний обробний центр."),
    ("CNC-4", "cnc", "Присадка ЧПК 4", 93.0, 13.5, "Портальний обробний центр."),
]
for i, (x, y) in enumerate(((66.0, 29.0), (75.0, 29.0), (84.0, 29.0),
                            (66.0, 34.0), (75.0, 34.0), (84.0, 34.0)), 1):
    MACHINES.append((f"ASM-{i}", "asm", f"Збирання {i}", x, y,
                     "Корпусна вайма з пневмоприжимами та верстак для встановлення фурнітури."))
MACHINES += [
    ("PACK-1", "pack", "Пакування 1", 94.6, 30.5,
     "Пакувальний стіл із гофрокартоном і палетообмотувач стрейч-плівкою."),
    ("PACK-2", "pack", "Пакування 2", 94.6, 39.5, "Пакувальний стіл і палетообмотувач."),
    ("SLIDE-1", "slide", "Форматно-розкрійний", 52.6, 41.3,
     "Форматно-розкрійний верстат із кареткою для штучних і нестандартних деталей."),
    ("VSAW-1", "vsaw", "Вертикальна пила", 58.7, 41.8,
     "Вертикальна панельна пила для малих партій і обрізків, економить площу."),
    ("DOWEL-1", "dowel", "Шкантування", 66.0, 22.6,
     "Свердлильно-присадний верстат із забиванням шкантів у торці деталей."),
    ("BORE-1", "bore", "Прохідна присадка", 73.6, 22.6,
     "Прохідний свердлильний верстат для серійних деталей: чотири агрегати, стрічка подачі."),
    ("HINGE-1", "hinge", "Встановлення завіс", 82.5, 21.2,
     "Пневматичний верстат запресовує завіси та монтажні планки у фасади."),
    ("SORT-1", "sortbot", "Сортувальний робот", 91.6, 21.0,
     "Роботизована комірка сортування: буферизує деталі після присадки й видає на збирання "
     "комплектами під замовлення."),
    ("ASMLINE-1", "asmline", "Лінія збирання корпусів", 75.2, 40.4,
     "Автоматична лінія: подача, станція клею і шкантів, автоматична вайма, поворотний "
     "пристрій, вихідний конвеєр."),
    ("BOX-1", "box", "Розкрій гофрокартону", 88.9, 35.0,
     "Робить коробку під розмір виробу з фанфолд-гофрокартону."),
    ("PACKLINE-1", "packline", "Термоусадка та обв'язка", 105.0, 29.3,
     "L-зварювач, термоусадочний тунель і обв'язувальна арка на одному конвеєрі."),
    ("SAND-1", "sand", "Шліфування фасадів", 55.6, 64.0,
     "Широкострічковий шліфувальний верстат для фасадів МДФ під фарбування."),
    ("GLUE-1", "glue", "Кабіна нанесення клею", 55.0, 69.4,
     "Розпилення клею на фасади перед облицюванням плівкою ПВХ."),
    ("PRESS-1", "press", "Мембранно-вакуумний прес", 66.6, 64.2,
     "Облицювання фасадів МДФ плівкою ПВХ: ІЧ-нагрів, вакуум, два човникові столи."),
    ("AUTOSPRAY-1", "autospray", "Автомат фарбування", 68.0, 69.5,
     "Автоматичне нанесення ґрунту й емалі на фасади, зона відкритого випаровування."),
    ("SPRAY-1", "spray", "Фарбувальна камера", 78.6, 64.4,
     "Ручне фарбування з водяною завісою для штучних фасадів і доробки."),
    ("DRY-1", "dry", "Сушильна камера", 88.0, 65.6,
     "Сушіння пофарбованих фасадів на етажерках при 35–40 °C."),
    ("UV-1", "uv", "УФ-лакування", 86.0, 70.0,
     "Вальцьове нанесення лаку з УФ-отвердінням: деталь готова одразу після тунелю."),
]
STATUS = {code: "work" for code, *_ in MACHINES}
STATUS.update({"SAW-3": "idle", "EDGE-3": "idle", "CNC-2": "stop", "ASM-5": "idle",
               "VSAW-1": "idle", "UV-1": "idle"})

# Габарити верстатів (для колон і розмітки): x, y
FOOTPRINT = {"saw": (7.4, 7.6), "edge": (12.6, 3.8), "cnc": (6.6, 4.4), "asm": (6.0, 3.6),
             "pack": (5.2, 3.2), "nest": (11.2, 4.6), "saw_book": (7.4, 7.6), "edge_robot": (12.6, 3.8),
             "slide": (3.8, 3.2), "vsaw": (6.0, 2.2), "dowel": (3.8, 2.4), "bore": (7.2, 2.6),
             "hinge": (3.4, 2.0), "sortbot": (9.8, 6.4), "asmline": (24.4, 3.4), "box": (3.2, 4.0),
             "packline": (10.0, 3.6), "sand": (6.2, 4.0), "glue": (3.8, 3.0), "press": (12.4, 3.4),
             "spray": (5.6, 4.2), "autospray": (13.2, 3.6), "dry": (6.6, 7.6), "uv": (10.8, 2.6)}

# Точки підключення аспірації в локальних координатах верстата
DUCT_POINTS = {"saw": [(0.3, 1.9, 1.95)],
               "edge": [(-2.3, 0.25, 1.55), (0.6, 0.25, 1.55), (2.9, 0.25, 1.55)],
               "cnc": [(-1.9, 1.5, 1.6)],
               "nest": [(0.0, 1.6, 2.6)]}
DUCT_POINTS["saw_book"] = DUCT_POINTS["saw"]
DUCT_POINTS["edge_robot"] = DUCT_POINTS["edge"]
DUCT_POINTS.update({"slide": [(0.55, 0.9, 1.95)], "vsaw": [(0.6, 0.5, 2.9)], "dowel": [(0.0, 0.65, 1.7)],
                    "bore": [(0.0, 0.3, 1.7)], "sand": [(0.0, -0.6, 2.85), (0.0, 0.6, 2.85)]})
# Витяжка фарбувальних дільниць — окремими трубами крізь покрівлю
EXHAUST_POINTS = {"glue": [(0.0, 0.5, 2.72)], "spray": [(0.0, 1.2, 3.15)],
                  "autospray": [(-2.1, 0.5, 2.8)], "dry": [(-1.5, 1.0, 3.88)]}
DUCT_MAIN_Y, DUCT_Z = 25.7, 7.6
DUCT_NORTH_X = 48.8  # вертикальна гілка магістралі до фільтра надворі

# Маршрут виробу: точки прив'язки дуг (x, y, z)
FLOW = [
    ("Z-RCV", "Приймання", (8.0, 11.0, 1.2)),
    ("Z-SHEETS", "Склад плит", (30.0, 13.0, 2.0)),
    ("SAW-1", "Розкрій", (55.8, 5.0, 2.3)),
    ("EDGE-1", "Крайка", (70.2, 4.0, 1.9)),
    ("CNC-1", "Присадка", (84.0, 5.0, 2.7)),
    ("ASM-3", "Збирання", (84.0, 29.0, 2.4)),
    ("PACK-1", "Пакування", (94.6, 30.5, 2.6)),
    ("Z-POST", "Вихід з лінії", (106.0, 27.5, 1.4)),
    ("Z-FG", "Склад ГП", (110.0, 45.0, 3.0)),
    ("Z-OUT", "Відвантаження", (110.0, 10.0, 1.4)),
]

# Прямокутники, крізь які не можна ставити колони (заповнюються будівельниками)
OBST = []


def obst(x0, y0, x1, y1):
    OBST.append((min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))


def blocked(x, y, pad=0.4):
    return any(x0 - pad < x < x1 + pad and y0 - pad < y < y1 + pad for x0, y0, x1, y1 in OBST)


# --------------------------------------------------------------------------
# Матеріали: колір (sRGB), шорсткість, металевість, [прозорість], [світіння]
# --------------------------------------------------------------------------
PALETTE = {
    "ground": ("#3a3d40", 0.95, 0.0),
    "floor": ("#aeb2b3", 0.6, 0.0),
    "wall": ("#d9dee2", 0.7, 0.1),
    "wall_band": ("#4f6679", 0.6, 0.2),
    "steel": ("#7d8a95", 0.4, 0.75),
    "steel_dark": ("#3c4650", 0.5, 0.6),
    "column": ("#8a96a0", 0.5, 0.5),
    "alu": ("#c7ccd1", 0.3, 0.85),
    "galv": ("#b4bcc3", 0.35, 0.9),
    "marking": ("#f2c230", 0.6, 0.0),
    "hazard_black": ("#1e1f21", 0.6, 0.0),
    "rack_upright": ("#2f5d8a", 0.45, 0.4),
    "rack_beam": ("#e8742a", 0.45, 0.3),
    "shelf": ("#9aa4ad", 0.5, 0.4),
    "bin": ("#2e86c1", 0.55, 0.0),
    "bin_red": ("#c0392b", 0.55, 0.0),
    "bin_yellow": ("#e5b223", 0.55, 0.0),
    "pallet": ("#b8925a", 0.9, 0.0),
    "carton": ("#c49a64", 0.85, 0.0),
    "tape": ("#9c7444", 0.5, 0.0),
    "wrap": ("#e6eef2", 0.15, 0.0, 0.35),
    "machine": ("#e3e6e8", 0.35, 0.15),
    "machine_mid": ("#b9c0c6", 0.4, 0.2),
    "machine_accent": ("#1d6a86", 0.35, 0.25),
    "machine_dark": ("#2b3036", 0.45, 0.3),
    "phenolic": ("#f1f1ec", 0.35, 0.0),
    "guard_glass": ("#bcd9e6", 0.05, 0.0, 0.28),
    "table_top": ("#c8a878", 0.7, 0.0),
    "rubber": ("#1c1d1f", 0.9, 0.0),
    "forklift": ("#f0a224", 0.45, 0.1),
    "glass": ("#8fb8cf", 0.1, 0.0),
    "truck_cab": ("#c8ced3", 0.4, 0.5),
    "trailer": ("#eef1f3", 0.5, 0.2),
    "dock_shelter": ("#232629", 0.9, 0.0),
    "lamp_off_g": ("#2f5a3f", 0.4, 0.0),
    "lamp_off_a": ("#6b5222", 0.4, 0.0),
    "lamp_off_r": ("#5e2a26", 0.4, 0.0),
    "status_green": ("#27ae60", 0.3, 0.0),
    "status_amber": ("#f39c12", 0.3, 0.0),
    "status_red": ("#e74c3c", 0.3, 0.0),
    "estop": ("#d0281d", 0.4, 0.0),
    "screen": ("#10303f", 0.2, 0.0),
    "screen_on": ("#1d3d52", 0.2, 0.0, 1.0, ("#3aa0d8", 0.8)),
    "led": ("#f4f7fa", 0.3, 0.0, 1.0, ("#ffffff", 2.0)),
    "flow": ("#18a6c9", 0.3, 0.0),
    "edge_roll": ("#c9a46f", 0.6, 0.0),
    "trousers": ("#2b3a55", 0.85, 0.0),
    "shirt": ("#4a5563", 0.85, 0.0),
    "hivis": ("#d7e62f", 0.6, 0.0),
    "hivis_or": ("#f07c22", 0.6, 0.0),
    "skin": ("#d6a27f", 0.7, 0.0),
    "hair": ("#3b2a20", 0.9, 0.0),
    "pegboard": ("#8e969c", 0.7, 0.2),
    "film_roll": ("#e9eef1", 0.2, 0.0, 0.8),
    "robot": ("#e8822a", 0.4, 0.2),
    "heater": ("#5a1c10", 0.4, 0.0, 1.0, ("#ff5a2a", 2.5)),
    "uv": ("#2a1a50", 0.3, 0.0, 1.0, ("#8a5cff", 4.0)),
    "fire_red": ("#c62828", 0.5, 0.1),
    "air_blue": ("#2f78c4", 0.4, 0.3),
    "water_glass": ("#7fb6d6", 0.05, 0.0, 0.45),
    "filter": ("#d7d2c4", 0.9, 0.0),
    "drum_blue": ("#2459a8", 0.45, 0.3),
    "ibc": ("#eef1f3", 0.2, 0.0, 0.7),
    "carton_bag": ("#e9e4d6", 0.9, 0.0),
}
for i, (_, hex_) in enumerate(SHEET_DECORS):
    PALETTE[f"decor{i}"] = (hex_, 0.7, 0.0)
for code, _, _, hex_, _ in ZONES:
    PALETTE["zone_" + code] = (hex_, 0.9, 0.0)

EDGE_DECORS = ["#c9a46f", "#efede6", "#45484c", "#4b3426", "#a7a39b", "#efede6"]
for i, hex_ in enumerate(EDGE_DECORS):
    PALETTE[f"edge{i}"] = (hex_, 0.6, 0.0)

MAT = {}


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_to_lin(hex_):
    h = hex_.lstrip("#")
    return [srgb_to_linear(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4)]


def make_materials():
    for name, spec in PALETTE.items():
        hex_, rough, metal = spec[:3]
        alpha = spec[3] if len(spec) > 3 else 1.0
        emit = spec[4] if len(spec) > 4 else None
        rgb = hex_to_lin(hex_)
        m = bpy.data.materials.new(name)
        if hasattr(m, "use_nodes") and not m.node_tree:
            m.use_nodes = True
        bsdf = m.node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
        bsdf.inputs["Roughness"].default_value = rough
        bsdf.inputs["Metallic"].default_value = metal
        if alpha < 1.0:
            bsdf.inputs["Alpha"].default_value = alpha
            if hasattr(m, "surface_render_method"):
                m.surface_render_method = "BLENDED"
            else:
                m.blend_method = "BLEND"
        if emit:
            bsdf.inputs["Emission Color"].default_value = (*hex_to_lin(emit[0]), 1.0)
            bsdf.inputs["Emission Strength"].default_value = emit[1]
        m.diffuse_color = (*rgb, alpha)
        MAT[name] = m


# --------------------------------------------------------------------------
# Побудова геометрії
# --------------------------------------------------------------------------
LAYER_OBJ = {}
LAYER_COLL = {}


class Mesh:
    """Набирає багато примітивів в один меш (менше об'єктів — швидша сцена)."""

    def __init__(self):
        self.bm = bmesh.new()
        self.mats = []

    def _mi(self, mat):
        if mat not in self.mats:
            self.mats.append(mat)
        return self.mats.index(mat)

    def _paint(self, faces, mat, smooth=False):
        mi = self._mi(mat)
        for f in faces:
            f.material_index = mi
            f.smooth = smooth

    @staticmethod
    def _faces_of(verts):
        return {f for v in verts for f in v.link_faces}

    def box(self, c, s, mat, rz=0.0, rot=None, bev=0.0):
        """c — центр, s — розміри (x, y, z), rz — поворот навколо Z у градусах,
        rot — (rx, ry, rz) у градусах, bev — радіус скруглення ребер."""
        rx, ry, rzz = rot if rot else (0.0, 0.0, rz)
        m = (Matrix.Translation(Vector(c))
             @ Euler((math.radians(rx), math.radians(ry), math.radians(rzz))).to_matrix().to_4x4()
             @ Matrix.Diagonal((*s, 1.0)))
        r = bmesh.ops.create_cube(self.bm, size=1.0, matrix=m)
        verts = r["verts"]
        self._paint(self._faces_of(verts), mat)
        bev = min(bev, min(s) * 0.45)
        if bev > 0.004:
            edges = list({e for v in verts for e in v.link_edges})
            res = bmesh.ops.bevel(self.bm, geom=verts + edges, offset=bev, offset_type="OFFSET",
                                  segments=2 if bev >= 0.02 else 1, profile=0.5,
                                  affect="EDGES", clamp_overlap=True)
            self._paint(res["faces"], mat, smooth=True)

    def box_lo(self, x, y, z0, sx, sy, sz, mat, rz=0.0, bev=0.0):
        """Коробка, що стоїть основою на висоті z0."""
        self.box((x, y, z0 + sz / 2), (sx, sy, sz), mat, rz, bev=bev)

    def cyl(self, c, r, h, mat, axis="Z", segs=20, r2=None, rot=None):
        if rot:
            R = Euler(tuple(math.radians(a) for a in rot)).to_matrix().to_4x4()
        else:
            R = {"Z": Matrix.Identity(4),
                 "X": Matrix.Rotation(math.radians(90), 4, "Y"),
                 "Y": Matrix.Rotation(math.radians(90), 4, "X")}[axis]
        res = bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=segs,
                                    radius1=r, radius2=r if r2 is None else r2, depth=h,
                                    matrix=Matrix.Translation(Vector(c)) @ R)
        faces = self._faces_of(res["verts"])
        self._paint(faces, mat, smooth=True)
        for f in faces:  # торці пласкі
            if len(f.verts) > 4:
                f.smooth = False

    def sphere(self, c, r, mat, subdiv=2, scale=(1, 1, 1)):
        m = Matrix.Translation(Vector(c)) @ Matrix.Diagonal((*scale, 1.0))
        res = bmesh.ops.create_icosphere(self.bm, subdivisions=subdiv, radius=r, matrix=m)
        self._paint(self._faces_of(res["verts"]), mat, smooth=True)

    def cone_dir(self, tip, direction, r, h, mat, segs=16):
        d = Vector(direction).normalized()
        rot = Vector((0, 0, 1)).rotation_difference(d).to_matrix().to_4x4()
        center = Vector(tip) - d * (h / 2)
        res = bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=segs,
                                    radius1=r, radius2=0.0, depth=h,
                                    matrix=Matrix.Translation(center) @ rot)
        self._paint(self._faces_of(res["verts"]), mat, smooth=True)

    def tube(self, pts, r, mat, segs=10, caps=False):
        """Труба вздовж ламаної pts (кільця орієнтуються за дотичною)."""
        rings = []
        prev_n = None
        for i, p in enumerate(pts):
            p = Vector(p)
            a = Vector(pts[max(i - 1, 0)])
            b = Vector(pts[min(i + 1, len(pts) - 1)])
            t = (b - a).normalized()
            if prev_n is None:
                n = t.orthogonal().normalized()
            else:  # переносимо нормаль, щоб труба не перекручувалась
                n = (prev_n - t * prev_n.dot(t)).normalized()
            prev_n = n
            bn = t.cross(n)
            rings.append([self.bm.verts.new(p + (n * math.cos(2 * math.pi * k / segs)
                                                 + bn * math.sin(2 * math.pi * k / segs)) * r)
                          for k in range(segs)])
        mi = self._mi(mat)
        for r0, r1 in zip(rings, rings[1:]):
            for k in range(segs):
                f = self.bm.faces.new((r0[k], r0[(k + 1) % segs], r1[(k + 1) % segs], r1[k]))
                f.material_index = mi
                f.smooth = True
        if caps:
            for ring in (rings[0], rings[-1][::-1]):
                f = self.bm.faces.new(ring[::-1])
                f.material_index = mi

    def build(self, name, layer, parent=None, loc=(0, 0, 0), rz=0.0, **props):
        me = bpy.data.meshes.new(name)
        self.bm.normal_update()
        self.bm.to_mesh(me)
        self.bm.free()
        for m in self.mats:
            me.materials.append(MAT[m])
        ob = bpy.data.objects.new(name, me)
        place(ob, layer, parent, loc, rz, props)
        return ob


def place(ob, layer, parent, loc, rz, props):
    LAYER_COLL[layer].objects.link(ob)
    ob.parent = parent or LAYER_OBJ[layer]
    ob.location = loc
    ob.rotation_euler = (0, 0, math.radians(rz))
    for k, v in props.items():
        ob[k] = v


def empty(name, layer, loc=(0, 0, 0), rz=0.0, parent=None, **props):
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_size = 0.5
    place(ob, layer, parent, loc, rz, props)
    return ob


def make_layers():
    root = bpy.data.objects.new("FACTORY", None)
    bpy.context.scene.collection.objects.link(root)
    for order, (key, label) in enumerate(LAYERS):
        coll = bpy.data.collections.new(label)
        bpy.context.scene.collection.children.link(coll)
        LAYER_COLL[key] = coll
        ob = bpy.data.objects.new("LAYER_" + key, None)
        coll.objects.link(ob)
        ob.parent = root
        ob["layer"] = key
        ob["label"] = label
        ob["order"] = order  # glTF-експортер сортує вузли за іменем, тож порядок зберігаємо явно
        LAYER_OBJ[key] = ob


def rounded_path(pts, radius=0.4, n=6):
    """Ламана із заокругленими кутами (для повітроводів)."""
    pts = [Vector(p) for p in pts]
    out = [pts[0]]
    for a, b, c in zip(pts, pts[1:], pts[2:]):
        d1, d2 = (b - a), (c - b)
        r = min(radius, d1.length / 2, d2.length / 2)
        p0, p1 = b - d1.normalized() * r, b + d2.normalized() * r
        for i in range(n + 1):
            t = i / n
            out.append((1 - t) ** 2 * p0 + 2 * (1 - t) * t * b + t ** 2 * p1)
    out.append(pts[-1])
    return [tuple(p) for p in out]


# ---------------------------------------------------------------- дрібні деталі
def pallet(m, x, y, z=0.0, sx=1.2, sy=0.8):
    """Європалета: нижні дошки, бобишки, поперечки, верхній настил."""
    ys = (-sy / 2 + 0.05, 0.0, sy / 2 - 0.05)
    xs = (-sx / 2 + 0.07, 0.0, sx / 2 - 0.07)
    if sx < sy:  # палета повернута довгою стороною вздовж Y
        for xx in (-sx / 2 + 0.05, 0.0, sx / 2 - 0.05):
            m.box_lo(x + xx, y, z, 0.1, sy, 0.022, "pallet")
        for xx in (-sx / 2 + 0.05, 0.0, sx / 2 - 0.05):
            for yy in (-sy / 2 + 0.07, 0.0, sy / 2 - 0.07):
                m.box_lo(x + xx, y + yy, z + 0.022, 0.1, 0.14, 0.078, "pallet")
        for yy in (-sy / 2 + 0.07, 0.0, sy / 2 - 0.07):
            m.box_lo(x, y + yy, z + 0.1, sx, 0.14, 0.022, "pallet")
        for k in range(5):
            m.box_lo(x - sx / 2 + 0.05 + k * (sx - 0.1) / 4, y, z + 0.122, 0.1, sy, 0.022, "pallet")
        return
    for yy in ys:
        m.box_lo(x, y + yy, z, sx, 0.1, 0.022, "pallet")
    for xx in xs:
        for yy in ys:
            m.box_lo(x + xx, y + yy, z + 0.022, 0.14, 0.1, 0.078, "pallet")
    for xx in xs:
        m.box_lo(x + xx, y, z + 0.1, 0.14, sy, 0.022, "pallet")
    for k in range(5):
        m.box_lo(x, y - sy / 2 + 0.05 + k * (sy - 0.1) / 4, z + 0.122, sx, 0.1, 0.022, "pallet")


def cartons(m, x, y, z, sx, sy, layers, wrap=True):
    """Шари коробок 2×2 зі скотчем; за потреби — стрейч-плівка."""
    bx, by, bh = sx / 2 - 0.01, sy / 2 - 0.01, 0.4
    for k in range(layers):
        for i in (-1, 1):
            for j in (-1, 1):
                cx, cy, cz = x + i * sx / 4, y + j * sy / 4, z + k * (bh + 0.005)
                m.box_lo(cx, cy, cz, bx, by, bh, "carton", bev=0.008)
                m.box_lo(cx, cy, cz + bh, bx * 0.98, 0.05, 0.003, "tape")
    if wrap:
        m.box_lo(x, y, z - 0.01, sx + 0.03, sy + 0.03, layers * (bh + 0.005) + 0.02, "wrap")


def hazard(m, x0, x1, y, z, depth=0.02, h=0.06, along="X", w=0.12):
    """Жовто-чорна смуга безпеки."""
    n = max(1, int(abs(x1 - x0) / w))
    for i in range(n):
        c = x0 + (i + 0.5) * (x1 - x0) / n
        mat = "marking" if i % 2 == 0 else "hazard_black"
        if along == "X":
            m.box_lo(c, y, z, abs(x1 - x0) / n, depth, h, mat)
        else:
            m.box_lo(y, c, z, depth, abs(x1 - x0) / n, h, mat)


def estop(m, x, y, z):
    m.box_lo(x, y, z, 0.09, 0.09, 0.07, "marking", bev=0.01)
    m.cyl((x, y, z + 0.09), 0.035, 0.04, "estop", segs=14)


def console(m, x, y, z_top, facing=-90.0, w=0.62):
    """Пульт оператора на стійці: нахилена панель, екран, кнопка аварійної зупинки."""
    m.box_lo(x, y, 0, 0.22, 0.22, z_top - 0.05, "machine_mid", bev=0.02)
    m.box_lo(x, y, 0, 0.45, 0.45, 0.04, "machine_dark", bev=0.01)
    a = math.radians(facing)
    ox, oy = math.cos(a), math.sin(a)
    tilt = 25
    m.box((x, y, z_top + 0.12), (0.42, w, 0.07), "machine", rot=(0, -tilt, facing + 90), bev=0.015)
    m.box((x + ox * 0.03, y + oy * 0.03, z_top + 0.15), (0.3, w * 0.55, 0.02), "screen_on",
          rot=(0, -tilt, facing + 90))
    m.box((x + ox * 0.18, y + oy * 0.18, z_top + 0.33), (0.05, w * 0.9, 0.36), "machine_dark",
          rot=(0, 10, facing + 90), bev=0.01)
    m.box((x + ox * 0.205, y + oy * 0.205, z_top + 0.33), (0.01, w * 0.8, 0.3), "screen_on",
          rot=(0, 10, facing + 90))
    estop(m, x - oy * w * 0.38, y + ox * w * 0.38, z_top + 0.12)


def signal_tower(m, x, y, z):
    m.cyl((x, y, z + 0.02), 0.05, 0.04, "machine_dark", segs=14)
    m.cyl((x, y, z + 0.17), 0.012, 0.26, "alu", segs=8)
    for i, mat in enumerate(("lamp_off_g", "lamp_off_a", "lamp_off_r")):
        m.cyl((x, y, z + 0.34 + i * 0.075), 0.045, 0.07, mat, segs=16)
    m.cyl((x, y, z + 0.57), 0.045, 0.02, "machine_dark", segs=16)


def status_lamp(x, y, z, status):
    lv = {"work": 0, "idle": 1, "stop": 2}[status]
    mat = {"work": "status_green", "idle": "status_amber", "stop": "status_red"}[status]
    m = Mesh()
    m.cyl((x, y, z + 0.34 + lv * 0.075), 0.048, 0.072, mat, segs=16)
    return m


def floor_frame(m, sx, sy, mat="marking", w=0.08):
    for (cx, cy, a, b) in ((0, -sy / 2, sx, w), (0, sy / 2, sx, w),
                           (-sx / 2, 0, w, sy), (sx / 2, 0, w, sy)):
        m.box((cx, cy, 0.022), (a, b, 0.02), mat)


def legs_frame(m, x, y, sx, sy, h, mat="machine_mid", t=0.06):
    for dx in (-sx / 2 + t, sx / 2 - t):
        for dy in (-sy / 2 + t, sy / 2 - t):
            m.box_lo(x + dx, y + dy, 0, t, t, h, mat)
            m.box_lo(x + dx, y + dy, 0, 0.12, 0.12, 0.02, "machine_dark")
    for dy in (-sy / 2 + t, sy / 2 - t):
        m.box_lo(x, y + dy, 0.15, sx - 2 * t, t * 0.8, t * 0.8, mat)


def roller_table(m, x, y, sx, sy, h, pitch=0.25, axis="Y"):
    legs_frame(m, x, y, sx, sy, h - 0.06)
    if axis == "Y":
        for dy in (-sy / 2, sy / 2):
            m.box_lo(x, y + dy, h - 0.1, sx, 0.05, 0.1, "alu", bev=0.006)
        n = int(sx / pitch)
        for i in range(n):
            m.cyl((x - sx / 2 + (i + 0.5) * sx / n, y, h - 0.03), 0.03, sy - 0.04, "galv",
                  axis="Y", segs=10)
    else:
        for dx in (-sx / 2, sx / 2):
            m.box_lo(x + dx, y, h - 0.1, 0.05, sy, 0.1, "alu", bev=0.006)
        n = int(sy / pitch)
        for i in range(n):
            m.cyl((x, y - sy / 2 + (i + 0.5) * sy / n, h - 0.03), 0.03, sx - 0.04, "galv",
                  axis="X", segs=10)



MESHES = {}


def shared(key, fn):
    """Меш, спільний для всіх об'єктів з тим самим ключем (у glTF зберігається один раз)."""
    me = MESHES.get(key)
    if me is None:
        m = Mesh()
        fn(m)
        me = bpy.data.meshes.new(key)
        m.bm.normal_update()
        m.bm.to_mesh(me)
        m.bm.free()
        for mt in m.mats:
            me.materials.append(MAT[mt])
        MESHES[key] = me
    return me


def instance(name, layer, me, parent=None, loc=(0, 0, 0), rz=0.0, **props):
    ob = bpy.data.objects.new(name, me)
    place(ob, layer, parent, loc, rz, props)
    return ob


# ---------------------------------------------------------------- будівля
def build_building():
    m = Mesh()
    m.box((W / 2, D / 2, -0.06), (W + 60, D + 40, 0.1), "ground")
    m.box((W / 2, D / 2, -0.1), (W, D, 0.2), "floor")
    m.build("Майданчик і підлога", "building")

    walls = Mesh()
    t = 0.3
    # північна стіна на всю висоту, південна — розріз (низький парапет), щоб було видно всередину
    walls.box_lo(W / 2, D + t / 2, 0, W + 2 * t, t, H, "wall")
    walls.box_lo(W / 2, D + t / 2 + 0.01, 0, W + 2 * t, t, 1.0, "wall_band")
    for k in range(20):  # стрічкові вікна
        walls.box_lo(3 + k * 6, D - 0.005, 5.6, 4.4, 0.02, 1.6, "glass")
    walls.box_lo(W / 2, -t / 2, 0, W + 2 * t, t, 1.0, "wall_band")
    for side, x in (("W", -t / 2), ("E", W + t / 2)):
        doors = sorted((y, w) for s, y, w in DOORS if s == side)
        y0 = 0.0
        for yc, w in doors:
            a, b = yc - w / 2, yc + w / 2
            walls.box_lo(x, (y0 + a) / 2, 0, t, a - y0, H, "wall")
            walls.box_lo(x, yc, DOOR_H, t, w, H - DOOR_H, "wall")
            y0 = b
        walls.box_lo(x, (y0 + D) / 2, 0, t, D - y0, H, "wall")
        walls.box_lo(x + (0.01 if side == "E" else -0.01), D / 2, 0, t, D, 1.0, "wall_band")
    walls.build("Стіни", "building")

    rf = Mesh()
    for x in range(0, int(W) + 1, 12):
        rf.box_lo(x, D / 2, H - 0.6, 0.25, D, 0.6, "steel")
        for k in range(10):  # решітка ферми
            rf.box((x, 3 + k * 6, H - 0.3), (0.06, 0.06, 0.7), "steel", rot=(40 if k % 2 else -40, 0, 0))
    for y in (15.0, 30.0, 45.0, 60.0):
        rf.box_lo(W / 2, y, H - 0.3, W, 0.14, 0.3, "steel_dark")
    for x in range(3, int(W), 6):  # світильники high-bay
        for y in range(5, int(D), 10):
            rf.cyl((x, y, H - 0.9), 0.03, 0.6, "steel_dark", segs=6)
            rf.cyl((x, y, H - 1.25), 0.32, 0.1, "machine_mid", segs=20)
            rf.cyl((x, y, H - 1.31), 0.28, 0.02, "led", segs=20)
    rf.build("Ферми та світильники", "roof")

    # офіс: два поверхи із суцільним склінням на південь
    of = Mesh()
    x0, y0, x1, y1 = 50.2, 45.6, 63.4, 59.6
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    for z in (0.0, 3.2):
        of.box_lo(cx, cy, z, x1 - x0, y1 - y0, 3.0, "wall")
        of.box_lo(cx, y0 - 0.01, z + 0.9, x1 - x0 - 0.6, 0.05, 1.7, "glass")
        for k in range(1, 9):
            of.box_lo(x0 + 0.3 + k * (x1 - x0 - 0.6) / 9, y0 - 0.03, z + 0.9, 0.06, 0.05, 1.7, "steel_dark")
        of.box_lo(cx, cy, z + 3.0, x1 - x0 + 0.2, y1 - y0 + 0.2, 0.2, "wall_band")
    of.box_lo(x0 + 1.4, y0 - 0.01, 0, 1.0, 0.06, 2.1, "steel_dark")
    for i in range(11):  # сходи
        of.box_lo(x1 + 0.7, y0 + 0.4 + i * 0.3, i * 0.3, 1.1, 0.3, 0.3, "steel")
    of.box_lo(x1 + 1.27, y0 + 2.0, 0, 0.04, 3.4, 4.3, "marking")
    of.build("OFFICE", "building", code="OFFICE", kind="building", label="Офіс",
             desc="Двоповерховий модуль: майстри, технологи, планування змін.")
    obst(x0, y0, x1 + 1.4, y1)

    so = Mesh()
    x0, y0, x1, y1 = 81.0, 45.6, 98.2, 59.6
    so.box_lo((x0 + x1) / 2, (y0 + y1) / 2, 0, x1 - x0, y1 - y0, 3.4, "wall")
    so.box_lo((x0 + x1) / 2, (y0 + y1) / 2, 3.4, x1 - x0 + 0.2, y1 - y0 + 0.2, 0.2, "wall_band")
    for k in range(6):
        so.box_lo(x0 + 1.6 + k * 2.8, y0 - 0.01, 1.0, 1.8, 0.05, 1.4, "glass")
    so.box_lo(x0 + 0.9, y0 - 0.01, 0, 1.2, 0.06, 2.2, "steel_dark")
    # перегородка між цехом і північною смугою + стіни приміщень у смузі
    pw = Mesh()
    x0 = 0.0
    for xc, w in ((20.0, 4.0), (44.6, 1.6), (56.0, 4.0), (75.0, 4.0), (90.0, 4.0), (104.0, 1.6),
                  (114.5, 4.0)):
        pw.box_lo((x0 + xc - w / 2) / 2, 60.0, 0, xc - w / 2 - x0, 0.2, 3.2, "wall")
        pw.box_lo(xc, 60.0, 2.6, w, 0.2, 0.6, "wall")
        x0 = xc + w / 2
    pw.box_lo((x0 + W) / 2, 60.0, 0, W - x0, 0.2, 3.2, "wall")
    pw.box_lo(W / 2, 60.0, 3.2, W, 0.22, 0.12, "wall_band")
    for x in (39.6, 49.6, 98.6, 109.6):
        pw.box_lo(x, 66.0, 0, 0.2, 12.0, 3.2, "wall")
        pw.box_lo(x, 66.0, 3.2, 0.22, 12.0, 0.12, "wall_band")
    pw.build("Перегородки", "building")

    so.build("SOCIAL", "building", code="SOCIAL", kind="building", label="Побутові приміщення",
             desc="Роздягальні, душові, їдальня на 60 місць, медпункт.")
    obst(x0, y0, x1, y1)

    for side, yc, w in DOORS:
        d = Mesh()
        inside = 1 if side == "W" else -1
        x = 0.0 if side == "W" else W
        d.box_lo(x - inside * 0.4, yc, 0, 0.5, w + 0.8, DOOR_H + 0.4, "dock_shelter", bev=0.05)
        d.box_lo(x + inside * 1.2, yc, 0.0, 2.4, w - 0.4, 0.03, "steel")
        hazard(d, yc - w / 2 + 0.2, yc + w / 2 - 0.2, x + inside * 2.4, 0.0, depth=0.1, h=0.032,
               along="Y")
        for dy in (-1, 1):
            d.box_lo(x + inside * 0.17, yc + dy * (w / 2 + 0.1), 0, 0.2, 0.2, DOOR_H, "marking")
            d.box_lo(x - inside * 0.68, yc + dy * 0.9, 0.9, 0.12, 0.25, 0.3, "rubber", bev=0.02)
        d.box_lo(x + inside * 0.45, yc, DOOR_H - 0.1, 0.5, w, 0.25, "machine_mid", bev=0.03)
        layer = "receiving" if side == "W" else "shipping"
        idx = sum(1 for s, yy, _ in DOORS if s == side and yy <= yc)
        kind_ua = "Ворота приймання" if side == "W" else "Ворота відвантаження"
        d.build(f"DOCK-{side}{idx}", layer, code=f"DOCK-{side}{idx}", kind="dock",
                label=f"{kind_ua} {idx}", desc="Докшелтер, секційні ворота, вирівнювальна платформа.")


def build_columns():
    m = Mesh()
    for x in range(12, int(W), 12):
        for y in (15, 30, 45, 60):
            if blocked(x, y):
                continue
            m.box_lo(x + 0.23, y, 1.3, 0.12, 0.3, 0.6, "fire_red", bev=0.01)  # пожежна шафа
            m.box_lo(x, y, 0, 0.45, 0.45, H, "column")
            m.box_lo(x, y, 0, 0.6, 0.6, 1.2, "marking")
            hazard(m, x - 0.3, x + 0.3, y - 0.305, 1.05, h=0.12, w=0.12)
    m.build("Колони", "building")


# ---------------------------------------------------------------- зони
def build_zones():
    for code, name, (x0, y0, x1, y1), _, desc in ZONES:
        m = Mesh()
        m.box(((x0 + x1) / 2, (y0 + y1) / 2, 0.006), (x1 - x0, y1 - y0, 0.012), "zone_" + code)
        w = 0.1
        for (cx, cy, sx, sy) in (((x0 + x1) / 2, y0, x1 - x0, w), ((x0 + x1) / 2, y1, x1 - x0, w),
                                 (x0, (y0 + y1) / 2, w, y1 - y0), (x1, (y0 + y1) / 2, w, y1 - y0)):
            m.box((cx, cy, 0.014), (sx, sy, 0.016), "marking")
        m.build(code, "zones", code=code, kind="zone", label=name, desc=desc,
                rect=[x0, y0, x1, y1])


# ---------------------------------------------------------------- склади
def sheet_stack(m, x, y, z, n, decor, thick=0.016):
    """Стос плит на піддоні з прокладками; кожні 10 листів — тонка лінія для об'єму."""
    m.box_lo(x, y, z, 2.9, 2.15, 0.03, "pallet")
    for dx in (-1.2, -0.4, 0.4, 1.2):
        m.box_lo(x + dx, y, z + 0.03, 0.1, 2.15, 0.07, "pallet")
    if not n:
        return
    h = n * thick
    m.box_lo(x, y, z + 0.1, 2.8, 2.07, h, "decor%d" % decor)
    for k in range(1, int(n / 10) + 1):
        zz = z + 0.1 + k * 10 * thick
        if zz < z + 0.1 + h - 0.005:
            m.box((x, y - 1.036, zz), (2.8, 0.004, 0.004), "machine_dark")


def stack_mesh(decor, n):
    thick = 0.003 if decor == 6 else 0.016

    def fn(m):
        sheet_stack(m, 0, 0, 0, n, decor, thick)
        m.box_lo(-1.5, 0, 0.01, 0.06, 2.15, 0.02, "marking")
    return shared(f"stack_{decor}_{n}", fn)


def build_receiving():
    m = Mesh()
    for i, (x, y, n) in enumerate(((6.0, 3.5, 30), (6.0, 7.0, 40), (6.0, 14.0, 22),
                                   (10.5, 3.5, 55), (10.5, 9.0, 18), (10.5, 20.0, 35))):
        sheet_stack(m, x, y, 0.0, n, i % 3)
        m.box_lo(x, y, 0.08, 2.86, 2.13, n * 0.016 + 0.04, "wrap")
    for k, (x, y) in enumerate(((3.0, 21.5), (3.0, 23.5), (5.0, 22.5))):
        pallet(m, x, y)
        cartons(m, x, y, 0.146, 1.15, 0.75, 2 + k % 2)
    m.build("IN-STAGE", "receiving", code="IN-STAGE", kind="stock",
            label="Вантаж на розвантаженні",
            desc="Стоси плит і палети з фурнітурою з двох фур, чекають на звірку.")

    q = Mesh()
    for qx in (5.0, 10.5):
        q.box_lo(qx, 31.0, 0.84, 2.0, 1.0, 0.05, "table_top", bev=0.01)
        legs_frame(q, qx, 31.0, 2.0, 1.0, 0.84)
        q.box_lo(qx + 0.1, 31.0, 0.89, 0.8, 0.6, 0.016, "decor0")
        q.box_lo(qx - 0.6, 31.2, 0.89, 0.3, 0.2, 0.04, "machine_dark", bev=0.005)
    sheet_stack(q, 4.0, 28.0, 0.0, 25, 2)
    for dx in (-1.45, 1.45):
        for dy in (-1.05, 1.05):
            q.box_lo(4.0 + dx, 28.0 + dy, 0, 0.08, 0.08, 1.0, "status_red")
    q.box_lo(4.0, 26.9, 0.85, 3.0, 0.02, 0.06, "status_red")
    sheet_stack(q, 10.5, 28.0, 0.0, 40, 0)
    q.build("QC-1", "receiving", code="QC-1", kind="stock", label="Вхідний контроль",
            desc="Столи замірів; стос ліворуч на карантині (червоні стійки — не пройшов перевірку).")
    obst(0, 0, 15.4, 35.4)


def build_sheets():
    """Портальний склад плит: стоси під порталом із вакуумним захопленням,
    рольганги подачі на розкрійні центри."""
    k = 0
    for j, y in enumerate(SHEET_ROWS_Y):
        for i, x in enumerate(SHEET_COLS_X):
            decor = (i * 3 + j * 5) % 7
            n = 0 if (i + 2 * j) % 11 == 0 else 5 * (2 + (i * 7 + j * 3) % 11)
            code = f"PLT-{chr(65 + j)}{i + 1}"
            name = SHEET_DECORS[decor][0] if n else "порожньо"
            instance(code, "sheets", stack_mesh(decor, n), loc=(x, y, 0), code=code, kind="stock",
                     label=f"Стос {code}", desc=f"{name}, {n} арк." if n else "Місце вільне.")
            k += 1

    g = Mesh()
    x0, x1, ya, yb, zr = 16.6, 44.0, 0.9, 26.6, 6.2
    for y in (ya, yb):  # колії порталу на стійках
        for x in (x0, x0 + 6.85, x0 + 13.7, x0 + 20.55, x1):
            g.box_lo(x, y, 0, 0.35, 0.35, zr, "machine_accent", bev=0.03)
            g.box_lo(x, y, 0, 0.6, 0.6, 0.03, "steel_dark")
            g.box_lo(x, y, 0, 0.5, 0.5, 1.1, "marking")
        g.box_lo((x0 + x1) / 2, y, zr, x1 - x0 + 0.4, 0.45, 0.55, "machine_accent", bev=0.04)
        g.box_lo((x0 + x1) / 2, y, zr + 0.55, x1 - x0 + 0.2, 0.12, 0.08, "steel")
    bx = 30.0  # міст порталу
    for dx in (-0.45, 0.45):
        g.box_lo(bx + dx, (ya + yb) / 2, zr + 0.6, 0.35, yb - ya + 0.8, 0.7, "machine", bev=0.05)
    for y in (ya, yb):
        g.box_lo(bx, y, zr + 0.55, 1.6, 0.8, 0.8, "machine_mid", bev=0.05)
    ty = 9.0  # візок і вакуумне захоплення над стосом
    g.box_lo(bx, ty, zr + 1.3, 1.5, 1.4, 0.6, "machine_accent", bev=0.05)
    g.box_lo(bx, ty, 3.1, 0.35, 0.35, zr - 1.8, "alu", bev=0.02)  # телескопічна колона
    g.box_lo(bx, ty, 2.85, 0.5, 0.5, 0.3, "machine_dark", bev=0.03)
    g.box_lo(bx, ty, 2.7, 2.6, 1.8, 0.12, "machine_mid", bev=0.02)
    for i in range(4):
        for j in range(3):
            g.cyl((bx - 1.05 + i * 0.7, ty - 0.6 + j * 0.6, 2.66), 0.1, 0.06, "rubber", segs=14)
    g.box_lo(bx, ty, 2.6, 2.8, 2.07, 0.016, "decor1")
    g.cyl((bx + 0.4, ty + 0.5, zr + 1.0), 0.06, 1.2, "machine_dark", rot=(0, 0, 0), segs=10)
    # рольганги подачі на розкрій
    for y in (5.0, 14.5, 24.0):
        roller_table(g, 47.0, y, 9.6, 2.1, 0.55, pitch=0.4, axis="Y")
        g.box_lo(42.5, y, 0, 3.0, 2.3, 0.5, "machine_mid", bev=0.03)  # підйомний стіл
        g.box_lo(42.5, y, 0.5, 2.8, 2.07, 0.016 * 3, "decor0")
    # огородження зони порталу
    for x in range(17, 44, 3):
        g.box_lo(x, 0.35, 0, 0.06, 0.06, 2.0, "marking")
        g.box_lo(x + 1.5, 0.35, 0.1, 2.9, 0.02, 1.8, "guard_glass")
    g.build("GANTRY-1", "sheets", code="GANTRY-1", kind="equipment", label="Портальний склад плит",
            desc="Портал над стосами з вакуумним захопленням: бере лист зі стосу і кладе на "
                 "рольганг подачі до розкрійних центрів. Без навантажувачів у зоні.")
    obst(16.0, 0.0, 51.8, 27.0)


def build_hardware():
    sec_w, nsec, x0 = 2.0, 12, 18.5
    levels = [0.12, 0.72, 1.32, 1.92]
    depth = 0.6
    rows = {f"R{k + 1}": 33.5 + 4.3 * k for k in range(6)}

    def frame(m):
        for s in range(nsec + 1):
            for dy in (-depth / 2, depth / 2):
                m.box_lo(s * sec_w, dy, 0, 0.06, 0.06, 2.5, "rack_upright")
            for z in (0.4, 1.2, 2.0):
                m.box((s * sec_w, 0, z), (0.02, depth, 0.02), "rack_upright", rot=(30, 0, 0))
        for z in levels:
            m.box_lo(nsec * sec_w / 2, 0, z - 0.03, nsec * sec_w, depth, 0.03, "shelf")
            for dy in (-depth / 2, depth / 2):
                m.box_lo(nsec * sec_w / 2, dy, z - 0.08, nsec * sec_w, 0.04, 0.08, "rack_beam")

    def bins(state):
        mat = {"ok": "bin", "low": "bin_yellow", "out": "bin_red"}[state]

        def fn(m):
            if state != "out":
                for b in range(4):
                    bx = -sec_w / 2 + 0.27 + b * 0.49
                    m.box_lo(bx, 0, 0, 0.44, 0.5, 0.26, mat, bev=0.012)
                    m.box_lo(bx, -0.24, 0.16, 0.2, 0.03, 0.08, mat, bev=0.008)
            m.box_lo(0, -depth / 2 - 0.03, -0.075, 0.24, 0.01, 0.06,
                     mat if state != "ok" else "phenolic")
        return shared("bins_" + state, fn)

    me_frame = shared("hw_rack", frame)
    for ri, (row, y) in enumerate(rows.items()):
        instance(f"RACK-{row}", "hardware", me_frame, loc=(x0, y, 0), code=f"RACK-{row}",
                 kind="rack", label=f"Стелаж {row}",
                 desc=f"{nsec} секцій × {len(levels)} яруси, комірки з лотками.")
        obst(x0, y - 0.4, x0 + nsec * sec_w, y + 0.4)
        for s in range(1, nsec + 1):
            for li, z in enumerate(levels, 1):
                code = f"FUR-{row}-S{s:02d}-L{li}"
                h = (ri * 7 + s * 3 + li * 5) % 23
                state = "low" if h in (0, 1) else "out" if h == 2 else "ok"
                instance(code, "hardware", bins(state), loc=(x0 + (s - 0.5) * sec_w, y, z),
                         code=code, kind="bin", state=state, label=f"Комірка {code}",
                         desc={"ok": "Запас у нормі.", "low": "Запас нижче мінімуму.",
                               "out": "Комірка порожня."}[state])


def build_edge():
    ys, ye, nsec = 37.5, 58.5, 4
    sec = (ye - ys) / nsec
    levels = (0.1, 0.9, 1.7)

    def frame(m):
        for k in range(nsec + 1):
            for dx in (-0.45, 0.45):
                m.box_lo(dx, ys + k * sec, 0, 0.06, 0.06, 2.4, "rack_upright")
        for z in levels:
            m.box_lo(0, (ys + ye) / 2, z - 0.04, 0.9, ye - ys, 0.04, "shelf")

    def rolls(decor, n):
        def fn(m):
            for k in range(n):
                cy = -sec / 2 + 0.45 + k * 0.42
                m.cyl((0, cy, 0.32), 0.3, 0.06, "edge%d" % decor, axis="Y", segs=24)
                m.cyl((0, cy, 0.32), 0.08, 0.065, "carton", axis="Y", segs=12)
        return shared(f"rolls_{decor}_{n}", fn)

    me_frame = shared("edge_rack", frame)
    for ui, x in enumerate((3.0, 7.5, 12.0), 1):
        u = f"U{ui}"
        instance(f"EB-{u}", "edge", me_frame, loc=(x, 0, 0), code=f"EB-{u}", kind="rack",
                 label=f"Стелаж крайки {u}", desc="Рулони крайки ПВХ стоять на ребрі.")
        obst(x - 0.5, ys, x + 0.5, ye)
        for s in range(1, nsec + 1):
            for li, z in enumerate(levels, 1):
                decor = (ui + s + li) % len(EDGE_DECORS)
                n = (ui * 5 + s * 3 + li * 7) % 12
                code = f"EB-{u}-S{s}-L{li}"
                instance(code, "edge", rolls(decor, n), loc=(x, ys + (s - 0.5) * sec, z),
                         code=code, kind="stock", label=f"Полиця {code}",
                         desc=f"{n} рулонів крайки по 200 м." if n else "Полиця порожня.")


def build_buffer():
    def cart(k):
        def fn(m):
            m.box_lo(0, 0, 0.15, 1.3, 2.2, 0.04, "steel", bev=0.01)
            for dx in (-0.55, 0.55):
                for dy in (-1.0, 1.0):
                    m.cyl((dx, dy, 0.075), 0.075, 0.05, "rubber", axis="X", segs=14)
                    m.box_lo(dx, dy, 0.13, 0.08, 0.06, 0.03, "steel_dark")
            for dy in (-1.05, 1.05):
                m.box_lo(0, dy, 0.19, 1.3, 0.05, 1.1, "steel", bev=0.01)
            m.cyl((0, -1.25, 1.3), 0.025, 1.0, "machine_dark", axis="X", segs=8)
            for j in range(k):
                for i in range(3):
                    m.box_lo(-0.4 + i * 0.4, -0.7 + j * 0.5, 0.19, 0.34, 0.44, 0.2,
                             ("bin", "bin_yellow", "bin")[(i + j) % 3], bev=0.01)
                    m.box_lo(-0.4 + i * 0.4, -0.7 + j * 0.5, 0.6, 0.34, 0.44, 0.18, "carton",
                             bev=0.005)
        return shared(f"cart_{k}", fn)

    for i in range(11):
        y = 28.0 + 2.8 * i
        k = 1 if i == 10 else 2 + i % 3
        code = f"KIT-{i + 1:02d}"
        instance(code, "buffer", cart(k), loc=(47.2, y, 0), code=code, kind="kit",
                 label=f"Візок {code}",
                 desc="Комплект фурнітури під одне замовлення." if k > 1
                 else "Візок майже порожній, чекає на комплектацію.")
    obst(46.4, 26.5, 48.0, 59.0)


def machine_saw(m):
    """Розкрійний центр: задній підйомний стіл, програмний штовхач, притискна балка,
    передні пневмостоли з отворами, кутовий упор, пульт."""
    # задній підйомний стіл зі стосом
    m.box_lo(-1.75, 0, 0, 2.9, 3.6, 0.35, "machine_mid", bev=0.03)
    for dx in (-0.9, 0.0, 0.9):
        m.box((-1.75 + dx, 0, 0.42), (0.08, 3.4, 0.14), "steel_dark", rot=(0, 0, 0))
    m.box_lo(-1.75, 0, 0.5, 2.82, 3.4, 0.04, "steel", bev=0.01)
    m.box_lo(-1.75, 0, 0.54, 2.8, 2.07, 0.3, "decor0")
    m.box((-1.75, -1.036, 0.69), (2.8, 0.004, 0.004), "machine_dark")
    # програмний штовхач: напрямні + портал із цангами
    for dy in (-2.1, 2.1):
        m.box_lo(-1.8, dy, 0, 3.6, 0.22, 1.05, "machine", bev=0.03)
        m.box_lo(-1.8, dy, 1.05, 3.6, 0.14, 0.06, "alu", bev=0.01)
        hazard(m, -3.55, -0.05, dy + (0.12 if dy > 0 else -0.12), 0.0, depth=0.01, h=0.12)
    m.box_lo(-2.6, 0, 1.0, 0.32, 4.5, 0.26, "machine_accent", bev=0.04)
    m.box_lo(-2.6, 0, 1.26, 0.25, 4.3, 0.08, "machine_dark", bev=0.01)
    for k in range(8):
        m.box_lo(-2.38, -1.75 + k * 0.5, 0.82, 0.12, 0.08, 0.2, "machine_dark", bev=0.01)
    # корпус пильної лінії та притискна балка
    m.box_lo(0.25, 0, 0, 0.9, 4.7, 0.86, "machine", bev=0.04)
    m.box_lo(0.25, 0, 0.86, 0.9, 4.5, 0.03, "steel")
    m.box((0.25, 0, 0.895), (0.03, 4.4, 0.01), "hazard_black")
    for dy in (-2.55, 2.55):
        m.box_lo(0.25, dy, 0, 0.75, 0.5, 1.6, "machine_accent", bev=0.05)
    m.box_lo(0.25, 0, 1.5, 0.95, 5.6, 0.52, "machine_accent", bev=0.08)
    m.box_lo(0.72, 0, 1.58, 0.02, 4.9, 0.36, "machine", bev=0.01)  # передня кришка
    m.box_lo(0.25, 0, 1.04, 0.3, 4.6, 0.1, "steel", bev=0.01)        # притискна шина
    for k in range(6):
        m.cyl((0.25, -1.9 + k * 0.76, 1.27), 0.05, 0.38, "alu", segs=12)  # пневмоциліндри
    m.box_lo(0.25, 3.0, 0.2, 0.7, 0.5, 0.7, "machine_dark", bev=0.04)  # двигун пили
    m.cyl((0.25, 2.65, 1.05), 0.16, 0.12, "steel_dark", axis="Y", segs=24)
    # передні пневмостоли
    for dy in (-1.45, 0.0, 1.45):
        legs_frame(m, 1.95, dy, 2.3, 1.15, 0.84)
        m.box_lo(1.95, dy, 0.84, 2.3, 1.15, 0.05, "phenolic", bev=0.01)
        for i in range(5):
            for j in range(3):
                m.cyl((1.1 + i * 0.42, dy - 0.38 + j * 0.38, 0.892), 0.012, 0.004, "machine_dark",
                      segs=8)
    m.box_lo(1.95, -2.08, 0.89, 2.3, 0.08, 0.1, "alu", bev=0.01)  # кутовий упор
    for i in range(4):
        m.box_lo(1.0 + i * 0.6, -2.08, 0.99, 0.02, 0.09, 0.012, "hazard_black")
    # нарізані деталі на столах
    for i, (dy, n) in enumerate(((-1.4, 4), (-0.15, 6), (1.25, 3))):
        m.box_lo(1.7 + 0.1 * i, dy, 0.89, 1.4, 0.72, 0.016 * n, "decor0")
    # світлова завіса та шафа керування
    for dy in (-2.4, 2.4):
        m.box_lo(-3.4, dy, 0, 0.07, 0.07, 1.8, "marking", bev=0.01)
        m.box_lo(-3.4, dy, 0, 0.2, 0.2, 0.02, "machine_dark")
    m.box_lo(-1.2, 3.35, 0, 1.2, 0.55, 2.0, "machine_mid", bev=0.02)
    m.box_lo(-1.2, 3.07, 0.2, 0.01, 0.4, 1.6, "machine_dark")
    m.box_lo(-1.0, 3.07, 1.0, 0.02, 0.03, 0.2, "steel_dark")
    m.box_lo(-1.2, 3.35, 2.0, 1.25, 0.6, 0.05, "machine_dark")
    # килимок оператора
    m.box_lo(2.0, -2.75, 0, 2.2, 0.8, 0.015, "rubber")
    console(m, 0.9, -3.05, 1.0, facing=90)
    # принтер етикеток зі штрихкодом для кожної деталі
    m.box_lo(3.25, -2.05, 0, 0.1, 0.1, 1.15, "steel_dark")
    m.box_lo(3.25, -2.05, 1.15, 0.35, 0.3, 0.25, "machine_dark", bev=0.02)
    m.box((3.25, -2.21, 1.3), (0.2, 0.01, 0.08), "screen_on")
    floor_frame(m, 7.4, 7.2)


def machine_edge(m):
    """Крайкооблицювальний верстат: секційна станина, гусениця подачі, верхня
    притискна балка з роликами, кожухи агрегатів з оглядовими вікнами, клейова
    ванна, магазин крайки, опорна консоль, конвеєри."""
    L = 8.0
    for i in range(6):  # станина секціями з дверцятами
        sx = L / 6
        cx = -L / 2 + (i + 0.5) * sx
        m.box_lo(cx, 0, 0.06, sx - 0.02, 0.95, 0.82, "machine", bev=0.02)
        m.box_lo(cx, -0.478, 0.35, 0.03, 0.01, 0.2, "steel_dark")
        m.box_lo(cx, -0.476, 0.12, sx - 0.12, 0.004, 0.66, "machine_mid")
    for x in (-L / 2 + 0.2, L / 2 - 0.2):
        for dy in (-0.35, 0.35):
            m.cyl((x, dy, 0.03), 0.06, 0.06, "machine_dark", segs=10)
    m.box_lo(0, -0.22, 0.88, L, 0.3, 0.06, "hazard_black")  # гусениця
    for k in range(40):
        m.box_lo(-L / 2 + 0.1 + k * 0.2, -0.22, 0.94, 0.16, 0.28, 0.01, "steel_dark")
    # верхня притискна балка
    for x in (-3.2, 0.0, 3.2):
        m.box_lo(x, 0.15, 0.88, 0.25, 0.22, 0.65, "machine_mid", bev=0.02)
    m.box_lo(0, -0.12, 1.4, L - 0.2, 0.45, 0.14, "machine_mid", bev=0.03)
    for k in range(36):
        m.cyl((-L / 2 + 0.25 + k * 0.215, -0.22, 1.12), 0.045, 0.12, "rubber", axis="Y", segs=12)
    # кожухи агрегатів
    hoods = [(-2.6, 1.3, "machine_accent"), (-1.15, 1.3, "machine"), (0.3, 1.3, "machine_accent"),
             (1.75, 1.3, "machine"), (3.15, 1.2, "machine_accent")]
    for x, w, mat in hoods:
        m.box_lo(x, 0.22, 0.95, w, 0.5, 0.55, mat, bev=0.06)
        m.box_lo(x, -0.035, 1.05, w * 0.7, 0.02, 0.32, "guard_glass", bev=0.01)
    # прозорий захисний козирок
    m.box((0, -0.55, 1.2), (L - 0.4, 0.02, 0.45), "guard_glass", rot=(-25, 0, 0))
    # клейова ванна
    m.box_lo(-3.6, 0.25, 0.95, 0.5, 0.45, 0.35, "machine_dark", bev=0.03)
    m.cyl((-3.6, 0.25, 1.38), 0.16, 0.08, "steel", segs=20)
    # магазин крайки на кронштейні
    m.box_lo(-4.15, -0.75, 0, 0.1, 0.1, 1.05, "steel_dark")
    m.box((-4.0, -0.62, 1.05), (0.35, 0.06, 0.06), "steel_dark", rot=(0, 0, 40))
    m.cyl((-3.85, -0.48, 1.1), 0.36, 0.02, "alu", segs=28)
    m.cyl((-3.85, -0.48, 1.13), 0.3, 0.04, "edge_roll", segs=28)
    m.cyl((-3.85, -0.48, 1.13), 0.08, 0.045, "carton", segs=12)
    # опорна консоль спереду
    m.box_lo(0, -1.0, 0.82, L, 0.06, 0.06, "alu", bev=0.01)
    for x in (-3.5, -1.5, 0.5, 2.5):
        m.box((x, -0.75, 0.8), (0.05, 0.5, 0.05), "steel_dark")
        m.cyl((x, -1.0, 0.9), 0.04, 0.03, "rubber", axis="Y", segs=10)
    # конвеєри: подача, вихід, повертальний позаду
    roller_table(m, -5.0, 0, 2.0, 1.1, 0.92, axis="Y")
    roller_table(m, 5.0, 0, 2.0, 1.1, 0.92, axis="Y")
    roller_table(m, 0, 1.25, 10.0, 0.6, 0.82, pitch=0.3, axis="Y")
    # пульт на поворотній консолі
    m.box_lo(-4.3, 0.55, 0.88, 0.1, 0.1, 0.7, "steel_dark")
    m.box((-4.05, 0.2, 1.58), (0.6, 0.08, 0.08), "steel_dark", rot=(0, 0, -50))
    m.box((-3.85, -0.05, 1.55), (0.06, 0.4, 0.3), "machine_dark", rot=(0, 15, 0), bev=0.01)
    m.box((-3.82, -0.05, 1.55), (0.01, 0.34, 0.24), "screen_on", rot=(0, 15, 0))
    estop(m, -3.6, -0.3, 0.88)
    # деталі на гусениці та на виході
    m.box_lo(-1.6, -0.15, 0.95, 1.4, 0.72, 0.016, "decor0")
    m.box_lo(4.9, 0.05, 0.92, 1.4, 0.72, 0.016 * 3, "decor0")
    floor_frame(m, 12.6, 3.8)


def machine_cnc(m):
    """Портальний обробний центр: станина, консолі з вакуумними присосками,
    портал, Z-каретка зі свердлильною головою і шпинделем, магазин
    інструменту, кабель-канал, бампери безпеки, огорожа, вакуум-насос."""
    m.box_lo(0, 0, 0, 4.4, 2.2, 0.72, "machine", bev=0.05)
    m.box_lo(0, -1.11, 0.1, 4.0, 0.01, 0.5, "machine_mid")
    m.box_lo(0, 0, 0.72, 4.2, 2.0, 0.04, "machine_dark")
    for x in (-1.9, 1.9):
        for dy in (-0.9, 0.9):
            m.cyl((x, dy, 0.03), 0.07, 0.06, "machine_dark", segs=10)
    # консолі з присосками
    for i in range(6):
        x = -1.75 + i * 0.7
        m.box_lo(x, 0, 0.76, 0.14, 1.9, 0.08, "alu", bev=0.01)
        for dy in (-0.55, 0.15):
            m.box_lo(x, dy, 0.84, 0.14, 0.12, 0.05, "machine_dark", bev=0.01)
    m.box_lo(-0.35, -0.2, 0.89, 1.6, 0.7, 0.016, "decor1")
    m.box_lo(-0.35, -0.2, 0.89 + 0.016, 1.6, 0.004, 0.001, "machine_dark")
    # напрямні порталу
    for dy in (-1.08, 1.08):
        m.box_lo(0, dy, 0.72, 4.3, 0.1, 0.14, "steel", bev=0.01)
    # портал
    gx = 0.5
    for dy in (-1.2, 1.2):
        m.box_lo(gx, dy, 0.76, 0.6, 0.32, 1.5, "machine_accent", bev=0.05)
    m.box_lo(gx, 0, 2.15, 0.66, 2.9, 0.5, "machine_accent", bev=0.07)
    m.box_lo(gx - 0.34, 0, 2.2, 0.01, 2.5, 0.38, "machine", bev=0.005)
    # кабель-канал на порталі
    for k in range(16):
        m.box_lo(gx + 0.12, -1.3 + k * 0.17, 2.65, 0.22, 0.14, 0.1, "machine_dark", bev=0.01)
    # Z-каретка та голова
    m.box_lo(gx - 0.42, 0.2, 1.2, 0.3, 0.45, 1.05, "machine", bev=0.03)
    m.box_lo(gx - 0.45, 0.2, 1.02, 0.36, 0.42, 0.2, "machine_dark", bev=0.02)
    for i in range(4):
        for j in range(3):
            m.cyl((gx - 0.55 + i * 0.07, 0.08 + j * 0.12, 0.97), 0.008, 0.1, "alu", segs=6)
    m.cyl((gx - 0.45, -0.18, 1.4), 0.12, 0.45, "machine_mid", segs=20)
    m.cyl((gx - 0.45, -0.18, 1.1), 0.05, 0.16, "steel", segs=12)
    m.cyl((gx - 0.45, 0.2, 0.98), 0.22, 0.05, "rubber", segs=24)  # щітка аспірації
    # магазин інструменту
    m.cyl((-2.0, -1.3, 1.25), 0.38, 0.06, "machine_mid", segs=28)
    for k in range(10):
        a = 2 * math.pi * k / 10
        m.cyl((-2.0 + 0.3 * math.cos(a), -1.3 + 0.3 * math.sin(a), 1.15), 0.03, 0.14, "alu", segs=8)
    m.box_lo(-2.0, -1.3, 0, 0.12, 0.12, 1.2, "steel_dark")
    # бампери безпеки та огорожа позаду
    m.box_lo(0, -1.45, 0.25, 4.4, 0.12, 0.12, "marking", bev=0.03)
    hazard(m, -2.2, 2.2, -1.52, 0.25, depth=0.005, h=0.12)
    for x in (-2.4, -0.8, 0.8, 2.4):
        m.box_lo(x, 1.9, 0, 0.06, 0.06, 1.9, "marking")
    for x in (-1.6, 0.0, 1.6):
        m.box_lo(x, 1.9, 0.15, 1.5, 0.02, 1.7, "guard_glass")
    m.box_lo(0, 1.9, 1.88, 4.86, 0.05, 0.05, "marking")
    # шафа керування, вакуум-насос, пульт
    m.box_lo(-2.85, 1.2, 0, 0.7, 0.6, 2.0, "machine_mid", bev=0.02)
    m.box_lo(-2.49, 1.2, 0.2, 0.01, 0.45, 1.6, "machine_dark")
    m.box_lo(2.8, 1.25, 0, 0.8, 0.6, 0.7, "machine_dark", bev=0.03)
    for k in range(6):
        m.box_lo(2.8, 0.94, 0.12 + k * 0.09, 0.7, 0.02, 0.03, "steel")
    console(m, 2.4, -1.9, 1.0, facing=-90)
    floor_frame(m, 6.6, 4.4)


def machine_asm(m):
    """Збиральна дільниця: корпусна вайма з пневмоприжимами та верстак."""
    # вайма: рама, ролики стола, стійки, приводи
    m.box_lo(0, 0, 0.6, 2.8, 1.3, 0.08, "steel", bev=0.01)
    legs_frame(m, 0, 0, 2.8, 1.3, 0.6, mat="machine_accent", t=0.08)
    for i in range(10):
        m.cyl((-1.25 + i * 0.28, 0, 0.71), 0.025, 1.2, "galv", axis="Y", segs=10)
    for dx in (-1.5, 1.5):
        m.box_lo(dx, -0.1, 0, 0.14, 0.14, 2.3, "machine_accent", bev=0.02)
        for z in (0.95, 1.35):
            m.cyl((dx * 0.86, -0.1, z), 0.04, 0.4, "alu", axis="X", segs=12)
            m.box((dx * 0.7, -0.1, z), (0.03, 0.3, 0.2), "steel_dark", bev=0.005)
    m.box_lo(0, -0.1, 2.3, 3.14, 0.16, 0.16, "machine_accent", bev=0.02)
    for dx in (-0.5, 0.5):
        m.cyl((dx, -0.1, 2.1), 0.045, 0.4, "alu", segs=12)
        m.box_lo(dx, -0.1, 1.8, 0.4, 0.4, 0.03, "steel_dark")
    # корпус шафи у ваймі
    cz = 0.75
    for dx in (-0.39, 0.39):
        m.box_lo(dx, 0, cz, 0.018, 0.56, 0.9, "decor0")
    for z in (cz, cz + 0.88):
        m.box_lo(0, 0, z, 0.8, 0.56, 0.018, "decor0")
    m.box_lo(0, 0, cz + 0.44, 0.76, 0.52, 0.016, "decor0")
    m.box_lo(0, 0.27, cz, 0.8, 0.005, 0.9, "decor6")
    # верстак
    bx, by = 0.0, 1.35
    m.box_lo(bx, by, 0.86, 2.2, 0.75, 0.05, "table_top", bev=0.01)
    legs_frame(m, bx, by, 2.2, 0.75, 0.86, mat="steel")
    m.box_lo(bx - 0.6, by, 0.1, 0.6, 0.7, 0.7, "machine_mid", bev=0.01)  # тумба з шухлядами
    for k in range(4):
        m.box_lo(bx - 0.6, by - 0.355, 0.15 + k * 0.17, 0.5, 0.01, 0.14, "machine", bev=0.003)
        m.box_lo(bx - 0.6, by - 0.365, 0.21 + k * 0.17, 0.16, 0.01, 0.02, "steel_dark")
    m.box_lo(bx, by + 0.35, 0.91, 2.2, 0.03, 1.0, "pegboard")
    for k in range(6):  # інструмент на перфопанелі
        m.box_lo(bx - 0.8 + k * 0.32, by + 0.32, 1.35, 0.05, 0.03, 0.25, "machine_dark")
    for k in range(5):  # лотки з фурнітурою
        m.box_lo(bx - 0.8 + k * 0.4, by + 0.25, 1.15, 0.3, 0.15, 0.12,
                 ("bin", "bin_yellow", "bin", "status_red", "bin")[k], bev=0.008)
    m.box_lo(bx + 0.5, by - 0.05, 0.91, 0.08, 0.2, 0.18, "machine_accent", bev=0.02)  # шуруповерт
    m.cyl((bx + 0.5, by - 0.17, 1.06), 0.02, 0.08, "machine_dark", axis="Y", segs=10)
    m.box_lo(bx + 0.5, by - 0.05, 0.91, 0.12, 0.12, 0.05, "machine_dark", bev=0.01)
    # котушка пневмошланга
    m.box_lo(1.7, 1.2, 0, 0.08, 0.08, 1.8, "steel_dark")
    m.cyl((1.7, 1.1, 1.6), 0.22, 0.12, "machine_accent", axis="Y", segs=20)
    # візок із деталями та готова шафа
    m.box_lo(-2.25, 0, 0.12, 1.0, 0.7, 0.04, "steel")
    for dx in (-0.4, 0.4):
        for dy in (-0.28, 0.28):
            m.cyl((-2.25 + dx, dy, 0.06), 0.06, 0.04, "rubber", axis="X", segs=12)
    for k in range(4):
        m.box_lo(-2.25, 0, 0.16 + k * 0.017, 0.8, 0.5, 0.016, "decor0")
    m.box_lo(2.35, -0.3, 0, 0.6, 0.58, 0.82, "decor0", bev=0.004)
    m.box_lo(2.35, -0.6, 0.02, 0.58, 0.02, 0.78, "decor1", bev=0.003)
    m.box_lo(2.35, -0.62, 0.6, 0.16, 0.02, 0.02, "steel")
    floor_frame(m, 6.0, 3.6)


def machine_pack(m):
    """Пакування: роликовий стіл, розмотувач гофрокартону, палетообмотувач."""
    roller_table(m, -0.9, 0, 2.2, 1.2, 0.88, axis="Y")
    m.box_lo(-1.2, 0, 0.88, 0.9, 0.65, 0.4, "carton", bev=0.008)
    m.box_lo(-1.2, -0.02, 1.28, 0.9, 0.05, 0.003, "tape")
    m.box_lo(-0.4, 0.1, 0.88, 0.5, 0.4, 0.03, "carton")
    # розмотувач гофрокартону
    for dx in (-1.9, 0.1):
        m.box_lo(dx, 0.85, 0, 0.06, 0.06, 1.15, "steel_dark")
    m.cyl((-0.9, 0.85, 1.1), 0.25, 1.8, "carton", axis="X", segs=24)
    m.cyl((-0.9, 0.85, 1.1), 0.03, 2.1, "steel", axis="X", segs=8)
    m.box((-0.9, 0.6, 0.98), (1.8, 0.4, 0.004), "carton", rot=(30, 0, 0))
    # палетообмотувач
    m.box_lo(1.5, 0, 0, 1.9, 1.9, 0.07, "machine_dark", bev=0.02)
    m.box((1.5, -1.15, 0.035), (1.9, 0.5, 0.02), "steel", rot=(-8, 0, 0))
    m.cyl((1.5, 0, 0.09), 0.85, 0.05, "steel", segs=36)
    m.box_lo(1.5, 1.1, 0, 0.22, 0.22, 2.5, "machine_accent", bev=0.03)
    m.box_lo(1.5, 1.32, 0.3, 0.3, 0.2, 0.6, "machine", bev=0.02)
    m.box((1.5, 1.425, 0.75), (0.2, 0.01, 0.12), "screen_on")
    m.box_lo(1.5, 0.9, 1.1, 0.34, 0.2, 0.45, "machine", bev=0.03)
    m.cyl((1.5, 0.78, 1.33), 0.07, 0.5, "film_roll", segs=16)
    pallet(m, 1.5, 0, 0.115)
    cartons(m, 1.5, 0, 0.26, 1.15, 0.75, 3)
    floor_frame(m, 5.2, 3.2)



def forklift(m):
    m.box_lo(0, 0, 0.15, 1.6, 1.05, 0.72, "forklift", bev=0.06)
    m.box_lo(-0.65, 0, 0.15, 0.42, 1.05, 0.95, "machine_dark", bev=0.08)  # противага
    for dx in (-0.55, 0.55):
        for dy in (-0.48, 0.48):
            m.cyl((dx, dy, 0.24), 0.24, 0.2, "rubber", axis="Y", segs=18)
            m.cyl((dx, dy * 1.02, 0.24), 0.12, 0.21, "steel", axis="Y", segs=12)
    for dx in (-0.5, 0.35):
        for dy in (-0.45, 0.45):
            m.box_lo(dx, dy, 0.87, 0.06, 0.06, 1.18, "machine_dark")
    m.box_lo(-0.07, 0, 2.05, 0.95, 1.0, 0.05, "machine_dark", bev=0.01)
    m.box_lo(-0.15, 0, 0.87, 0.45, 0.5, 0.12, "machine_dark", bev=0.04)  # сидіння
    m.box((-0.36, 0, 1.2), (0.08, 0.48, 0.5), "machine_dark", rot=(0, -12, 0), bev=0.03)
    m.cyl((0.22, 0, 1.25), 0.15, 0.03, "machine_dark", rot=(0, -40, 0), segs=16)  # кермо
    m.cyl((0.12, 0, 1.05), 0.025, 0.4, "machine_dark", rot=(0, -40, 0), segs=8)
    for dy in (-0.32, 0.32):
        m.box_lo(0.88, dy, 0.05, 0.08, 0.1, 2.4, "steel_dark", bev=0.01)  # щогла
    m.box_lo(0.88, 0, 2.3, 0.08, 0.74, 0.08, "steel_dark")
    m.box_lo(0.95, 0, 0.1, 0.06, 0.9, 0.5, "steel_dark")  # каретка
    for dy in (-0.25, 0.25):
        m.box_lo(1.5, dy, 0.1, 1.1, 0.12, 0.04, "steel_dark")
    m.cyl((-0.1, 0, 2.12), 0.06, 0.08, "status_amber", segs=12)  # маячок


def person(m, x, y, rz=0.0, vest="hivis", arms="front"):
    """Низькополігональна фігура оператора (зріст ~1,75 м)."""
    a = math.radians(rz)
    ca, sa = math.cos(a), math.sin(a)

    def P(lx, ly, z):
        return (x + lx * ca - ly * sa, y + lx * sa + ly * ca, z)
    for s in (-1, 1):
        m.box(P(0, s * 0.1, 0.43), (0.16, 0.15, 0.82), "trousers", rz=rz, bev=0.05)
        m.box(P(0.04, s * 0.1, 0.04), (0.27, 0.12, 0.08), "rubber", rz=rz, bev=0.03)
    m.box(P(0, 0, 1.13), (0.24, 0.42, 0.62), "shirt", rz=rz, bev=0.08)
    m.box(P(0, 0, 1.15), (0.27, 0.45, 0.46), vest, rz=rz, bev=0.08)
    for s in (-1, 1):
        if arms == "front":
            m.box(P(0.18, s * 0.26, 1.08), (0.48, 0.1, 0.1), "shirt", rot=(0, 35, rz), bev=0.04)
            m.sphere(P(0.38, s * 0.24, 0.94), 0.05, "skin", subdiv=1)
        else:
            m.box(P(0, s * 0.27, 1.08), (0.1, 0.1, 0.58), "shirt", rz=rz, bev=0.04)
            m.sphere(P(0, s * 0.27, 0.76), 0.05, "skin", subdiv=1)
    m.cyl(P(0, 0, 1.5), 0.05, 0.1, "skin", segs=10)
    m.sphere(P(0.01, 0, 1.64), 0.11, "skin", scale=(1.0, 0.9, 1.12))
    m.sphere(P(-0.01, 0, 1.69), 0.112, "hair", scale=(1.0, 0.92, 0.85))
    for s in (-1, 1):  # навушники
        m.cyl(P(0, s * 0.11, 1.64), 0.045, 0.04, "status_red", axis="Y", segs=12, rot=(90, 0, rz))




def machine_nest(m):
    """Нестинг-центр: підйомний стіл завантаження зі стосом МДФ, стіл із жертовною
    плитою, портал зі шпинделем і витяжним ковпаком, лінійний магазин інструменту,
    стрічковий конвеєр вивантаження, принтер етикеток, шафа керування."""
    # завантаження
    m.box_lo(-4.0, 0, 0, 2.9, 2.3, 0.45, "machine_mid", bev=0.03)
    m.box_lo(-4.0, 0, 0.45, 2.8, 2.07, 0.018 * 14, "decor5")
    for dy in (-1.3, 1.3):
        m.box_lo(-3.4, dy, 0, 4.0, 0.2, 1.0, "machine", bev=0.03)
    m.box_lo(-3.2, 0, 1.0, 0.25, 2.8, 0.2, "machine_accent", bev=0.03)  # штовхач
    # станина та стіл
    m.box_lo(0.3, 0, 0, 4.4, 2.5, 0.8, "machine", bev=0.05)
    m.box_lo(0.3, 0, 0.8, 4.2, 2.3, 0.05, "machine_dark")
    m.box_lo(0.3, 0, 0.85, 4.1, 2.2, 0.03, "table_top")
    m.box_lo(0.0, 0, 0.88, 2.8, 2.07, 0.018, "decor5")
    for k in range(1, 4):
        m.box((0.0 - 1.4 + k * 0.7, 0, 0.899), (0.006, 2.0, 0.002), "machine_dark")
    m.box((0.0, 0, 0.899), (2.7, 0.006, 0.002), "machine_dark")
    for dy in (-1.2, 1.2):
        m.box_lo(0.3, dy, 0.8, 4.4, 0.1, 0.14, "steel", bev=0.01)
    # портал
    gx = 0.6
    for dy in (-1.4, 1.4):
        m.box_lo(gx, dy, 0.8, 0.6, 0.32, 1.5, "machine_accent", bev=0.05)
    m.box_lo(gx, 0, 2.2, 0.7, 3.1, 0.55, "machine_accent", bev=0.07)
    for k in range(18):
        m.box_lo(gx + 0.14, -1.45 + k * 0.17, 2.75, 0.22, 0.14, 0.1, "machine_dark", bev=0.01)
    m.box_lo(gx - 0.45, -0.3, 1.25, 0.32, 0.5, 1.1, "machine", bev=0.03)
    m.cyl((gx - 0.45, -0.3, 1.45), 0.14, 0.5, "machine_mid", segs=20)
    m.cyl((gx - 0.45, -0.3, 1.0), 0.26, 0.2, "guard_glass", segs=24)  # витяжний ковпак
    m.cyl((gx - 0.45, -0.3, 0.93), 0.27, 0.05, "rubber", segs=24)
    m.cyl((gx - 0.45, -0.3, 0.98), 0.03, 0.14, "alu", segs=8)
    # лінійний магазин інструменту
    m.box_lo(-1.8, 1.45, 0.8, 1.0, 0.25, 0.25, "machine_mid", bev=0.02)
    for k in range(8):
        m.cyl((-2.2 + k * 0.12, 1.45, 1.12), 0.035, 0.12, "alu", segs=8)
    # вивантаження: стрічковий конвеєр
    legs_frame(m, 4.4, 0, 3.0, 2.3, 0.82)
    m.box_lo(4.4, 0, 0.82, 3.0, 2.3, 0.06, "rubber", bev=0.02)
    for dx in (-1.5, 1.5):
        m.cyl((4.4 + dx, 0, 0.85), 0.06, 2.3, "steel", axis="Y", segs=12)
    for i, (dx, dy) in enumerate(((-0.8, -0.5), (0.1, 0.6), (0.9, -0.4))):
        m.box_lo(4.4 + dx, dy, 0.88, 0.7, 0.5, 0.018, "decor5")
        m.box_lo(4.4 + dx, dy, 0.898, 0.1, 0.06, 0.002, "phenolic")  # етикетка
    m.box_lo(5.3, -1.5, 0, 0.12, 0.12, 1.3, "steel_dark")
    m.box_lo(5.3, -1.4, 1.3, 0.35, 0.3, 0.25, "machine_dark", bev=0.02)  # принтер етикеток
    # шафа керування, бампер, пульт
    m.box_lo(-1.8, 1.95, 0, 0.9, 0.5, 2.0, "machine_mid", bev=0.02)
    m.box_lo(-1.8, 1.69, 0.2, 0.7, 0.01, 1.6, "machine_dark")
    m.box_lo(0.3, -1.6, 0.25, 4.4, 0.12, 0.12, "marking", bev=0.03)
    hazard(m, -1.9, 2.5, -1.67, 0.25, depth=0.005, h=0.12)
    console(m, 2.3, -2.35, 1.0, facing=90)
    floor_frame(m, 11.2, 4.6)


# ---------------------------------------------------------------- додаткове обладнання
def robot(m, x, y, rz=0.0, z=0.0, part=True):
    """Шестиосьовий промисловий робот у фіксованій позі (рука витягнута вздовж локальної X)."""
    a = math.radians(rz)
    ca, sa = math.cos(a), math.sin(a)

    def P(lx, ly, lz):
        return (x + lx * ca - ly * sa, y + lx * sa + ly * ca, z + lz)
    m.cyl(P(0, 0, 0.03), 0.42, 0.06, "machine_dark", segs=20)
    m.cyl(P(0, 0, 0.22), 0.34, 0.32, "robot", segs=24)
    m.box(P(0, 0, 0.55), (0.55, 0.5, 0.35), "robot", rot=(0, 0, rz), bev=0.06)
    m.cyl(P(0, 0, 0.75), 0.17, 0.62, "robot", segs=18, rot=(90, 0, rz))
    m.box(P(0.25, 0, 1.175), (0.24, 0.28, 1.0), "robot", rot=(0, 30.5, rz), bev=0.06)
    m.cyl(P(0.5, 0, 1.6), 0.14, 0.45, "robot", segs=18, rot=(90, 0, rz))
    m.box(P(0.95, 0, 1.525), (0.92, 0.2, 0.2), "robot", rot=(0, 9.5, rz), bev=0.05)
    m.box(P(0.42, 0, 1.78), (0.32, 0.24, 0.24), "machine_dark", rot=(0, 0, rz), bev=0.04)
    m.cyl(P(1.42, 0, 1.38), 0.07, 0.16, "robot", segs=14)
    m.cyl(P(1.42, 0, 1.28), 0.1, 0.04, "machine_dark", segs=16)
    m.box(P(1.42, 0, 1.24), (0.7, 0.45, 0.05), "alu", rot=(0, 0, rz), bev=0.01)
    for i in (-1, 1):
        for j in (-1, 1):
            m.cyl(P(1.42 + i * 0.25, j * 0.15, 1.2), 0.04, 0.04, "rubber", segs=10)
    if part:
        m.box(P(1.42, 0, 1.17), (0.9, 0.6, 0.016), "decor0", rot=(0, 0, rz))


def fence(m, pts, h=1.9, step=1.6):
    """Захисна огорожа: стійки + прозорі панелі вздовж ламаної."""
    for a, b in zip(pts, pts[1:]):
        a, b = Vector((*a, 0)), Vector((*b, 0))
        n = max(1, round((b - a).length / step))
        ang = math.degrees(math.atan2(b.y - a.y, b.x - a.x))
        for k in range(n + 1):
            p = a + (b - a) * (k / n)
            m.box_lo(p.x, p.y, 0, 0.06, 0.06, h, "marking")
        mid, ln = (a + b) / 2, (b - a).length
        m.box((mid.x, mid.y, 0.15 + (h - 0.3) / 2), (ln, 0.02, h - 0.3), "guard_glass", rz=ang)
        m.box((mid.x, mid.y, h - 0.03), (ln, 0.05, 0.05), "marking", rz=ang)


def cabinet(m, x, y, z, w=0.8, d=0.56, h=0.8, decor="decor0"):
    """Зібраний корпус шафи."""
    for dx in (-w / 2 + 0.009, w / 2 - 0.009):
        m.box_lo(x + dx, y, z, 0.018, d, h, decor)
    for zz in (z, z + h - 0.018):
        m.box_lo(x, y, zz, w, d, 0.018, decor)
    m.box_lo(x, y + d / 2 - 0.003, z, w, 0.004, h, "decor6")


def rack_cart(m, x, y, n=6):
    """Етажерка на колесах із фасадами на полицях."""
    for dx in (-0.6, 0.6):
        for dy in (-0.3, 0.3):
            m.box_lo(x + dx, y + dy, 0.1, 0.03, 0.03, 1.8, "steel")
            m.cyl((x + dx, y + dy, 0.05), 0.05, 0.04, "rubber", axis="X", segs=10)
    for k in range(n):
        z = 0.25 + k * 0.27
        m.box_lo(x, y, z, 1.2, 0.6, 0.02, "steel")
        m.box_lo(x, y, z + 0.02, 1.0, 0.5, 0.019, "decor5" if k % 2 else "phenolic")


def machine_saw_book(m):
    machine_saw(m)
    m.box_lo(-1.75, 0, 0.84, 2.8, 2.07, 0.36, "decor1")  # вищий стос на підйомному столі
    for dy in (-1.4, -0.15, 1.25):
        m.box_lo(1.8, dy, 0.98, 1.3, 0.7, 0.096, "decor1")  # «книги» деталей


def machine_edge_robot(m):
    machine_edge(m)
    robot(m, 5.9, 1.25, rz=-125.8)
    fence(m, [(4.3, 2.05), (6.45, 2.05), (6.45, 0.65)])


def machine_slide(m):
    """Форматно-розкрійний верстат із кареткою."""
    m.box_lo(0, 0, 0, 1.1, 0.9, 0.85, "machine_mid", bev=0.03)
    m.box_lo(0, 0.1, 0.85, 1.2, 1.1, 0.05, "steel", bev=0.01)
    m.cyl((0.0, 0.1, 0.86), 0.17, 0.004, "steel", rot=(90, 0, 0), segs=24)
    m.box_lo(-0.2, -0.55, 0.7, 3.2, 0.35, 0.2, "alu", bev=0.02)
    m.box_lo(-0.2, -0.55, 0.9, 3.2, 0.38, 0.02, "steel")
    m.box_lo(-0.9, -1.2, 0.88, 0.12, 1.3, 0.05, "alu")
    m.box_lo(-0.9, -1.8, 0, 0.06, 0.06, 0.88, "steel_dark")
    m.box_lo(-0.6, -1.25, 0.93, 0.06, 1.2, 0.1, "alu")
    m.box_lo(0, 0.45, 0.9, 1.2, 0.06, 0.1, "alu")
    m.box_lo(0, 0.78, 0.85, 1.3, 0.08, 0.06, "steel")
    m.box_lo(0.55, 0.9, 0, 0.12, 0.12, 1.9, "steel_dark")
    m.box((0.28, 0.5, 1.85), (0.7, 0.08, 0.08), "steel_dark", rz=-55)
    m.box_lo(0, 0.1, 1.05, 0.35, 0.12, 0.18, "machine_accent", bev=0.02)
    m.tube([(0, 0.1, 1.23), (0.1, 0.25, 1.75), (0.55, 0.9, 1.95)], 0.04, "rubber")
    m.box_lo(-0.4, -0.9, 0.92, 2.0, 0.9, 0.018, "decor0")
    estop(m, 0.45, -0.42, 0.85)
    floor_frame(m, 3.8, 3.2)


def machine_vsaw(m):
    """Вертикальна панельна пила: рама з нахилом назад, опорна балка з роликами,
    вертикальна напрямна з пильним агрегатом."""
    m.box((0, 0.35, 1.3), (5.4, 0.12, 2.4), "machine_accent", rot=(-6, 0, 0), bev=0.03)
    for z in (0.6, 1.1, 1.6, 2.1):
        m.box((0, 0.25 + (z - 0.3) * 0.105, z), (5.2, 0.06, 0.06), "alu", rot=(-6, 0, 0))
    m.box_lo(0, -0.15, 0, 5.6, 0.5, 0.3, "machine_mid", bev=0.02)
    for k in range(14):
        m.cyl((-2.6 + k * 0.4, -0.1, 0.32), 0.04, 0.3, "rubber", axis="Y", segs=10)
    m.box((0.6, 0.18, 1.45), (0.25, 0.2, 2.9), "steel", rot=(-6, 0, 0), bev=0.02)
    m.box((0.6, 0.02, 1.2), (0.35, 0.25, 0.35), "machine_dark", rot=(-6, 0, 0), bev=0.03)
    m.box((-0.5, 0.2, 1.37), (2.8, 0.018, 2.07), "decor2", rot=(-6, 0, 0))
    for x in (-2.75, 2.75):
        m.box_lo(x, 0.6, 0, 0.15, 0.7, 0.1, "machine_dark")
    m.box_lo(2.4, -0.7, 0, 0.3, 0.3, 1.2, "machine_dark")
    m.box((2.4, -0.86, 1.35), (0.4, 0.04, 0.3), "screen_on")
    floor_frame(m, 6.0, 2.2)


def machine_dowel(m):
    """Свердлильно-присадний верстат із забиванням шкантів."""
    legs_frame(m, 0, 0, 3.4, 1.0, 0.85)
    m.box_lo(0, 0, 0.85, 3.4, 1.0, 0.05, "phenolic", bev=0.01)
    m.box_lo(0, 0.7, 0, 1.4, 0.5, 1.35, "machine", bev=0.04)
    m.box_lo(0, 0.6, 1.35, 1.5, 0.7, 0.35, "machine_accent", bev=0.05)
    m.box_lo(0, 0.3, 0.9, 1.0, 0.3, 0.25, "machine_dark", bev=0.02)
    for k in range(6):
        m.cyl((-0.4 + k * 0.16, 0.12, 1.0), 0.012, 0.12, "alu", axis="Y", segs=6)
    m.cyl((0.45, 0.6, 1.85), 0.25, 0.18, "steel", segs=24)  # вібробункер шкантів
    m.cyl((0.45, 0.6, 1.76), 0.08, 0.15, "steel_dark", segs=10)
    m.tube([(0.45, 0.45, 1.75), (0.3, 0.35, 1.35), (0.1, 0.3, 1.1)], 0.02, "guard_glass")
    for k in range(3):
        m.cyl((-1.2 + k * 1.2, -0.1, 1.15), 0.04, 0.3, "alu", segs=10)
    m.box_lo(-0.3, -0.1, 0.9, 2.2, 0.6, 0.018, "decor0")
    m.box((-0.6, 0.44, 1.15), (0.4, 0.02, 0.3), "screen_on")
    m.box_lo(0, -0.85, 0, 3.4, 0.6, 0.015, "rubber")
    floor_frame(m, 3.8, 2.4)


def machine_bore(m):
    """Прохідний свердлильний верстат: стрічка подачі, чотири свердлильні агрегати."""
    m.box_lo(0, 0, 0, 5.0, 1.4, 0.85, "machine", bev=0.04)
    m.box_lo(0, -0.2, 0.85, 5.0, 0.6, 0.03, "rubber")
    for k in range(4):
        m.box_lo(-1.6 + k * 1.05, 0.3, 0.88, 0.7, 0.6, 0.7, "machine_accent" if k % 2 else "machine_mid",
                 bev=0.04)
    m.box_lo(0, -0.62, 0.95, 4.6, 0.02, 0.45, "guard_glass")
    m.box_lo(0, 0.0, 1.58, 5.0, 1.3, 0.12, "machine", bev=0.03)
    roller_table(m, -3.4, 0, 1.6, 1.3, 0.88, axis="Y")
    roller_table(m, 3.4, 0, 1.6, 1.3, 0.88, axis="Y")
    m.box_lo(-3.4, -0.1, 0.88, 0.9, 0.6, 0.018, "decor1")
    m.box_lo(3.3, 0.0, 0.88, 0.9, 0.6, 0.036, "decor1")
    m.box_lo(2.0, -1.0, 0, 0.35, 0.3, 1.3, "machine_dark")
    m.box((2.0, -1.16, 1.45), (0.45, 0.05, 0.3), "screen_on")
    floor_frame(m, 7.2, 2.6)


def machine_hinge(m):
    """Верстат для встановлення завіс і монтажних планок: дві пневмоголови з бункерами."""
    legs_frame(m, 0, 0, 2.2, 0.9, 0.85)
    m.box_lo(0, 0, 0.85, 2.2, 0.9, 0.05, "phenolic", bev=0.01)
    for x in (-0.55, 0.55):
        m.box_lo(x, 0.38, 0.9, 0.25, 0.2, 0.85, "machine_accent", bev=0.03)
        m.box_lo(x, 0.2, 1.55, 0.25, 0.45, 0.2, "machine_accent", bev=0.03)
        m.cyl((x, 0.05, 1.38), 0.05, 0.3, "alu", segs=12)
        m.box_lo(x, 0.05, 1.08, 0.12, 0.12, 0.12, "machine_dark")
        m.cyl((x, 0.5, 1.95), 0.16, 0.12, "steel", segs=20)
    m.box_lo(0, -0.05, 0.9, 1.6, 0.5, 0.018, "decor1")
    m.box_lo(-1.4, 0, 0, 0.5, 0.5, 0.9, "steel", bev=0.02)
    floor_frame(m, 3.4, 2.0)


def machine_sortbot(m):
    """Роботизована комірка сортування: робот на лінійній колії між стелажами з деталями."""
    L = 7.0
    m.box_lo(0, 0, 0, L, 0.5, 0.12, "steel_dark")
    m.box_lo(0, 0, 0.12, L, 0.18, 0.06, "alu")
    m.box_lo(-1.0, 0, 0.18, 0.9, 0.8, 0.15, "machine_mid", bev=0.03)
    robot(m, -1.0, 0, rz=90, z=0.33)
    for side in (-1, 1):
        yy = side * 2.1
        for k in range(9):
            for dy in (-0.42, 0.42):
                m.box_lo(-L / 2 + 0.02 + k * 0.87, yy + dy, 0, 0.06, 0.06, 2.6, "rack_upright")
        for s in range(8):
            x = -L / 2 + 0.455 + s * 0.87
            for lv in range(4):
                z = 0.3 + lv * 0.6
                m.box_lo(x, yy, z - 0.04, 0.8, 0.9, 0.04, "steel")
                for k in range((s * 3 + lv * 5 + side) % 5):
                    m.box_lo(x - 0.3 + k * 0.15, yy, z, 0.018, 0.8, 0.42, "decor%d" % ((s + k) % 3))
    roller_table(m, -L / 2 - 0.9, 0, 1.4, 1.2, 0.85, axis="X")
    roller_table(m, L / 2 + 0.9, 0, 1.4, 1.2, 0.85, axis="X")
    x0, x1, y0, y1 = -L / 2 - 0.3, L / 2 + 0.3, -2.75, 2.75
    fence(m, [(x0, -0.75), (x0, y0), (x1, y0), (x1, -0.75)])
    fence(m, [(x0, 0.75), (x0, y1), (x1, y1), (x1, 0.75)])
    console(m, L / 2 - 0.5, y0 - 0.5, 1.0, facing=90)
    floor_frame(m, 9.8, 6.4)


def machine_asmline(m):
    """Автоматична лінія збирання корпусів: подача, станція клею і шкантів,
    автоматична вайма, поворотний пристрій, вихідний конвеєр."""
    roller_table(m, -9.5, 0, 5.0, 1.4, 0.85, pitch=0.3, axis="Y")
    m.box_lo(-10.0, 0, 0.86, 1.0, 0.6, 0.1, "decor0")
    m.box_lo(-5.6, 0, 0, 2.4, 1.6, 0.85, "machine", bev=0.04)
    m.box_lo(-5.6, 0.55, 0.85, 2.4, 0.5, 1.0, "machine_accent", bev=0.05)
    m.box_lo(-5.6, 0.1, 1.5, 2.4, 0.4, 0.3, "machine_accent", bev=0.04)
    for k in range(5):
        m.cyl((-6.5 + k * 0.45, 0.1, 1.3), 0.03, 0.35, "alu", segs=8)
    cx = -1.0
    m.box_lo(cx, 0, 0, 3.6, 1.8, 0.75, "machine_mid", bev=0.04)
    for dx in (-1.9, 1.9):
        for dy in (-1.0, 1.0):
            m.box_lo(cx + dx, dy, 0, 0.2, 0.2, 2.8, "machine_accent", bev=0.03)
    m.box_lo(cx, 0, 2.8, 4.0, 2.2, 0.25, "machine_accent", bev=0.05)
    for dy in (-0.95, 0.95):
        m.box_lo(cx, dy, 0.75, 3.4, 0.03, 1.9, "guard_glass")
    for k in range(4):
        m.cyl((cx - 1.2 + k * 0.8, 0, 2.55), 0.05, 0.4, "alu", segs=12)
    m.box_lo(cx, 0, 2.0, 3.2, 1.2, 0.08, "steel_dark")
    for dx in (-1.6, 1.6):
        m.cyl((cx + dx, 0, 1.4), 0.05, 0.5, "alu", axis="X", segs=12)
    cabinet(m, cx, 0, 0.75, w=1.0, d=0.6, h=1.2)
    m.cyl((3.2, 0, 0.4), 0.9, 0.8, "machine_mid", segs=28)
    m.cyl((3.2, 0, 0.82), 0.85, 0.04, "steel", segs=28)
    cabinet(m, 3.2, 0, 0.84, w=0.8, d=0.56, h=0.8)
    roller_table(m, 7.8, 0, 6.6, 1.4, 0.85, pitch=0.3, axis="Y")
    for x in (6.0, 8.4, 10.6):
        cabinet(m, x, 0, 0.86, w=0.8, d=0.56, h=0.8)
    console(m, -3.6, -1.4, 1.0, facing=90)
    floor_frame(m, 24.4, 3.4)


def machine_box(m):
    """Станок розкрою гофрокартону: коробка під розмір виробу з фанфолд-пачок."""
    m.box_lo(0, 0, 0, 2.6, 1.3, 1.25, "machine", bev=0.05)
    m.box_lo(0, 0, 1.25, 2.6, 1.3, 0.25, "machine_accent", bev=0.05)
    m.box_lo(0, -0.66, 0.6, 2.2, 0.02, 0.5, "guard_glass")
    m.box((0.9, -0.66, 1.1), (0.35, 0.02, 0.25), "screen_on")
    legs_frame(m, 0, -1.0, 2.6, 0.7, 0.85)
    m.box_lo(0, -1.0, 0.85, 2.6, 0.7, 0.03, "steel")
    m.box_lo(0.2, -1.0, 0.88, 1.8, 0.6, 0.004, "carton")
    for k, dx in enumerate((-0.9, 0.0, 0.9)):
        m.box_lo(dx, 1.45, 0, 0.85, 1.0, 0.12, "pallet")
        m.box_lo(dx, 1.45, 0.12, 0.8, 0.95, 0.9 - k * 0.2, "carton")
        m.box((dx, 0.95, 1.35), (0.75, 0.7, 0.004), "carton", rot=(-35, 0, 0))
    floor_frame(m, 3.2, 4.0)


def machine_packline(m):
    """Лінія термоусадки та обв'язки: L-зварювач, термотунель, обв'язувальна арка."""
    roller_table(m, 0, 0, 9.0, 1.3, 0.85, pitch=0.35, axis="Y")
    m.box_lo(-2.8, 0.75, 0, 0.4, 0.3, 1.4, "machine_mid", bev=0.02)
    m.box((-2.8, 0, 1.15), (1.4, 1.4, 0.06), "machine_accent", bev=0.02)
    m.cyl((-2.8, 0.95, 1.55), 0.15, 1.2, "film_roll", axis="X", segs=16)
    m.box_lo(0.6, 0, 0.85, 2.6, 1.6, 1.1, "machine", bev=0.05)
    m.box_lo(0.6, 0, 1.95, 2.2, 1.2, 0.25, "machine_accent", bev=0.05)
    for xe in (0.6 - 1.31, 0.6 + 1.31):
        for k in range(6):
            m.box_lo(xe, -0.55 + k * 0.22, 1.0, 0.01, 0.2, 0.85, "rubber")
    for dy in (-0.85, 0.85):
        m.box_lo(3.4, dy, 0, 0.3, 0.3, 2.2, "machine_mid", bev=0.03)
    m.box_lo(3.4, 0, 2.2, 0.3, 2.0, 0.3, "machine_mid", bev=0.03)
    m.box_lo(3.4, -1.25, 0, 0.6, 0.5, 1.0, "machine_accent", bev=0.03)
    m.cyl((3.4, -1.55, 0.6), 0.3, 0.15, "machine_dark", axis="Y", segs=20)
    m.box_lo(-3.8, 0, 0.85, 1.0, 0.6, 0.5, "carton", bev=0.008)
    m.box_lo(2.4, 0, 0.85, 1.02, 0.62, 0.52, "wrap")
    m.box_lo(2.4, 0, 0.86, 1.0, 0.6, 0.5, "carton", bev=0.008)
    floor_frame(m, 10.0, 3.6)


def machine_sand(m):
    """Широкострічковий шліфувальний верстат із рольгангами."""
    m.box_lo(0, 0, 0, 1.8, 2.6, 0.75, "machine_mid", bev=0.04)
    m.box_lo(0, 0, 0.75, 1.9, 2.2, 0.06, "rubber")
    for dy in (-1.35, 1.35):
        m.box_lo(0, dy, 0, 1.8, 0.3, 1.05, "machine", bev=0.03)
    m.box_lo(0, 0, 1.05, 1.8, 3.0, 1.25, "machine", bev=0.06)
    m.box_lo(0, 0, 2.3, 1.4, 2.6, 0.25, "machine_accent", bev=0.05)
    m.box_lo(0.91, 0, 1.25, 0.02, 2.4, 0.8, "machine_mid")
    for dy in (-0.6, 0.6):
        m.cyl((0, dy, 2.7), 0.18, 0.3, "galv", segs=16)
    roller_table(m, -2.0, 0, 2.0, 2.2, 0.8, axis="Y")
    roller_table(m, 2.0, 0, 2.0, 2.2, 0.8, axis="Y")
    for dy in (-0.45, 0.45):
        m.box_lo(-2.0, dy, 0.8, 0.7, 0.5, 0.019, "decor5")
        m.box_lo(2.1, dy, 0.8, 0.7, 0.5, 0.019, "phenolic")
    m.box_lo(0.6, -1.85, 0, 0.35, 0.3, 1.4, "machine_dark")
    m.box((0.6, -2.01, 1.5), (0.4, 0.04, 0.3), "screen_on")
    floor_frame(m, 6.2, 4.0)


def machine_glue(m):
    """Кабіна розпилення клею перед мембранним пресом: фільтрова стінка, поворотний стіл."""
    m.box_lo(0, 1.1, 0, 3.2, 0.12, 2.6, "machine")
    m.box_lo(0, 1.0, 0.4, 2.8, 0.06, 1.9, "filter")
    for x in (-1.55, 1.55):
        m.box_lo(x, 0, 0, 0.1, 2.3, 2.6, "machine")
    m.box_lo(0, 0, 2.6, 3.2, 2.3, 0.12, "machine")
    m.box_lo(0, 0, 2.55, 2.4, 1.4, 0.04, "led")
    m.cyl((0, 0.1, 0.35), 0.08, 0.7, "steel_dark", segs=10)
    m.cyl((0, 0.1, 0.72), 0.6, 0.04, "steel", segs=28)
    m.box_lo(0, 0.1, 0.74, 0.9, 0.6, 0.019, "decor5")
    m.box_lo(1.0, -0.8, 0, 0.5, 0.5, 0.8, "machine_dark", bev=0.03)
    m.cyl((1.0, -0.8, 0.95), 0.18, 0.3, "steel", segs=16)
    m.tube([(1.0, -0.8, 1.0), (0.6, -0.5, 1.1), (0.3, -0.3, 1.15)], 0.015, "rubber")
    floor_frame(m, 3.8, 3.0)


def machine_press(m):
    """Мембранно-вакуумний прес: прес із піднятою кришкою ІЧ-нагрівачів,
    два човникові столи з фасадами, вакуум-насос, стійка з плівкою ПВХ."""
    m.box_lo(0, 0, 0, 3.8, 2.1, 1.0, "machine_mid", bev=0.05)
    for dx in (-1.95, 1.95):
        for dy in (-1.0, 1.0):
            m.box_lo(dx, dy, 1.0, 0.2, 0.2, 1.3, "machine_accent", bev=0.03)
    m.box_lo(0, 0, 1.85, 4.0, 2.2, 0.55, "machine_accent", bev=0.06)
    m.box_lo(0, 0, 1.8, 3.6, 1.9, 0.04, "heater")
    m.box_lo(0, 0, 1.0, 3.6, 1.9, 0.05, "rubber")
    for sx in (-1, 1):
        x = sx * 4.0
        legs_frame(m, x, 0, 3.8, 1.9, 0.85)
        m.box_lo(x, 0, 0.85, 3.8, 1.9, 0.15, "steel", bev=0.02)
        for i in range(3):
            for j in range(2):
                m.box_lo(x - 1.2 + i * 1.2, -0.45 + j * 0.9, 1.0, 1.0, 0.7, 0.022,
                         "decor2" if sx > 0 else "decor5", bev=0.006)
    m.box_lo(2.4, 1.4, 0, 0.8, 0.6, 0.9, "machine_dark", bev=0.03)
    m.cyl((2.4, 1.4, 1.05), 0.15, 0.3, "steel", segs=16)
    m.box_lo(-2.2, 1.35, 0, 0.1, 0.1, 1.3, "steel_dark")
    m.cyl((-2.2, 1.35, 1.35), 0.15, 1.5, "decor2", axis="X", segs=16)
    console(m, 0.8, -1.6, 1.0, facing=90)
    floor_frame(m, 12.4, 3.4)


def machine_spray(m):
    """Фарбувальна камера з водяною завісою та етажеркою фасадів."""
    w, d, h = 5.0, 3.6, 3.0
    m.box_lo(0, d / 2, 0, w, 0.12, h, "machine")
    m.box_lo(0, d / 2 - 0.1, 0.2, w - 0.4, 0.06, 2.4, "water_glass")
    m.box_lo(0, d / 2 - 0.45, 0, w - 0.2, 0.6, 0.35, "machine_mid")
    for x in (-w / 2, w / 2):
        m.box_lo(x, 0, 0, 0.12, d, h, "machine")
    m.box_lo(0, 0, h, w + 0.12, d, 0.15, "machine")
    for x in (-1.5, 0, 1.5):
        m.box_lo(x, 0, h - 0.06, 1.2, 0.4, 0.05, "led")
    rack_cart(m, -1.2, 0.3)
    m.cyl((1.2, 0.4, 0.45), 0.06, 0.9, "steel_dark", segs=10)
    m.cyl((1.2, 0.4, 0.92), 0.55, 0.04, "steel", segs=24)
    m.box_lo(1.2, 0.4, 0.94, 0.8, 0.5, 0.019, "phenolic")
    m.box_lo(-2.0, -1.5, 0, 0.6, 0.5, 0.9, "machine_dark", bev=0.03)
    m.tube([(-2.0, -1.5, 0.9), (-1.4, -1.0, 1.1), (0.4, -0.7, 1.0)], 0.015, "rubber")
    floor_frame(m, 5.6, 4.2)


def machine_autospray(m):
    """Автомат фарбування: кабіна з робочими пістолетами, зона відкритого випаровування."""
    roller_table(m, -5.0, 0, 2.2, 1.5, 0.9, axis="Y")
    m.box_lo(-2.1, 0, 0, 3.6, 2.4, 2.4, "machine", bev=0.05)
    m.box_lo(-2.1, -1.21, 0.9, 2.6, 0.02, 1.0, "guard_glass")
    m.box_lo(-2.1, 0, 2.4, 3.0, 1.8, 0.4, "machine_accent", bev=0.05)
    m.box_lo(-2.1, 0, 0.88, 3.8, 1.4, 0.04, "rubber")
    m.box_lo(2.2, 0, 0, 4.8, 1.9, 1.4, "machine_mid", bev=0.05)
    m.box_lo(2.2, 0, 1.4, 4.6, 1.7, 0.2, "machine_accent", bev=0.04)
    m.box_lo(2.2, -0.96, 0.9, 4.2, 0.02, 0.35, "guard_glass")
    roller_table(m, 5.6, 0, 1.6, 1.5, 0.9, axis="Y")
    m.box_lo(-5.0, 0, 0.9, 0.9, 0.6, 0.019, "decor5")
    m.box_lo(5.6, 0, 0.9, 0.9, 0.6, 0.019, "decor1")
    m.box_lo(-2.1, 1.55, 0, 0.8, 0.5, 1.6, "machine_dark", bev=0.03)
    console(m, -3.6, -1.6, 1.0, facing=90)
    floor_frame(m, 13.2, 3.6)


def machine_dry(m):
    """Сушильна камера з відчиненими дверима та етажерками всередині."""
    w, d, h = 6.0, 4.4, 3.0
    m.box_lo(0, d / 2, 0, w, 0.12, h, "wall")
    for x in (-w / 2, w / 2):
        m.box_lo(x, 0, 0, 0.12, d, h, "wall")
    m.box_lo(0, 0, h, w + 0.12, d + 0.12, 0.12, "wall_band")
    for x in (-2.55, 2.55):
        m.box_lo(x, -d / 2, 0, 0.9, 0.12, h, "wall")
    m.box_lo(0, -d / 2, 2.6, 4.2, 0.12, 0.4, "wall")
    for x in (-2.05, 2.05):
        m.box_lo(x, -d / 2 - 0.8, 0, 0.06, 1.6, 2.55, "machine_mid")
    for x in (-1.8, -0.6, 0.6, 1.8):
        rack_cart(m, x, 0.6)
    m.box_lo(1.5, 0.8, h + 0.12, 2.0, 1.4, 1.0, "machine_mid", bev=0.04)
    m.cyl((-1.5, 1.0, h + 0.5), 0.3, 0.75, "galv", segs=18)
    m.box((2.8, -d / 2 - 0.07, 1.4), (0.5, 0.02, 0.4), "screen_on")
    floor_frame(m, 6.6, 5.0)


def machine_uv(m):
    """Лінія лакування з УФ-сушінням: вальцьовий лаконаносний верстат і два УФ-тунелі."""
    roller_table(m, -4.0, 0, 2.0, 1.4, 0.9, axis="Y")
    m.box_lo(-1.9, 0, 0, 1.6, 1.8, 1.2, "machine", bev=0.05)
    m.cyl((-1.9, 0, 1.05), 0.12, 1.5, "rubber", axis="Y", segs=16)
    m.cyl((-1.9, 0, 1.3), 0.09, 1.5, "steel", axis="Y", segs=14)
    m.box_lo(-1.9, 0, 1.35, 1.6, 1.8, 0.35, "machine_accent", bev=0.05)
    for x in (0.6, 2.4):
        m.box_lo(x, 0, 0, 1.5, 1.6, 0.85, "machine_mid", bev=0.04)
        m.box_lo(x, 0, 0.85, 1.5, 1.6, 0.7, "machine_dark", bev=0.05)
        m.box_lo(x, -0.81, 0.9, 1.2, 0.01, 0.12, "uv")
        m.box_lo(x, 0, 1.55, 0.9, 0.8, 0.3, "machine_mid", bev=0.03)
    m.box_lo(1.5, 0, 0.85, 4.0, 1.3, 0.03, "rubber")
    roller_table(m, 4.4, 0, 1.8, 1.4, 0.9, axis="Y")
    m.box_lo(-4.0, 0, 0.9, 0.9, 0.6, 0.019, "decor5")
    m.box_lo(4.4, 0, 0.9, 0.9, 0.6, 0.02, "decor1")
    floor_frame(m, 10.8, 2.6)


# ---------------------------------------------------------------- склади ЛФМ і пакування, інженерія
def build_north_rooms():
    """Склад пакувальних матеріалів, склад ЛФМ, етажерки готових фасадів."""
    def pallet_stack(m):
        for k in range(14):
            pallet(m, 0, 0, k * 0.144)
    ps = shared("pallet_stack", pallet_stack)
    for i in range(6):
        code = f"PAL-{i + 1}"
        instance(code, "shipping", ps, loc=(3.0 + (i % 3) * 1.6, 62.5 + (i // 3) * 1.2, 0), code=code,
                 kind="stock", label="Стос порожніх палет", desc="14 європалет для готової продукції.")

    pk = Mesh()
    for i in range(5):
        for j in range(3):
            x, y = 10.0 + i * 1.3, 62.6 + j * 1.25
            pk.box_lo(x, y, 0, 1.15, 1.0, 0.12, "pallet")
            pk.box_lo(x, y, 0.12, 1.1, 0.95, 0.6 + 0.2 * ((i + j) % 4), "carton")
    for i in range(4):
        for j in range(2):
            x, y = 18.5 + i * 1.4, 63.0 + j * 2.0
            pallet(pk, x, y)
            for a in range(2):
                for b in range(3):
                    pk.cyl((x - 0.3 + a * 0.6, y, 0.25 + b * 0.22), 0.1, 0.5, "film_roll", axis="X", segs=14)
    for i in range(3):
        pallet(pk, 28.0 + i * 1.6, 63.0)
        cartons(pk, 28.0 + i * 1.6, 63.0, 0.146, 1.15, 0.75, 3, wrap=False)
    for x in (31.0, 34.0, 37.0):
        pk.box_lo(x, 69.8, 0, 2.6, 0.9, 2.4, "shelf", bev=0.01)
        for z in (0.6, 1.2, 1.8):
            pk.box_lo(x, 69.6, z, 2.4, 0.5, 0.3, "carton", bev=0.005)
    pk.build("PACK-STORE", "shipping", code="PACK-STORE", kind="stock", label="Склад пакувальних матеріалів",
             desc="Фанфолд-гофрокартон, стрейч-плівка, кутики, скотч.")

    ps_ = Mesh()
    for i in range(3):
        for j in range(2):
            x, y = 41.5 + i * 1.5, 62.4 + j * 1.6
            pallet(ps_, x, y)
            for a in (-0.27, 0.27):
                for b in (-0.18, 0.18):
                    ps_.cyl((x + a, y + b, 0.146 + 0.44), 0.27, 0.88, "drum_blue", segs=18)
    for i in range(3):
        x = 42.0 + i * 1.4
        pallet(ps_, x, 69.6)
        ps_.box_lo(x, 69.6, 0.15, 1.0, 1.15, 1.0, "ibc")
        for z in (0.4, 0.75, 1.1):
            ps_.box_lo(x, 69.6, z, 1.04, 1.19, 0.03, "steel")
        ps_.cyl((x, 69.6, 1.2), 0.1, 0.06, "machine_dark", segs=12)
    ps_.box_lo(47.8, 66.0, 0, 0.9, 3.0, 2.0, "shelf", bev=0.01)
    for z in (0.3, 0.9, 1.5):
        for k in range(6):
            ps_.cyl((47.8, 64.8 + k * 0.45, z + 0.15), 0.12, 0.3, "machine_mid" if k % 2 else "status_amber",
                    segs=12)
    ps_.box_lo(40.5, 66.0, 0, 0.6, 2.0, 0.1, "status_amber")  # піддон для розливів
    ps_.box_lo(49.3, 61.5, 0.9, 0.2, 0.25, 0.6, "fire_red", bev=0.02)
    ps_.build("PAINT-STORE", "facade", code="PAINT-STORE", kind="stock", label="Склад ЛФМ",
              desc="Фарби, лаки, розчинники, клей: бочки, єврокуби, стелаж банок. "
                   "Окреме вогнестійке приміщення.")

    def cart_m(m):
        rack_cart(m, 0, 0)
    rc = shared("rack_cart", cart_m)
    for i, (x, y) in enumerate(((93.5, 62.5), (93.5, 64.3), (96.0, 62.5), (96.0, 64.3), (96.0, 68.5))):
        code = f"FRONTS-{i + 1}"
        instance(code, "facade", rc, loc=(x, y, 0), code=code, kind="kit", label=f"Етажерка {code}",
                 desc="Готові пофарбовані фасади, чекають на збирання.")


def build_utilities():
    # компресорна
    c = Mesh()
    for x in (101.5, 104.5):
        c.box_lo(x, 69.6, 0, 1.9, 1.0, 1.7, "machine_accent", bev=0.05)
        for k in range(6):
            c.box_lo(x, 69.09, 0.3 + k * 0.2, 1.5, 0.02, 0.06, "steel")
        c.cyl((x, 69.6, 1.75), 0.35, 0.1, "machine_dark", segs=20)
        c.box((x + 0.75, 69.08, 1.3), (0.25, 0.02, 0.18), "screen_on")
    for dx in (-0.4, 0.4):
        for dy in (-0.4, 0.4):
            c.box_lo(107.6 + dx, 69.5 + dy, 0, 0.08, 0.08, 0.5, "steel_dark")
    c.cyl((107.6, 69.5, 1.6), 0.62, 2.2, "galv", segs=24)
    c.sphere((107.6, 69.5, 2.7), 0.62, "galv", scale=(1, 1, 0.4))
    c.sphere((107.6, 69.5, 0.5), 0.62, "galv", scale=(1, 1, 0.4))
    c.box_lo(101.6, 66.4, 0, 1.2, 0.8, 1.3, "machine_mid", bev=0.04)  # осушувач
    for k in range(3):
        c.cyl((103.3 + k * 0.5, 66.4, 1.2), 0.08, 0.5, "steel", segs=12)
    c.tube(rounded_path([(101.5, 69.0, 1.8), (101.5, 67.9, 2.6), (107.6, 67.9, 2.6), (107.6, 69.5, 2.9)],
                        radius=0.25), 0.05, "air_blue", segs=10)
    c.tube(rounded_path([(107.6, 69.5, 3.0), (107.6, 69.5, 4.0), (107.6, 61.0, 4.0), (107.6, 61.0, 8.15)],
                        radius=0.3), 0.06, "air_blue", segs=10)
    c.build("COMPRESSOR", "utilities", code="COMPRESSOR", kind="equipment", label="Компресорна станція",
            desc="Два гвинтові компресори, ресивер 2 м³, рефрижераторний осушувач і фільтри. "
                 "Пневматика для верстатів, вайм і продувки.")
    # кільцева пневмомагістраль під покрівлею
    a = Mesh()
    ring = [(107.6, 61.0, 8.15), (99.2, 61.0, 8.15), (99.2, 45.5, 8.15), (50.5, 45.5, 8.15),
            (50.5, 1.0, 8.15), (99.2, 1.0, 8.15), (99.2, 45.5, 8.15)]
    a.tube(rounded_path(ring, radius=0.6), 0.06, "air_blue", segs=10)
    for x in range(54, 98, 6):  # спуски до дільниць
        a.tube([(x, 1.0, 8.15), (x, 1.0, 2.0)], 0.03, "air_blue", segs=8)
        a.box_lo(x, 1.0, 1.2, 0.15, 0.12, 0.3, "machine_dark")
    a.build("AIR-RING", "utilities", code="AIR-RING", kind="equipment", label="Пневмомагістраль",
            desc="Кільце стисненого повітря 6 бар під покрівлею з опусками до дільниць.")

    # зарядна станція
    z = Mesh()
    for k in range(4):
        x = 111.5 + k * 2.2
        z.box_lo(x, 71.2, 0.6, 0.6, 0.35, 1.0, "machine_mid", bev=0.03)
        z.box((x, 71.02, 1.3), (0.3, 0.02, 0.18), "screen_on")
        z.tube([(x, 71.0, 0.7), (x, 70.2, 0.3), (x, 69.4, 0.6)], 0.025, "rubber", segs=8)
    for k in range(5):
        z.box((110.4 + k * 2.2, 66.5, 0.022), (0.08, 9.0, 0.02), "marking")
    z.build("CHARGING", "utilities", code="CHARGING", kind="equipment", label="Зарядна станція",
            desc="Чотири зарядні пристрої для тягових АКБ навантажувачів, витяжна вентиляція.")
    for i, x in enumerate((111.5, 113.7)):
        instance(f"FL-C{i + 1}", "transport", shared("fl_empty", forklift), loc=(x, 68.0, 0), rz=-90,
                 code=f"FL-C{i + 1}", kind="vehicle", label="Навантажувач на зарядці",
                 desc="Акумулятор заряджається.")

    # спринклери та пожежні шафи
    s = Mesh()
    s.box_lo(1.0, D / 2, H - 0.75, 0.12, D - 2, 0.12, "fire_red")
    for y in range(5, int(D), 5):
        s.box_lo(W / 2, y, H - 0.7, W - 1.5, 0.05, 0.05, "fire_red")
        for x in range(4, int(W), 4):
            s.box_lo(x, y, H - 0.8, 0.03, 0.03, 0.1, "steel")
    s.build("SPRINKLERS", "roof", code="SPRINKLERS", kind="equipment", label="Спринклерне пожежогасіння",
            desc="Розподільні трубопроводи під покрівлею, зрошувачі з кроком 4 × 5 м.")

    # надворі: котельня на відходах, силос стружки, брикетувальний прес, пожежні резервуари
    o = Mesh()
    sx, sy = 56.5, D + 6.0
    for dx in (-1.4, 1.4):
        for dy in (-1.4, 1.4):
            o.box_lo(sx + dx, sy + dy, 0, 0.18, 0.18, 3.0, "steel_dark")
    o.cyl((sx, sy, 6.5), 2.0, 7.0, "galv", segs=28)
    o.cyl((sx, sy, 2.4), 2.0, 1.2, "galv", r2=0.3, segs=28, rot=(180, 0, 0))
    o.cone_dir((sx, sy, 11.0 + 0.6), (0, 0, 1), 2.05, 0.6, "galv", segs=28)
    o.tube([(48.8 + 1.0, D + 5.0, 6.8), (sx - 1.5, sy, 10.6)], 0.25, "galv", segs=14)
    bx, by = 65.5, D + 6.0
    o.box_lo(bx, by, 0, 8.0, 6.0, 4.5, "wall")
    o.box_lo(bx, by, 4.5, 8.2, 6.2, 0.2, "wall_band")
    o.box_lo(bx - 2.0, by - 3.01, 0, 2.4, 0.05, 3.0, "steel_dark")
    for k in range(4):
        o.box_lo(bx + 1.0 + k * 0.8, by - 3.01, 1.8, 0.5, 0.04, 1.2, "glass")
    o.cyl((bx + 3.0, by + 2.0, 7.7), 0.45, 15.4, "steel", segs=20)
    o.cyl((bx + 3.0, by + 2.0, 15.5), 0.5, 0.2, "steel_dark", segs=20)
    o.tube([(sx + 0.3, sy, 1.9), (sx + 1.5, sy, 1.2), (bx - 4.0, by, 1.2)], 0.2, "steel", segs=12)
    px, py = 52.0, D + 9.5
    o.box_lo(px, py, 0, 2.4, 1.1, 1.3, "machine_accent", bev=0.05)
    o.box((px - 0.6, py, 1.75), (1.0, 1.0, 0.9), "galv", rot=(0, 0, 0))
    o.box((px + 1.6, py, 0.75), (1.0, 0.3, 0.06), "steel", rot=(0, 20, 0))
    for k in range(3):
        pallet(o, px + 3.0 + k * 1.4, py, sx=1.2, sy=1.0)
        o.box_lo(px + 3.0 + k * 1.4, py, 0.146, 0.95, 0.9, 0.9, "carton_bag", bev=0.08)
    for tx in (8.0, 17.0):
        o.cyl((tx, D + 7.0, 4.0), 3.5, 8.0, "galv", segs=32)
        o.cyl((tx, D + 7.0, 8.1), 3.55, 0.2, "steel", segs=32)
        for k in range(10):
            o.box_lo(tx + 3.55, D + 7.0, k * 0.8, 0.05, 0.5, 0.04, "steel_dark")
    o.box_lo(25.0, D + 5.5, 0, 4.0, 3.0, 3.0, "wall")
    o.box_lo(25.0, D + 5.5, 3.0, 4.2, 3.2, 0.15, "fire_red")
    o.tube([(17.0 + 3.5, D + 7.0, 1.0), (23.0, D + 5.5, 1.0)], 0.12, "fire_red", segs=12)
    o.tube([(25.0, D + 4.0, 1.0), (25.0, D + 0.3, 1.0)], 0.12, "fire_red", segs=12)
    o.build("OUTSIDE", "utilities", code="BOILER", kind="equipment", label="Котельня, силос, брикетування",
            desc="Котельня на деревних відходах із силосом стружки від аспірації та брикетувальним "
                 "пресом; два пожежні резервуари по 300 м³ і насосна пожежогасіння.")


MACHINE_BUILDERS = {"saw": machine_saw, "edge": machine_edge, "cnc": machine_cnc,
                    "asm": machine_asm, "pack": machine_pack, "nest": machine_nest,
                    "saw_book": machine_saw_book, "edge_robot": machine_edge_robot,
                    "slide": machine_slide, "vsaw": machine_vsaw, "dowel": machine_dowel,
                    "bore": machine_bore, "hinge": machine_hinge, "sortbot": machine_sortbot,
                    "asmline": machine_asmline, "box": machine_box, "packline": machine_packline,
                    "sand": machine_sand, "glue": machine_glue, "press": machine_press,
                    "spray": machine_spray, "autospray": machine_autospray, "dry": machine_dry,
                    "uv": machine_uv}
TOWER_POS = {"saw": (-0.4, 2.55, 2.02), "edge": (3.85, -0.35, 1.55), "cnc": (-2.85, 1.2, 2.05),
             "asm": (1.5, -0.1, 2.46), "pack": (1.5, 1.1, 2.5), "nest": (-1.8, 1.95, 2.02),
             "saw_book": (-0.4, 2.55, 2.02), "edge_robot": (3.85, -0.35, 1.55),
             "slide": (0.55, 0.9, 1.9), "vsaw": (2.6, 0.5, 2.45), "dowel": (-0.55, 0.75, 1.7),
             "bore": (2.3, 0.5, 1.7), "hinge": (-1.4, 0.0, 0.9), "sortbot": (4.0, -2.75, 1.9),
             "asmline": (0.9, 1.0, 3.05), "box": (-1.1, 0.4, 1.5), "packline": (3.4, 0.85, 2.5),
             "sand": (0.6, -1.2, 2.55), "glue": (1.4, -1.0, 2.72), "press": (1.95, 1.0, 2.3),
             "spray": (2.3, -1.6, 3.15), "autospray": (-0.5, -1.0, 2.8), "dry": (2.55, -2.2, 3.12),
             "uv": (-1.3, 0.7, 1.7)}
# Де стоїть оператор: x, y, поворот (локально); None — автоматична дільниця без оператора
OPERATOR = {"saw": (0.9, -3.65, 90), "edge": (-5.0, -0.95, 90), "cnc": (2.4, -2.55, 90),
            "asm": (0.0, -1.0, 90), "pack": (-0.9, -0.95, 90), "nest": (2.3, -2.9, 90),
            "saw_book": (0.9, -3.65, 90), "edge_robot": (-5.0, -0.95, 90), "slide": (0.9, -1.0, 90),
            "vsaw": (0.6, -1.1, 90), "dowel": (0.0, -0.95, 90), "bore": (-3.4, -1.05, 90),
            "hinge": (0.0, -0.85, 90), "sortbot": None, "asmline": (-3.6, -2.0, 90),
            "box": (0.4, -1.65, 90), "packline": (-3.8, -1.15, 90), "sand": (-2.0, -1.6, 90),
            "glue": (0.0, -0.7, 90), "press": (0.8, -2.15, 90), "spray": (0.6, -0.6, 90),
            "autospray": (-5.0, -1.1, 90), "dry": None, "uv": (4.4, -1.1, 90)}


def build_machines():
    for code, typ, name, x, y, desc in MACHINES:
        root = empty(code, "line", loc=(x, y, 0), code=code, kind="machine", label=name,
                     desc=desc, status=STATUS[code])
        tx, ty, tz = TOWER_POS[typ]

        def body(m, typ=typ, tx=tx, ty=ty, tz=tz):
            MACHINE_BUILDERS[typ](m)
            signal_tower(m, tx, ty, tz)
        instance(code + "_body", "line", shared("machine_" + typ, body), parent=root)
        st = STATUS[code]

        def lamp(m, st=st, tx=tx, ty=ty, tz=tz):
            lv = {"work": 0, "idle": 1, "stop": 2}[st]
            m.cyl((tx, ty, tz + 0.34 + lv * 0.075), 0.048, 0.072,
                  {"work": "status_green", "idle": "status_amber", "stop": "status_red"}[st], segs=16)
        instance(code + "_lamp", "line", shared(f"lamp_{typ}_{st}", lamp), parent=root,
                 role="status")
        fx, fy = FOOTPRINT[typ]
        obst(x - fx / 2, y - fy / 2, x + fx / 2, y + fy / 2)


def build_maintenance():
    m = Mesh()
    for x in (66.0, 69.0, 72.0):
        m.box_lo(x, 58.6, 0.86, 2.0, 0.8, 0.05, "table_top", bev=0.01)
        legs_frame(m, x, 58.6, 2.0, 0.8, 0.86, mat="steel")
        m.box_lo(x - 0.6, 58.75, 0.91, 0.3, 0.2, 0.15, "machine_dark", bev=0.02)
    for x, mat in ((75.5, "status_red"), (76.8, "machine_dark"), (78.1, "machine_dark")):
        m.box_lo(x, 58.8, 0, 1.0, 0.6, 2.0, mat, bev=0.02)
        m.box_lo(x, 58.49, 0.2, 0.01, 0.9, 1.6, "steel_dark")
    m.cyl((69.0, 58.6, 0.93), 0.3, 0.01, "steel", segs=32)
    m.box_lo(70.0, 55.0, 0, 0.8, 0.6, 0.9, "machine_mid", bev=0.02)  # заточувальний верстат
    m.cyl((70.0, 55.0, 1.05), 0.15, 0.05, "steel_dark", axis="X", segs=20)
    m.box_lo(74.0, 54.0, 0, 1.6, 1.2, 1.3, "machine_mid", bev=0.03)  # балансувальний стенд
    m.cyl((74.0, 54.0, 1.45), 0.2, 0.25, "steel", segs=16)
    for k in range(4):  # стелаж запчастин
        m.box_lo(79.5, 47.5 + k * 2.2, 0, 0.6, 2.0, 2.2, "shelf", bev=0.01)
    m.build("MAINT", "line", code="MAINT-1", kind="building", label="Ремонтна дільниця",
            desc="Верстаки, шафи з інструментом, заточування пил, балансування фрез, запчастини.")


# ---------------------------------------------------------------- аспірація
def build_dust():
    m = Mesh()
    branch_xs = []
    for code, typ, _, mx, my, _ in MACHINES:
        for (lx, ly, lz) in DUCT_POINTS.get(typ, []):
            px, py = mx + lx, my + ly
            if py > 45:  # північна смуга — гілка вздовж X до вертикальної ділянки магістралі
                pts = [(px, py, lz), (px, py, DUCT_Z - 0.7), (DUCT_NORTH_X, py, DUCT_Z - 0.7),
                       (DUCT_NORTH_X, py, DUCT_Z)]
            else:
                branch_xs.append(px)
                pts = [(px, py, lz), (px, py, DUCT_Z - 0.7), (px, DUCT_MAIN_Y, DUCT_Z - 0.7),
                       (px, DUCT_MAIN_Y, DUCT_Z)]
            pts = rounded_path(pts, radius=0.35)
            m.tube(pts, 0.11, "galv", segs=14)
            m.cyl((px, py, lz + 0.1), 0.15, 0.2, "galv", segs=16)
            m.cyl((px, py, DUCT_Z - 1.9), 0.14, 0.12, "steel_dark", segs=16)
    # магістраль під покрівлею, далі крізь північну стіну до фільтра
    xe, xw = max(branch_xs) + 0.5, DUCT_NORTH_X
    fy = D + 5.0
    main = rounded_path([(xe, DUCT_MAIN_Y, DUCT_Z), (xw, DUCT_MAIN_Y, DUCT_Z),
                         (xw, fy - 1.5, DUCT_Z), (xw, fy - 1.5, 7.0)], radius=1.2, n=8)
    m.tube(main, 0.38, "galv", segs=22, caps=True)
    for x in range(int(xw) + 2, int(xe), 3):
        m.box_lo(x, DUCT_MAIN_Y, DUCT_Z + 0.38, 0.03, 0.03, H - DUCT_Z - 0.95, "steel_dark")
        m.cyl((x, DUCT_MAIN_Y, DUCT_Z), 0.4, 0.05, "steel_dark", axis="X", segs=22)
    # рукавний фільтр, циклон і вентилятор надворі
    fx = xw
    for dx in (-1.4, 1.4):
        for dy in (-1.4, 1.4):
            m.box_lo(fx + dx, fy + dy, 0, 0.16, 0.16, 2.6, "steel_dark")
    m.box_lo(fx, fy, 2.6, 3.2, 3.2, 4.6, "galv", bev=0.05)
    for k in range(7):
        m.box_lo(fx, fy - 1.61, 3.0 + k * 0.6, 3.2, 0.02, 0.05, "steel")
    m.cyl((fx, fy, 2.0), 1.55, 1.2, "galv", r2=0.25, segs=24, rot=(180, 0, 0))
    m.box_lo(fx, fy, 0, 1.1, 1.1, 1.0, "machine_accent", bev=0.03)
    m.box_lo(fx + 3.0, fy, 0, 1.6, 1.3, 1.4, "machine_accent", bev=0.04)
    m.cyl((fx + 3.0, fy, 1.9), 0.45, 1.0, "galv", segs=20)
    m.cyl((fx + 3.0, fy, 5.0), 0.35, 5.2, "galv", segs=20)
    m.box_lo(fx, fy, 7.2, 3.5, 3.5, 0.08, "steel_dark")
    for k in range(9):  # сходи обслуговування
        m.box_lo(fx - 2.0, fy - 1.2 + k * 0.3, k * 0.3, 0.8, 0.3, 0.3, "steel")
    for code, typ, _, mx, my, _ in MACHINES:  # витяжка фарбувальних дільниць крізь покрівлю
        for (lx, ly, lz) in EXHAUST_POINTS.get(typ, []):
            px, py = mx + lx, my + ly
            m.tube([(px, py, lz), (px, py, H + 1.6)], 0.22, "galv", segs=16)
            m.cone_dir((px, py, H + 2.0), (0, 0, 1), 0.4, 0.3, "galv", segs=16)
            m.box_lo(px, py, H - 1.6, 0.6, 0.6, 0.5, "machine_mid", bev=0.03)
    m.build("DUST", "dust", code="DUST-1", kind="equipment", label="Аспірація",
            desc="Відсмоктування стружки від розкрою, нестингу, крайкооблицювання та ЧПК: "
                 "магістраль під покрівлею, рукавний фільтр і вентилятор надворі.")


# ---------------------------------------------------------------- готова продукція
FG_ROWS = [100.2, 104.0, 105.1, 108.9, 110.0, 113.8, 114.9, 118.7]
FG_PRODUCTS = ["Шафа нижня 600", "Шафа верхня 800", "Пенал 400", "Тумба 3 шухляди",
               "Стіл офісний 1400", "Шафа для документів 800", "Комод 4 шухляди"]


def build_fg():
    bay_w, nbay, y0 = 2.7, 9, 32.0
    levels = [0.0, 1.9, 3.8, 5.7]
    depth = 1.1

    def frame(m):
        for b in range(nbay + 1):
            for dx in (-depth / 2, depth / 2):
                m.box_lo(dx, b * bay_w, 0, 0.09, 0.07, 7.4, "rack_upright")
                m.box_lo(dx, b * bay_w, 0, 0.18, 0.14, 0.01, "steel_dark")
            for k, z in enumerate((0.6, 1.5, 2.4, 3.3, 4.2, 5.1, 6.0, 6.9)):
                m.box((0, b * bay_w, z), (depth, 0.03, 0.03), "rack_upright",
                      rot=(0, 30 if k % 2 else -30, 0))
        m.box_lo(-depth / 2 - 0.12, 0, 0, 0.12, 0.2, 0.4, "marking", bev=0.01)
        m.box_lo(-depth / 2 - 0.12, nbay * bay_w, 0, 0.12, 0.2, 0.4, "marking", bev=0.01)
        for z in levels[1:]:
            for dx in (-depth / 2, depth / 2):
                m.box_lo(dx, nbay * bay_w / 2, z - 0.12, 0.06, nbay * bay_w, 0.12, "rack_beam")

    def load(n, l0, l1):
        def fn(m):
            for p, layers in zip(range(n), (l0, l1)):
                py = -0.65 + p * 1.3
                pallet(m, 0, py, 0.02, sx=1.0, sy=1.2)
                cartons(m, 0, py, 0.166, 0.95, 1.15, layers)
            m.box_lo(-depth / 2 - 0.02, 0, 0.05, 0.01, 0.3, 0.08, "phenolic" if n else "status_amber")
        return shared(f"fg_{n}_{l0}_{l1}", fn)

    me_frame = shared("fg_rack", frame)
    for ri, x in enumerate(FG_ROWS, 1):
        row = f"R{ri}"
        instance(f"FG-RACK-{row}", "fg", me_frame, loc=(x, y0, 0), code=f"FG-RACK-{row}",
                 kind="rack", label=f"Палетний стелаж {row}",
                 desc=f"{nbay} прольотів × {len(levels)} яруси.")
        obst(x - depth / 2 - 0.2, y0, x + depth / 2, y0 + nbay * bay_w)
        for b in range(1, nbay + 1):
            for li, z in enumerate(levels, 1):
                code = f"FG-{row}-B{b}-L{li}"
                seed = (ri * 11 + b * 3 + li * 5) % 7
                n = 0 if seed in (0, 4) else (1 if seed == 3 else 2)
                l0, l1 = 2 + seed % 2, 2 + (seed + 1) % 2
                prod = FG_PRODUCTS[(b + li + ri) % len(FG_PRODUCTS)]
                instance(code, "fg", load(n, l0 if n else 0, l1 if n > 1 else 0),
                         loc=(x, y0 + (b - 0.5) * bay_w, z + (0.0 if li == 1 else 0.0)),
                         code=code, kind="stock", label=f"Комірка {code}",
                         desc=f"{prod}: {n} палет." if n else "Вільно.")


def build_post_and_shipping():
    m = Mesh()
    for i, x in enumerate((112.0, 113.7, 115.4, 117.1)):
        pallet(m, x, 27.6)
        cartons(m, x, 27.6, 0.146, 1.15, 0.75, 2 + i % 2)
    m.build("POST-STAGE", "fg", code="POST-STAGE", kind="stock", label="Готово до розміщення",
            desc="Запаковані палети з лінії чекають на розміщення в стелажі.")

    s = Mesh()
    for j, (_, y, _) in enumerate(d for d in DOORS if d[0] == "E"):
        for k in range(6):
            x = 104.0 + k * 1.7
            if (j * 3 + k) % 5 == 4:
                continue
            pallet(s, x, y)
            cartons(s, x, y, 0.146, 1.15, 0.75, 2 + (j + k) % 2)
        s.box((108.3, y - 0.65, 0.022), (10.5, 0.08, 0.02), "marking")
        s.box((108.3, y + 0.65, 0.022), (10.5, 0.08, 0.02), "marking")
    s.build("OUT-STAGE", "shipping", code="OUT-STAGE", kind="stock",
            label="Відвантаження на сьогодні",
            desc="Палети, зібрані в коридори під машини до воріт 1–4.")
    obst(99.0, 0.0, 120.0, 30.4)


# ---------------------------------------------------------------- люди
def build_people():
    def body(vest, arms):
        return shared(f"person_{vest}_{arms}", lambda m: person(m, 0, 0, 0, vest, arms))

    people = []
    for code, typ, name, x, y, _ in MACHINES:
        st = STATUS[code]
        if st == "idle":
            continue
        if OPERATOR.get(typ) is None:
            continue
        ox, oy, rz = OPERATOR[typ]
        vest = "hivis_or" if st == "stop" else "hivis"
        if typ in ("spray", "glue", "autospray", "uv"):
            vest = "phenolic"  # маляр у білому комбінезоні
        label = "Налагоджувальник" if st == "stop" else "Оператор"
        people.append((f"OP-{code}", f"{label} · {name}", x + ox, y + oy, rz, vest,
                       "down" if st == "stop" else "front",
                       "Діагностика зупинки верстата." if st == "stop" else f"Працює на дільниці «{name}»."))
    people += [
        ("OP-W1", "Комірник", 25.0, 37.6, -90, "hivis", "front", "Комплектування фурнітури."),
        ("OP-W2", "Комірник", 35.0, 46.2, 90, "hivis", "front", "Комплектування фурнітури."),
        ("OP-W3", "Приймальник", 9.0, 12.0, 180, "hivis_or", "down", "Звірка поставки з накладною."),
        ("OP-W4", "Оператор порталу", 45.5, 1.4, 120, "hivis", "front", "Керує портальним складом плит."),
        ("OP-W5", "Комірник ГП", 107.0, 28.5, 90, "hivis_or", "down", "Розміщення готової продукції."),
    ]
    for code, label, x, y, rz, vest, arms, desc in people:
        instance(code, "people", body(vest, arms), loc=(x, y, 0), rz=rz, code=code,
                 kind="person", label=label, desc=desc)


def build_transport():
    def fl_pallet(m):
        forklift(m)
        pallet(m, 1.45, 0, 0.14)
        cartons(m, 1.45, 0, 0.286, 1.1, 0.75, 1)

    def fl_sheets(m):
        forklift(m)
        sheet_stack(m, 1.6, 0, 0.14, 22, 1)

    for code, label, x, y, rz, fn, desc in (
            ("FL-1", "Навантажувач 1", 102.1, 44.0, -90, fl_pallet,
             "Електронавантажувач 1,6 т, висота підйому 6 м."),
            ("FL-2", "Навантажувач 2", 8.5, 16.5, 0, fl_sheets,
             "Розвантажує фуру зі стосами плит."),
            ("FL-3", "Навантажувач 3", 110.0, 6.8, 180, fl_pallet,
             "Вантажить палети в машину біля воріт 1."),
            ("FL-4", "Навантажувач 4", 111.9, 50.0, 90, fl_pallet,
             "Знімає палету з третього ярусу.")):
        key = "fl_sheets" if fn is fl_sheets else "fl_pallet"
        instance(code, "transport", shared(key, fn), loc=(x, y, 0), rz=rz, code=code,
                 kind="vehicle", label=label, desc=desc)

    def truck(m, length=13.6):
        m.box_lo(0, 0, 1.1, length, 2.5, 2.9, "trailer", bev=0.04)
        for k in range(1, 12):
            m.box_lo(-length / 2 + k * length / 12, -1.255, 1.15, 0.04, 0.01, 2.8, "machine_mid")
        m.box_lo(-length / 2 - 1.15, 0, 0.6, 2.2, 2.4, 2.6, "truck_cab", bev=0.12)
        m.box_lo(-length / 2 - 2.2, 0, 1.9, 0.1, 2.1, 1.0, "glass")
        m.box_lo(-length / 2 - 2.25, 0, 0.6, 0.1, 2.2, 0.4, "machine_dark", bev=0.03)
        m.box_lo(-1.0, 0, 0.6, length, 1.0, 0.5, "steel_dark")
        for x in (-length / 2 - 1.5, length / 2 - 3.6, length / 2 - 2.3, length / 2 - 1.0):
            for dy in (-1.0, 1.0):
                m.cyl((x, dy, 0.5), 0.5, 0.35, "rubber", axis="Y", segs=20)
                m.cyl((x, dy * 1.01, 0.5), 0.28, 0.36, "steel", axis="Y", segs=14)

    me = shared("truck", truck)
    for code, label, x, y, rz in (("TRUCK-IN-1", "Фура на розвантаженні", -7.3, 11.0, 0),
                                  ("TRUCK-IN-2", "Фура на розвантаженні", -7.3, 17.0, 0),
                                  ("TRUCK-OUT-1", "Машина під навантаженням", W + 7.3, 4.0, 180),
                                  ("TRUCK-OUT-2", "Машина під навантаженням", W + 7.3, 15.0, 180)):
        instance(code, "transport", me, loc=(x, y, 0), rz=rz, code=code, kind="vehicle",
                 label=label, desc="Напівпричіп 13,6 м біля воріт.")


# ---------------------------------------------------------------- маршрут
def arc_points(p0, p1, n=28):
    a, b = Vector(p0), Vector(p1)
    lift = 1.6 + 0.1 * (b - a).length
    c = (a + b) / 2 + Vector((0, 0, lift))
    return [tuple((1 - t) ** 2 * a + 2 * (1 - t) * t * c + t ** 2 * b)
            for t in (i / n for i in range(n + 1))]


def build_flow():
    m = Mesh()
    for (_, _, p0), (_, _, p1) in zip(FLOW, FLOW[1:]):
        pts = arc_points(p0, p1)
        m.tube(pts[:-2], 0.09, "flow")
        tip = Vector(pts[-1])
        m.cone_dir(tip, tip - Vector(pts[-3]), 0.28, 0.7, "flow")
    for _, _, p in FLOW:
        m.cyl(p, 0.22, 0.14, "flow", segs=16)
    m.build("FLOW", "flow", code="FLOW", kind="flow", label="Маршрут виробу",
            desc="Приймання → склад плит → розкрій → крайка → присадка → збирання → "
                 "пакування → склад ГП → відвантаження.",
            route=json.dumps([{"code": c, "label": n, "p": p} for c, n, p in FLOW],
                             ensure_ascii=False))


# --------------------------------------------------------------------------
def embed_viewer(out_dir, glb):
    """Однофайловий переглядач: модель вбудована в base64, відкривається без веб-сервера."""
    viewer = os.path.join(os.path.dirname(os.path.abspath(__file__)), "viewer", "index.html")
    with open(glb, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    with open(viewer, encoding="utf-8") as f:
        html = f.read()
    html = html.replace("<!-- MODEL_DATA -->",
                        f'<script type="application/octet-stream" id="model-data">{data}</script>')
    standalone = ('<!doctype html>\n<html lang="uk"><head><meta charset="utf-8">'
                  '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
                  '</head><body>\n' + html + "\n</body></html>\n")
    with open(os.path.join(out_dir, "factory_viewer.html"), "w", encoding="utf-8") as f:
        f.write(standalone)


def main(out_dir):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = "METRIC"
    make_materials()
    make_layers()
    LAYER_OBJ["building"].parent["dims"] = f"{W:.0f} × {D:.0f} м · h {H:.0f} м"
    build_building()
    build_zones()
    build_receiving()
    build_sheets()
    build_hardware()
    build_edge()
    build_buffer()
    build_machines()
    build_maintenance()
    build_dust()
    build_fg()
    build_post_and_shipping()
    build_north_rooms()
    build_utilities()
    build_transport()
    build_people()
    build_flow()
    build_columns()

    # камера і світло — для тих, хто відкриє .blend
    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    bpy.context.scene.collection.objects.link(cam)
    cam.location = (20, -62, 74)
    cam.rotation_euler = (math.radians(52), 0, math.radians(-25))
    bpy.context.scene.camera = cam
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 3
    sun.rotation_euler = (math.radians(40), math.radians(15), math.radians(30))
    bpy.context.scene.collection.objects.link(sun)

    os.makedirs(out_dir, exist_ok=True)
    glb = os.path.join(out_dir, "factory.glb")
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", export_extras=True,
                              export_yup=True, export_apply=True, export_cameras=False,
                              export_lights=False)
    bpy.ops.wm.usd_export(filepath=os.path.join(out_dir, "factory.usdz"),
                          export_materials=True, generate_preview_surface=True,
                          convert_orientation=True, export_global_forward_selection="NEGATIVE_Z",
                          export_global_up_selection="Y", export_lights=False,
                          export_cameras=False)
    bpy.context.preferences.filepaths.save_version = 0  # без factory.blend1
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(os.path.join(out_dir, "factory.blend")))
    shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), "viewer", "index.html"),
                os.path.join(out_dir, "index.html"))
    embed_viewer(out_dir, glb)
    objs = [o for o in bpy.data.objects if o.type == "MESH"]
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs)
    print(f"objects={len(objs)} unique_meshes={len(bpy.data.meshes)} rendered_tris={tris}")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    if argv and argv[0] == "--embed":  # python build_scene.py --embed dist/factory_web.glb dist
        embed_viewer(argv[2], argv[1])
    else:
        main(argv[0] if argv else "dist")
