#!/usr/bin/env python3
"""Автоперевірки config-log.md (B-04). Вихід: JSON [{id, status, msg}]. Лише stdlib.
Статуси: PASS / FAIL / MANUAL (потрібна людина) / SKIP (скрипт не бачить базу чи вхід не передано).
SKIP не є PASS: перелік у SKILL.md, розділ «Автоперевірка»."""
import argparse, json, re, sys
from pathlib import Path

ALLOWED = {"застосовано", "відхилення", "очікує відповіді", "очікує: виконує людина", "передано в D-02"}
DRIFT_CLASSES = {"збіг", "дрейф", "втрачено", "зайве", "не перевірено"}
ANCHOR = re.compile(r"^[\w.]+:[^|]*\|.*:[\w.]+$")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?<![\w:])(\+?380\d{9}|0\d{9})(?!\w)")  # id-patterns/pii-patterns.md
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
FIO = re.compile(r"\b[А-ЯІЇЄҐ][а-яіїєґ'’-]+\s+[А-ЯІЇЄҐ][а-яіїєґ'’-]+\s+[А-ЯІЇЄҐ][а-яіїєґ'’-]+\b")
TRUE, FALSE = {"true", "вкл.", "вкл", "так", "yes", "on"}, {"false", "викл.", "викл", "ні", "no", "off"}


def sections(text):
    out, cur = {}, None
    for line in text.splitlines():
        m = re.match(r"^#{2,3}\s+(.*)", line)
        if m:
            cur = m.group(1).strip(); out[cur] = []
        elif cur:
            out[cur].append(line)
    return out


def rows(lines):
    """Рядки даних таблиць: перший рядок кожної таблиці (заголовок) і роздільник пропускаються."""
    res, in_tbl = [], False
    for l in lines:
        if l.startswith("|"):
            if re.match(r"^\|[\s:|-]+\|?\s*$", l):
                continue
            if not in_tbl:
                in_tbl = True; continue  # заголовок таблиці, будь-який текст
            res.append([c.strip() for c in re.split(r"(?<!\\)\|", l.strip().strip("|"))])
        else:
            in_tbl = False
    return res


def norm(v):
    v = v.strip().strip("`").strip().lower()
    if v in TRUE: return "true"
    if v in FALSE: return "false"
    m = re.match(r"^(\d+)\s*:", v)  # many2one «id:назва»
    if m: return repr(float(m.group(1)))
    try: return repr(float(v.replace(",", ".")))
    except ValueError: return v


def normv(v):
    """Версія як в Odoo adapt_version: без серії 19.0. -> додати."""
    v = v.strip().strip("`").strip()
    return v if v.startswith("19.0.") else "19.0." + v


def assumptions(sw):
    m = re.search(r"^#{1,4}\s+[^\n]*[Дд]опущення[^\n]*\n(.*?)(?=^#{1,4}\s|\Z)", sw, re.S | re.M)
    return m.group(1) if m else None


def active_keys(ans_text, schema):
    keys = set(re.findall(r"^\s*(VP-\d+)\s*:", ans_text, re.M))
    if schema.exists():
        s = schema.read_text(encoding="utf-8")
        for m in re.finditer(r"^\s*(VP-\d+)\s*:(.*?)(?=^\s*VP-\d+\s*:|\Z)", s, re.S | re.M):
            if re.search(r"deprecated:\s*true", m.group(2)[:600]):
                keys.discard(m.group(1))
    return keys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--client-dir", required=True)
    ap.add_argument("--package", required=True)
    ap.add_argument("--mode", choices=["apply", "fix", "reconcile"], default="apply")
    ap.add_argument("--tag-before"); ap.add_argument("--tag-after")
    ap.add_argument("--incident-file"); ap.add_argument("--incident-id")
    a = ap.parse_args()
    cd, pkg = Path(a.client_dir), Path(a.package)
    res = []
    add = lambda i, s, m="": res.append({"id": i, "status": s, "msg": m})
    out = lambda: (print(json.dumps(res, ensure_ascii=False, indent=1)), 1 if any(r["status"] == "FAIL" for r in res) else 0)[1]
    log = cd / "config-log.md"
    if not log.exists():
        add("config-log", "FAIL", "config-log.md не знайдено"); return out()
    text = log.read_text(encoding="utf-8")
    sec = sections(text)
    miss_h = [h for h in ["Шапка", "Параметри анкети", "Доналаштування поза анкетою", "Ролі/групи", "Модулі", "Виправлення", "Запити в D-02"] if h not in sec]
    add("headers", "FAIL" if miss_h else "PASS", f"немає розділів: {miss_h}" if miss_h else "")
    main_rows = rows(sec.get("Параметри анкети", [])) + rows(sec.get("Доналаштування поза анкетою", [])) + rows(sec.get("Виправлення", []))
    # колонки: 0 ID,1 дата,2 джерело,3 параметр,4 значення(нормалізоване),5 шлях,6 якір,7 read-back,8 хто,9 статус,10 погодження
    full = [r for r in main_rows if len(r) > 9]
    bad = [r[0] for r in full if r[9] not in ALLOWED]
    bad_ap = [r[0] for r in full if r[9] == "відхилення" and (len(r) < 11 or not r[10].strip("-— "))]
    msgs = ([f"недозволені статуси: {bad}"] if bad else []) + ([f"«відхилення» без погодження: {bad_ap}"] if bad_ap else [])
    add("status-allowed", "FAIL" if msgs else "PASS", "; ".join(msgs))
    nrb = [r[0] for r in full if r[9] == "застосовано" and (r[7] in {"", "-", "—"} or norm(r[7]) != norm(r[4]))]
    add("readback", "FAIL" if nrb else "PASS", f"немає/не збігається read-back (після нормалізації): {nrb}" if nrb else "")
    nan = [r[0] for r in main_rows if len(r) > 6 and not ANCHOR.match(r[6].strip("`").replace("\\|", "|"))]
    add("anchor", "FAIL" if nan else "PASS", f"якір не за форматом: {nan}" if nan else "")
    ans = cd / "answers.yaml"
    if ans.exists():
        keys = active_keys(ans.read_text(encoding="utf-8"), pkg / "templates" / "answers.yaml")
        got = [r[2] for r in rows(sec.get("Параметри анкети", [])) if len(r) > 2 and r[2].startswith("VP-")]
        miss, extra = keys - set(got), set(got) - keys
        dup = {k for k in got if got.count(k) > 1}
        if a.mode == "apply":
            b = miss or extra or dup
            add("vp-coverage", "FAIL" if b else "PASS", f"немає: {sorted(miss)}, зайві: {sorted(extra)}, дублі: {sorted(dup)}" if b else "")
        else:
            add("vp-coverage", "SKIP", "лише в режимі apply")
        sow = cd / "sow.md"
        waits = [r for r in full if r[9] == "очікує відповіді"]
        if sow.exists() and waits:
            part = assumptions(sow.read_text(encoding="utf-8"))
            if part is None:
                add("sow-assumptions", "MANUAL", "у sow.md немає розділу «Допущення»; перевірити людині")
            else:
                badw = [r[0] for r in waits if not re.search(r"\b" + re.escape(r[2]) + r"\b", part)]
                add("sow-assumptions", "FAIL" if badw else "PASS", f"ключ не в допущеннях SOW: {badw}" if badw else "")
    else:
        add("vp-coverage", "SKIP", "answers.yaml не знайдено")
    fg = cd / "fit-gap.md"
    if fg.exists():
        fgs = set(re.findall(r"\b(FG-\d+)\b[^\n]*доналаштуванн", fg.read_text(encoding="utf-8")))
        got = {r[2] for r in rows(sec.get("Доналаштування поза анкетою", [])) if len(r) > 2}
        if a.mode == "apply":
            b = fgs - got
            add("fg-coverage", "FAIL" if b else "PASS", f"немає FG: {sorted(b)}" if b else "")
        else:
            add("fg-coverage", "SKIP", "лише в режимі apply")
    else:
        add("fg-coverage", "SKIP", "fit-gap.md не знайдено")
    roles = rows(sec.get("Ролі/групи", []))
    good = [r for r in roles if len(r) > 2 and re.fullmatch(r"\d+", r[2].strip())]
    if a.mode == "apply":
        add("roles", "PASS" if good else "FAIL", "" if good else "немає жодного рядка групи з числом у колонці кількості")
    else:
        add("roles", "SKIP", "лише в режимі apply")
    mods = rows(sec.get("Модулі", []))
    badm = [r[0] for r in mods if len(r) > 2 and r[2] != "installed"]
    badv = [r[0] for r in mods if len(r) > 3 and r[1] and r[3] and normv(r[1]) != normv(r[3])]
    if a.mode == "apply":
        add("modules", "FAIL" if (badm or badv or not mods) else "PASS",
            "; ".join(x for x in [f"не installed: {badm}" if badm else "", f"версія != очікуваної: {badv}" if badv else "", "розділ порожній" if not mods else ""] if x))
        addons = pkg / "addons"
        if addons.is_dir():
            names = {p.parent.name for p in addons.glob("*/__manifest__.py")}
            lack = sorted(names - {r[0] for r in mods})
            add("modules-set", "FAIL" if lack else "PASS", f"модулі addons/ поза журналом (робоча копія; для тегу — git show): {lack}" if lack else "")
        else:
            add("modules-set", "SKIP", "package/addons не знайдено у робочій копії")
    else:
        add("modules", "SKIP", "лише в режимі apply")
    pii, fio = [], []
    for i, l in enumerate(text.splitlines(), 1):
        l2 = DATE.sub("", l)
        cells = [re.sub(r"[\s()-]", "", c) for c in re.split(r"\|", l2)] + [l2]
        if EMAIL.search(l2) or any(PHONE.search(c) for c in cells):
            pii.append(i)
    for l in sec.get("Ролі/групи", []):
        if FIO.search(l): fio.append(l[:40])
    add("pii", "FAIL" if pii else "PASS", f"email/телефон у рядках {pii[:10]}" if pii else "")
    if fio:
        add("pii-fio", "MANUAL", f"схоже на ПІБ у «Ролі/групи»: {fio[:3]}")
    add("connection", "SKIP", "виконує runner за журналом запуску (connection.db після кожного виклику)")
    if a.mode == "fix":
        if a.tag_before and a.tag_after:
            add("tag-unchanged", "PASS" if a.tag_before == a.tag_after else "FAIL", f"{a.tag_before} -> {a.tag_after}" if a.tag_before != a.tag_after else "")
        else:
            add("tag-unchanged", "SKIP", "передайте --tag-before/--tag-after (значення project.test_tag до/після)")
        if a.incident_file and a.incident_id:
            f = Path(a.incident_file)
            lines = [l for l in f.read_text(encoding="utf-8").splitlines() if a.incident_id in l] if f.exists() else []
            ok = bool(lines) and any("виправлено на тесті" in l and "B-12" in l for l in lines)
            add("incident-status", "PASS" if ok else "FAIL", "" if ok else f"рядок {a.incident_id} без статусу «виправлено на тесті — передано в B-12»")
        else:
            add("incident-status", "SKIP", "передайте --incident-file і --incident-id (для режиму (в) не застосовується)")
    if a.mode == "reconcile":
        dr = cd / "config-drift.md"
        if not dr.exists():
            add("drift-file", "FAIL", "config-drift.md не знайдено")
        else:
            dt = dr.read_text(encoding="utf-8")
            head = dt[:800]
            drows = [r for r in rows(dt.splitlines()) if len(r) >= 5]
            badc = [r[0] for r in drows if r[-1].strip().lower() not in DRIFT_CLASSES]
            probs = ([] if re.search(r"\bpackage/v\d+\.\d+(\.\d+|-odoo\d+)?\b", head) else ["немає тегу звірки в шапці"]) + \
                    ([f"недозволений клас: {badc}"] if badc else []) + ([] if drows else ["таблиця порожня"])
            add("drift-file", "FAIL" if probs else "PASS", "; ".join(probs))
    if "застосовано в прод" in text.lower():
        add("no-prod-status", "FAIL", "знайдено «застосовано в прод»")
    else:
        add("no-prod-status", "PASS")
    return out()


if __name__ == "__main__":
    sys.exit(main())
