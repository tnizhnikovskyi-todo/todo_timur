#!/usr/bin/env python3
"""Автоперевірки config-log.md (B-04). Вихід: JSON [{id, status, msg}]. Лише stdlib.
Чого не можна перевірити без бази/прапорців — SKIP, не PASS."""
import argparse, json, re, sys
from pathlib import Path

ALLOWED = {"застосовано", "відхилення", "очікує відповіді", "очікує: виконує людина", "передано в D-02"}
ANCHOR = re.compile(r"^[\w.]+:[^|]*\|.*:[\w.]+$")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE = re.compile(r"\+?\d[\d\s()-]{8,}\d")


def sections(text):
    out, cur = {}, None
    for line in text.splitlines():
        m = re.match(r"^##\s+(.*)", line)
        if m:
            cur = m.group(1).strip(); out[cur] = []
        elif cur:
            out[cur].append(line)
    return out


def rows(lines):
    res = []
    for l in lines:
        if l.startswith("|") and not re.match(r"^\|[\s:-]+\|", l):
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", l.strip().strip("|"))]
            if cells and cells[0] != "ID" and cells[0].upper() != "ID":
                res.append(cells)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--client-dir", required=True)
    ap.add_argument("--package", required=True)
    ap.add_argument("--mode", choices=["apply", "fix", "reconcile"], default="apply")
    a = ap.parse_args()
    cd = Path(a.client_dir)
    res = []
    add = lambda i, s, m="": res.append({"id": i, "status": s, "msg": m})
    log = cd / "config-log.md"
    if not log.exists():
        add("config-log", "FAIL", "config-log.md не знайдено"); print(json.dumps(res, ensure_ascii=False)); return 1
    text = log.read_text(encoding="utf-8")
    sec = sections(text)
    for h in ["Шапка", "Параметри анкети", "Доналаштування поза анкетою", "Ролі/групи", "Модулі", "Виправлення", "Запити в D-02"]:
        if h not in sec:
            add("headers", "FAIL", f"немає розділу «{h}»")
    main_rows = rows(sec.get("Параметри анкети", [])) + rows(sec.get("Доналаштування поза анкетою", [])) + rows(sec.get("Виправлення", []))
    # колонки: 0 ID,1 дата,2 джерело,3 параметр,4 значення,5 шлях,6 якір,7 read-back,8 хто,9 статус,10 погодження
    bad_status = [r[0] for r in main_rows if len(r) > 9 and r[9] not in ALLOWED]
    add("status-allowed", "FAIL" if bad_status else "PASS", f"недозволені статуси: {bad_status}" if bad_status else "")
    nrb = [r[0] for r in main_rows if len(r) > 9 and r[9] == "застосовано" and (not r[7] or r[7] in {"-", "—"} or r[7] != r[4])]
    add("readback", "FAIL" if nrb else "PASS", f"немає/не збігається read-back: {nrb}" if nrb else "")
    nan = [r[0] for r in main_rows if len(r) > 6 and not ANCHOR.match(r[6].strip("`").replace("\\|", "|"))]
    add("anchor", "FAIL" if nan else "PASS", f"якір не за форматом: {nan}" if nan else "")
    nap = [r[0] for r in main_rows if len(r) > 10 and r[9] == "відхилення" and not r[10].strip("-— ")]
    if nap:
        add("status-allowed", "FAIL", f"«відхилення» без погодження: {nap}")
    # vp-coverage
    ans = cd / "answers.yaml"
    if ans.exists():
        keys = set(re.findall(r"^\s*(VP-\d+)\s*:", ans.read_text(encoding="utf-8"), re.M))
        got = [r[2] for r in rows(sec.get("Параметри анкети", [])) if len(r) > 2 and r[2].startswith("VP-")]
        miss, extra = keys - set(got), set(got) - keys
        dup = {k for k in got if got.count(k) > 1}
        bad = (a.mode == "apply") and (miss or extra or dup)
        add("vp-coverage", "FAIL" if bad else ("PASS" if a.mode == "apply" else "SKIP"),
            f"немає: {sorted(miss)}, зайві: {sorted(extra)}, дублі: {sorted(dup)}" if bad else "")
        sow = cd / "sow.md"
        if sow.exists():
            sw = sow.read_text(encoding="utf-8")
            waits = [r for r in main_rows if len(r) > 9 and r[9] == "очікує відповіді"]
            badw = [r[0] for r in waits if r[2] not in sw]
            add("sow-assumptions", "FAIL" if badw else "PASS", f"ключ не в допущеннях SOW: {badw}" if badw else "")
    else:
        add("vp-coverage", "SKIP", "answers.yaml не знайдено")
    # fg-coverage
    fg = cd / "fit-gap.md"
    if fg.exists():
        fgs = set(re.findall(r"\b(FG-\d+)\b[^\n]*доналаштуванн", fg.read_text(encoding="utf-8")))
        got = {r[2] for r in rows(sec.get("Доналаштування поза анкетою", [])) if len(r) > 2}
        add("fg-coverage", "FAIL" if (a.mode == "apply" and fgs - got) else "PASS", f"немає FG: {sorted(fgs - got)}" if fgs - got else "")
    else:
        add("fg-coverage", "SKIP", "fit-gap.md не знайдено")
    roles = rows(sec.get("Ролі/групи", []))
    add("roles", ("FAIL" if (a.mode == "apply" and not roles) else "PASS") if roles or a.mode == "apply" else "SKIP",
        "розділ порожній" if (a.mode == "apply" and not roles) else "існування груп у res.groups скрипт не бачить; підтверджує крок 6")
    mods = rows(sec.get("Модулі", []))
    badm = [r[0] for r in mods if len(r) > 2 and r[2] != "installed"]
    add("modules", "FAIL" if badm else ("PASS" if mods else "SKIP"), f"не installed: {badm}" if badm else "множину з addons/ тегу перевіряє крок 3")
    pii = [i for i, l in enumerate(text.splitlines(), 1) if EMAIL.search(l) or PHONE.search(l)]
    add("pii", "FAIL" if pii else "PASS", f"email/телефон у рядках {pii[:10]}" if pii else "")
    add("connection", "SKIP", "перевіряється за журналом запуску runner (connection.db після кожного виклику)")
    if a.mode == "fix":
        add("incident-status", "SKIP", "статус рядка інциденту перевіряє runner у hypercare.md/support-log.md")
        add("tag-unchanged", "SKIP", "порівняти тег у проєкті до/після (поля flow)")
    if "застосовано в прод" in text.lower():
        add("no-prod-status", "FAIL", "знайдено «застосовано в прод»")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 1 if any(r["status"] == "FAIL" for r in res) else 0


if __name__ == "__main__":
    sys.exit(main())
