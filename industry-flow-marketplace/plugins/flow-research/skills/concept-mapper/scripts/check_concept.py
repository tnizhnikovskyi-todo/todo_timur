#!/usr/bin/env python3
"""Автоперевірки A-20 (CM-*). stdlib. Вивід: JSON [{id,status,msg}]. Код виходу 1, якщо є FAIL.
Запускати з кореня клону; <concept_dir> — відносний шлях. --base = git.base наряду (без нього CM-ids/CM-scope = SKIP).
CM-pii: ПІБ (три слова з великої) дає MANUAL, а не FAIL (pii-patterns.md): людина перевіряє збіг; решта шаблонів — FAIL.
Використання: check_concept.py <concept_dir> --input briefing.md=<шлях> [--input ...] [--base <SHA>]
              [--research <research_dir> --intake OWNER-INTAKE.md [--k1 K1.md] [--facts facts.yaml]]
--research і --intake ОБОВ'ЯЗКОВІ для A-20: без них CM-args = FAIL (щоб runner не пропустив нові перевірки мовчки).
Старий режим «лише concept/» — явний прапорець --concept-only (нові CM-* тоді SKIP; для A-20 не використовувати).
Шлях до скриптів flow-autocheck (плагін flow-core): --autocheck-dir <шлях до .../flow-core/skills/flow-autocheck/scripts> або змінна оточення FLOW_AUTOCHECK_DIR
(у кеші встановлених плагінів сусідній плагін може лежати деінде; за замовчуванням — відносно цього файла).
Із --research додатково: CM-research (розділи OWNER-BRIEF §1-10, BOX §1-13, SALES §1-7, REJECTED), CM-buyer (роль-покупець має екран-дашборд і сценарій),
CM-roles-scenarios (кожна роль має SC, кожна F — крок SC, роль SC = роль екрана), CM-base-edition (основа екрана: Стд CE|Стд EE|td_|ToDo-готовий|Інтегр),
CM-dnr (check_rejected.py: позиції do_not_reject без K1 у відкинутому), CM-facts (check_facts.py: числа = facts.yaml). Без --research (лише з --concept-only) вони SKIP.
Ключ --input = ім'я файлу з колонки «Джерело» (наприклад past-projects.md); значення = шлях до файлу на SHA наряду."""
import argparse, json, os, re, subprocess, sys
from pathlib import Path

HEAD = {"features.md": ["Ролі", "Болі", "Функції", "Поза концепцією", "Відкриті питання"],
        "screens.md": ["Екрани"], "scenarios.md": ["Сценарії"]}
PII = {"email": r"[\w.+-]+@[\w-]+\.[\w.-]+", "phone": r"(?<![\w:])(\+?380\d{9}|0\d{9})(?!\w)",
       "sum": r"(\d[\d\s.,]*\s?(грн|₴|\$|€|USD|UAH|EUR))|(\d\s?(тис\.?|млн|млрд)\s?(грн|₴|\$|€|USD|UAH|EUR))|([$€₴]\s?\d)",
       "pib": r"\b[А-ЯІЇЄҐ][а-яіїєґ'’-]+\s+[А-ЯІЇЄҐ][а-яіїєґ'’-]+\s+[А-ЯІЇЄҐ][а-яіїєґ'’-]+\b",
       "edrpou_iban": r"\bUA\d{2}[\s\d]{20,}|ЄДРПОУ\D{0,5}\d{8}\b"}
ID = re.compile(r"\b(?:ROLE|PAIN|F|S|SC)-\d{2,}\b")
res = []

def add(i, ok, msg="", status=None):
    res.append({"id": i, "status": status or ("PASS" if ok else "FAIL"), "msg": "" if ok else msg})

class GitError(Exception):
    pass

def norm(s):
    s = re.sub(r"[«»„“”\"]", '"', s); s = re.sub(r"[’ʼ`']", "'", s)
    s = re.sub(r"[—–]", "-", s); s = re.sub(r"[*_`]", "", s)
    return re.sub(r"\s+", " ", s).strip().strip(".,;: ").lower()

def sections(text):
    parts = re.split(r"^## ", text, flags=re.M)[1:]
    return {p.split("\n", 1)[0].strip(): (p.split("\n", 1)[1] if "\n" in p else "") for p in parts}

def rows(sec):
    out = []
    for l in sec.splitlines():
        if l.startswith("|") and not re.match(r"^\|[\s:|-]+\|$", l):
            out.append([c.strip() for c in l.strip().strip("|").split("|")])
    return [r for r in out[1:]] if out else []  # без заголовка таблиці

BASES = ["Стд CE", "Стд EE", "td_", "ToDo-готовий", "Інтегр"]
RESEARCH_NUMBERED = {"OWNER-BRIEF.md": 10, "BOX.md": 13, "SALES.md": 7}
HERE = os.path.dirname(os.path.abspath(__file__))
AUTOCHECK = os.environ.get("FLOW_AUTOCHECK_DIR") or os.path.normpath(os.path.join(HERE, "..", "..", "..", "..", "flow-core", "skills", "flow-autocheck", "scripts"))

def table(sec):
    """(заголовок, рядки) першої таблиці розділу."""
    out = [[c.strip() for c in l.strip().strip("|").split("|")] for l in sec.splitlines()
           if l.startswith("|") and not re.match(r"^\|[\s:|-]+\|$", l)]
    return (out[0], out[1:]) if out else ([], [])

def col(head, *names):
    for n in names:
        for i, h in enumerate(head):
            if h.lower().startswith(n.lower()):
                return i
    return None

def run_aux(script, *args):
    """Запуск сусідньої автоперевірки; повертає (список результатів | None, причина)."""
    path = os.path.join(AUTOCHECK, script)
    if not os.path.exists(path):
        return None, f"немає {script} у {AUTOCHECK}: задай --autocheck-dir або FLOW_AUTOCHECK_DIR (flow-core/skills/flow-autocheck/scripts)"
    r = subprocess.run([sys.executable, "-I", path, *args], capture_output=True, text=True)
    try:
        return json.loads(r.stdout), ""
    except ValueError:
        return None, (r.stderr or r.stdout).strip()[:200]

def git(*a):
    r = subprocess.run(["git", *a], capture_output=True, text=True)
    if r.returncode != 0:
        raise GitError(r.stderr.strip()[:200])
    return r.stdout

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("dir"); ap.add_argument("--input", action="append", default=[])
    ap.add_argument("--base"); ap.add_argument("--research"); ap.add_argument("--intake"); ap.add_argument("--k1"); ap.add_argument("--facts")
    ap.add_argument("--concept-only", action="store_true"); ap.add_argument("--autocheck-dir")
    a = ap.parse_args()
    global AUTOCHECK
    if a.autocheck_dir: AUTOCHECK = a.autocheck_dir
    d = Path(a.dir); inputs = dict(x.split("=", 1) for x in a.input)
    txt, secs, missing = {}, {}, []
    for f, hs in HEAD.items():
        p = d / f
        if not p.exists(): missing.append(f); continue
        txt[f] = p.read_text(encoding="utf-8"); secs[f] = sections(txt[f])
        missing += [f"{f}§{h}" for h in hs if h not in secs[f]]
    if not a.concept_only and not (a.research and a.intake):
        add("CM-args", False, "немає --research і/або --intake: для A-20 вони обов'язкові (CM-research/CM-buyer/CM-roles-scenarios/CM-base-edition/CM-dnr/CM-facts без них не виконуються); явний старий режим — --concept-only")
    add("CM-files", not missing, "немає: " + ", ".join(missing))
    if missing:
        print(json.dumps(res, ensure_ascii=False, indent=1)); sys.exit(1)
    feat = secs["features.md"]
    roles = {r[0] for r in rows(feat["Ролі"])}
    pains = {r[0]: r for r in rows(feat["Болі"]) if len(r) >= 5}
    funcs = [r for r in rows(feat["Функції"]) if len(r) >= 6]
    # CM-src, CM-quote
    bad_src, bad_q = [], []
    for pid, r in pains.items():
        srcs = [s.strip() for s in r[3].split(";") if s.strip()]
        files = [s.split("§")[0].strip() for s in srcs]
        if not srcs or any(f not in inputs and Path(f).name not in {Path(k).name for k in inputs} for f in files):
            bad_src.append(pid); continue
        q = r[4].strip().strip('«»"')
        body = [norm(Path(inputs.get(f) or next(v for k, v in inputs.items() if Path(k).name == Path(f).name)).read_text(encoding="utf-8")) for f in files]
        if len(q.split()) > 25 or not q or not any(norm(q) in b for b in body):
            bad_q.append(pid)
    add("CM-src", not bad_src, "джерело поза входами: " + ", ".join(bad_src))
    add("CM-quote", not bad_q, "цитата не знайдена/задовга: " + ", ".join(bad_q))
    # CM-feat, CM-signal
    bad_f, bad_s = [], []
    for r in funcs:
        fr, fp = set(re.findall(r"ROLE-\d+", r[2])), re.findall(r"PAIN-\d+", r[3])
        if not fr or not fp or not fr <= roles or not set(fp) <= set(pains):
            bad_f.append(r[0]); continue
        n = len({s.strip() for p in fp for s in pains[p][3].split(";") if s.strip()})
        if r[4].strip() != str(n): bad_s.append(f"{r[0]} (є {r[4]}, має бути {n})")
    add("CM-feat", not bad_f and bool(funcs), "функція без ролі/болю або порожньо: " + ", ".join(bad_f))
    add("CM-signal", not bad_s, "; ".join(bad_s))
    # CM-count, CM-trace
    scr = {m for m in re.findall(r"^\|\s*(S-\d+)\s*\|", txt["screens.md"], flags=re.M)}
    sc = re.split(r"^### (?=SC-)", txt["scenarios.md"], flags=re.M)[1:]
    sc_roles = [(re.findall(r"ROLE-\d+", b.split("\n", 1)[0]) or [None])[0] for b in sc]
    why = []
    if not 10 <= len(scr) <= 15: why.append(f"екранів {len(scr)} (потрібно 10-15)")
    if not 4 <= len(sc) <= 8: why.append(f"сценаріїв {len(sc)} (потрібно 4-8: по одному на роль)")
    if None in sc_roles: why.append("у заголовку SC немає ROLE-xx")
    dup = sorted({r for r in sc_roles if r and sc_roles.count(r) > 1})
    if dup: why.append("ролі сценаріїв повторюються: " + ", ".join(f"{r} x{sc_roles.count(r)}" for r in dup))
    add("CM-count", not why, "; ".join(why))
    fids = {r[0] for r in funcs}; sc_text = "\n".join(sc)
    used_s, used_f = set(re.findall(r"S-\d+", sc_text)), set(re.findall(r"F-\d+", sc_text))
    f_on_s = set(re.findall(r"F-\d+", "\n".join(l for l in txt["screens.md"].splitlines() if re.match(r"^\|\s*S-\d+", l))))
    probs = [f"F без екрана: {sorted(fids - f_on_s)}" if fids - f_on_s else "",
             f"S поза сценаріями: {sorted(scr - used_s)}" if scr - used_s else "",
             f"S/F у SC не існують: {sorted((used_s - scr) | (used_f - fids))}" if (used_s - scr) | (used_f - fids) else ""]
    add("CM-trace", not any(probs), "; ".join(p for p in probs if p))
    # CM-ids
    if a.base:
        try:
            top = Path(git("rev-parse", "--show-toplevel").strip())
            rel = d.resolve().relative_to(top).as_posix()
            # файлу ще не було на base (перший запуск) — порожня база, ID не могли зникнути
            old = {f: (git("show", f"{a.base}:{rel}/{f}") if git("ls-tree", a.base, f"{rel}/{f}").strip() else "") for f in HEAD}
            gone = sorted({i for t in old.values() for i in ID.findall(t)} - {i for t in txt.values() for i in ID.findall(t)})
            add("CM-ids", not gone, "зникли ID: " + ", ".join(gone))
            if a.research:  # REJ-xxx з REJECTED.md на base не мають зникнути (A-20 лише дописує G4/G4а, чужі рядки A-03b не перезаписує)
                rr = Path(a.research).resolve().relative_to(top).as_posix() + "/REJECTED.md"
                oldr = git("show", f"{a.base}:{rr}") if git("ls-tree", a.base, rr).strip() else ""
                newr = Path(a.research, "REJECTED.md").read_text(encoding="utf-8") if Path(a.research, "REJECTED.md").exists() else ""
                gone_r = sorted(set(re.findall(r"REJ-\d+", oldr)) - set(re.findall(r"REJ-\d+", newr)))
                add("CM-rej-ids", not gone_r, "зникли REJ-ID з base (REJECTED.md не перезаписують): " + ", ".join(gone_r))
        except (GitError, ValueError, OSError) as e:
            add("CM-ids", False, f"не вдалось прочитати base {a.base}: {e}")
    # CM-pii
    flags = {"email": re.I, "sum": re.I}  # ПІБ — лише з урахуванням регістру (три слова З ВЕЛИКОЇ)
    hits = [f"{f}:{k}" for f, t in txt.items() for k, p in PII.items() if k != "pib" and re.search(p, t, flags.get(k, 0))]
    pib = [f"{f}:{k}" for f, t in txt.items() for k, p in PII.items() if k == "pib" and re.search(p, t)]
    if hits:
        add("CM-pii", False, ", ".join(hits + pib))
    elif pib:
        add("CM-pii", False, "ПІБ? перевірити вручну (назва посади/процесу — ок): " + ", ".join(pib), status="MANUAL")
    else:
        add("CM-pii", True)
    # --- нові перевірки A-20 (потрібні --research, --intake) ---
    screen_head, screen_rows = table(secs["screens.md"]["Екрани"])
    ci_r, ci_t, ci_b = col(screen_head, "Ролі"), col(screen_head, "Тип"), col(screen_head, "Основа")
    role_rows = {r[0]: r for r in rows(feat["Ролі"])}
    if not a.research:
        for i in ("CM-research", "CM-buyer", "CM-roles-scenarios", "CM-base-edition", "CM-dnr", "CM-facts"):
            res.append({"id": i, "status": "SKIP", "msg": "--concept-only: без --research"})
    else:
        rd = Path(a.research)
        # CM-research
        bad = []
        for f, n in RESEARCH_NUMBERED.items():
            p = rd / f
            if not p.exists(): bad.append(f"немає {f}"); continue
            have = {int(x) for x in re.findall(r"^##\s+(\d+)", p.read_text(encoding="utf-8"), flags=re.M)}
            miss = sorted(set(range(1, n + 1)) - have)
            if miss: bad.append(f"{f}: немає розділів {miss}")
        if not (rd / "REJECTED.md").exists(): bad.append("немає REJECTED.md")
        add("CM-research", not bad, "; ".join(bad))
        # CM-buyer: роль-покупець (позначка [покупець] у колонці «Роль») має екран-дашборд і сценарій
        buyers = [rid for rid, r in role_rows.items() if len(r) > 1 and re.search(r"\[\s*покупець\s*\]", r[1], re.I)]
        why = []
        if not buyers:
            why.append("жодну роль не позначено [покупець] у колонці «Роль» (покупець — це роль із екраном-дашбордом)")
        for b in buyers:
            ok_s = [r for r in screen_rows if ci_r is not None and ci_t is not None and len(r) > max(ci_r, ci_t)
                    and b in re.findall(r"ROLE-\d+", r[ci_r]) and re.search(r"дашборд|зведення", r[ci_t], re.I)]
            if not ok_s: why.append(f"{b}: немає екрана-дашборда/зведення з цією роллю")
            if b not in sc_roles: why.append(f"{b}: немає сценарію")
        add("CM-buyer", not why, "; ".join(why))
        # CM-roles-scenarios
        why = []
        miss_r = sorted(set(role_rows) - set(sc_roles))
        if miss_r: why.append(f"ролі без сценарію: {miss_r}")
        live = [r[0] for r in funcs if not r[6].strip().lower().startswith("знято")] if funcs and all(len(r) > 6 for r in funcs) else [r[0] for r in funcs]
        no_step = sorted(set(live) - used_f)
        if no_step: why.append(f"F без кроку в сценаріях: {no_step}")
        s_roles = {r[0]: set(re.findall(r"ROLE-\d+", r[ci_r])) for r in screen_rows if ci_r is not None and len(r) > ci_r}
        for blk, rid in zip(sc, sc_roles):
            sid = blk.split("\n", 1)[0].split()[0]
            bad_s = sorted(s for s in set(re.findall(r"S-\d+", blk)) if s in s_roles and rid not in s_roles[s])
            if bad_s: why.append(f"{sid} ({rid}): екрани {bad_s} не мають цієї ролі в screens.md")
        add("CM-roles-scenarios", not why, "; ".join(why))
        # CM-base-edition
        why = []
        if ci_b is None:
            why.append("у таблиці екранів немає колонки «Основа»")
        else:
            for r in screen_rows:
                v = r[ci_b] if len(r) > ci_b else ""
                if not v.strip() or not all(x.strip() in BASES for x in re.split(r"[,;/+]", v) if x.strip()):
                    why.append(f"{r[0]}: основа «{v}» не з {BASES} (OCA — лише ідея, пишемо в td_)")
        add("CM-base-edition", not why, "; ".join(why[:8]))
        # CM-dnr
        if not a.intake:
            add("CM-dnr", False, "не передано --intake (OWNER-INTAKE.md)")
        else:
            args = [str(rd / "REJECTED.md"), "--intake", a.intake] + (["--k1", a.k1] if a.k1 else [])
            out, why = run_aux("check_rejected.py", *args)
            if out is None: add("CM-dnr", False, why)
            else:
                bad = [f"{x['id']}: {x['msg']}" for x in out if x["status"] == "FAIL"]
                man = [f"{x['id']}: {x['msg']}" for x in out if x["status"] == "MANUAL"]
                if bad: add("CM-dnr", False, "; ".join(bad)[:600])
                elif man: add("CM-dnr", False, "; ".join(man)[:300], status="MANUAL")
                else: add("CM-dnr", True)
        # CM-facts
        fy = a.facts or str(rd / "facts.yaml")
        if not os.path.exists(fy):
            add("CM-facts", False, f"немає {fy} (єдине джерело чисел)")
        else:
            targets = [str(rd / f) for f in ("OWNER-BRIEF.md", "BOX.md", "SALES.md") if (rd / f).exists()]
            out, why = run_aux("check_facts.py", fy, *targets, "--require-markers")  # число без маркера — FAIL/WARN
            out2, why2 = run_aux("check_facts.py", fy, str(d))  # concept/*: годин і цін немає; маркери не вимагаємо
            if out is None or out2 is None: add("CM-facts", False, why or why2)
            else:
                bad = [f"{x['id']}: {x['msg']}" for x in out + out2 if x["status"] == "FAIL"]
                add("CM-facts", not bad, "; ".join(bad)[:600])
    # CM-scope
    if not a.base:
        res.append({"id": "CM-ids", "status": "SKIP", "msg": "немає --base"}); res.append({"id": "CM-scope", "status": "SKIP", "msg": "немає --base"})
    else:
        try:
            ch = [x for x in git("diff", "--name-only", a.base).splitlines() if x]
            rel = d.resolve().relative_to(Path(git("rev-parse", "--show-toplevel").strip())).as_posix()
            own = rel + "/"; tpl = "docs/industries/_template/concept/"
            extra = []
            if a.research:
                rr = Path(a.research).resolve().relative_to(Path(git("rev-parse", "--show-toplevel").strip())).as_posix()
                extra = [f"{rr}/{f}" for f in ("OWNER-BRIEF.md", "BOX.md", "SALES.md", "REJECTED.md", "facts.yaml")]
            bad = [x for x in ch if not x.startswith(own) and not x.startswith(tpl) and x not in extra]
            add("CM-scope", not bad, "зачеплено: " + ", ".join(bad))
        except (GitError, ValueError) as e:
            add("CM-scope", False, f"не вдалось прочитати base {a.base}: {e}")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(1 if any(r["status"] == "FAIL" for r in res) else 0)

main()
