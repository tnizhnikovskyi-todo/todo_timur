#!/usr/bin/env python3
"""Автоперевірки hypercare.md / support-log.md (B-09, B-10). Вихід: JSON [{id, status, msg}]. Лише stdlib.
Чого не можна перевірити без вхідних файлів чи --base — SKIP, не PASS.
Запускати з кореня репо; <файл> — репо-відносний шлях (інакше SD-protected -> SKIP з поясненням).
Використання: check_support.py <файл> [--base <sha з git.base наряду>] [--mode intake|hypercare-close|sla-month]
              [--tr ТР.md] [--delivery-log delivery-log.md] [--other <другий реєстр>] [--period РРРР-ММ]
              [--routes flow-client-delivery/references/triage-routes.md]
Шаблони ПДн узгоджені з flow-core/references/pii-patterns.md (змінювати разом)."""
import argparse, json, os, re, subprocess
from datetime import date, timedelta
from pathlib import Path

TYPES = {"баг конфіг", "баг код", "дані", "навчання", "дефект пакета", "нова вимога",
         "платформа-інфраструктура", "консультація"}
SEV = {"критична", "висока", "середня", "низька"}
STATUS_RE = re.compile(r"^(в роботі \(.+\)|виправлено на тесті|застосовано в прод( \(B-12\))?|закрито.*|передано в беклог \(D-02\)|"
                       r"передано в D-02|очікує Підтримку|потрібен AC — Підтримка)", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?<![\w:])(\+?380\d{9}|0\d{9})(?!\w)")
IBAN = re.compile(r"\bUA\d{2}[\s\d]{20,}|ЄДРПОУ\D{0,5}\d{8}\b")
URL = re.compile(r"\bhttps?://[^\s)>\]]+")
IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
SECRET = re.compile(r"(password|passwd|pwd|api[_-]?key|token|secret)\s*[:=]\s*\S+", re.I)
FIO = re.compile(r"\b[А-ЯІЇЄҐ][а-яіїєґ'’-]+\s+[А-ЯІЇЄҐ][а-яіїєґ'’-]+\s+[А-ЯІЇЄҐ][а-яіїєґ'’-]+\b")
HUMAN_COLS = ["застосування в прод", "реакція", "вирішення", "хто", "підтвердження клієнта", "надіслано"]
QUOTE = re.compile(r"[«\"“]([^»\"”]{40,})[»\"”]")
REQUIRED = {"hypercare": ["Заголовний блок", "Реєстр інцидентів", "Запити в D-02", "Журнал запусків"],
            "support-log": ["Умови SLA", "Реєстр звернень", "Запити в D-02", "Зміни умов", "Журнал запусків"]}
PROTECTED = ["застосування в прод", "рішення d-02", "реакція", "вирішення", "підтвердження клієнта", "надіслано", "хто"]


def sections(text):
    out, cur = {}, None
    for l in text.splitlines():
        m = re.match(r"^##\s+(.*)", l)
        if m:
            cur = m.group(1).strip(); out[cur] = []
        elif cur is not None:
            out[cur].append(l)
    return out


def table(lines):
    hdr, rows = None, []
    for l in lines:
        if not l.startswith("|") or re.match(r"^\|[\s:-]+\|", l):
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", l.strip().strip("|"))]
        if hdr is None:
            hdr = [c.lower() for c in cells]
        elif cells and cells[0]:  # рядок без першої клітинки (примітка після таблиці) — не рядок реєстру
            rows.append(dict(zip(hdr, cells)))
    return hdr or [], rows


def col(row, *names):
    for k, v in row.items():
        if any(k.startswith(n) for n in names):
            return v
    return ""


def registry(text):
    s = sections(text)
    for name, lines in s.items():
        if name.startswith("Реєстр"):
            return table(lines)
    return [], []


def git_show(base, path):
    """Працює з будь-якого cwd: репо-корінь і відносний шлях визначаються від самого файлу."""
    try:
        d = os.path.dirname(os.path.abspath(path))
        top = subprocess.run(["git", "-C", d, "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True).stdout.strip()
        rel = os.path.relpath(os.path.abspath(path), top)
        return subprocess.run(["git", "-C", top, "show", f"{base}:{rel}"], capture_output=True, text=True, check=True).stdout
    except Exception:
        return None


def parse_routes(text):
    """triage-routes.md: таблиця «Типи й маршрути» -> {тип: множина кодів кроків}; «Дефект пакета × серйозність» -> {серйозність: коди}."""
    types, sev = {}, {}
    for name, lines in sections_h3(text).items():
        _, rows = table(lines)
        for r in rows:
            key = (col(r, "тип") or col(r, "серйозність")).lower()
            val = col(r, "маршрут")
            codes = set(re.findall(r"\b[A-D]-\d{2}[a-d]?\b", val))
            words = {w for w in ("підтримк", "тімлід", "рішення") if w in val.lower()}
            if name.startswith("Типи"):
                types[key] = codes | words
            elif name.startswith("Дефект"):
                sev[key] = codes | words
    return types, sev


def sections_h3(text):
    out, cur = {}, None
    for l in text.splitlines():
        m = re.match(r"^#{2,3}\s+(.*)", l)
        if m:
            cur = m.group(1).strip(); out[cur] = []
        elif cur is not None:
            out[cur].append(l)
    return out


def route_ok(route, types, sev, typ, severity):
    allowed = set(types.get(typ, set()))
    if typ == "дефект пакета":
        allowed = set(sev.get(severity, set())) or allowed
    r = route.lower()
    if typ in {"баг конфіг", "баг код"}:
        return "b-13" in r
    return any(c.lower() in r for c in allowed) if allowed else True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file"); ap.add_argument("--base"); ap.add_argument("--mode", default="intake")
    ap.add_argument("--tr"); ap.add_argument("--delivery-log"); ap.add_argument("--other"); ap.add_argument("--period"); ap.add_argument("--routes")
    a = ap.parse_args()
    text = Path(a.file).read_text(encoding="utf-8")
    kind = "support-log" if "support" in Path(a.file).name else "hypercare"
    secs = sections(text)
    res = []

    def add(i, ok, msg="", skip=False):
        res.append({"id": i, "status": "SKIP" if skip else ("PASS" if ok else "FAIL"), "msg": msg})

    miss = [h for h in REQUIRED[kind] if h not in secs]
    add("SD-columns", not miss, "немає заголовків: " + ", ".join(miss) if miss else "")
    hdr, rows = registry(text)
    bad = []
    for r in rows:
        rid = col(r, "id")
        sev = col(r, "серйозність", "пріоритет").lower()
        typ = col(r, "тип").lower()
        st = col(r, "статус").lower()
        if (kind == "hypercare" and sev not in SEV) or typ not in TYPES or not STATUS_RE.match(st):
            bad.append(rid)
    add("SD-enums", not bad, "значення поза переліком: " + ", ".join(bad) if bad else "")

    empty = [col(r, "id") for r in rows if not col(r, "маршрут")]
    add("SD-route", not empty, "порожній маршрут: " + ", ".join(empty) if empty else "")
    if a.routes and Path(a.routes).exists():
        types, sev = parse_routes(Path(a.routes).read_text(encoding="utf-8"))
        badr = [col(r, "id") for r in rows if col(r, "маршрут") and
                not route_ok(col(r, "маршрут"), types, sev, col(r, "тип").lower(), col(r, "серйозність", "пріоритет").lower())]
        add("SD-route-table", not badr and bool(types), "маршрут не за triage-routes.md: " + ", ".join(badr) if badr else ("таблицю не розібрано" if not types else ""))
    else:
        add("SD-route-table", True, "не передано --routes (triage-routes.md)", skip=True)

    if a.tr and Path(a.tr).exists():
        tr = Path(a.tr).read_text(encoding="utf-8")
        noac = [col(r, "id") for r in rows if col(r, "тип").lower() in {"баг конфіг", "баг код"}
                and (not re.search(r"AC-\d+", col(r, "ac")) or col(r, "ac").split(",")[0].strip() not in tr
                     and not all(x.strip() in tr for x in re.findall(r"AC-\d+", col(r, "ac"))))]
        add("SD-ac", not noac, "AC відсутній у ТР: " + ", ".join(noac) if noac else "")
    else:
        add("SD-ac", True, "ТР не передано (--tr)", skip=True)

    dl = Path(a.delivery_log).read_text(encoding="utf-8") if a.delivery_log and Path(a.delivery_log).exists() else None
    badc = []
    for r in rows:
        if col(r, "статус").lower().startswith("закрито") and col(r, "тип").lower() not in {"консультація"}:
            conf = col(r, "підтвердження клієнта") if kind == "hypercare" else (
                col(r, "вирішення", "хто") or ("підтвердж" in col(r, "статус").lower() and "закрито" in col(r, "статус").lower()))
            if not conf:
                badc.append(col(r, "id"))
            elif col(r, "тип").lower() in {"баг конфіг", "баг код"} and (dl is None or col(r, "id") not in dl):
                badc.append(col(r, "id"))
    add("SD-close", not badc, "закрито без підтвердження/B-12: " + ", ".join(badc) if badc else "", skip=(dl is None and not badc))

    d02 = "".join(secs.get("Запити в D-02", []))
    badp = [col(r, "id") for r in rows if col(r, "тип").lower() == "дефект пакета"
            and col(r, "серйозність", "пріоритет").lower() in {"критична", "висока"}
            and (col(r, "id") not in d02 or "A-19" not in (col(r, "примітка ai", "маршрут") + col(r, "маршрут")))]
    add("SD-pkg-defect", not badp, "немає обходу/D-02/A-19: " + ", ".join(badp) if badp else "")
    # середній дефект пакета -> «рішення Підтримки» (triage-routes.md), у D-02 без рішення не йде
    badd = [col(r, "id") for r in rows if col(r, "id") not in d02 and (col(r, "тип").lower() == "нова вимога" or (
            col(r, "тип").lower() == "дефект пакета" and col(r, "серйозність", "пріоритет").lower() != "середня"))]
    add("SD-d02", not badd, "не в «Запити в D-02»: " + ", ".join(badd) if badd else "")

    if a.base:
        old = git_show(a.base, a.file)
        if old is None:
            add("SD-protected", True, "базового файлу немає в git за цим шляхом (запуск з кореня репо, шлях репо-відносний, --base = git.base)", skip=True)
        else:
            oh, orows = registry(old)
            changed = []
            om = {col(r, "id"): r for r in orows}
            for r in rows:
                o = om.get(col(r, "id"))
                if not o:
                    # новий рядок: людські колонки мають бути порожні
                    changed += [f"{col(r, 'id')}:{k}(новий)" for k, v in r.items()
                                if v and any(k.startswith(p) for p in HUMAN_COLS) and not v.lower().startswith("перенесено")]
                    continue
                for k in r:
                    if any(k.startswith(p) for p in PROTECTED) and o.get(k, "") != r[k]:
                        changed.append(f"{col(r, 'id')}:{k}")
            for name in ("Запити в D-02",):
                _, nr = table(secs.get(name, [])); _, orr = table(sections(old).get(name, []))
                omap = {col(r, "id"): col(r, "рішення") for r in orr}
                changed += [f"{col(r, 'id')}:D-02" for r in nr if col(r, "id") in omap and omap[col(r, "id")] != col(r, "рішення")]
            add("SD-protected", not changed, "змінено чужі колонки: " + ", ".join(changed) if changed else "")
    else:
        add("SD-protected", True, "немає --base", skip=True)

    ids = [col(r, "id") for r in rows]; tids = [col(r, "джерело") for r in rows]
    dup = {i for i in ids if ids.count(i) > 1} | {t for t in tids if t and tids.count(t) > 1}
    if a.other and Path(a.other).exists():
        _, orows = registry(Path(a.other).read_text(encoding="utf-8"))
        for r in rows:
            for o in orows:
                if col(o, "джерело") == col(r, "джерело") and col(r, "джерело") and "перенесено з b-09" not in " ".join(r.values()).lower() \
                        and "перенесено" not in " ".join(o.values()).lower():
                    dup.add(col(r, "джерело"))
    add("SD-dup", not dup, "дублі: " + ", ".join(sorted(dup)) if dup else "")

    if kind == "support-log":
        sla = "".join(secs.get("Умови SLA", []))
        add("SD-sla-source", bool(re.search(r"drive:[\w-]+@\S+", sla)), "немає drive:<fileId>@<modifiedTime>" if not re.search(r"drive:[\w-]+@\S+", sla) else "")
        bs = [col(r, "id") for r in rows if not col(r, "sla-строк", "sla") or
              (not col(r, "реакція") and col(r, "дотримання").lower().startswith("в межах"))]
        add("SD-sla", not bs, "без SLA-строку або «в межах» без реакції: " + ", ".join(bs) if bs else "")
        if a.mode == "sla-month":
            rep = [n for n in secs if n.startswith("Звіт SLA")]
            ok = bool(rep) and (not a.period or any(a.period in n for n in rep))
            late = [col(r, "id") for r in rows if col(r, "дотримання").lower() == "прострочено" and not col(r, "причина")]
            add("SD-report", ok and not late, ("немає звіту за період; " if not ok else "") + ("прострочені без причини: " + ", ".join(late) if late else ""))
    else:
        for i in ("SD-sla", "SD-sla-source", "SD-report"):
            add(i, True, "не застосовується до hypercare.md", skip=True)

    if a.mode == "hypercare-close" and kind == "hypercare":
        hb = "".join(secs.get("Заголовний блок", []))
        m = re.search(r"завершення hypercare[^|]*\|\s*(\d{4}-\d{2}-\d{2})", hb)
        def hd(name):
            mm = re.search(name + r"[^|]*\|\s*(\d{4}-\d{2}-\d{2})", hb, re.I)
            return date.fromisoformat(mm.group(1)) if mm else None
        g, lc, dl_, end = hd("дата go-live"), hd("дата останнього критичного"), hd("граничний строк"), hd("дата завершення hypercare")
        if not end or not g:
            add("SD-14days", True, "дата завершення або go-live порожні (очікувано, якщо ще не done)", skip=True)
        else:
            start = max(g, lc) if lc else g
            probs = []
            if end < start + timedelta(days=14):
                probs.append(f"завершення {end} раніше за {start + timedelta(days=14)}")
            if dl_ and end > dl_:
                probs.append(f"завершення {end} пізніше за граничний строк {dl_} (потрібне рішення PM у flow/decisions.md)")
            add("SD-14days", not probs, "; ".join(probs))
    else:
        add("SD-14days", True, "лише для hypercare-close", skip=True)

    pii = []
    norm = re.sub(r"(?<=\d)[\s()-]+(?=\d)", "", text)  # нормалізація телефонів із пробілами/дефісами
    for name, rx, src in (("e-mail", EMAIL, text), ("телефон", PHONE, norm), ("IBAN/ЄДРПОУ", IBAN, text),
                          ("url", URL, text), ("ip", IP, text), ("secret", SECRET, text)):
        ln = [i + 1 for i, l in enumerate(src.splitlines()) if rx.search(l)]
        if ln:
            pii.append(f"{name}: рядки {ln[:5]}")  # значення збігу не друкуємо
    if any(len(q.split()) > 10 for q in QUOTE.findall(text)): pii.append("цитата >10 слів")
    add("SD-pii", not pii, "знайдено: " + "; ".join(pii) if pii else "")
    fio = [i + 1 for i, l in enumerate(text.splitlines()) if FIO.search(l)]
    if fio:  # три слова з великої: можливі хибні спрацьовування -> MANUAL, не FAIL
        res.append({"id": "SD-pii-name", "status": "MANUAL", "msg": f"можливе ПІБ, рядки {fio[:5]}: перевірити людиною"})
    res = [r for r in res if r]
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
