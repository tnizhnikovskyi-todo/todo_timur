#!/usr/bin/env python3
"""Автоперевірки файлового боку B-06 (MIG-*). Запуск: python3 -I check_migration.py --client-dir clients/<к> --tag <тег> [--mode main|reconcile|return] [--readme <README тегу>]
Те, що потребує бази Odoo (MIG-conn), агент записує з журналу запуску. Вихід — JSON-масив {id,status,msg}."""
import argparse, json, os, re, subprocess, sys

HEADINGS = ["База клієнта", "Джерела й обсяги", "Маппінг", "Послідовність", "Валідація й очистка", "Таблиця звірки",
            "Перевірка часу операцій", "Ризики", "Фінальний імпорт при cutover", "Виправлення даних", "Запити в D-02"]
SECRET = re.compile(r"(password|passwd|pwd|api[_-]?key|token|secret)\s*[:=]|://[^/\s]*@|[\w-]+(?:\.[\w-]+)+:\d{2,5}\b", re.I)
TAGRX = re.compile(r"(?:package/)?v?\d+\.\d+(?:\.\d+)?(?![\w.-])")
MODEL_RX = re.compile(r"\b\d{2}b?_[a-z][a-z0-9_.]*[a-z0-9]")


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


def norm_tag(t):
    return re.sub(r"^(package/)?v?", "", t.strip().rstrip(".-;,"))


def seq_of(text):
    out = []
    for m in MODEL_RX.findall(text or ""):
        m = re.sub(r"\.csv$", "", m)
        if m not in out:
            out.append(m)
    return out


def num(s):
    try:
        return float(s.replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def mapping_columns(path):
    """Простий stdlib-розбір mapping.yaml: {template: {ключі columns}}."""
    res, cur, cind = {}, None, None
    for ln in open(path, encoding="utf-8").read().splitlines():
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        ind = len(ln) - len(ln.lstrip())
        m = re.match(r"\s*-?\s*template:\s*['\"]?([^\s'\"#]+)", ln)
        if m:
            cur, cind = m.group(1), None
            res.setdefault(cur, set())
            continue
        if cur and re.match(r"\s*columns:\s*(#.*)?$", ln):
            cind = ind
            continue
        if cur and cind is not None:
            if ind <= cind:
                cind = None
                continue
            k = re.match(r"\s*['\"]?([^\s'\":#]+)['\"]?\s*:", ln)
            if k and ind == (len(ln) - len(ln.lstrip())) and not ln.lstrip().startswith("-"):
                res[cur].add(k.group(1)) if ind <= cind + 4 else None
    return res


def required_missing(mp, a):
    """Заголовки шаблонів тегу, яких немає серед ключів columns у mapping.yaml. None — шаблони недоступні."""
    out = []
    for tpl, keys in mapping_columns(mp).items():
        if a.templates and os.path.isfile(os.path.join(a.templates, tpl)):
            txt = open(os.path.join(a.templates, tpl), encoding="utf-8-sig").read()
        else:
            txt = run(["git", "show", a.tag + ":package/master-data/" + tpl], a.repo)
        if not txt.strip():
            return None
        head = [h.strip() for h in txt.splitlines()[0].split(",") if h.strip() and h.strip() != "id"]
        out += ["%s: %s" % (tpl, h) for h in head if h not in keys]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--client-dir", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--mode", default="main")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--templates", help="тека шаблонів майстер-даних тегу (інакше git show <тег>:package/master-data/<файл>)")
    ap.add_argument("--readme", help="README майстер-даних тегу (інакше git show <тег>:package/master-data/README.md)")
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
    tags = []
    for ln in base.splitlines():
        if re.search(r"[Тт]ег", ln):
            tags += [m.group(0) for m in TAGRX.finditer(ln)]
    ok_tag = bool(tags) and all(norm_tag(t) == norm_tag(a.tag) for t in tags)
    add("MIG-tag", "PASS" if ok_tag else "FAIL",
        "" if ok_tag else ("у плані: %s; очікується: %s" % (", ".join(tags), a.tag) if tags else "тег у «Базі клієнта» не знайдено"))
    add("MIG-registry", "FAIL" if SECRET.search(base) else "PASS", "облікові дані/хост у «Базі клієнта»" if SECRET.search(base) else "")

    rows = table_rows(section(plan, "Таблиця звірки"))
    if a.mode in ("main", "reconcile"):
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
        firsts = {r[0].strip() for r in rows}
        nocov = [n for n in names if n.strip() not in firsts]
        add("MIG-coverage", "FAIL" if nocov else ("PASS" if names else "SKIP"), "немає рядка звірки: " + ", ".join(nocov) if nocov else "")
        seq = section(plan, "Послідовність") or ""
        readme = open(a.readme, encoding="utf-8").read() if a.readme and os.path.isfile(a.readme) else \
            run(["git", "show", a.tag + ":package/master-data/README.md"], a.repo)
        ref_seq, plan_seq = seq_of(section(readme, "Порядок імпорту") or readme), seq_of(seq)
        common = [m for m in plan_seq if m in ref_seq]
        if ref_seq and common:
            exp = [m for m in ref_seq if m in common]
            add("MIG-order", "PASS" if common == exp else "FAIL",
                "" if common == exp else "порядок у плані відрізняється від README тегу: " + ", ".join(common))
        else:
            pos = [m.start() for m in re.finditer(r"залишк|сальдо", seq, re.I)]
            if not pos:
                add("MIG-order", "SKIP", "README тегу недоступний (немає --readme/git) і залишків у плані немає")
            else:
                last = max(pos) >= len(seq) // 2
                add("MIG-order", "PASS" if last else "FAIL", "" if last else "залишки мають бути в кінці послідовності")
        mp = os.path.join(a.client_dir, "migration", "mapping.yaml")
        if os.path.isfile(mp):
            miss = required_missing(mp, a)
            if miss is None:
                add("MIG-required", "SKIP", "шаблони тегу недоступні (немає --templates/git) — пункт PM вручну")
            else:
                add("MIG-required", "FAIL" if miss else "PASS", ("не покрито колонок шаблону: " + "; ".join(miss[:10])) if miss else "")
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
