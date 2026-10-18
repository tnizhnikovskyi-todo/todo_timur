"""R-21: корисне навантаження команд (payload CR-01) і запасна текстова граматика.

Чисті функції без `env` і без імпортів Odoo (X-93): цей файл побайтово копіюється в пакет плагінів колектора
(`f3d_collector_mc/cmdtext.py`, AC-80). Усі помилки — `ValueError("<поле>: <проблема>")`.
"""

import re

MAX_TEXT = 64

CODE = re.compile(r"^[A-Z0-9][A-Z0-9\-]{0,31}$")
REF = re.compile(r"^[A-Za-z0-9/_\-\.]{1,32}$")
JOB = re.compile(r"^[A-Za-z0-9_\-\.]{1,32}$")
LOT = re.compile(r"^[A-Za-z0-9_\-\.]{1,40}$")
TOKEN = re.compile(r"^[0-9a-f]{16}$")
TEXT_INT = re.compile(r"^\d{1,4}$")
TEXT_ID = re.compile(r"^\d{1,9}$")
METHODS = ("Store", "StoreAndStart", "Start", "Stop", "Pause", "Resume", "Cancel", "Abort", "Clear")

# Типи значень: CODE, CODE?, REF, JOB, LOT?, INT, PRIO, ID, TOKEN. «?» — допускається null.
# (вид, операція) -> ключі в порядку таблиці R-21 (ключ операції — `method` для `job`, `op` для решти).
_JOB_FULL = (("job", "JOB"), ("qty", "INT"), ("ref", "REF"), ("priority", "PRIO"))
_JOB_SHORT = (("job", "JOB"),)
SCHEMA = {
    "job": {m: _JOB_FULL if m in ("Store", "StoreAndStart") else _JOB_SHORT for m in METHODS},
    "gantry": {
        "feed": (
            ("stack", "CODE?"),
            ("target", "CODE"),
            ("sheets", "INT"),
            ("product", "CODE"),
            ("priority", "PRIO"),
            ("ref", "REF"),
        ),
        "cancel": (("id", "JOB"),),
        "stack": (("stack", "CODE"), ("qty", "INT"), ("product", "CODE"), ("lot", "LOT?")),
    },
    "cutopt": {
        "upload": (("map", "ID"), ("token", "TOKEN")),
        "status": (("job", "JOB"),),
        "release": (("job", "JOB"), ("machine", "CODE"), ("priority", "PRIO")),
        "mpr": (("job", "JOB"), ("part", "JOB")),
    },
}


def _op_key(kind):
    return "method" if kind == "job" else "op"


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _check_value(key, typ, value):
    """Перевіряє значення поля `key` типу `typ`; `ValueError("<key>: …")`."""
    if typ.endswith("?"):
        if value is None:
            return
        typ = typ[:-1]
    if typ in ("INT", "PRIO", "ID"):
        lo, hi = {"INT": (1, 9999), "PRIO": (1, 9), "ID": (1, 999999999)}[typ]
        if not _is_int(value):
            raise ValueError("%s: очікується ціле число" % key)
        if not lo <= value <= hi:
            raise ValueError("%s: поза межами %d…%d" % (key, lo, hi))
        return
    rx = {"CODE": CODE, "REF": REF, "JOB": JOB, "LOT": LOT, "TOKEN": TOKEN}[typ]
    if not isinstance(value, str):
        raise ValueError("%s: очікується рядок" % key)
    if not rx.match(value):
        raise ValueError("%s: недопустиме значення %r" % (key, value))


def _schema(kind, op):
    if kind not in SCHEMA:
        raise ValueError("kind: невідомий вид команди %r" % (kind,))
    ops = SCHEMA[kind]
    if op not in ops:
        raise ValueError("%s: невідома операція %r" % (_op_key(kind), op))
    return ops[op]


def check_payload(kind, payload):
    """Перевіряє готовий об'єкт (перед будь-яким мережевим викликом); повертає його копію в порядку таблиці."""
    if kind not in SCHEMA:
        raise ValueError("kind: невідомий вид команди %r" % (kind,))
    if not isinstance(payload, dict):
        raise ValueError("payload: очікується об'єкт")
    okey = _op_key(kind)
    if okey not in payload:
        raise ValueError("%s: відсутнє" % okey)
    op = payload[okey]
    schema = _schema(kind, op)
    out = {okey: op}
    for key, typ in schema:
        if key not in payload:
            raise ValueError("%s: відсутнє" % key)
        _check_value(key, typ, payload[key])
        out[key] = payload[key]
    known = {okey} | {k for k, _t in schema}
    for key in payload:
        if key not in known:
            raise ValueError("%s: зайве" % key)
    return out


def build_payload(kind, op, **fields):
    """Об'єкт за таблицею R-21 (відсутній або зайвий ключ, недопустиме значення — `ValueError`)."""
    return check_payload(kind, {_op_key(kind): op, **fields})


def _to_text(kind, payload):
    parts = [str(payload[_op_key(kind)])]
    for key, _typ in SCHEMA[kind][payload[_op_key(kind)]]:
        v = payload[key]
        if v is None:
            parts.append("*" if key == "stack" else "-")
        else:
            parts.append(str(v))
    return ";".join(parts)


def build_cmd(kind, op, **fields):
    """Запасний текст (`;`, ≤ 64 символи)."""
    text = _to_text(kind, build_payload(kind, op, **fields))
    if len(text) > MAX_TEXT:
        raise ValueError("length: %d > %d" % (len(text), MAX_TEXT))
    return text


def parse_cmd(kind, text):
    """Розбір запасного тексту; повертає той самий об'єкт, що `build_payload`."""
    if kind not in SCHEMA:
        raise ValueError("kind: невідомий вид команди %r" % (kind,))
    if not isinstance(text, str):
        raise ValueError("text: очікується рядок")
    if len(text) > MAX_TEXT:
        raise ValueError("length: %d > %d" % (len(text), MAX_TEXT))
    items = text.split(";")
    op = items[0]
    schema = _schema(kind, op)
    if len(items) - 1 != len(schema):
        raise ValueError("fields: очікується %d" % (len(schema) + 1))
    fields = {}
    for (key, typ), raw in zip(schema, items[1:], strict=True):
        base = typ.rstrip("?")
        if typ.endswith("?") and raw == ("*" if key == "stack" else "-"):
            fields[key] = None
        elif base in ("INT", "PRIO"):
            if not TEXT_INT.match(raw):
                raise ValueError("%s: очікується ціле число" % key)
            fields[key] = int(raw)
        elif base == "ID":
            if not TEXT_ID.match(raw):
                raise ValueError("%s: очікується ціле число" % key)
            fields[key] = int(raw)
        else:
            fields[key] = raw
    return build_payload(kind, op, **fields)


def cmd_label(kind, payload):
    """Довідковий текст команди: запасна граматика, якщо ≤ 64 символи, інакше перші 63 символи + «…»."""
    text = _to_text(kind, check_payload(kind, payload))
    return text if len(text) <= MAX_TEXT else text[: MAX_TEXT - 1] + "…"


def result_text(kind, payload, data):
    """Запасний `result` з об'єкта результату `call()` (колонка «Запасний result» R-21)."""
    payload = check_payload(kind, payload)
    data = data or {}
    op = payload[_op_key(kind)]
    try:
        if kind == "job":
            return "ok ReturnStatus=%s" % data["ReturnStatus"]
        if kind == "gantry":
            if op == "feed":
                return str(data["id"])
            if op == "cancel":
                return str(data.get("state", "cancelled"))
            return "stack %s=%s" % (data["id"], data["qty"])
        if op == "upload":
            return "%s %s" % (data["job_id"], data["state"])
        if op == "status":
            if data.get("sheets") is not None and data.get("waste_pct") is not None:
                return "%s %g %g" % (data["state"], data["sheets"], data["waste_pct"])
            return str(data["state"])
        if op == "release":
            return "%s %s" % (data["state"], data.get("job_order_id") or data["job_id"])
        if data.get("size_kb") is None:
            return "no mpr"
        return "mpr %s %g КБ" % (data["part"], data["size_kb"])
    except KeyError as e:
        raise ValueError("result: відсутнє %s" % e) from e
