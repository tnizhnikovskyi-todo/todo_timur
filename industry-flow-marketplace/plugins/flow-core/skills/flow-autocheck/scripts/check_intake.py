#!/usr/bin/env python3
"""Автоперевірка анкети власника (INT-*). stdlib. Вивід: JSON [{id,status,msg}]; код виходу 1, якщо є FAIL.
Використання: check_intake.py <OWNER-INTAKE.md> [--brief <файл з питаннями власнику>] [--page owner-page/index.html]
Анкета 0.3.0 — 6 пунктів (editions*, icp*, todo_data*, brand*, materials*, do_not_do) + блок `defaults:` (AI-замовчування, не блокує) + необов'язкове `tariffs`.
INT-file  — файл є, непорожній, містить YAML-блок (```yaml ...```).
INT-block — усі блокуючі ключі (позначені * у плані; список нижче) заповнені: не null, не «уточнити», не плейсхолдер {{…}}.
--allow-empty: INT-block лише за наявністю ключів (крок prepare, поля ще порожні).
INT-dup   — питання в --brief/--page (рядки з «?») не перепитують те, що вже визначає анкета (редакції, ICP, дані ToDo, бренд, формати).
INT-legacy — WARN «вилучено в 0.3.0», якщо в анкеті лишились pricing.*, do_not_reject.*, ambition.scope/evidence_gate, rounds.human_target (не вимагаються й не блокують).
Блокуючі поля й переліки значень читаються з шаблона анкети flow-research/skills/owner-questionnaire/references/owner-intake-template.md
(або --template <файл>). Розмітка в YAML-блоці шаблона: `*` після ключа (`editions*:`) або в коментарі рядка (`# * ce|ee|both`) — блокуючий;
позначка `*` на ключі верхнього рівня без `*` на підключах робить блокуючими всі підключі; перелік значень — у коментарі як `a|b|c`.
Шаблон не знайдено або в ньому немає розмітки — запасний зашитий перелік (BLOCKING/ENUMS) і WARN INT-template."""
import argparse, importlib.util, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
_s = importlib.util.spec_from_file_location("_miniyaml", os.path.join(HERE, "_miniyaml.py"))
Y = importlib.util.module_from_spec(_s); _s.loader.exec_module(Y)

# блокуючі ключі (0.3.0, анкета 6 пунктів): ключ верхнього рівня -> перелік підключів (порожній = значення самого ключа).
# Шостий пункт `do_not_do` (список «що точно не робимо») може бути порожнім і не блокує.
BLOCKING = {
    "editions": [],
    "icp": ["min_employees", "legal_forms", "light_tariff_fop"],
    "todo_data": ["allowed_sources", "mode", "internal_raw_storage", "push_deidentified"],
    "brand": ["materials"],
    "materials": ["formats", "languages"],
}
ENUMS = {"editions": {"ce", "ee", "both"}, "brand.materials": {"todo", "white_label"}}
# ключі й підключі, вилучені в 0.3.0 (LESSONS §24): наявність = WARN, не FAIL
REMOVED = ["pricing", "do_not_reject", "ambition.scope", "ambition.evidence_gate", "rounds.human_target"]
# теми питань, які анкета вже закриває: ключ анкети -> regex питання (рядок із «?»)
DUP = {
    "editions": r"(?i)(\bCE\b.*\b(чи|or)\b.*\bEE\b|яку\s+редакці|які\s+редакці|редакці\w*\s+(CE|EE|Odoo))",
    "icp": r"(?i)(мінімальн\w+\s+(кількість\s+)?(працівник|штат)|для\s+яких\s+компаній|ICP|ФОП\b.*(легк|тариф))",
    "todo_data": r"(?i)(чи\s+можна\s+(брати|використ\w+)\s+дані\s+ToDo|дозвіл\w*\s+на\s+(внутріш|дані)|дані\s+ToDo.*(дозвол|можна))",
    "brand": r"(?i)(white[- ]?label|під\s+яким\s+брендом|бренд\w*\s+(матеріал|ToDo))",
    "materials": r"(?i)(які\s+формат\w*\s+(матеріал|відео)|reels|вертикальн\w+\s+відео)",
}
TEMPLATE = os.path.normpath(os.path.join(HERE, "..", "..", "..", "..", "flow-research", "skills", "owner-questionnaire", "references", "owner-intake-template.md"))
res = []


def read_template(path):
    """-> (blocking dict, enums dict) з шаблона або None, якщо немає/без розмітки."""
    try:
        t = open(path, encoding="utf-8").read()
    except OSError:
        return None
    m = re.search(r"```ya?ml\s*\n(.*?)```", t, re.S)
    if not m:
        return None
    blocking, enums, cur, cur_star, any_sub_star = {}, {}, None, False, {}
    for l in m.group(1).splitlines():
        mm = re.match(r"^(\s*)([A-Za-z_][\w]*)(\*?)\s*:(.*)$", l)
        if not mm:
            continue
        ind, key, star, rest = len(mm.group(1)), mm.group(2), bool(mm.group(3)), mm.group(4)
        comment = rest.split("#", 1)[1] if "#" in rest else ""
        star = star or "*" in comment
        path_key = key if ind == 0 else (f"{cur}.{key}" if cur else key)
        en = re.search(r"\b([\w-]+(?:\|[\w-]+)+)\b", comment)
        if en:
            enums[path_key] = set(en.group(1).split("|"))
        if ind == 0:
            cur, cur_star = key, star
            if star:
                blocking.setdefault(key, [])
        elif cur:
            if star:
                blocking.setdefault(cur, [])
                blocking[cur].append(key); any_sub_star[cur] = True
            elif cur_star:
                blocking.setdefault(cur, []).append(key)
    for k in list(blocking):
        if any_sub_star.get(k):
            pass
    return (blocking, enums) if blocking else None


def add(i, status, msg=""):
    res.append({"id": i, "status": status, "msg": msg})


def unfilled(v):
    if v is None:
        return True
    if isinstance(v, str):
        s = v.strip().lower()
        return s in ("", "уточнити", "?", "tbd", "null") or v.strip() == "TODO" or s.startswith("{{")
    if isinstance(v, (list, dict)):
        return len(v) == 0
    return False


def strip_stars(d):
    """Ключі анкети, скопійовані з розміткою шаблона (`editions*:`), нормалізуються: кінцева `*` знімається."""
    if isinstance(d, dict):
        return {(k.rstrip("*").strip() if isinstance(k, str) else k): strip_stars(v) for k, v in d.items()}
    return d


def get_block(text):
    m = re.search(r"```ya?ml\s*\n(.*?)```", text, re.S)
    return m.group(1) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("intake"); ap.add_argument("--brief"); ap.add_argument("--page"); ap.add_argument("--template"); ap.add_argument("--allow-empty", action="store_true", help="режим prepare: перевірити лише наявність ключів, не заповненість")
    a = ap.parse_args()
    try:
        text = open(a.intake, encoding="utf-8").read()
    except OSError:
        text = ""
    blk = get_block(text) if text.strip() else None
    if not text.strip():
        add("INT-file", "FAIL", f"Немає або порожній {a.intake}: запусти A-02b (owner-questionnaire prepare)")
    elif blk is None:
        add("INT-file", "FAIL", "У анкеті немає YAML-блоку ```yaml``` з полями (editions, icp, todo_data, brand, materials, do_not_do)")
    else:
        add("INT-file", "PASS")
    if blk is None:
        add("INT-block", "SKIP", "немає YAML-блоку"); add("INT-dup", "SKIP", "немає YAML-блоку")
        print(json.dumps(res, ensure_ascii=False, indent=1)); sys.exit(1)
    try:
        data = Y.loads(blk) or {}
    except Exception as e:  # noqa
        add("INT-block", "FAIL", f"YAML-блок не розібрано: {str(e)[:80]}")
        add("INT-dup", "SKIP", "анкету не розібрано"); print(json.dumps(res, ensure_ascii=False, indent=1)); sys.exit(1)
    data = strip_stars(data)
    tpl = read_template(a.template or TEMPLATE)
    if tpl and any(k in tpl[0] for k in ("pricing", "do_not_reject", "ambition", "market")):
        tpl = None  # шаблон 0.2.0 (ще не оновлено): блокуючі ключі брати із зашитого переліку 0.3.0
    if tpl:
        BL, EN = tpl
    else:
        BL, EN = BLOCKING, ENUMS
        add("INT-template", "WARN", "Шаблон анкети owner-intake-template.md не знайдено або без розмітки `*` — використано запасний перелік блокуючих полів; перевір, що він збігається з шаблоном")
    bad = []
    for k, subs in BL.items():
        v = data.get(k)
        if a.allow_empty:
            if k not in data or (subs and not isinstance(v, dict)) or any(x not in v for x in subs):
                bad.append(k)
            continue
        if not subs:
            if unfilled(v):
                bad.append(k)
        elif not isinstance(v, dict):
            bad.append(k)
        else:
            bad += [f"{k}.{s}" for s in subs if s not in v or (unfilled(v[s]) and not isinstance(v[s], bool) and v[s] != 0)]
    for k, allowed in ({} if a.allow_empty else EN).items():
        cur = data
        for p in k.split("."):
            cur = cur.get(p) if isinstance(cur, dict) else None
        if cur is not None and not unfilled(cur) and str(cur).lower() not in allowed:
            bad.append(f"{k}={cur} (дозволено: {'|'.join(sorted(allowed))})")
    legacy = []
    for r in REMOVED:
        for root, pref in ((data, ""), (data.get("defaults") if isinstance(data.get("defaults"), dict) else {}, "defaults.")):
            cur = root
            for p_ in r.split("."):
                cur = cur.get(p_) if isinstance(cur, dict) else None
            if cur is not None:
                legacy.append(pref + r)
    if legacy:
        add("INT-legacy", "WARN", "вилучено в 0.3.0 (не вимагається, ігнорується): " + ", ".join(legacy))
    add("INT-block", not bad and "PASS" or "FAIL", "" if not bad else "Заповни блокуючі поля анкети (запитай власника в A-02b): " + ", ".join(bad))
    # INT-dup
    dups = []
    for label, path in (("brief", a.brief), ("page", a.page)):
        if not path:
            continue
        try:
            lines = open(path, encoding="utf-8").read().splitlines()
        except OSError:
            add("INT-dup", "FAIL", f"Немає файлу {path}"); continue
        for n, l in enumerate(lines, 1):
            if "?" not in l:
                continue
            clean = re.sub(r"<[^>]+>", " ", l)
            for key, rx in DUP.items():
                if key in data and not unfilled(data[key]) and re.search(rx, clean):
                    dups.append(f"{os.path.basename(path)}:{n} ({key})")
    if a.brief or a.page:
        if not any(r["id"] == "INT-dup" for r in res):
            add("INT-dup", "FAIL" if dups else "PASS",
                "" if not dups else "Прибери питання, які вже закриває анкета (покажи їх як «з анкети», не питай знову): " + "; ".join(dups[:10]))
    else:
        add("INT-dup", "SKIP", "--brief/--page не передано")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(1 if any(r["status"] == "FAIL" for r in res) else 0)


if __name__ == "__main__":
    main()
