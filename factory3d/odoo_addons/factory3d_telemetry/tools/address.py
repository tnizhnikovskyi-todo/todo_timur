"""Валідація `address` сигналу й `params` джерела за типом (SPEC Додаток A, R-26). Чисті функції без ORM.

Кожна помилка — рядок виду «<ключ>: <проблема>»; порожній список — усе гаразд.
"""
import ipaddress
import json
import math
import re

TYPES = ("modbus_tcp", "mqtt", "http_push", "opcua", "bacnet_ip", "helvarnet", "sics", "rest_vendor")
SECRET_KEYS = ("password", "token", "secret", "api_key", "key")

HOST_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9\-\.]{0,251}[A-Za-z0-9])?$")
JSONPATH_RE = re.compile(r"^\$(\.[A-Za-z_][A-Za-z0-9_\-]*|\[[0-9]+\])+$")
REF_RE = re.compile(r"^F3D_[A-Z0-9_]{1,60}$")
ROUTE_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
CLIENT_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")
PROP_RE = re.compile(r"^[a-z][a-z0-9\-]{0,63}$")
NODEID_RE = re.compile(r"^ns=\d+;[sigb]=.{1,240}$")
ENDPOINT_RE = re.compile(r"^opc\.tcp://")
HTTP_URL_RE = re.compile(r"^https?://")
DEVICE_RE = re.compile(r"^@\d+\.\d+\.\d+\.\d+$")
REST_PATH_RE = re.compile(r"^/\S{0,255}$")

MAX_STR = 1024
MAX_JSON = 8 * 1024

BACNET_OBJECTS = (
    "analog-input", "analog-output", "analog-value", "binary-input", "binary-output", "binary-value",
    "multi-state-input", "multi-state-value", "life-safety-zone", "life-safety-point",
    "positive-integer-value", "device",
    "AI", "AO", "AV", "BI", "BO", "BV", "MSI", "MSV", "LSZ", "LSP", "PIV",
)
MODBUS_TYPES = ("bool", "u16", "i16", "u32", "i32", "f32", "u64", "i64", "f64")
MODBUS_WIDTH = {"bool": 1, "u16": 1, "i16": 1, "u32": 2, "i32": 2, "f32": 2, "u64": 4, "i64": 4, "f64": 4}


# --- примітиви: кожен повертає список помилок для ключа ---------------------------------------------
def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _int(key, v, lo=None, hi=None):
    if not _is_int(v):
        return ["%s: має бути ціле число" % key]
    return _range(key, v, lo, hi)


def _num(key, v, lo=None, hi=None):
    if not _is_num(v):
        return ["%s: має бути число" % key]
    return _range(key, v, lo, hi)


def _range(key, v, lo, hi):
    if (lo is not None and v < lo) or (hi is not None and v > hi):
        return ["%s: поза межами %s…%s" % (key, "" if lo is None else lo, "" if hi is None else hi)]
    return []


def _str(key, v, regex=None, desc=None, enum=None, maxlen=MAX_STR, minlen=0):
    if not isinstance(v, str):
        return ["%s: має бути рядок" % key]
    if len(v) > maxlen or len(v) < minlen:
        return ["%s: поза межами довжини %s…%s" % (key, minlen, maxlen)]
    if enum is not None and v not in enum:
        return ["%s: недопустиме значення «%s»; дозволено: %s" % (key, v, ", ".join(enum))]
    if regex is not None and not regex.match(v):
        return ["%s: не відповідає формату %s" % (key, desc or regex.pattern)]
    return []


def _bool(key, v):
    return [] if isinstance(v, bool) else ["%s: має бути булеве" % key]


def _obj(key, v):
    return [] if isinstance(v, dict) else ["%s: має бути об'єкт" % key]


def _host(key, v):
    err = _str(key, v, maxlen=253, minlen=1)
    if err:
        return err
    if HOST_RE.match(v):
        return []
    try:
        ipaddress.ip_address(v.strip("[]"))
        return []
    except ValueError:
        return ["%s: не відповідає формату ім'я DNS або IP-адреса" % key]


def _path(key, v):
    return _str(key, v, JSONPATH_RE, "JSONPath ($.a.b[0])")


def _ref(key, v):
    return _str(key, v, REF_RE, "F3D_<ІМЯ> (змінна середовища)")


def _str_map(key, v, int_keys=False):
    err = _obj(key, v)
    if err:
        return err
    out = []
    for k, val in v.items():
        if int_keys and not re.match(r"^-?\d+$", str(k)):
            out.append("%s.%s: ключ має бути цілим числом" % (key, k))
        out += _str("%s.%s" % (key, k), val, maxlen=64)
    return out


def _check_spec(obj, spec, required=(), prefix=""):
    """spec: ключ -> функція (key, value) -> [errors]. Повертає помилки відомих ключів і відсутніх обов'язкових."""
    errors = []
    for key in required:
        if key not in obj or obj[key] is None:
            errors.append("%s%s: обов'язковий" % (prefix, key))
    for key, fn in spec.items():
        if key in obj and obj[key] is not None:
            errors += fn(prefix + key, obj[key])
    return errors


def _common(obj, strict=False, spec=None):
    """Загальні правила A.0: розмір, ключі з `_`, скінченні числа, спільні scale/offset."""
    errors = []
    try:
        if len(json.dumps(obj, ensure_ascii=False).encode()) > MAX_JSON:
            errors.append("json: завеликий (> 8 КБ)")
    except (TypeError, ValueError):
        errors.append("json: не серіалізується")
    for key in obj:
        if str(key).startswith("_"):
            errors.append("%s: ключі, що починаються з «_», заборонені" % key)
    if _has_bad_number(obj):
        errors.append("json: числа мають бути скінченними")
    if strict and spec is not None:
        for key in obj:
            if key not in spec and key not in ("scale", "offset") and not str(key).startswith("_"):
                errors.append("%s: невідомий ключ (схема sics не допускає додаткових)" % key)
    return errors


def _has_bad_number(v):
    if isinstance(v, float):
        return math.isnan(v) or math.isinf(v)
    if isinstance(v, dict):
        return any(_has_bad_number(x) for x in v.values())
    if isinstance(v, (list, tuple)):
        return any(_has_bad_number(x) for x in v)
    return False


def _scale_offset(obj):
    errors = []
    if obj.get("scale") is not None:
        errors += _num("scale", obj["scale"])
        if not errors and obj["scale"] == 0:
            errors.append("scale: має бути ≠ 0")
    if obj.get("offset") is not None:
        errors += _num("offset", obj["offset"])
    return errors


# --- address -----------------------------------------------------------------------------------------
def _addr_modbus(a):
    errors = _check_spec(a, {
        "fc": lambda k, v: _int(k, v, 1, 4),
        "addr": lambda k, v: _int(k, v, 0, 65535),
        "unit": lambda k, v: _int(k, v, 1, 247),
        "type": lambda k, v: _str(k, v, enum=MODBUS_TYPES),
        "count": lambda k, v: _int(k, v, 1, 125),
        "agg": lambda k, v: _str(k, v, enum=("max", "min", "sum", "avg", "first")),
        "wordorder": lambda k, v: _str(k, v, enum=("big", "little")),
        "byteorder": lambda k, v: _str(k, v, enum=("big", "little")),
        "bit": lambda k, v: _int(k, v, 0, 15),
        "doc": lambda k, v: _str(k, v, maxlen=256),
        "map": lambda k, v: _str_map(k, v, int_keys=True),
    }, required=("fc",))
    if "addr" not in a and not a.get("states"):
        errors.append("addr: обов'язковий (якщо немає states)")
    fc, typ = a.get("fc"), a.get("type")
    if _is_int(fc) and typ in MODBUS_TYPES:
        if fc in (1, 2) and typ != "bool":
            errors.append("type: для fc 1/2 допустимий лише bool")
        count = a.get("count")
        if _is_int(count) and 1 <= count <= 125:
            width = MODBUS_WIDTH[typ]
            if count % width:
                errors.append("count: має бути кратним ширині типу (%s)" % width)
            elif count > width and not a.get("agg"):
                errors.append("count: більше ширини типу — лише разом з agg")
    if "bit" in a and _is_int(a["bit"]):
        eff = typ or ("bool" if fc in (1, 2) else "u16")
        if eff != "bool" or fc in (1, 2):
            errors.append("bit: лише з type=bool і fc 3/4")
    if a.get("range") is not None:
        r = a["range"]
        if not (isinstance(r, list) and len(r) == 2 and all(_is_num(x) for x in r)):
            errors.append("range: має бути список із двох чисел")
        elif not r[0] < r[1]:
            errors.append("range: має бути lo < hi")
    if a.get("states") is not None:
        st = a["states"]
        if not isinstance(st, list):
            errors.append("states: має бути список")
        elif not 1 <= len(st) <= 16:
            errors.append("states: поза межами 1…16 елементів")
        else:
            for i, item in enumerate(st):
                p = "states[%s]." % i
                if not isinstance(item, dict):
                    errors.append("states[%s]: має бути об'єкт" % i)
                    continue
                errors += _check_spec(item, {
                    "addr": lambda k, v: _int(k, v, 0, 65535),
                    "eq": lambda k, v: _int(k, v),
                    "text": lambda k, v: _str(k, v, maxlen=64),
                    "fc": lambda k, v: _int(k, v, 1, 4),
                }, required=("addr", "eq", "text"), prefix=p)
    if a.get("write") is not None:
        w = a["write"]
        if not isinstance(w, dict):
            errors.append("write: має бути об'єкт")
        else:
            errors += _check_spec(w, {
                "fc": lambda k, v: _int(k, v, 5, 16),
                "addr": lambda k, v: _int(k, v, 0, 65535),
                "pulse_ms": lambda k, v: _int(k, v, 100, 10000),
            }, required=("fc", "addr"), prefix="write.")
            if _is_int(w.get("fc")) and w["fc"] not in (5, 6, 16):
                errors.append("write.fc: недопустиме значення «%s»; дозволено: 5, 6, 16" % w["fc"])
            if "pulse_ms" in w and w.get("fc") not in (5, 6):
                errors.append("write.pulse_ms: лише з fc 5 або 6")
    return errors


def _topic(key, v):
    err = _str(key, v, maxlen=256, minlen=1)
    if err:
        return err
    if "+" in v or "#" in v or "\x00" in v or any(not lvl for lvl in v.split("/")):
        return ["%s: не відповідає формату топік без wildcard і порожніх рівнів" % key]
    return []


def _addr_mqtt(a):
    errors = _check_spec(a, {
        "topic": _topic,
        "path": _path,
        "ts_path": _path,
        "device": lambda k, v: _str(k, v, maxlen=32),
        "map": lambda k, v: _str_map(k, v),
    }, required=("topic", "path"))
    if a.get("write") is not None:
        w = a["write"]
        if not isinstance(w, dict):
            errors.append("write: має бути об'єкт")
        else:
            errors += _check_spec(w, {
                "topic": _topic,
                "template": lambda k, v: _str(k, v, maxlen=1024),
            }, required=("topic", "template"), prefix="write.")
    return errors


def _addr_http_push(a):
    errors = _check_spec(a, {
        "route": lambda k, v: _str(k, v, ROUTE_RE, "^[a-z][a-z0-9_]{0,31}$"),
        "path": _path,
        "ts_path": _path,
    }, required=("route", "path"))
    if a.get("match") is not None:
        m = a["match"]
        if not isinstance(m, dict):
            errors.append("match: має бути об'єкт")
        else:
            for k, v in m.items():
                if not (isinstance(v, (str, int, float, bool))):
                    errors.append("match.%s: має бути рядок, число або булеве" % k)
    return errors


def _addr_bacnet(a):
    errors = _check_spec(a, {
        "object": lambda k, v: _str(k, v, enum=BACNET_OBJECTS),
        "instance": lambda k, v: _int(k, v, 0, 4194302),
        "property": lambda k, v: _str(k, v, PROP_RE, "^[a-z][a-z0-9\\-]{0,63}$"),
        "index": lambda k, v: _int(k, v, 0),
        "device": lambda k, v: _int(k, v, 0, 4194302),
        "mode": lambda k, v: _str(k, v, enum=("cov", "poll")),
        "priority": lambda k, v: _int(k, v, 1, 16),
        "map": lambda k, v: _str_map(k, v),
        "check_reliability": _bool,
        "read_priority_array": _bool,
    }, required=("object", "instance"))
    if a.get("cov_increment") is not None:
        errors += _num("cov_increment", a["cov_increment"])
        if not errors and a["cov_increment"] <= 0:
            errors.append("cov_increment: має бути > 0")
    if a.get("states") is not None:
        st = a["states"]
        if not isinstance(st, list):
            errors.append("states: має бути список")
        elif not 1 <= len(st) <= 16:
            errors.append("states: поза межами 1…16 елементів")
        else:
            for i, item in enumerate(st):
                if not isinstance(item, dict):
                    errors.append("states[%s]: має бути об'єкт" % i)
                    continue
                errors += _check_spec(item, {
                    "object": lambda k, v: _str(k, v, enum=BACNET_OBJECTS),
                    "instance": lambda k, v: _int(k, v, 0, 4194302),
                    "text": lambda k, v: _str(k, v, maxlen=64),
                }, required=("object", "instance", "text"), prefix="states[%s]." % i)
                if "eq" not in item:
                    errors.append("states[%s].eq: обов'язковий" % i)
    return errors


def _addr_opcua(a):
    return _check_spec(a, {
        "nodeid": lambda k, v: _str(k, v, NODEID_RE, "ns=<n>;s|i|g|b=<id>"),
        "mode": lambda k, v: _str(k, v, enum=("subscribe", "poll")),
        "sampling_ms": lambda k, v: _int(k, v, 0, 60000),
        "map": lambda k, v: _str_map(k, v),
    }, required=("nodeid",))


def _addr_helvarnet(a):
    errors = _check_spec(a, {
        "group": lambda k, v: _int(k, v, 1, 16383),
        "device": lambda k, v: _str(k, v, DEVICE_RE, "@c.r.s.d"),
        "query": lambda k, v: _str(k, v, maxlen=64),
        "map": lambda k, v: _str_map(k, v),
    })
    if a.get("group") is None and a.get("device") is None:
        errors.append("group: потрібен один із group або device")
    return errors


def _addr_sics(a):
    errors = _check_spec(a, {
        "field": lambda k, v: _str(k, v, enum=("weight", "stable")),
        "cmd": lambda k, v: _str(k, v, enum=("SI",)),
        "doc": lambda k, v: _str(k, v, maxlen=128),
    }, required=("field",))
    if a.get("write") is not None:
        w = a["write"]
        if not isinstance(w, dict):
            errors.append("write: має бути об'єкт")
        else:
            errors += _check_spec(w, {"cmd": lambda k, v: _str(k, v, enum=("Z", "T", "TAC"))},
                                  required=("cmd",), prefix="write.")
            for k in w:
                if k != "cmd":
                    errors.append("write.%s: невідомий ключ" % k)
    return errors


def _addr_rest(a):
    errors = _check_spec(a, {
        "method": lambda k, v: _str(k, v, enum=("GET", "POST")),
        "path": lambda k, v: _str(k, v, REST_PATH_RE, "/шлях"),
        "json_path": _path,
    }, required=("path", "json_path"))
    if a.get("query") is not None:
        q = a["query"]
        if not isinstance(q, dict):
            errors.append("query: має бути об'єкт")
        else:
            for k, v in q.items():
                if not isinstance(v, (str, int, float)) or isinstance(v, bool):
                    errors.append("query.%s: має бути рядок або число" % k)
    return errors


ADDRESS_VALIDATORS = {
    "modbus_tcp": _addr_modbus, "mqtt": _addr_mqtt, "http_push": _addr_http_push, "bacnet_ip": _addr_bacnet,
    "opcua": _addr_opcua, "helvarnet": _addr_helvarnet, "sics": _addr_sics, "rest_vendor": _addr_rest,
}
ADDRESS_STRICT = {
    "sics": ("field", "cmd", "write", "doc"),
}


def validate_address(type, address, local_types=()):  # noqa: A002
    """Перевірка `address` сигналу за типом джерела (Додаток A.1). `{}` і локальні типи — без перевірки."""
    if type in local_types:
        return []
    if address in (None, False, {}):
        return []
    if not isinstance(address, dict):
        return ["адреса має бути об'єктом JSON"]
    validator = ADDRESS_VALIDATORS.get(type)
    if validator is None:
        return []
    errors = _common(address, strict=type in ADDRESS_STRICT, spec=dict.fromkeys(ADDRESS_STRICT.get(type, ())))
    errors += _scale_offset(address)
    errors += validator(address)
    return errors


# --- params ------------------------------------------------------------------------------------------
def _topic_filter(key, v):
    err = _str(key, v, maxlen=256, minlen=1)
    if err:
        return err
    levels = v.split("/")
    for i, lvl in enumerate(levels):
        if "#" in lvl and (lvl != "#" or i != len(levels) - 1):
            return ["%s: не відповідає формату фільтр MQTT (# лише останнім рівнем)" % key]
        if "+" in lvl and lvl != "+":
            return ["%s: не відповідає формату фільтр MQTT (+ — цілий рівень)" % key]
    return []


def _list_of(key, v, item_fn, lo, hi):
    if not isinstance(v, list):
        return ["%s: має бути список" % key]
    if not lo <= len(v) <= hi:
        return ["%s: поза межами %s…%s елементів" % (key, lo, hi)]
    errors = []
    for item in v:
        errors += item_fn(key, item)
    return errors


def _params_modbus(p):
    return _check_spec(p, {
        "host": _host,
        "port": lambda k, v: _int(k, v, 1, 65535),
        "unit": lambda k, v: _int(k, v, 1, 247),
        "timeout_s": lambda k, v: _num(k, v, 0.5, 60),
        "retries": lambda k, v: _int(k, v, 0, 5),
        "max_block": lambda k, v: _int(k, v, 1, 125),
        "gap_max": lambda k, v: _int(k, v, 0, 32),
    }, required=("host",))


def _params_mqtt(p):
    return _check_spec(p, {
        "host": _host,
        "port": lambda k, v: _int(k, v, 1, 65535),
        "username": lambda k, v: _str(k, v, maxlen=256),
        "password_ref": _ref,
        "client_id": lambda k, v: _str(k, v, CLIENT_ID_RE, "^[A-Za-z0-9_\\-]{1,64}$"),
        "topics": lambda k, v: _list_of(k, v, _topic_filter, 1, 32),
        "status_topic": lambda k, v: _str(k, v, maxlen=256),
        "status_online_path": _path,
        "keepalive_s": lambda k, v: _int(k, v, 5, 600),
        "tls": _bool,
        "qos": lambda k, v: _int(k, v, 0, 1),
    }, required=("host", "client_id", "topics"))


def _params_http_push(p):
    return _check_spec(p, {
        "routes": lambda k, v: _list_of(
            k, v, lambda kk, vv: _str(kk, vv, ROUTE_RE, "^[a-z][a-z0-9_]{0,31}$"), 1, 16),
        "allow_ips": lambda k, v: _list_of(k, v, lambda kk, vv: _str(kk, vv, maxlen=256, minlen=1), 0, 256),
        "token_ref": _ref,
        "secret_ref": _ref,
        "max_body_kb": lambda k, v: _int(k, v, 1, 1024),
    }, required=("routes",))


def _params_bacnet(p):
    return _check_spec(p, {
        "host": _host,
        "port": lambda k, v: _int(k, v, 1, 65535),
        "device": lambda k, v: _int(k, v, 0, 4194302),
        "address": lambda k, v: _str(k, v, maxlen=64),
        "network": lambda k, v: _int(k, v, 1, 65534),
        "timeout_s": lambda k, v: _num(k, v, 1, 60),
        "rpm": _bool,
        "rpm_max": lambda k, v: _int(k, v, 1, 200),
        "cov_lifetime_s": lambda k, v: _int(k, v, 60, 3600),
        "read_only": _bool,
        "events": _bool,
    }, required=("host", "device"))


def _params_opcua(p):
    return _check_spec(p, {
        "endpoint": lambda k, v: _str(k, v, ENDPOINT_RE, "opc.tcp://…"),
        "security_mode": lambda k, v: _str(k, v, enum=("None", "Sign", "SignAndEncrypt")),
        "security_policy": lambda k, v: _str(
            k, v, enum=("None", "Basic256Sha256", "Aes128_Sha256_RsaOaep", "Aes256_Sha256_RsaPss")),
        "username": lambda k, v: _str(k, v, maxlen=256),
        "password_ref": _ref, "cert_ref": _ref, "key_ref": _ref,
        "timeout_s": lambda k, v: _num(k, v, 0.1, 600),
        "publishing_interval_ms": lambda k, v: _int(k, v, 50, 60000),
    }, required=("endpoint",))


def _params_helvarnet(p):
    return _check_spec(p, {
        "host": _host,
        "port": lambda k, v: _int(k, v, 1, 65535),
        "protocol": lambda k, v: _str(k, v, enum=("tcp", "udp")),
        "timeout_s": lambda k, v: _num(k, v, 0.1, 600),
    }, required=("host",))


SICS_PARAM_KEYS = ("host", "port", "mode", "period_s", "timeout_s", "unit", "dialect", "reset_on_connect")


def _params_sics(p):
    errors = _check_spec(p, {
        "host": lambda k, v: _str(k, v, maxlen=253, minlen=1),
        "port": lambda k, v: _int(k, v, 1, 65535),
        "mode": lambda k, v: _str(k, v, enum=("stream", "poll")),
        "period_s": lambda k, v: _num(k, v, 0.2, 60),
        "timeout_s": lambda k, v: _num(k, v, 0.5, 30),
        "unit": lambda k, v: _str(k, v, enum=("kg", "t", "lb", "g")),
        "dialect": lambda k, v: _str(k, v, enum=("mt_sics",)),
        "reset_on_connect": _bool,
    }, required=("host",))
    for k in p:
        if k not in SICS_PARAM_KEYS and not str(k).startswith("_"):
            errors.append("%s: невідомий ключ (схема sics не допускає додаткових)" % k)
    return errors


def _params_rest(p):
    return _check_spec(p, {
        "base_url": lambda k, v: _str(k, v, HTTP_URL_RE, "http(s)://…"),
        "auth": lambda k, v: _str(k, v, enum=("none", "api_key", "bearer", "basic")),
        "header": lambda k, v: _str(k, v, maxlen=128),
        "key_ref": _ref,
        "user": lambda k, v: _str(k, v, maxlen=256),
        "password_ref": _ref,
        "verify_tls": _bool,
        "timeout_s": lambda k, v: _num(k, v, 1, 60),
    }, required=("base_url",))


PARAMS_VALIDATORS = {
    "modbus_tcp": _params_modbus, "mqtt": _params_mqtt, "http_push": _params_http_push,
    "bacnet_ip": _params_bacnet, "opcua": _params_opcua, "helvarnet": _params_helvarnet,
    "sics": _params_sics, "rest_vendor": _params_rest,
}


def _secret_errors(params):
    return ["%s: секрети не зберігаються в Odoo — використайте %s_ref" % (k, k) for k in params if k in SECRET_KEYS]


def validate_params(type, params, local_types=()):  # noqa: A002
    """Перевірка `params` джерела за типом (Додаток A.2). Локальний тип — лише об'єкт без секретів (R-26)."""
    if not isinstance(params, dict):
        return ["параметри мають бути об'єктом JSON"]
    is_local = type in local_types
    if not is_local and type not in PARAMS_VALIDATORS:
        return ["type: невідомий тип джерела «%s»" % type]
    errors = _common(params)
    errors += _secret_errors(params)
    if is_local:
        return errors
    errors += PARAMS_VALIDATORS[type](params)
    return errors
