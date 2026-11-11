#!/usr/bin/env python3
"""Автоперевірки A-04 (PP-*). stdlib. Вивід: JSON [{id, status, msg}]. Код виходу 1, якщо є FAIL.

Denylist назв клієнтів = ЛИШЕ колонка «назва клієнта/проєкту» sources.md (за рядком заголовка таблиці) + stdin
(лише з прапорцем --stdin: імена учасників Fathom, по одному в рядку). Ідентифікатори (project_id, репозиторії, recording_id) і підстава обробки
в denylist не потрапляють (flow-core/references/pii-patterns.md, flow-research/references/sources-format.md).

Запуск: check_past_projects.py --doc <past-projects.md> --sources <_input/sources.md> --repo <корінь репо>
        [--repo alias=<шлях іншого репо>] [--scope-files <where>[,<where2>]] [--base <git.base>] [--head <git.head>] [--stdin] [--no-fathom]
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


ALWAYS_OK = ("observations/",)  # runner комітить сюди окремим комітом (flow-step-runner); завжди дозволено


# Відомі вхідні файли сусідніх кроків у _input/ (A-05 crm.csv; README.md теки). Решта видимих файлів і тек - PP-input FAIL.
KNOWN_INPUTS = {"README.md", "crm.csv"}  # signals.csv/calls.md A-23 тримає в demand/_input/, не тут


def stray_inputs(sources):
    """Невідомі видимі файли й теки в _input/ (приховані .*, *.bak, *~ і KNOWN_INPUTS ігноруються)."""
    return sorted(f for f in os.listdir(Path(sources).parent)
                  if f != Path(sources).name and f not in KNOWN_INPUTS
                  and not f.startswith(".") and not f.endswith((".bak", "~")))


def sources_repos(path):
    """-> {код: [(репозиторій, ref|None)]}. Колонка «репозиторії»: `шлях@ref`, кілька через `,`/`;`;
    окрема колонка «ref» діє на всі репозиторії рядка без власного @ref. Немає ref -> гілка за замовчуванням."""
    res, repo_i, ref_i = {}, None, None
    for l in Path(path).read_text(encoding="utf-8").splitlines():
        if not l.startswith("|"):
            continue
        cs = cells(l)
        if not cs or re.match(r"^[\s:|-]+$", "".join(cs)):
            continue
        if not CODE.fullmatch(cs[0]):
            if repo_i is None and "код" in cs[0].lower():
                for i, c in enumerate(cs):
                    lc = c.lower().strip()
                    if "репозитор" in lc and repo_i is None:
                        repo_i = i
                    if lc == "ref" or lc.startswith("ref ") or lc.startswith("ref("):
                        ref_i = i
            continue
        if repo_i is None or repo_i >= len(cs):
            continue
        col_ref = cs[ref_i].strip() if ref_i is not None and ref_i < len(cs) else ""
        items = []
        for part in re.split(r"[;,]", cs[repo_i]):
            part = part.strip()
            if not part:
                continue
            if re.match(r"^[\w.-]+@[\w.-]+:", part) or "://" in part:  # SSH/URL з @ - не шлях@ref; PP-ref дає FAIL
                items.append((part, None))
                continue
            r, _, ref = part.rpartition("@") if "@" in part else (part, "", "")
            items.append((r.strip(), (ref.strip() or col_ref) or None))
        res[cs[0]] = items
    return res


def run_checks(doc, sources, repos, scope_files="", base="", head="", stdin_names=(), no_fathom=False):
    out = []

    def add(i, ok, msg="", warn=False):
        out.append({"id": i, "status": "PASS" if ok else ("WARN" if warn else "FAIL"), "msg": "" if ok else msg})

    text = Path(doc).read_text(encoding="utf-8")
    secs = sections(text)
    # підрозділ «### Модулі власної ERP» (без repo:/П-xx) виділяється з розділу модулів і перевіряється окремо (PP-erp)
    erp_rx = re.compile(r"^### Модулі власної ERP[^\n]*\n(.*?)(?=^### |\Z)", re.M | re.S)
    erp_m = erp_rx.search(secs.get(SECTIONS[2], ""))
    erp_sub = erp_m.group(1) if erp_m else None
    if erp_m:
        secs[SECTIONS[2]] = erp_rx.sub("", secs[SECTIONS[2]])
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
                if no_fathom:
                    viol.append("fathom заборонено DATA_POLICY")
                elif len(cs_) == 1:
                    viol += [c for c in cs_ if modes.get(c) == "only_reports"]
                else:  # кілька кодів: потрібен формат «П-xx fathom:…» для кожного fathom:
                    pairs = re.findall(r"(П-\d{2})\s+fathom:", line)
                    if len(pairs) < line.count("fathom:"):
                        viol.append(f"рядок з кількома П-xx без пар «П-xx fathom:…» ({r[0][:30]})")
                    viol += [c for c in pairs if modes.get(c) == "only_reports"]
    if no_fathom:
        for r in rows(secs.get(SECTIONS[0], "")):
            if "fathom:" in " | ".join(r):
                viol.append("fathom заборонено DATA_POLICY")
    add("PP-mode", not viol, f"fathom: проти режиму/політики: {sorted(set(viol))}")

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

    # PP-erp: підрозділ власної ERP допустимий лише за рядком «власна ERP» у sources.md; без repo:/П-xx; 4 колонки
    if erp_sub is not None:
        try:
            has_row = bool(re.search(r"^\|\s*власна ERP\s*\|", Path(sources).read_text(encoding="utf-8"), re.M))
        except OSError:
            has_row = False
        erp_rows = [r for r in rows(erp_sub) if "немає даних" not in " ".join(r).lower()]
        erp_bad = []
        if not has_row:
            erp_bad.append("у sources.md немає рядка «власна ERP»")
        for r in erp_rows:
            line = " | ".join(r)
            if "repo:" in line or CODE.search(line):
                erp_bad.append(f"{r[0][:30]}: repo:/П-xx заборонені")
            elif len(r) < 4 or not all(c.strip("- ") for c in r[:4]):
                erp_bad.append(f"{r[0][:30]}: потрібні 4 колонки")
        add("PP-erp", not erp_bad, "; ".join(erp_bad[:5]))

    # PP-ref: коміт repo:<шлях>@<sha> має лежати на ref рядка sources.md, а без ref - на гілці за замовчуванням.
    # Клон береться за репозиторієм рядка (repo:<alias>/...); ref шукається серед <ref>, origin/<ref>, refs/remotes/origin/<ref>, refs/tags/<ref>.
    ref_bad, ref_warn = [], []
    try:
        srepos = sources_repos(sources)
    except OSError:
        srepos = {}
    doc_repos = [(m.group(1), m.group(2)) for r in mod_rows for m in re.finditer(r"repo:(\S+?)@([0-9a-fA-F]{4,40})", " | ".join(r))]
    multi = len(repos) > 1
    main_root = repos.get("") or next(iter(repos.values()), ".")
    dflt = {}

    def default_ref(root):
        if root not in dflt:
            o = git(root, "symbolic-ref", "-q", "refs/remotes/origin/HEAD")
            h = git(root, "symbolic-ref", "-q", "HEAD")
            dflt[root] = o.stdout.strip() if o.returncode == 0 and o.stdout.strip() else ("HEAD" if h.returncode == 0 else None)
        return dflt[root]

    for code, items in srepos.items():
        for rpath, ref in items:
            if not rpath:
                continue
            if "@" in rpath:
                ref_bad.append(f"{code}: SSH-URL/«@» у репозиторії не допускається (лише шлях або owner/repo)")
                continue
            root, rel, aliased = main_root, rpath, False
            for alias, path in repos.items():
                if alias and rpath.startswith(alias + "/"):
                    root, rel, aliased = path, rpath[len(alias) + 1:], True
            roots = [root] if aliased or not multi else [root] + [v for v in repos.values() if v != root]
            target = None
            if ref:
                for rt in roots:
                    for cand in (ref, f"origin/{ref}", f"refs/remotes/origin/{ref}", f"refs/tags/{ref}"):
                        if git(rt, "rev-parse", "--verify", "-q", f"{cand}^{{commit}}").returncode == 0:
                            target = (rt, cand)
                            break
                    if target:
                        break
                if not target:
                    (ref_warn if multi and not aliased else ref_bad).append(
                        f"{code}: ref {ref} не знайдено в клоні" + (" (репозиторій не зіставлено з --repo)" if multi and not aliased else ""))
                    continue
            else:
                dr = default_ref(root)
                if dr is None:
                    ref_warn.append(f"{code}: гілку за замовчуванням не визначено, перевірку пропущено")
                    continue
                target = (root, dr)
            troot, tref = target
            for rp, sha in doc_repos:
                drt, drel = repo_for(rp)
                if drt != troot and not (drt is None and troot == main_root):
                    continue
                if not (drel == rel or drel.startswith(rel.rstrip("/") + "/") or rel.startswith(drel.rstrip("/") + "/")):
                    continue
                if git(troot, "merge-base", "--is-ancestor", sha, tref).returncode != 0:
                    ref_bad.append(f"{rp}@{sha} не на " + (f"ref {ref}" if ref else "гілці за замовчуванням"))
    add("PP-ref", not ref_bad and not ref_warn, "; ".join((ref_bad + ref_warn)[:5]), warn=not ref_bad)

    rep = secs.get("Що вже робили", "").split("### Повторювані вимоги")
    rep_bad = [r[0] for r in rows(rep[1])
               if "немає даних" not in " ".join(r).lower() and len(set(CODE.findall(r[1] if len(r) > 1 else ""))) < 2] if len(rep) > 1 else []
    add("PP-repeat", not rep_bad, "; ".join(rep_bad[:5]))

    yes = sum(1 for r in rows(secs.get(SECTIONS[0], "")) if len(r) > 2 and r[2].lower().startswith("так"))
    m = re.search(r"N\s*=\s*(\d+)", secs.get(SECTIONS[5], ""))
    add("PP-count", bool(m) and int(m.group(1)) == yes, f"у таблиці {yes}, у розділі {m.group(1) if m else 'немає N'}")

    # PP-internal: розділ «Внутрішні сигнали ToDo» (К-07) необов'язковий; якщо є - кожен рядок має клас, вибірку й критерій
    isec = secs.get("Внутрішні сигнали ToDo")
    ibad = []
    if isec is not None and (rows(isec) or "немає даних" not in isec.lower()):
        # «немає даних» вимикає перевірку лише коли в розділі немає рядків таблиці
        irows = rows(isec)
        hl = next((l for l in isec.splitlines() if l.startswith("|")), "")
        hdr = [c.lower() for c in cells(hl)] if hl else []
        ic = {k: next((n for n, h in enumerate(hdr) if k in h), None) for k in ("клас", "вибірк")}
        # «критері» - серед колонок, відмінних від знайденої для «вибірк» (заголовок «Вибірка (N, критерій)» не рахується)
        ic["критері"] = next((n for n, h in enumerate(hdr) if "критері" in h and n != ic["вибірк"]), None)
        if None in ic.values():
            ibad.append("немає колонок «Клас», «Вибірка», «Критерій»")
        else:
            for r in irows:
                if len(r) <= max(ic.values()) or r[ic["клас"]] != "internal-aggregated" or not r[ic["вибірк"]] or not r[ic["критері"]]:
                    ibad.append(r[0][:40] if r else "?")
    add("PP-internal", not ibad, "розділ «Внутрішні сигнали ToDo»: " + "; ".join(ibad[:5]))

    # PP-rejected: реєстр відкинутого (flow-core/references/rejected-register.md); повну перевірку формату дає check_rejected.py
    rsec = secs.get("Відкинуто")
    rok = rsec is not None and (bool(re.search(r"нічого не відкинуто", rsec)) or bool(re.search(r"\|\s*ID\s*\|", rsec)))
    add("PP-rejected", rok, "немає розділу «## Відкинуто» з таблицею реєстру (ID...) або рядка «нічого не відкинуто»")

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
                       if not any(c == a or (a.endswith("/") and c.startswith(a)) for a in allowed + list(ALWAYS_OK)))
        inp = sorted(c for c in changed if "/_input/" in "/" + c)
        add("PP-scope", not extra and not inp,
            "; ".join(filter(None, ["зайве: " + ", ".join(extra[:5]) if extra else "",
                                    "_input/ змінено/додано до git: " + ", ".join(inp[:3]) if inp else ""])))
    stray = stray_inputs(sources)
    add("PP-input", not stray, "невідомі файли/теки в _input/ (README.md, crm.csv дозволені; агент не прибирає; waiting_human): " + ", ".join(stray[:3]))
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
            "| П-03 | Вигаданий Клієнт В | proj_example3 | | | згода | повний |\n\n"
            "| джерело | alias підключення | db | режим читання |\n|---|---|---|---|\n"
            "| власна ERP | own-erp-example | example_db | лише модулі |\n", encoding="utf-8")
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
        # реєстр відкинутого й внутрішні сигнали (К-07)
        base_t = tpl.replace("abc1234", sha)
        doc.write_text(base_t.split("## Відкинуто")[0], encoding="utf-8")
        if [o for o in run() if o["id"] == "PP-rejected"][0]["status"] != "FAIL":
            errs.append("PP-rejected має ловити відсутній розділ «Відкинуто»")
        doc.write_text(base_t.replace("internal-aggregated", "internal-raw"), encoding="utf-8")
        if [o for o in run() if o["id"] == "PP-internal"][0]["status"] != "FAIL":
            errs.append("PP-internal має ловити клас, що не internal-aggregated")
        # порожній «Критерій відбору» і «немає даних» поруч із рядками таблиці не мають вимикати перевірку
        doc.write_text(re.sub(r"(\| internal-aggregated \| [^|]*\|)[^|]*\|", r"\1 |", base_t, count=1) + "\n", encoding="utf-8")
        if [o for o in run() if o["id"] == "PP-internal"][0]["status"] != "FAIL":
            errs.append("PP-internal має ловити порожній «Критерій відбору»")
        doc.write_text(base_t.replace("internal-aggregated", "internal-raw").replace("## Внутрішні сигнали ToDo", "## Внутрішні сигнали ToDo\n\nнемає даних (обхід)\n", 1), encoding="utf-8")
        if [o for o in run() if o["id"] == "PP-internal"][0]["status"] != "FAIL":
            errs.append("«немає даних» не має вимикати PP-internal за наявності рядків таблиці")
        doc.write_text(tpl.replace("abc1234", sha), encoding="utf-8")
        (d / "docs/industries/test/stray.md").write_text("x")
        if [o for o in run() if o["id"] == "PP-scope"][0]["status"] != "FAIL":
            errs.append("PP-scope має ловити новий (untracked) сторонній файл")
        # observations/ коммітить runner - дозволено; прихований файл у _input/ ігнорується; видимий - PP-input FAIL
        (d / "docs/industries/test/stray.md").unlink()
        (d / "observations").mkdir(); (d / "observations/2026-01-01-x.md").write_text("x")
        sh("add", "-A"); sh("commit", "-qm", "obs")
        (inp / ".DS_Store").write_text("x")
        bad = [o for o in run(base=sha) if o["status"] != "PASS"]
        if bad:
            errs.append(f"observations/ і .DS_Store не мають давати FAIL: {bad}")
        (inp / "backup.txt").write_text("x")
        if [o for o in run() if o["id"] == "PP-input"][0]["status"] != "FAIL":
            errs.append("PP-input має ловити видимий сторонній файл")
        (inp / "backup.txt").unlink()
        # сусідні вхідні файли кроків (crm.csv, README.md) не є помилкою
        (inp / "crm.csv").write_text("x"); (inp / "README.md").write_text("x")
        if [o for o in run() if o["id"] == "PP-input"][0]["status"] != "PASS":
            errs.append("crm.csv і README.md у _input/ не мають давати FAIL PP-input")
        (inp / "crm.csv").unlink(); (inp / "README.md").unlink()
        # @ref: sha на ref -> PASS; sha не з ref -> FAIL
        sh("branch", "feat"); sh("checkout", "-q", "feat")
        (d / "odoo_addons/td_edge/x.txt").write_text("x"); sh("add", "-A"); sh("commit", "-qm", "feat")
        sha_feat = sh("rev-parse", "--short", "HEAD").stdout.strip()
        sh("checkout", "-q", "-")
        (d / "odoo_addons/td_edge/y.txt").write_text("y"); sh("add", "-A"); sh("commit", "-qm", "main")
        sha_main = sh("rev-parse", "--short", "HEAD").stdout.strip()
        src_txt = (inp / "sources.md").read_text(encoding="utf-8")
        (inp / "sources.md").write_text(src_txt.replace("odoo_addons/td_edge |", "odoo_addons/td_edge@feat |"), encoding="utf-8")
        doc.write_text(tpl.replace("abc1234", sha_main), encoding="utf-8")
        if [o for o in run() if o["id"] == "PP-ref"][0]["status"] != "FAIL":
            errs.append("PP-ref має ловити sha, якого немає на ref")
        doc.write_text(tpl.replace("abc1234", sha_feat), encoding="utf-8")
        if [o for o in run() if o["id"] == "PP-ref"][0]["status"] != "PASS":
            errs.append("PP-ref: sha на ref має давати PASS")
        (inp / "sources.md").write_text(src_txt.replace("odoo_addons/td_edge |", "odoo_addons/td_edge@nope |"), encoding="utf-8")
        if [o for o in run() if o["id"] == "PP-ref"][0]["status"] != "FAIL":
            errs.append("PP-ref: неіснуючий ref має давати FAIL")
        # remote-only ref (origin/feat без локальної гілки) -> PASS; без ref sha з іншої гілки -> FAIL
        cl = d.parent / (d.name + "_clone")
        subprocess.run(["git", "clone", "-q", str(d), str(cl)], capture_output=True)
        (inp / "sources.md").write_text(src_txt.replace("odoo_addons/td_edge |", "odoo_addons/td_edge@feat |"), encoding="utf-8")
        doc.write_text(tpl.replace("abc1234", sha_feat), encoding="utf-8")
        run_cl = lambda r: [o for o in run_checks(str(doc), str(inp / "sources.md"), r, scope_files=rel) if o["id"] == "PP-ref"][0]["status"]
        if run_cl({"": str(cl)}) != "PASS":
            errs.append("PP-ref: ref, що є лише як origin/<ref> у клоні, має давати PASS")
        # кілька репозиторіїв: ref лише у другому (alias)
        (inp / "sources.md").write_text(src_txt.replace("odoo_addons/td_edge |", "two/odoo_addons/td_edge@feat |"), encoding="utf-8")
        doc.write_text(tpl.replace("abc1234", sha_feat).replace("repo:odoo_addons/td_edge", "repo:two/odoo_addons/td_edge"), encoding="utf-8")
        if run_cl({"": str(d / "odoo_addons"), "two": str(cl)}) != "PASS":
            errs.append("PP-ref: ref лише у репо з alias має давати PASS")
        (inp / "sources.md").write_text(src_txt.replace("odoo_addons/td_edge |", "other/x@feat |"), encoding="utf-8")
        if run_cl({"": str(d / "odoo_addons"), "two": str(cl)}) == "FAIL":
            errs.append("PP-ref: незіставлений репозиторій має давати WARN, не FAIL")
        (inp / "sources.md").write_text(src_txt.replace("odoo_addons/td_edge |", "git@example.invalid:o/r |"), encoding="utf-8")
        if run_cl({"": str(cl)}) != "FAIL":
            errs.append("PP-ref: SSH-URL з @ має давати FAIL")
        # без ref: sha з іншої гілки (не default) -> FAIL
        (inp / "sources.md").write_text(src_txt, encoding="utf-8")
        doc.write_text(tpl.replace("abc1234", sha_feat), encoding="utf-8")
        if [o for o in run() if o["id"] == "PP-ref"][0]["status"] != "FAIL":
            errs.append("PP-ref без ref має ловити sha не з гілки за замовчуванням")
        doc.write_text(tpl.replace("abc1234", sha), encoding="utf-8")
        if [o for o in run() if o["id"] == "PP-ref"][0]["status"] != "PASS":
            errs.append("PP-ref без ref: sha на гілці за замовчуванням має давати PASS")
        # тека в _input/ -> PP-input FAIL
        (inp / "subdir").mkdir()
        if [o for o in run() if o["id"] == "PP-input"][0]["status"] != "FAIL":
            errs.append("PP-input має ловити теку")
        (inp / "subdir").rmdir()
        # fathom: --no-fathom і рядок з кількома кодами без пар
        base_doc = tpl.replace("abc1234", sha)
        if [o for o in run_checks(str(doc), str(inp / "sources.md"), {"": str(d)}, no_fathom=True) if o["id"] == "PP-mode"][0]["status"] != "FAIL":
            errs.append("--no-fathom має давати FAIL PP-mode (шаблон містить fathom:)")
        # PP-erp: підрозділ без рядка у sources.md, з repo:/П-xx — FAIL
        sp = inp / "sources.md"; keep = sp.read_text(encoding="utf-8")
        sp.write_text(keep.split("\n| джерело")[0] + "\n", encoding="utf-8")
        if [o for o in run() if o["id"] == "PP-erp"][0]["status"] != "FAIL":
            errs.append("підрозділ власної ERP без рядка «власна ERP» у sources.md має давати FAIL PP-erp")
        sp.write_text(keep, encoding="utf-8")
        doc.write_text(base_doc.replace("| mrp_example |", "| П-01 repo:x@abc1234 |"), encoding="utf-8")
        if [o for o in run() if o["id"] == "PP-erp"][0]["status"] != "FAIL":
            errs.append("repo:/П-xx у підрозділі власної ERP має давати FAIL PP-erp")
        doc.write_text(base_doc.replace("1 (П-01) | fathom:rec_0001", "2 (П-01, П-02) | fathom:rec_0001"), encoding="utf-8")
        if [o for o in run() if o["id"] == "PP-mode"][0]["status"] != "FAIL":
            errs.append("рядок з кількома П-xx і fathom: без пар «П-xx fathom:» має давати FAIL PP-mode")
    print(json.dumps({"self_test": "PASS" if not errs else "FAIL", "errors": errs}, ensure_ascii=False, indent=1))
    sys.exit(1 if errs else 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc"); ap.add_argument("--sources")
    ap.add_argument("--repo", action="append", default=[])
    ap.add_argument("--scope-files", default=""); ap.add_argument("--base", default=""); ap.add_argument("--head", default="")
    ap.add_argument("--no-fathom", action="store_true", help="DATA_POLICY забороняє Fathom: будь-який fathom: у документі = FAIL PP-mode")
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
    out = run_checks(a.doc, a.sources, repos, a.scope_files, a.base, a.head, names, a.no_fathom)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    sys.exit(1 if any(o["status"] == "FAIL" for o in out) else 0)


if __name__ == "__main__":
    main()
