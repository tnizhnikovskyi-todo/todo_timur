#!/usr/bin/env python3
"""Автоперевірки файлового боку B-06 (MIG-*). Запуск: python3 -I check_migration.py --client-dir clients/<к> --tag <тег> [--mode main|return]
Те, що потребує бази Odoo (MIG-conn), агент записує з журналу запуску. Вихід — JSON-масив {id,status,msg}."""
import argparse, json, os, re, subprocess, sys

HEADINGS = ["База клієнта", "Джерела й обсяги", "Маппінг", "Послідовність", "Валідація й очистка", "Таблиця звірки",
            "Перевірка часу операцій", "Ризики", "Фінальний імпорт при cutover", "Виправлення даних", "Запити в D-02"]
SECRET = re.compile(r"(password|passwd|api[_-]?key|token|login|https?://)", re.I)


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True).stdout


def section(text, title):
    m = re.search(r"^##\s+" + re.escape(title) + r"\s*$(.*?)(?=^##\s|\Z)", text, re.S | re.M)
    return m.group(1) if m else None


def table_rows(body):
    rows = []
    for ln in (body or "").splitlines():
        if ln.strip().startswith("|") and not re.match(r"^\|[\s\-:|]+\|?$", ln.strip()):
            rows.append([c.strip() for c in ln.strip().strip("|").split("|")])
    return rows[1:] if rows else []


def num(s):
    try:
        return float(s.replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--client-dir", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--mode", default="main")
    ap.add_argument("--repo", default=".")
    a = ap.parse_args()
    out = []
    add = lambda i, s, m="": out.append({"id": i, "status": s, "msg": m})
    plan_p = os.path.join(a.client_dir, "migration-plan.md")
    if not os.path.isfile(plan_p):
        add("MIG-headings", "FAIL", "немає migration-plan.md")
        print(json.dumps(out, ensure_ascii=False)); sys.exit(1)
    plan = open(plan_p, encoding="utf-8").read()

    miss = [h for h in HEADINGS if not re.search(r"^##\s+" + re.escape(h) + r"\s*$", plan, re.M)]
    add("MIG-headings", "FAIL" if miss else "PASS", "немає розділів: " + ", ".join(miss) if miss else "")

    base = section(plan, "База клієнта") or ""
    tags = re.findall(r"[Тт]ег[^\n]*?(v?\d+\.\d+\.\d+\S*)", base)
    add("MIG-tag", "PASS" if tags and all(t == a.tag for t in tags) else "FAIL",
        "" if tags else "тег у «Базі клієнта» не знайдено")
    add("MIG-registry", "FAIL" if SECRET.search(base) else "PASS", "облікові дані/хост у «Базі клієнта»" if SECRET.search(base) else "")

    rows = table_rows(section(plan, "Таблиця звірки"))
    if a.mode == "main":
        # колонки: 0 довідник,1 модель,2 тип,3 зап.джерело,4 сума джерело,5 зап.Odoo,6 сума Odoo,7 розбіжн.,8 пропуски
        empty_src = [r[0] for r in rows if len(r) > 4 and (not r[3] or not r[4])]
        add("MIG-source", "waiting_human" if empty_src or not rows else "PASS",
            ("колонки джерела порожні: " + ", ".join(empty_src[:10])) if empty_src else ("таблиця порожня" if not rows else ""))
        bad = []
        for r in rows:
            if len(r) < 9 or any(x in ("", "—") for x in r[3:7]):
                continue
            src_n, odoo_n, sum_s, sum_o = num(r[3]), num(r[5]), num(r[4]), num(r[6])
            if sum_s is not None and sum_o is not None and sum_s != sum_o:
                bad.append(r[0])
            elif src_n is not None and odoo_n is not None and src_n != odoo_n and not re.search(r"[A-Z_]{3,}", r[8]):
                bad.append(r[0])
        add("MIG-recon", "FAIL" if bad else ("PASS" if rows else "SKIP"), "розбіжності без пояснення: " + ", ".join(bad) if bad else "")
        src = section(plan, "Джерела й обсяги")
        names = [r[0] for r in table_rows(src) if r and r[0]]
        have = " ".join(r[0] for r in rows)
        nocov = [n for n in names if n not in have]
        add("MIG-coverage", "FAIL" if nocov else ("PASS" if names else "SKIP"), "немає рядка звірки: " + ", ".join(nocov) if nocov else "")
        seq = section(plan, "Послідовність") or ""
        pos = [m.start() for m in re.finditer(r"залишк|сальдо", seq, re.I)]
        add("MIG-order", "SKIP", "порівняння з README тегу виконати git show; залишки згадано: %d" % len(pos)) if not pos else \
            add("MIG-order", "PASS" if max(pos) >= len(seq) // 2 else "FAIL", "залишки мають бути в кінці послідовності")
        mp = os.path.join(a.client_dir, "migration", "mapping.yaml")
        if os.path.isfile(mp):
            tpl = run(["git", "ls-tree", "--name-only", a.tag, "package/master-data/"], a.repo).split()
            add("MIG-required", "SKIP", "перевірка обов'язкових колонок за %d шаблонами тегу — виконати вручну/скриптом шаблонів" % len(tpl))
        else:
            add("MIG-required", "FAIL", "немає migration/mapping.yaml")
    else:
        fixes = table_rows(section(plan, "Виправлення даних"))
        add("MIG-return", "PASS" if fixes else "FAIL", "" if fixes else "немає запису у «Виправлення даних»")

    drafts = run(["git", "ls-files", "*план_міграції_*"], a.repo).split()
    add("MIG-draft", "FAIL" if drafts else "PASS", ", ".join(drafts))
    tracked = run(["git", "ls-files", a.client_dir], a.repo).split()
    leak = [f for f in tracked if "/_input/" in f or (f.endswith(".csv") and "/migration/" in f)]
    add("MIG-git", "FAIL" if leak else "PASS", "дані в git: " + ", ".join(leak[:5]) if leak else "")
    d2 = section(plan, "Запити в D-02") or ""
    old = run(["git", "show", "HEAD:" + plan_p], a.repo)
    oldd2 = section(old, "Запити в D-02") if old else None
    if oldd2 is None:
        add("MIG-d02", "SKIP", "попередньої версії немає")
    else:
        col = lambda t: [r[-1] for r in table_rows(t) if r]
        add("MIG-d02", "PASS" if col(d2)[:len(col(oldd2))] == col(oldd2) else "FAIL", "")
    print(json.dumps(out, ensure_ascii=False))
    sys.exit(1 if any(o["status"] == "FAIL" for o in out) else 0)


if __name__ == "__main__":
    main()
