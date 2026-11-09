#!/usr/bin/env python3
"""Автоперевірки hypercare.md / support-log.md (B-09, B-10). Вихід: JSON [{id, status, msg}]. Лише stdlib.
Чого не можна перевірити без вхідних файлів чи --base — SKIP, не PASS.
Використання: check_support.py <файл> [--base <sha>] [--mode intake|hypercare-close|sla-month] [--tr ТР.md]
              [--delivery-log delivery-log.md] [--other <другий реєстр>] [--period РРРР-ММ]"""
import argparse, json, re, subprocess
from pathlib import Path

TYPES = {"баг конфіг", "баг код", "дані", "навчання", "дефект пакета", "нова вимога",
         "платформа-інфраструктура", "консультація"}
SEV = {"критична", "висока", "середня", "низька"}
STATUS_RE = re.compile(r"^(в роботі \(.+\)|виправлено на тесті|застосовано в прод( \(B-12\))?|закрито.*|передано в беклог \(D-02\)|"
                       r"передано в D-02|очікує Підтримку|потрібен AC — Підтримка)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE = re.compile(r"(\+380|\b0\d{2})[\s()-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}")
IBAN = re.compile(r"\bUA\d{2}[\dA-Z]{10,}\b|\b\d{8}\b(?=\s*ЄДРПОУ)|ЄДРПОУ\s*\d{8,10}")
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
        else:
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
    try:
        return subprocess.run(["git", "show", f"{base}:{path}"], capture_output=True, text=True, check=True).stdout
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file"); ap.add_argument("--base"); ap.add_argument("--mode", default="intake")
    ap.add_argument("--tr"); ap.add_argument("--delivery-log"); ap.add_argument("--other"); ap.add_argument("--period")
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

    add("SD-route", all(col(r, "маршрут") for r in rows), "порожній маршрут у рядках" if not all(col(r, "маршрут") for r in rows) else "")

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
            conf = col(r, "підтвердження клієнта") if kind == "hypercare" else col(r, "статус")
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
    badd = [col(r, "id") for r in rows if col(r, "тип").lower() in {"нова вимога", "дефект пакета"} and col(r, "id") not in d02]
    add("SD-d02", not badd, "не в «Запити в D-02»: " + ", ".join(badd) if badd else "")

    if a.base:
        old = git_show(a.base, a.file)
        if old is None:
            add("SD-protected", True, "базового файлу немає в git", skip=True)
        else:
            oh, orows = registry(old)
            changed = []
            om = {col(r, "id"): r for r in orows}
            for r in rows:
                o = om.get(col(r, "id"))
                if not o:
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
        add("SD-14days", True, "дату завершення внесено: перевірити відлік скриптом sla_calc.py days-clean" if m else "дата завершення порожня (очікувано, якщо ще не done)", skip=True)
    else:
        add("SD-14days", True, "лише для hypercare-close", skip=True)

    pii = []
    if EMAIL.search(text): pii.append("e-mail")
    if PHONE.search(text): pii.append("телефон")
    if IBAN.search(text): pii.append("IBAN/ЄДРПОУ")
    if any(len(q.split()) > 10 for q in QUOTE.findall(text)): pii.append("цитата >10 слів")
    add("SD-pii", not pii, "знайдено: " + ", ".join(pii) if pii else "")
    res = [r for r in res if r]
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
