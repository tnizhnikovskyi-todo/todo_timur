#!/usr/bin/env python3
"""Автоперевірки A-20 (CM-*). stdlib. Вивід: JSON [{id,status,msg}]. Код виходу 1, якщо є FAIL.
Запускати з кореня клону; <concept_dir> — відносний шлях. --base = git.base наряду.
Використання: check_concept.py <concept_dir> --input briefing.md=<шлях> [--input ...] [--base <SHA>]
Ключ --input = ім'я файлу з колонки «Джерело» (наприклад past-projects.md); значення = шлях до файлу на SHA наряду."""
import argparse, json, re, subprocess, sys
from pathlib import Path

HEAD = {"features.md": ["Ролі", "Болі", "Функції", "Поза концепцією", "Відкриті питання"],
        "screens.md": ["Екрани"], "scenarios.md": ["Сценарії"]}
PII = {"email": r"[\w.+-]+@[\w-]+\.[\w.-]+", "phone": r"(?<![\w:])(\+?380\d{9}|0\d{9})(?!\w)",
       "sum": r"(\d[\d\s.,]*\s?(грн|₴|\$|€|USD|UAH|EUR))|(\d\s?(тис\.?|млн|млрд)\s?(грн|₴|\$|€|USD|UAH|EUR))|([$€₴]\s?\d)",
       "pib": r"\b[А-ЯІЇЄҐ][а-яіїєґ'’-]+\s+[А-ЯІЇЄҐ][а-яіїєґ'’-]+\s+[А-ЯІЇЄҐ][а-яіїєґ'’-]+\b",
       "edrpou_iban": r"\bUA\d{2}[\s\d]{20,}|ЄДРПОУ\D{0,5}\d{8}\b"}
ID = re.compile(r"\b(?:ROLE|PAIN|F|S|SC)-\d{2,}\b")
res = []

def add(i, ok, msg=""):
    res.append({"id": i, "status": "PASS" if ok else "FAIL", "msg": "" if ok else msg})

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

def git(*a):
    r = subprocess.run(["git", *a], capture_output=True, text=True)
    if r.returncode != 0:
        raise GitError(r.stderr.strip()[:200])
    return r.stdout

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("dir"); ap.add_argument("--input", action="append", default=[])
    ap.add_argument("--base"); a = ap.parse_args()
    d = Path(a.dir); inputs = dict(x.split("=", 1) for x in a.input)
    txt, secs, missing = {}, {}, []
    for f, hs in HEAD.items():
        p = d / f
        if not p.exists(): missing.append(f); continue
        txt[f] = p.read_text(encoding="utf-8"); secs[f] = sections(txt[f])
        missing += [f"{f}§{h}" for h in hs if h not in secs[f]]
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
    if not 4 <= len(sc) <= 6: why.append(f"сценаріїв {len(sc)} (потрібно 4-6)")
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
            old = {f: git("show", f"{a.base}:{rel}/{f}") for f in HEAD}
            gone = sorted({i for t in old.values() for i in ID.findall(t)} - {i for t in txt.values() for i in ID.findall(t)})
            add("CM-ids", not gone, "зникли ID: " + ", ".join(gone))
        except (GitError, ValueError, OSError) as e:
            add("CM-ids", False, f"не вдалось прочитати base {a.base}: {e}")
    # CM-pii
    hits = [f"{f}:{k}" for f, t in txt.items() for k, p in PII.items() if re.search(p, t, re.I)]
    add("CM-pii", not hits, ", ".join(hits))
    # CM-scope
    if a.base:
        try:
            ch = [x for x in git("diff", "--name-only", a.base).splitlines() if x]
            bad = [x for x in ch if "/concept/" not in x and "/_template/concept/" not in x]
            add("CM-scope", not bad, "зачеплено: " + ", ".join(bad))
        except GitError as e:
            add("CM-scope", False, f"не вдалось прочитати base {a.base}: {e}")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(1 if any(r["status"] == "FAIL" for r in res) else 0)

main()
