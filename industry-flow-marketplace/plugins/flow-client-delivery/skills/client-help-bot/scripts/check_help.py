#!/usr/bin/env python3
"""Автоперевірки бота-помічника (B-07). Вихід: JSON [{id, status, msg}]. Лише stdlib.
Використання: check_help.py --dir clients/<к>/help-bot [--prod-alias prod-ro-<к>] [--allowlist <prod-read-allowlist.md>]
              [--prod-db <db>] [--mode prepare|answer] [--drafts <файл; у 0.1 не використовується runner-ом>]
Чого не можна перевірити без вхідних файлів — SKIP, не PASS. Шаблони ПДн узгоджені з flow-core/references/pii-patterns.md (змінювати разом)."""
import argparse, json, re
from pathlib import Path

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?<![\w:])(\+?380\d{9}|0\d{9})(?!\w)")
IBAN = re.compile(r"\bUA\d{2}[\s\d]{20,}|ЄДРПОУ\D{0,5}\d{8}\b")
URL = re.compile(r"\bhttps?://[^\s)>\]]+")
IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
SECRET = re.compile(r"(password|passwd|pwd|api[_-]?key|token|secret)\s*[:=]\s*\S+", re.I)
FIO = re.compile(r"\b[А-ЯІЇЄҐ][а-яіїєґ'’-]+\s+[А-ЯІЇЄҐ][а-яіїєґ'’-]+\s+[А-ЯІЇЄҐ][а-яіїєґ'’-]+\b")
PII = [("email", EMAIL), ("phone", PHONE), ("iban", IBAN), ("url", URL), ("ip", IP), ("secret", SECRET), ("fio", FIO)]
CODES = re.compile(r"\b[A-D]-\d{2}\b|\btd\.\w+|\bINC-\d+")
READ_TOOLS = {"odoo_search_read", "odoo_get_fields"}
REQ = {"help-log.md": ["Реєстр питань", "Передано в support-desk", "Прогалини матеріалів", "Журнал запусків"],
       "query-log.md": ["Журнал запитів до проду"], "kb-index.md": ["Теми", "Чек-лист передумов"]}
HELP_COLS = ["id", "джерело", "дата", "роль", "переказ", "джерела", "статус", "чернетка"]
QUERY_COLS = ["час", "id", "connection", "інструмент", "модель", "домен", "поля", "записів", "результат"]


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
        elif cells and cells[0]:
            rows.append(dict(zip(hdr, cells)))
    return hdr or [], rows


def col(row, name):
    for k, v in row.items():
        if k.startswith(name):
            return v
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True); ap.add_argument("--prod-alias"); ap.add_argument("--allowlist")
    ap.add_argument("--mode", default="answer", choices=["prepare", "answer"]); ap.add_argument("--drafts"); ap.add_argument("--prod-db")
    a = ap.parse_args()
    res = []
    add = lambda i, s, m="": res.append({"id": i, "status": s, "msg": m})
    d = Path(a.dir)
    texts = {n: (d / n).read_text(encoding="utf-8") if (d / n).exists() else None for n in REQ}
    names = REQ if a.mode == "answer" else {"kb-index.md": REQ["kb-index.md"]}
    if a.mode == "prepare" and texts["kb-index.md"] and re.search(r"^Стан:\s*бот не підключено:\s*\S+", texts["kb-index.md"], re.M):
        add("HB-columns", "PASS"); add("HB-prepare", "PASS", "бот не підключено (рядок «Стан» у kb-index.md); чек-лист не потрібен")
        print(json.dumps(res, ensure_ascii=False, indent=1)); return
    miss = sorted({f"{n}: немає файла" if texts[n] is None else f"{n}: немає розділу {h}"
            for n, hs in names.items() for h in hs if texts[n] is None or h not in sections(texts[n])})
    add("HB-columns", "FAIL" if miss else "PASS", "; ".join(miss))
    if a.mode == "answer" and not miss:
        sec = sections(texts["help-log.md"]); qh, hrows = table(sec["Реєстр питань"])
        sec_q = sections(texts["query-log.md"]); qh2, qrows = table(sec_q["Журнал запитів до проду"])
        bad = [c for c in HELP_COLS if not any(h.startswith(c) for h in qh)] + [c for c in QUERY_COLS if not any(h.startswith(c) for h in qh2)]
        if bad:
            res[0] = {"id": "HB-columns", "status": "FAIL", "msg": "немає колонок: " + ", ".join(bad)}
        # HB-conn
        # клітинка: "<alias> (db <db>)"; alias порівнюється точно (перший токен), db — з --prod-db
        def parse(c):
            m = re.match(r"^\s*(\S+)\s*(?:\(\s*db\s+([^)\s]+)\s*\))?", c)
            return (m.group(1), m.group(2)) if m else ("", None)
        wrong, nodb = [], []
        for r in qrows:
            al, db = parse(col(r, "connection"))
            if al == "flow": continue
            if al != a.prod_alias: wrong.append(col(r, "connection") or "(порожньо)")
            elif a.prod_db and db != a.prod_db: wrong.append(col(r, "connection") + f" (очікується db {a.prod_db})")
            elif not a.prod_db: nodb.append(col(r, "id"))
        if not a.prod_alias: add("HB-conn", "SKIP", "немає --prod-alias")
        elif wrong: add("HB-conn", "FAIL", "інше підключення: " + ", ".join(sorted(set(wrong))))
        elif nodb: add("HB-conn", "SKIP", "alias збігається, db не звірено: немає --prod-db")
        else: add("HB-conn", "PASS")
        # HB-readonly
        nr = [col(r, "інструмент") for r in qrows if col(r, "інструмент") not in READ_TOOLS]
        body = texts["help-log.md"] + texts["query-log.md"]
        write = re.search(r"^ODOO:|odoo_(create|write|execute)", body, re.M)
        add("HB-readonly", "FAIL" if (nr or write) else "PASS", "недозволений інструмент або запис" if (nr or write) else "")
        # HB-allowlist
        if a.allowlist and Path(a.allowlist).exists():
            _, arows = table(sections(Path(a.allowlist).read_text(encoding="utf-8")).get("Формат рядка (його читає `check_help.py`)", []))
            allow = {col(r, "модель"): {f.strip() for f in col(r, "поля").split(",")} for r in arows}
            errs = []
            for r in qrows:
                m, fl = col(r, "модель"), col(r, "поля")
                if col(r, "інструмент") == "odoo_get_fields" and m in allow: continue
                fields = {f.strip() for f in fl.split(",") if f.strip()}
                if m not in allow: errs.append(f"{m}: немає в allow-list")
                elif not fields or fl.strip() in ("*", "усі", "—"): errs.append(f"{m}: без fields")
                elif fields - allow[m]: errs.append(f"{m}: {sorted(fields - allow[m])}")
            add("HB-allowlist", "FAIL" if errs else "PASS", "; ".join(errs))
        else:
            add("HB-allowlist", "SKIP", "немає --allowlist")
        # HB-logged
        logged = {col(r, "id") for r in qrows}
        unl = [col(r, "id") for r in hrows if "prod-ro:" in col(r, "джерела") and col(r, "id") not in logged]
        add("HB-logged", "FAIL" if unl else "PASS", "без query-log: " + ", ".join(unl) if unl else "")
        # HB-sources
        ns = [col(r, "id") for r in hrows if col(r, "статус").lower().startswith("чернетка") and not col(r, "джерела").strip()]
        add("HB-sources", "FAIL" if ns else "PASS", "без джерела: " + ", ".join(ns) if ns else "")
        # HB-limits
        add("HB-limits", "FAIL" if len(qrows) > 60 else "SKIP", f"запитів {len(qrows)} > 60" if len(qrows) > 60 else "ліміт 60 запитів у межах; ліміт 20 тредів і запитів на запуск скрипт не бачить (немає розмежування запусків) — перевіряє Підтримка за «Журналом запусків»")
        # HB-pii, HB-codes
        pii = []
        for n in ("help-log.md", "query-log.md"):
            for i, l in enumerate(texts[n].splitlines(), 1):
                pii += [f"{t}:{n}:{i}" for t, p in PII if p.search(l)]
        dr = Path(a.drafts).read_text(encoding="utf-8") if a.drafts and Path(a.drafts).exists() else None
        codes = [f"{n}:{i}" for n, tx in (("help-log.md", texts["help-log.md"]), ("drafts", dr or "")) for i, l in enumerate(tx.splitlines(), 1) if n == "drafts" and CODES.search(l)]
        if dr:
            pii += [f"{t}:drafts:{i}" for i, l in enumerate(dr.splitlines(), 1) for t, p in PII if p.search(l)]
        add("HB-pii", "FAIL" if pii else "PASS", ", ".join(pii[:10]))
        add("HB-codes", "SKIP" if dr is None else ("FAIL" if codes else "PASS"), "чернетки не зберігаються в репо: HB-codes і ПДн чернеток — MANUAL (Підтримка)" if dr is None else ", ".join(codes[:10]))
    elif a.mode == "prepare" and not miss:
        t = texts["kb-index.md"]; sec = sections(t)
        boxes = [l for l in sec["Чек-лист передумов"] if l.strip().startswith("- [")]
        open_ = [l for l in boxes if l.strip().startswith("- [ ]")]
        add("HB-prepare", "FAIL" if (not boxes or open_) else "PASS", f"незаповнених пунктів: {len(open_)}" if open_ else ("немає чек-листа" if not boxes else ""))
        add("HB-pii", "FAIL" if any(p.search(t) for _, p in PII) else "PASS")
        mrows = table(sec.get("Моделі allow-list для цього клієнта", []))[1]
        badm = [col(r, "модель") for r in mrows if not re.match(r"(так|не перевірено|вилучено)", col(r, "підтверджено").lower())]
        add("HB-models", "FAIL" if badm else "PASS", "немає значення «Підтверджено» (так / не перевірено / вилучено): " + ", ".join(badm) if badm else "")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
