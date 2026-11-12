#!/usr/bin/env python3
"""Детермінований рендер автоекспорту стану флоу (C-02). Лише stdlib. Запуск: python3 -I state_export.py <cmd> ...

Підкоманди:
  check-ids --ids FILE.json|-      перевірка ідентифікаторів data_sources (масив рядків); exit 1 при будь-якому FAIL
  render --snapshot PATH [PATH..] --out DIR [--merge]   JSON-знімок(и) -> flow/*.md, clients/REGISTRY.md (PATH: файл або тека частин)
  verify --snapshot PATH [PATH..] --dir DIR [--merge]   повторний рендер у пам'яті і порівняння з DIR; exit 1 при diff
  prune --older-than YYYY-MM --dir DIR   видалити запуски старші за місяць зі знімка-бази й файлів flow/runs/ (строк зберігання)
--merge: частини зливаються з накопиченою базою DIR/flow/.snapshot.json за стабільними ключами (рядки, яких немає у частинах,
зберігаються; рішення лише додаються); render оновлює базу. verify --merge бере шапку з бази й показує розбіжність
«файли репо != Odoo» для рядків із частин. Без --merge знімок має бути повним.
  check-decisions --rows FILE.json|-   veto-batch (К-08): позначка «внесено AI від імені власника» + посилання; exit 1 при FAIL
  stats --runs FILE.json [FILE..]   групування запусків за step x skill_version x ISO-тиждень (JSON і md)
Формат знімка — references/export-format.md. Значення збігів PII у вивід не друкуються.
"""
import argparse, datetime, difflib, json, os, re, sys, tempfile
from collections import OrderedDict

SCHEMA_VERSION = 1
BASE = "flow/.snapshot.json"
RUN_KEYS = ("step", "scope", "attempt", "result", "finished", "skill_versions", "usage", "task", "review_rounds", "human_rounds")
HEADER = "<!-- AUTO-EXPORT з Odoo (flow). Не редагувати. -->\nЗнято: {taken} · SHA репо: {sha} · Джерело: odoo:flow · Версія схеми: 1\n"

PII = OrderedDict([
    ("email", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+", re.I)),
    ("phone", re.compile(r"(?<![\w:])(\+?380\d{9}|0\d{9})(?!\w)")),
    ("url", re.compile(r"\bhttps?://[^\s)>\]]+|\b[\w-]+(\.[\w-]+)+\.(com|net|org|ua|io|dev|app)\b", re.I)),
    ("ip", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("secret", re.compile(r"(password|passwd|pwd|api[_-]?key|token|secret)\s*[:=]\s*\S+", re.I)),
    ("pib", re.compile(r"\b[А-ЯІЇЄҐ][а-яіїєґ'’-]+\s+[А-ЯІЇЄҐ][а-яіїєґ'’-]+\s+[А-ЯІЇЄҐ][а-яіїєґ'’-]+\b")),
    ("edrpou_iban", re.compile(r"\bUA\d{2}[\s\d]{20,}|ЄДРПОУ\D{0,5}\d{8}\b", re.I)),
])
ID_RE = {
    "aikb": re.compile(r"^aikb:[\w.:-]+$"),
    "fathom": re.compile(r"^fathom:[\w.:-]+$"),
    "odoo-mcp": re.compile(r"^odoo-mcp:[\w-]+$"),
    "drive": re.compile(r"^drive:[\w-]+$"),
    "gmail": re.compile(r"^gmail:[\w-]+$"),
    "repo": re.compile(r"^repo:[\w./-]+@[0-9a-f]{7,40}$"),
}


def pii_types(text):
    return [n for n, rx in PII.items() if rx.search(text)]


def check_id(s):
    """Повертає (status, reason). Причина — без значення збігу."""
    if not isinstance(s, str) or not s:
        return "FAIL", "not-string"
    if re.search(r"\s", s):
        return "FAIL", "whitespace"
    prefix = s.split(":", 1)[0]
    rx = ID_RE.get(prefix)
    if rx is None:
        return "FAIL", "unknown-prefix"
    if not rx.match(s):
        return "FAIL", "bad-format"
    if prefix != "repo":
        found = pii_types(s.split(":", 1)[1])
        if found:
            return "FAIL", "pii:" + ",".join(found)
    return "PASS", ""


def cmd_check_ids(a):
    raw = sys.stdin.read() if a.ids == "-" else open(a.ids, encoding="utf-8").read()
    ids = json.loads(raw)
    bad = 0
    out = []
    for i, s in enumerate(ids):
        st, why = check_id(s)
        bad += st == "FAIL"
        out.append({"idx": i, "status": st, "reason": why})
    print(json.dumps({"checked": len(ids), "failed": bad, "items": [o for o in out if o["status"] == "FAIL"]}, ensure_ascii=False))
    return 1 if bad else 0


# ---------- знімок ----------
KEYS = {
    "steps": lambda r: "%s|%s" % (r.get("step"), r.get("scope")),
    "clients": lambda r: r.get("client_id"),
    "decisions": lambda r: r.get("decision_id"),
    "runs": lambda r: "%s|%s|%s" % (r.get("step"), r.get("scope"), r.get("attempt")),
    "open_questions": lambda r: "%s|%s|%s" % (r.get("date"), r.get("step"), r.get("question")),
    "ai_stop": lambda r: "%s|%s" % (r.get("type"), r.get("id")),
    "lessons": lambda r: r.get("lsn"),
}


def load_snapshot(paths, base=None, keep_header=False):
    files = []
    for p in paths:
        if os.path.isdir(p):
            files += sorted(os.path.join(p, f) for f in os.listdir(p) if f.endswith(".json"))
        else:
            files.append(p)
    if not files and not base:
        sys.exit("немає файлів знімка")
    snap = {"package": {}}
    merged = {k: OrderedDict() for k in KEYS}
    parts = [json.load(open(f, encoding="utf-8")) for f in files]
    if base and os.path.exists(base):
        parts.insert(0, json.load(open(base, encoding="utf-8")))
    base_hdr = {}
    for i, part in enumerate(parts):
        is_base = bool(base) and os.path.exists(base) and i == 0
        for k in ("taken", "repo_sha", "schema_version"):
            if k in part:
                if is_base:
                    base_hdr[k] = part[k]
                if not (keep_header and not is_base and k != "schema_version"):
                    snap[k] = part[k]
        snap["package"].update(part.get("package", {}))
        for k in KEYS:
            for row in part.get(k, []):
                if k == "runs":
                    row = {x: row[x] for x in RUN_KEYS if x in row}  # білий список; memo тощо не зберігаємо
                key = KEYS[k](row)
                if k == "decisions" and key in merged[k]:
                    continue  # журнал рішень лише доповнюється
                merged[k][key] = row  # останній виграє
    snap.update({k: list(v.values()) for k, v in merged.items()})
    for k in ("taken", "repo_sha"):
        if not snap.get(k):
            sys.exit("у знімку немає поля %s" % k)
    if snap.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
        sys.exit("непідтримувана версія схеми знімка")
    return snap


def nat(v):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", str(v))]


def cell(v):
    if v is None or v == "":
        return "н/д"
    if isinstance(v, bool):
        return "так" if v else "ні"
    if isinstance(v, (list, tuple)):
        return ", ".join(cell(x) for x in v) if v else "—"
    if isinstance(v, dict):
        return "; ".join("%s=%s" % (k, cell(v[k])) for k in sorted(v))
    return str(v).replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


def table(cols, rows):
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(cell(r.get(c)) for c in cols) + " |" for r in rows]
    return "\n".join(out) + "\n"


def scan_pii(snap):
    """Перевіряє всі текстові поля знімка (крім dates/ids формату). Повертає список (шлях, типи) без значень."""
    problems = []
    def walk(x, path):
        if isinstance(x, dict):
            for k, v in x.items():
                walk(v, path + [str(k)])
        elif isinstance(x, list):
            for i, v in enumerate(x):
                walk(v, path + [str(i)])
        elif isinstance(x, str):
            t = pii_types(x)
            if t:
                problems.append((".".join(path), t))
    for k in ("package", "steps", "clients", "decisions", "runs", "open_questions", "ai_stop", "lessons"):
        walk(snap.get(k), [k])
    return problems


def runs_row(r):
    sv = r.get("skill_versions") or {}
    u = r.get("usage") or {}
    return {
        "step": r.get("step"), "scope": r.get("scope"), "attempt": r.get("attempt"), "result": r.get("result"),
        "skill_versions": ", ".join("%s@%s" % (k, sv[k]) for k in sorted(sv)) or None,
        "usage": "cost_usd=%s; in=%s; out=%s" % (u.get("cost_usd", "н/д"), u.get("tokens_in", "н/д"), u.get("tokens_out", "н/д")),
        "задача": r.get("task"),
    }


def render_all(snap):
    h = HEADER.format(taken=snap["taken"], sha=snap["repo_sha"])
    files = OrderedDict()
    pk = snap.get("package", {})
    pkg_rows = [{"поле": k, "значення": pk.get(k)} for k in ("industry", "package_tag", "candidate_tag", "phase", "flow_version")]
    pkg_rows[0]["поле"] = "галузь"
    steps = sorted(snap["steps"], key=lambda r: (nat(r.get("step")), str(r.get("scope"))))
    clients = sorted(snap["clients"], key=lambda r: str(r.get("client_id")))
    crow = [{"клієнт": c.get("client_id"), "стан": c.get("state"), "крок у роботі": c.get("current_step"),
             "прапорці": sorted(c.get("flags") or []), "остання зміна": c.get("changed")} for c in clients]
    srow = [{"step": s.get("step"), "scope": s.get("scope"), "стан": s.get("state"), "спроба": s.get("attempt"),
             "останній звіт (ISO)": s.get("last_report"), "PR": s.get("pr"), "задача": s.get("task")} for s in steps]
    files["flow/state.md"] = (h + "\n# Стан флоу\n\n## Пакет\n" + table(["поле", "значення"], pkg_rows)
        + "\n## Кроки пакета\n" + table(["step", "scope", "стан", "спроба", "останній звіт (ISO)", "PR", "задача"], srow)
        + "\n## Клієнти\n" + table(["клієнт", "стан", "крок у роботі", "прапорці", "остання зміна"], crow))
    dec = sorted(snap["decisions"], key=lambda r: nat(r.get("decision_id")))
    drow = [{"№": d.get("decision_id"), "дата": d.get("date"), "гейт/крок": d.get("gate"), "scope": d.get("scope"),
             "рішення (затверджено/повернено/…)": d.get("decision"), "куди повернуто": d.get("returned_to"),
             "роль автора": d.get("role"), "задача": d.get("task"), "коментар (≤200 символів, без ПІБ/контактів/сум)": (d.get("comment") or "")[:200]} for d in dec]
    files["flow/decisions.md"] = h + "\n# Журнал рішень\n\n" + table(list(drow[0].keys()) if drow else
        ["№", "дата", "гейт/крок", "scope", "рішення (затверджено/повернено/…)", "куди повернуто", "роль автора", "задача", "коментар (≤200 символів, без ПІБ/контактів/сум)"], drow)
    oq = sorted(snap["open_questions"], key=lambda r: (str(r.get("date")), str(r.get("step")), str(r.get("question"))))
    files["flow/open-questions.md"] = h + "\n# Відкриті питання\n\n" + table(["дата", "крок", "питання", "хто відповідає", "статус"],
        [{"дата": q.get("date"), "крок": q.get("step"), "питання": q.get("question"), "хто відповідає": q.get("owner"), "статус": q.get("status")} for q in oq])
    st = sorted(snap["ai_stop"], key=lambda r: (str(r.get("type")), str(r.get("id"))))
    files["flow/ai-stop.md"] = h + "\n# Стоп-лист «AI зупинено»\n\n" + table(["тип", "ідентифікатор", "причина", "дата", "хто вніс"],
        [{"тип": s.get("type"), "ідентифікатор": s.get("id"), "причина": s.get("reason"), "дата": s.get("date"), "хто вніс": s.get("by")} for s in st])
    months = OrderedDict()
    for r in sorted(snap["runs"], key=lambda r: (str(r.get("finished") or "")[:7], nat(r.get("step")), str(r.get("scope")), int(r.get("attempt") or 0))):
        months.setdefault((r.get("finished") or "н/д")[:7], []).append(runs_row(r))
    for m, rows in months.items():
        files["flow/runs/%s.md" % m] = h + "\n# Запуски %s\n\n" % m + table(["step", "scope", "attempt", "result", "skill_versions", "usage", "задача"], rows)
    # уроки: flow/lessons/** пише лише skill-retro (INDEX.md, LSN-xxx.md); тут лише облік у знімку (lessons) для stats/reconcile
    reg_cols = [("ідентифікатор клієнта", "client_id"), ("стан", "state"), ("пілот (так/ні)", "pilot"), ("package_tag", "package_tag"),
                ("candidate_tag", "candidate_tag"), ("go-live (дата)", "go_live"), ("alias тест-бази", "test_alias"),
                ("згода на агрегати (так/ні)", "aggregates_consent"),
                ("стоп-лист (так/ні)", "ai_stop"), ("SHA останнього APPROVE B-04/B-11", "approve_sha"), ("мітка Gmail", "gmail_label"), ("file id договору", "contract_file_id")]
    files["clients/REGISTRY.md"] = h + "\n# Реєстр клієнтів\n\n" + table([c for c, _ in reg_cols], [{c: cl.get(k) for c, k in reg_cols} for cl in clients])
    return files


def build(a, merge=False, snapshot=None):
    base = os.path.join(a.dir if hasattr(a, "dir") and a.dir else a.out, BASE) if merge else None
    snap = load_snapshot(snapshot if snapshot is not None else a.snapshot, base, keep_header=(a.cmd == "verify" and merge))
    probs = scan_pii(snap)
    if probs:
        print(json.dumps({"error": "pii-in-snapshot", "fields": [{"path": p, "types": t} for p, t in probs]}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)
    for cl in snap["clients"]:
        for f in ("test_alias",):
            if cl.get(f) and re.search(r"[:/@]", str(cl[f])):
                print(json.dumps({"error": "alias-not-a-name", "client": cl.get("client_id")}, ensure_ascii=False), file=sys.stderr)
                sys.exit(2)
    return render_all(snap), snap


def cmd_render(a):
    files, snap = build(a, a.merge)
    if a.merge:
        files = dict(files)
        files[BASE] = json.dumps(snap, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    for rel, text in files.items():
        p = os.path.join(a.out, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w", encoding="utf-8", newline="\n").write(text)
    print(json.dumps({"files": sorted(files), "rows": sum(t.count("\n| ") - 1 for t in files.values())}, ensure_ascii=False))
    return 0


def cmd_verify(a):
    files, snap = build(a, a.merge)
    diffs = []
    for rel, text in files.items():
        p = os.path.join(a.dir, rel)
        cur = open(p, encoding="utf-8").read() if os.path.exists(p) else ""
        if cur != text:
            diffs.append((rel, "".join(list(difflib.unified_diff(cur.splitlines(True), text.splitlines(True), "repo", "render"))[:40])))
    extra = []
    if os.path.isdir(os.path.join(a.dir, "flow/runs")):
        extra = [f for f in os.listdir(os.path.join(a.dir, "flow/runs")) if "flow/runs/" + f not in files and f.endswith(".md")]
    ok = not diffs and not extra
    print(json.dumps({"ok": ok, "changed": [d[0] for d in diffs], "extra_in_repo": extra}, ensure_ascii=False))
    if diffs and a.show:
        for rel, d in diffs:
            print("--- " + rel + "\n" + d)
    return 0 if ok else 1


LINK_RE = re.compile(r"^\s*(odoo:task/\d+(#\d+)?|https?://\S+)\s*$")  # лише в полі link/task
BATCH_MARK = "внесено AI від імені власника"


def cmd_check_decisions(a):
    """veto-batch (К-08): кожен рядок -- позначка в ролі + посилання на повідомлення/задачу, інакше FAIL."""
    rows = json.load(sys.stdin if a.rows == "-" else open(a.rows, encoding="utf-8"))
    res = []
    for r in rows:
        did = r.get("decision_id") or r.get("№") or "?"
        role = str(r.get("role") or r.get("роль автора") or "")
        link = str(r.get("link") or r.get("task") or r.get("задача") or "")  # лише поле посилання, не довільний текст коментаря
        if BATCH_MARK not in role:
            res.append({"id": "DEC-mark", "status": "FAIL", "msg": "%s: немає позначки «%s» у ролі" % (did, BATCH_MARK)})
        elif not LINK_RE.search(link):
            res.append({"id": "DEC-link", "status": "FAIL", "msg": "%s: немає посилання на повідомлення/задачу власника" % did})
        else:
            res.append({"id": "DEC-batch", "status": "PASS", "msg": str(did)})
    if not rows:
        res.append({"id": "DEC-batch", "status": "SKIP", "msg": "немає рядків"})
    print(json.dumps(res, ensure_ascii=False))
    return 1 if any(x["status"] == "FAIL" for x in res) else 0


def cmd_prune(a):
    base = os.path.join(a.dir, BASE)
    if not os.path.exists(base):
        sys.exit("немає бази " + BASE)
    snap = json.load(open(base, encoding="utf-8"))
    keep = [r for r in snap.get("runs", []) if str(r.get("finished") or "")[:7] >= a.older_than]
    removed = len(snap.get("runs", [])) - len(keep)
    snap["runs"] = keep
    open(base, "w", encoding="utf-8", newline="\n").write(json.dumps(snap, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    rd = os.path.join(a.dir, "flow/runs")
    gone = []
    if os.path.isdir(rd):
        for f in sorted(os.listdir(rd)):
            if f.endswith(".md") and f[:-3] < a.older_than:
                os.remove(os.path.join(rd, f))
                gone.append("flow/runs/" + f)
    print(json.dumps({"runs_removed": removed, "files_removed": gone}, ensure_ascii=False))
    return 0


def cmd_stats(a):
    runs = []
    for f in a.runs:
        part = json.load(open(f, encoding="utf-8"))
        if not isinstance(part, list) or not all(isinstance(x, dict) for x in part):
            print("помилка: %s — очікується масив запусків (список словників), а не знімок" % f, file=sys.stderr)
            return 2
        runs += part
    agg = OrderedDict()
    incomplete = 0
    for r in runs:
        if r.get("run_status") == "неповний":
            incomplete += 1
            continue
        d = datetime.datetime.fromisoformat(str(r["finished"]).replace("Z", "+00:00"))
        y, w, _ = d.isocalendar()
        sv = r.get("skill_versions") or {}
        key = (r.get("step"), ", ".join("%s@%s" % (k, sv[k]) for k in sorted(sv)) or "н/д", "%d-W%02d" % (y, w))
        g = agg.setdefault(key, {"attempts": 0, "escalations": 0, "returns": 0, "cost_usd": 0.0, "tokens_in": 0, "tokens_out": 0, "review_rounds": 0, "human_rounds": 0})
        g["review_rounds"] += int(r.get("review_rounds") or 0)
        g["human_rounds"] += int(r.get("human_rounds") or 0)
        g["attempts"] += 1
        g["escalations"] += r.get("result") == "escalated"
        g["returns"] += r.get("result") == "returned"
        g["cost_usd"] += float(r.get("cost_usd") or 0)
        g["tokens_in"] += int(r.get("tokens_in") or 0)
        g["tokens_out"] += int(r.get("tokens_out") or 0)
    rows = [dict(step=k[0], skill_version=k[1], week=k[2], **{m: (round(v, 4) if m == "cost_usd" else v) for m, v in g.items()}) for k, g in sorted(agg.items(), key=lambda kv: (nat(kv[0][0]), kv[0][1], kv[0][2]))]
    print(json.dumps({"incomplete_runs": incomplete, "rows": rows}, ensure_ascii=False))
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    c = sp.add_parser("check-ids"); c.add_argument("--ids", required=True); c.set_defaults(f=cmd_check_ids)
    r = sp.add_parser("render"); r.add_argument("--snapshot", nargs="+", required=True); r.add_argument("--out", required=True); r.add_argument("--merge", action="store_true"); r.set_defaults(f=cmd_render)
    v = sp.add_parser("verify"); v.add_argument("--snapshot", nargs="+", required=True); v.add_argument("--dir", required=True); v.add_argument("--show", action="store_true"); v.add_argument("--merge", action="store_true"); v.set_defaults(f=cmd_verify)
    pr = sp.add_parser("prune"); pr.add_argument("--older-than", required=True, help="YYYY-MM"); pr.add_argument("--dir", required=True); pr.set_defaults(f=cmd_prune)
    d = sp.add_parser("check-decisions"); d.add_argument("--rows", required=True, help="JSON-масив рядків або -"); d.set_defaults(f=cmd_check_decisions)
    s = sp.add_parser("stats"); s.add_argument("--runs", nargs="+", required=True); s.set_defaults(f=cmd_stats)
    a = p.parse_args()
    sys.exit(a.f(a))


if __name__ == "__main__":
    main()
