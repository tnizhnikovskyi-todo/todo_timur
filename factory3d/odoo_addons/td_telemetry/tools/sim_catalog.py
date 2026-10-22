"""R-24 (CT-11): розбір адрес каталогу емулятора td_iot_sim в `address` сигналу (SPEC Додаток A.1).

Чисті функції без ORM: `parse_sim_address`, `source_key` (Додаток C.3), `module_for_code` / `kind_for_mode`
(R-15), `equipment_code`, `parse_nominal`, `parse_enum_map`.
"""

import re

# --- Modbus: вендорська нотація (R-24 (б), iot_sim §8.4.1) ---------------------------------------------
HUAWEI_UNITS = range(61, 70)  # SUN2000 / LUNA2000: номер у документі вже PDU
ADAM_UNITS = range(80, 97)
PM5560_UNITS = range(1, 60)
ELEKTRONIKON_UNIT = 70
ATYS_UNIT = 71
TEDOM_UNIT = 72

TYPES = ("bool", "u16", "i16", "u32", "i32", "f32", "u64", "i64", "f64")
OBJECTS = {
    "AI": "analog-input",
    "AO": "analog-output",
    "AV": "analog-value",
    "BI": "binary-input",
    "BO": "binary-output",
    "BV": "binary-value",
    "MSI": "multi-state-input",
    "MSV": "multi-state-value",
    "LSZ": "life-safety-zone",
    "LSP": "life-safety-point",
    "PIV": "positive-integer-value",
}
OBJ_RE = "|".join(OBJECTS)

RE_PDU = re.compile(r"^\s*Modbus u(\d+)(?: \([^)]*\))? fc([1-4]) pdu(\d+)(?:\+(\d+))?(.*)$", re.S)
RE_HR = re.compile(r"^\s*Modbus u(\d+)(?: \([^)]*\))? HR (\d+)(?:[–-](\d+))?", re.S)
RE_DI = re.compile(r"^\s*Modbus u(\d+)(?: \([^)]*\))?\s+(?=D[IO]\d+ coil)", re.S)
RE_DI_ITEM = re.compile(r"DI(\d+) coil 0*(\d+)(?:\s*\(([^)]*)\))?")
RE_DO_ITEM = re.compile(r"DO(\d+) coil 0*(\d+)")
RE_MQTT = re.compile(r"^\s*MQTT (\S+) → \$\.(\S+)")
RE_BAC = re.compile(r"^\s*BACnet dev (\d+)\s+(.*)$", re.S)
RE_BAC_OBJ = re.compile(r"\s*(%s):(\d+)(?: \(([^)]*)\))?\s*,?" % OBJ_RE)
RE_OPCUA = re.compile(r"^\s*(?:OPC UA\|)?(ns=\d+;[sigb]=\S+)")
RE_GET = re.compile(r"^\s*GET (/\S+) → \$\.(\S+)")
RE_POST = re.compile(r"^\s*HTTP POST <collector>/f3d/(\w+) → (.+)$", re.S)
RE_SICS = re.compile(r"^\s*SICS\b.*?«(\w+)»", re.S)
RE_RANGE = re.compile(r"(?:=|→)\s*([−+\-]?\d[\d\s  ]*?)\s*…\s*([−+\-]?\d[\d\s  ]*)")
RE_NUM = re.compile(r"[−+\-]?\d+(?:[.,]\d+)?")
SPACES = "   \t"


def _num(text):
    text = (text or "").replace("−", "-")
    for ch in SPACES:
        text = text.replace(ch, "")
    text = text.replace(",", ".")
    value = float(text)
    return int(value) if value == int(value) else value


def parse_nominal(text):
    """Перше число з колонки «Номінал» (`12.18 (шум 0.08, …)` → 12.18); None, якщо числа немає."""
    m = RE_NUM.search((text or "").replace("−", "-"))
    return float(m.group(0).replace(",", ".")) if m else None


def parse_enum_map(unit):
    """`0 stop/1 load/2 unload/3 fault` → {"0": "stop", …}; інакше None."""
    parts = [p.strip() for p in (unit or "").split("/")]
    if len(parts) < 2:
        return None
    result = {}
    for part in parts:
        m = re.match(r"^(\d+)\s+(\S.*)$", part)
        if not m:
            return None
        result[m.group(1)] = m.group(2)
    return result


def _pdu(unit, num):
    """R-24 (б): (fc, addr) за номером із документа вендора; None — unit поза переліком."""
    if unit in HUAWEI_UNITS or unit in (ATYS_UNIT, TEDOM_UNIT):
        return 3, num
    if unit in ADAM_UNITS:
        if num >= 40001:
            return 3, num - 40001
        if 30001 <= num < 40000:
            return 4, num - 30001
        if 1 <= num < 10000:
            return 1, num - 1
        return None
    if unit in PM5560_UNITS or unit == ELEKTRONIKON_UNIT:
        return 3, num - 1
    return None


def _scale_offset(scale, text):
    """Колонка «Масштаб» → {"scale"?, "offset"?, "range"?}."""
    result = {}
    scale = (scale or "").strip()
    m = re.match(r"^×\s*([\d.,]+)", scale)
    if m:
        value = float(m.group(1).replace(",", "."))
        if value != 1:
            result["scale"] = value
        return result
    if "R-20" in scale or "→" in scale:
        rng = RE_RANGE.search(scale) or RE_RANGE.search(text or "")
        if rng:
            lo, hi = _num(rng.group(1)), _num(rng.group(2))
            result.update(scale=float("%.8g" % ((hi - lo) / 65535.0)), offset=lo, range=[lo, hi])
    return result


def _typed(vals, dtype):
    if "type" not in vals:
        t = (dtype or "").strip().lower()
        if t in TYPES:
            vals["type"] = t
    return vals


def _parse_modbus(text, dtype, scale, unit):
    m = RE_PDU.match(text)
    if m:
        u, fc, addr, count, rest = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4), m.group(5)
        vals = {"unit": u, "fc": fc, "addr": addr}
        if count:
            vals["count"] = int(count)
        tm = re.match(r"\s*(%s)\b" % "|".join(TYPES), rest)
        if tm:
            vals["type"] = tm.group(1)
            rest_after = rest[tm.end() :]
            am = re.match(r"\s+(max|min|sum|avg|first)\b", rest_after)
            if am:
                vals["agg"] = am.group(1)
                rest_after = rest_after[am.end() :]
            wm = re.match(r"\s+(little|big)\b", rest_after)
            if wm:
                vals["wordorder"] = wm.group(1)
        di = list(RE_DI_ITEM.finditer(rest))
        if fc in (1, 2) and len(di) >= 2:
            return {"unit": u, "fc": fc, "states": _states(di)}
        wr = re.search(r"запис fc([56]|16) pdu(\d+)", rest)
        if wr:
            vals["write"] = {"fc": int(wr.group(1)), "addr": int(wr.group(2))}
        if "·" in rest:
            vals["doc"] = rest.split("·", 1)[1].strip()[:256]
        _typed(vals, dtype)
        vals.update(_scale_offset(scale, text))
        enum = parse_enum_map(unit)
        if enum and fc in (3, 4):
            vals["map"] = enum
        return vals
    m = RE_HR.match(text)
    if m:
        u, first = int(m.group(1)), int(m.group(2))
        located = _pdu(u, first)
        if not located:
            return None
        fc, addr = located
        vals = {"unit": u, "fc": fc, "addr": addr}
        if m.group(3):
            vals["count"] = int(m.group(3)) - first + 1
        _typed(vals, dtype)
        if "ADAM" in text and "лічильник" in text:
            vals["wordorder"] = "little"
        vals.update(_scale_offset(scale, text))
        enum = parse_enum_map(unit)
        if enum:
            vals["map"] = enum
        vals["doc"] = text[text.index("HR ") :].strip()[:256]
        return vals
    m = RE_DI.match(text)
    if m:
        u = int(m.group(1))
        di = list(RE_DI_ITEM.finditer(text))
        if len(di) >= 2:
            return {"unit": u, "fc": 2, "states": _states(di)}
        if len(di) == 1:
            return {"unit": u, "fc": 2, "addr": int(di[0].group(2)) - 1, "type": "bool"}
        do = RE_DO_ITEM.search(text)
        if do:
            addr = int(do.group(2)) - 1
            return {"unit": u, "fc": 1, "addr": addr, "type": "bool", "write": {"fc": 5, "addr": addr}}
    return None


def _states(items):
    """Складений стан із DI: аварійні → fault (eq 1), перший решта → running (1) / stopped (0)."""
    faults, normal = [], []
    for it in items:
        addr, label = int(it.group(2)) - 1, (it.group(3) or "").lower()
        (faults if re.search(r"авар|несправн|fault", label) else normal).append(addr)
    states = [{"addr": a, "eq": 1, "text": "fault"} for a in faults]
    if normal:
        states += [{"addr": normal[0], "eq": 1, "text": "running"}, {"addr": normal[0], "eq": 0, "text": "stopped"}]
    return states


def _parse_bacnet(text, unit):
    m = RE_BAC.match(text)
    if not m:
        return None
    device, rest = int(m.group(1)), m.group(2)
    objs, pos = [], 0
    while True:
        om = RE_BAC_OBJ.match(rest, pos)
        if not om:
            break
        objs.append((om.group(1), int(om.group(2)), om.group(3) or ""))
        pos = om.end()
    if not objs:
        return None
    if len(objs) == 1:
        kind, instance, _label = objs[0]
        vals = {"device": device, "object": OBJECTS[kind], "instance": instance, "property": "present-value"}
        enum = parse_enum_map(unit)
        if enum and kind in ("MSV", "MSI"):
            vals["map"] = enum
        return vals
    faults, normal = [], []
    for kind, instance, label in objs:
        mm = re.search(r"→\s*(\w+)", label)
        if mm:
            faults.append({"object": OBJECTS[kind], "instance": instance, "eq": 1, "text": mm.group(1)})
        else:
            normal.append((kind, instance))
    if len(normal) != 1:
        return None
    kind, instance = normal[0]
    obj = OBJECTS[kind]
    states = faults + [
        {"object": obj, "instance": instance, "eq": 1, "text": "running"},
        {"object": obj, "instance": instance, "eq": 0, "text": "stopped"},
    ]
    return {"device": device, "states": states}


def parse_sim_address(protocol, text, dtype=None, scale=None, unit=None):
    """R-24: адреса каталогу емулятора → `address` (dict) або None (`unparsed`).

    `protocol` — підказка (не обов'язкова); `dtype`, `scale`, `unit` — колонки «Тип», «Масштаб», «Одиниця»
    рядка каталогу (тип, множник/зсув R-20, enum-карта).
    """
    text = (text or "").strip()
    if not text or text.startswith(("Σ", "похідна", "обчислює", "розрахунок")):
        return None
    if (dtype or "") == "Method":
        return None
    m = RE_POST.match(text)
    if m:
        field = re.match(r"\s*([A-Za-z_]\w*)", m.group(2))
        return {"route": m.group(1), "path": "$." + field.group(1)} if field else None
    if text.startswith("SICS"):
        # рядок каталогу емулятора для `stable`: «SICS статус «S» (стабільно) / «D» (динамічно)» — першими в лапках
        # стоять літери статусу, а не команда, тож перевіряємо слово «стабіл»/«stable» до розбору «<команда>»
        if "stable" in text or "стабіл" in text:
            return {"cmd": "SI", "field": "stable"}
        m = RE_SICS.match(text)
        if not m or m.group(1) != "SI":
            return None
        return {"cmd": "SI", "field": "weight"}
    m = RE_GET.match(text)
    if m:
        return {"method": "GET", "path": m.group(1), "json_path": "$." + m.group(2)}
    m = RE_MQTT.match(text)
    if m:
        return {"topic": m.group(1), "path": "$." + m.group(2)}
    m = RE_OPCUA.match(text)
    if m:
        return {"nodeid": m.group(1)}
    if text.startswith("BACnet"):
        return _parse_bacnet(text, unit)
    if text.startswith("Modbus"):
        return _parse_modbus(text, dtype, scale, unit)
    return None


def source_key(text):
    """Додаток C.3: ключ джерела за адресою (Modbus — `u<unit>`, MQTT — `mqtt`, BACnet — `dev<n>` …)."""
    text = (text or "").strip()
    for regex, fmt in (
        (r"^Modbus u(\d+)", "u%s"),
        (r"^MQTT\b", "mqtt"),
        (r"^BACnet dev (\d+)", "dev%s"),
        (r"^HTTP POST <collector>/f3d/(\w+)", "http:%s"),
        (r"^(?:OPC UA\||ns=\d+;)", "opcua"),
        (r"^GET /", "rest"),
        (r"^SICS\b", "sics"),
    ):
        m = re.match(regex, text)
        if m:
            return fmt % m.groups() if m.groups() else fmt
    return None


# --- R-15 -----------------------------------------------------------------------------------------------
def module_for_code(code):
    """R-15: `module` за префіксом коду сигналу (CT-09)."""
    parts = (code or "").split("/")
    head = parts[0]
    if head in ("energy", "infra"):
        if head == "infra" and len(parts) > 1 and parts[1] == "water":
            return "telemetry"
        if head == "infra" and len(parts) > 1 and parts[1] == "genset":
            return "genset"
        return "energy"
    return {
        "ventilation": "bms",
        "lighting": "bms",
        "fire": "fire_safety",
        "equipment": "telemetry",
        "workcenters": "machine_connect",
        "yard": "yard",
        "access": "access",
    }.get(head, "other")


def kind_for_mode(mode):
    """R-15: `kind` за `x_mode` рівня 0."""
    return "counter" if mode in ("hours", "energy", "counter") else "gauge"


def equipment_code(code):
    """Код обладнання з коду сигналу (Додаток C.2: сегмент коду, `infra/water/*` → WATER)."""
    parts = (code or "").split("/")
    if len(parts) < 3:
        return None
    if parts[0] == "infra" and parts[1] == "water":
        return "WATER"
    if parts[1] in ("consumers", "transformers", "units", "groups", "lpr") and len(parts) > 3:
        return parts[2]
    return parts[1]
