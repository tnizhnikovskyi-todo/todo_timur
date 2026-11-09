#!/usr/bin/env python3
"""Автоперевірки A-04 (PP-*). stdlib. Вивід: JSON [{id, status, msg}]. Код виходу 1, якщо є FAIL.

Denylist назв клієнтів = ЛИШЕ колонка «назва клієнта/проєкту» sources.md (за рядком заголовка таблиці) + stdin
(лише з прапорцем --stdin: імена учасників Fathom, по одному в рядку). Ідентифікатори (project_id, репозиторії, recording_id) і підстава обробки
в denylist не потрапляють (flow-core/references/pii-patterns.md, flow-research/references/sources-format.md).

Запуск: check_past_projects.py --doc <past-projects.md> --sources <_input/sources.md> --repo <корінь репо>
        [--repo alias=<шлях іншого репо>] [--scope-files <where>[,<where2>]] [--base <git.base>] [--head <git.head>] [--stdin]
        check_past_projects.py --self-test   (шаблон із references/ + приклад sources має давати всі PASS)
Шлях у repo:<шлях>@<sha>: перший --repo без alias — основний; `repo:<alias>/<шлях>@<sha>` — репо з `--repo alias=<шлях>`."""
import argparse, json, os, re, subprocess, sys, tempfile
from pathlib import Path

SECTIONS = ["Проєкти й джерела", "Що вже робили", "Модулі для повторного використання",
            "Болі клієнтів", "Прогалини", "Для шлюзу: проєкти в цільовому сегменті"]
ID = re.compile(r"\b(aikb:\S+|fathom:\S+|repo:\S+)")
CODE = re.compile(r"П-\d{2}")
# Збігається з flow-core/references/pii-patterns.md (змінювати разом)
PII = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+", re.I),
    "phone": re.compile(r"(?<![\w:])(\+?380\d{9}|0\d{9})(?!\w)", re.I),
    "url/host": re.compile(r"\bhttps?://[^\s)>\]]+|\b[\w-]+(\.[\w-]+)+\.(com|net|org|ua|io|dev|app)\b", re.I),
    "ip": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "secret": re.compile(r"(password|passwd|pwd|api[_-]?key|token|secret)\s*[:=]\s*\S+", re.I),
    "sum": re.compile(r"(\d[\d\s.,]*\s?(грн|₴|\$|€|USD|UAH|EUR|тис\.|млн|млрд))|([$€₴]\s?\d)", re.I),
    "edrpou_iban": re.compile(r"\bUA\d{2}[\s\d]{20,}|ЄДРПОУ\D{0,5}\d{8}\b", re.I),
    "fio": re.compile(r"\b[А-ЯІЇЄҐ][а-яіїєґ'’-]+\s+[А-ЯІЇЄҐ][а-яіїєґ'’-]+\s+[А-ЯІЇЄҐ][а-яіїєґ'’-]+(ович|евич|ївна|івна|ична)\b"),
}
ODOO_VER = re.compile(r"^\d{1,2}\.0\.")  # 16.0.1.0 - версія модуля, не IP


def cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def rows(sec):
    res = []
    for l in sec.splitlines():
        if not l.startswith("|"):
            continue
        if re.match(r"^\|[\s:|-]+\|$", l):
            if res:
                res.pop()  # попередній рядок - заголовок таблиці
            continue
        res.append(cells(l))
    return res


def sections(text):
    parts = re.split(r"^## ", text, flags=re.M)[1:]
    return {p.split("\n", 1)[0].strip(): p.split("\n", 1)[1] if "\n" in p else "" for p in parts}


def sources_info(path):
    """-> (codes, modes, deny, problems). Колонки визначаються за рядком заголовка."""
    codes, modes, deny, problems = [], {}, set(), []
    name_i = basis_i = None
    for l in Path(path).read_text(encoding="utf-8").splitlines():
        if not l.startswith("|"):
            continue
        cs = cells(l)
        if not cs or re.match(r"^[\s:|-]+$", "".join(cs)):
            continue
        if not CODE.fullmatch(cs[0]):
            if name_i is None and "код" in cs[0].lower():  # рядок заголовка
                for i, c in enumerate(cs):
                    lc = c.lower()
                    if "назва" in lc and name_i is None:
                        name_i = i
                    if "підстав" in lc:
                        basis_i = i
            continue
        if cs[0] in codes:
            problems.append(f"дубль коду {cs[0]}")
        codes.append(cs[0])
        only = any("лише звіти" in c.lower() for c in cs)
        if basis_i is not None:
            b = cs[basis_i].strip().lower() if basis_i < len(cs) else ""
            if b in ("", "-", "немає", "нема"):
                only = True  # немає підстави -> лише звіти (DATA_POLICY)
        modes[cs[0]] = "only_reports" if only else "full"
        if name_i is not None and name_i < len(cs):
            for part in re.split(r"[;,]", cs[name_i]):
                if len(part.strip()) >= 4:
                    deny.add(part.strip().lower())
    if name_i is None:
        problems.append("у sources.md не знайдено колонку «назва клієнта/проєкту» в рядку заголовка")
    if not codes:
        problems.append("у sources.md немає жодного коду П-xx")
    return codes, modes, deny, problems


def git(repo, *a):
    return subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True)


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def pii_hits(text, deny, fname):
    hits = []
    for k, rx in PII.items():
        for m in rx.finditer(text):
            if k == "ip" and ODOO_VER.match(m.group(0)):
                continue
            hits.append(f"{k}:{fname}:{line_of(text, m.start())}")
    low = text.lower()
    for d in sorted(deny):
        i = low.find(d)
        if i >= 0:
            hits.append(f"denylist:{fname}:{line_of(text, i)}")
    return hits


def changed_files(repo, base, head):
    """Змінені + нові (untracked) файли відносно HEAD/робочого дерева; з --base - ще й закомічене base..head."""
    names = set()
    st = git(repo, "status", "--porcelain", "-uall").stdout
    for l in st.splitlines():
        p = l[3:]
        if " -> " in p:
            names.update(x.strip('"') for x in p.split(" -> "))
        else:
            names.add(p.strip('"'))
    if base:
        names |= set(git(repo, "diff", "--name-only", f"{base}...{head or 'HEAD'}").stdout.split())
    return names


def run_checks(doc, sources, repos, scope_files="", base="", head="", stdin_names=()):
    out = []

    def add(i, ok, msg=""):
        out.append({"id": i, "status": "PASS" if ok else "FAIL", "msg": "" if ok else msg})

    text = Path(doc).read_text(encoding="utf-8")
    secs = sections(text)
    miss = [s for s in SECTIONS if s not in secs]
    add("PP-sections", not miss, "немає: " + ", ".join(miss))
    codes, modes, deny, problems = sources_info(sources)
    add("PP-sources", not problems, "; ".join(problems))
    deny |= {n.strip().lower() for n in stdin_names if len(n.strip()) >= 3}

    doc_codes = set(CODE.findall(text))
    bad, absent = sorted(doc_codes - set(codes)), sorted(set(codes) - doc_codes)
    add("PP-codes", not bad and not absent, f"вигадані: {bad}; пропущені: {absent}")

    bad_rows = []
    for s in SECTIONS[1:5]:
        for r in rows(secs.get(s, "")):
            line = " | ".join(r)
            if "немає даних" in line.lower():
                continue
            if not ID.search(line) or not CODE.search(line):
                bad_rows.append(f"{s}: {r[0][:40]}")
    add("PP-src", not bad_rows, "; ".join(bad_rows[:5]))

    viol = []
    for r in rows(secs.get(SECTIONS[0], "")):
        line = " | ".join(r)
        for c in set(CODE.findall(r[0] if r else "")):
            if modes.get(c) == "only_reports" and "fathom:" in line:
                viol.append(c)
    for s in SECTIONS[1:5]:
        for r in rows(secs.get(s, "")):
            line = " | ".join(r)
            cs_ = set(CODE.findall(line))
            if "fathom:" in line:
                viol += [c for c in cs_ if modes.get(c) == "only_reports" and len(cs_) == 1]
    add("PP-mode", not viol, f"fathom: для режиму «лише звіти»: {sorted(set(viol))}")

    def repo_for(p):
        for alias, path in repos.items():
            if alias and p.startswith(alias + "/"):
                return path, p[len(alias) + 1:]
        return repos.get(""), p

    mod_rows = [r for r in rows(secs.get(SECTIONS[2], "")) if "немає даних" not in " ".join(r).lower()]
    repo_bad, ver_bad = [], []
    for r in mod_rows:
        line = " | ".join(r)
        found = list(re.finditer(r"repo:(\S+?)@([0-9a-fA-F]{4,40})", line))
        if not found:
            repo_bad.append(f"{r[0]}: немає repo:")
        for m in found:
            rp, sha = m.groups()
            root, rel = repo_for(rp)
            if root is None or git(root, "cat-file", "-e", f"{sha}:{rel}").returncode != 0:
                repo_bad.append(f"{rp}@{sha}")
        if len(r) < 4 or not r[2].strip("- ") or not r[3].strip("- "):
            ver_bad.append(r[0])
    add("PP-repo", not repo_bad, "; ".join(repo_bad[:5]))
    add("PP-ver", not ver_bad, "; ".join(ver_bad[:5]))

    rep = secs.get("Що вже робили", "").split("### Повторювані вимоги")
    rep_bad = [r[0] for r in rows(rep[1])
               if "немає даних" not in " ".join(r).lower() and len(set(CODE.findall(r[1] if len(r) > 1 else ""))) < 2] if len(rep) > 1 else []
    add("PP-repeat", not rep_bad, "; ".join(rep_bad[:5]))

    yes = sum(1 for r in rows(secs.get(SECTIONS[0], "")) if len(r) > 2 and r[2].lower().startswith("так"))
    m = re.search(r"N\s*=\s*(\d+)", secs.get(SECTIONS[5], ""))
    add("PP-count", bool(m) and int(m.group(1)) == yes, f"у таблиці {yes}, у розділі {m.group(1) if m else 'немає N'}")

    hits = pii_hits(text, deny, Path(doc).name)
    add("PP-pii", not hits, "збіги (значення не виводяться): " + ", ".join(hits[:8]))

    main_repo = repos.get("") or next(iter(repos.values()), ".")
    src = str(Path(sources).resolve())
    ign = git(main_repo, "check-ignore", "-q", src).returncode == 0
    tracked = bool(git(main_repo, "ls-files", src).stdout.strip())
    add("PP-gitignore", ign and not tracked, "sources.md не ігнорується або відстежується - СТОП-ІНЦИДЕНТ")

    if scope_files:
        allowed = [x for x in scope_files.split(",") if x]
        changed = changed_files(main_repo, base, head)
        extra = sorted(c for c in changed
                       if not any(c == a or (a.endswith("/") and c.startswith(a)) for a in allowed))
        inp = sorted(c for c in changed if "/_input/" in "/" + c)
        stray = sorted(f for f in os.listdir(Path(sources).parent) if f != Path(sources).name)
        add("PP-scope", not extra and not inp and not stray,
            "; ".join(filter(None, ["зайве: " + ", ".join(extra[:5]) if extra else "",
                                    "_input/ змінено/додано до git: " + ", ".join(inp[:3]) if inp else "",
                                    "сторонні файли в _input/: " + ", ".join(stray[:3]) if stray else ""])))
    return out


def self_test():
    here = Path(__file__).resolve().parent
    tpl = (here.parent / "references" / "past-projects-template.md").read_text(encoding="utf-8")
    fmt = here.parents[2] / "references" / "sources-format.md"
    errs = []
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        sh = lambda *a: subprocess.run(["git", "-C", str(d), *a], capture_output=True, text=True)
        sh("init", "-q"); sh("config", "user.email", "t@example.invalid"); sh("config", "user.name", "t")
        (d / "odoo_addons/td_edge").mkdir(parents=True)
        (d / "odoo_addons/td_edge/__manifest__.py").write_text("{'name':'x','version':'16.0.1.0'}")
        (d / ".gitignore").write_text("docs/industries/*/_input/\n")
        sh("add", "-A"); sh("commit", "-qm", "init")
        sha = sh("rev-parse", "--short", "HEAD").stdout.strip()
        inp = d / "docs/industries/test/_input"; inp.mkdir(parents=True)
        (inp / "sources.md").write_text(
            "| код П-xx | назва клієнта/проєкту | AIKB project_id | репозиторії | Fathom recording_id | підстава обробки | режим читання |\n"
            "|---|---|---|---|---|---|---|\n"
            "| П-01 | Вигаданий Клієнт А | proj_example1 | odoo_addons/td_edge | rec_0001 | згода/договір, пункт про AI | повний |\n"
            "| П-02 | Вигаданий Клієнт Б | proj_example2 | | | немає | лише звіти |\n"
            "| П-03 | Вигаданий Клієнт В | proj_example3 | | | згода | повний |\n", encoding="utf-8")
        doc = d / "docs/industries/test/past-projects.md"
        doc.write_text(tpl.replace("abc1234", sha), encoding="utf-8")
        rel = "docs/industries/test/past-projects.md"
        run = lambda **kw: run_checks(str(doc), str(inp / "sources.md"), {"": str(d)}, scope_files=rel, **kw)
        bad = [o for o in run() if o["status"] != "PASS"]
        if bad:
            errs.append(f"шаблон + sources мають давати всі PASS: {bad}")
        if fmt.exists():  # приклад із sources-format.md парситься, імена беруться лише з колонки назви
            codes, _, deny, pr = sources_info(fmt)
            if pr or "вигаданий клієнт а" not in deny or any(x in deny for x in ("rec_0001", "proj_example1", "немає")):
                errs.append(f"sources-format.md: denylist {sorted(deny)}, проблеми {pr}")
        doc.write_text(tpl.replace("abc1234", sha) + "\nВигаданий Клієнт А скаржився.\n", encoding="utf-8")
        if all(o["status"] == "PASS" for o in run() if o["id"] == "PP-pii"):
            errs.append("PP-pii має ловити назву клієнта")
        doc.write_text(tpl.replace("abc1234", sha), encoding="utf-8")
        (d / "docs/industries/test/stray.md").write_text("x")
        if [o for o in run() if o["id"] == "PP-scope"][0]["status"] != "FAIL":
            errs.append("PP-scope має ловити новий (untracked) сторонній файл")
    print(json.dumps({"self_test": "PASS" if not errs else "FAIL", "errors": errs}, ensure_ascii=False, indent=1))
    sys.exit(1 if errs else 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc"); ap.add_argument("--sources")
    ap.add_argument("--repo", action="append", default=[])
    ap.add_argument("--scope-files", default=""); ap.add_argument("--base", default=""); ap.add_argument("--head", default="")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--stdin", action="store_true", help="читати імена учасників Fathom зі stdin (по одному в рядку)")
    a = ap.parse_args()
    if a.self_test:
        self_test()
    if not a.doc or not a.sources:
        ap.error("потрібні --doc і --sources")
    repos = {}
    for r in a.repo or ["."]:
        alias, _, path = r.partition("=")
        if path:
            repos[alias] = path
        else:
            repos.setdefault("", r)
    names = sys.stdin.read().splitlines() if a.stdin else []
    out = run_checks(a.doc, a.sources, repos, a.scope_files, a.base, a.head, names)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    sys.exit(1 if any(o["status"] == "FAIL" for o in out) else 0)


if __name__ == "__main__":
    main()
