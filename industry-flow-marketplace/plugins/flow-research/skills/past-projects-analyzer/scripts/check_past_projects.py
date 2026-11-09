#!/usr/bin/env python3
"""Автоперевірки A-04 (PP-*). stdlib. Вивід: JSON [{id, status, msg}]. Код виходу 1, якщо є FAIL.
Denylist: з sources.md (клітинки таблиці, окрім колонок режиму/підстави) + stdin (імена учасників Fathom, по одному в рядку)."""
import argparse, json, re, subprocess, sys
from pathlib import Path

SECTIONS = ["Проєкти й джерела", "Що вже робили", "Модулі для повторного використання",
            "Болі клієнтів", "Прогалини", "Для шлюзу: проєкти в цільовому сегменті"]
ID = re.compile(r"\b(aikb:\S+|fathom:\S+|repo:\S+)")
CODE = re.compile(r"П-\d{2}")
PII = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "phone": re.compile(r"(?<![\w:])(\+?380\d{9}|0\d{9})(?!\w)"),
    "sum": re.compile(r"(\d[\d\s.,]*\s?(грн|₴|\$|€|USD|UAH|EUR|тис\.|млн|млрд))|([$€₴]\s?\d)", re.I),
    "edrpou_iban": re.compile(r"\bUA\d{2}[\s\d]{20,}|ЄДРПОУ\D{0,5}\d{8}\b", re.I),
    "fio": re.compile(r"\b[А-ЯІЇЄҐ][а-яіїєґ'’]+\s+[А-ЯІЇЄҐ][а-яіїєґ'’]+\s+[А-ЯІЇЄҐ][а-яіїєґ'’]*(ович|евич|ївна|івна|ична)\b"),
}

def rows(sec):
    res = []
    for l in sec.splitlines():
        if not l.startswith("|"):
            continue
        if re.match(r"^\|[\s:|-]+\|$", l):
            if res:
                res.pop()  # попередній рядок - заголовок таблиці
            continue
        res.append([c.strip() for c in l.strip().strip("|").split("|")])
    return res

def sections(text):
    parts = re.split(r"^## ", text, flags=re.M)[1:]
    return {p.split("\n", 1)[0].strip(): p.split("\n", 1)[1] if "\n" in p else "" for p in parts}

def sources_info(path):
    codes, modes, deny = [], {}, set()
    for l in Path(path).read_text(encoding="utf-8").splitlines():
        if not l.startswith("|"):
            continue
        cells = [c.strip() for c in l.strip().strip("|").split("|")]
        if not cells or not CODE.fullmatch(cells[0]):
            continue
        codes.append(cells[0])
        modes[cells[0]] = "only_reports" if any("лише звіти" in c.lower() for c in cells) else "full"
        for c in cells[1:]:
            low = c.lower()
            if "лише звіти" in low or low in ("повний", "") or len(c) < 4:
                continue
            for part in re.split(r"[;,]", c):
                if len(part.strip()) >= 4:
                    deny.add(part.strip().lower())
    return codes, modes, deny

def git(repo, *a):
    return subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", required=True); ap.add_argument("--sources", required=True)
    ap.add_argument("--repo", default="."); ap.add_argument("--scope-files", default="")
    a = ap.parse_args()
    out = []
    def add(i, ok, msg=""): out.append({"id": i, "status": "PASS" if ok else "FAIL", "msg": msg})

    text = Path(a.doc).read_text(encoding="utf-8")
    secs = sections(text)
    miss = [s for s in SECTIONS if s not in secs]
    add("PP-sections", not miss, "немає: " + ", ".join(miss))
    codes, modes, deny = sources_info(a.sources)
    if not sys.stdin.isatty():
        deny |= {l.strip().lower() for l in sys.stdin if len(l.strip()) >= 3}

    # PP-codes: коди в документі ⊆ sources; кожен код sources згаданий
    doc_codes = set(CODE.findall(text))
    bad, absent = sorted(doc_codes - set(codes)), sorted(set(codes) - doc_codes)
    add("PP-codes", not bad and not absent, f"вигадані: {bad}; пропущені: {absent}")

    # PP-src: рядки таблиць процесів/модулів/болів/прогалин
    bad_rows = []
    for s in SECTIONS[1:5]:
        for r in rows(secs.get(s, "")):
            line = " | ".join(r)
            if "немає даних" in line.lower():
                continue
            if not ID.search(line) or not CODE.search(line):
                bad_rows.append(f"{s}: {r[0][:40]}")
    add("PP-src", not bad_rows, "; ".join(bad_rows[:5]))

    # PP-mode
    viol = []
    for r in rows(secs.get(SECTIONS[0], "")):
        line = " | ".join(r)
        for c in set(CODE.findall(r[0] if r else "")):
            if modes.get(c) == "only_reports" and "fathom:" in line:
                viol.append(c)
    for s in SECTIONS[1:5]:
        for r in rows(secs.get(s, "")):
            line = " | ".join(r)
            for c in set(CODE.findall(line)):
                if modes.get(c) == "only_reports" and "fathom:" in line and len(set(CODE.findall(line))) == 1:
                    viol.append(c)
    add("PP-mode", not viol, f"fathom: для режиму «лише звіти»: {sorted(set(viol))}")

    # PP-repo, PP-ver
    mod_rows = [r for r in rows(secs.get(SECTIONS[2], "")) if "немає даних" not in " ".join(r).lower()]
    repo_bad, ver_bad = [], []
    for r in mod_rows:
        line = " | ".join(r)
        for m in re.finditer(r"repo:(\S+?)@([0-9a-fA-F]{4,40})", line):
            p, sha = m.groups()
            if git(a.repo, "cat-file", "-e", f"{sha}:{p}").returncode != 0:
                repo_bad.append(f"{p}@{sha}")
        if not re.search(r"repo:\S+@\w+", line):
            repo_bad.append(f"{r[0]}: немає repo:")
        if len(r) < 4 or not r[2].strip("- ") or not r[3].strip("- "):
            ver_bad.append(r[0])
    add("PP-repo", not repo_bad, "; ".join(repo_bad[:5]))
    add("PP-ver", not ver_bad, "; ".join(ver_bad[:5]))

    # PP-repeat
    rep = secs.get("Що вже робили", "").split("### Повторювані вимоги")
    rep_bad = [r[0] for r in rows(rep[1])
               if "немає даних" not in " ".join(r).lower() and len(set(CODE.findall(r[1] if len(r) > 1 else ""))) < 2] if len(rep) > 1 else []
    add("PP-repeat", not rep_bad, "; ".join(rep_bad[:5]))

    # PP-count
    yes = sum(1 for r in rows(secs.get(SECTIONS[0], "")) if len(r) > 2 and r[2].lower().startswith("так"))
    m = re.search(r"N\s*=\s*(\d+)", secs.get(SECTIONS[5], ""))
    add("PP-count", bool(m) and int(m.group(1)) == yes, f"у таблиці {yes}, у розділі {m.group(1) if m else 'немає N'}")

    # PP-pii
    hits = [k for k, rx in PII.items() if rx.search(text)]
    low = text.lower()
    hits += ["denylist" for d in deny if d in low][:1]
    add("PP-pii", not hits, "збіги: " + ", ".join(hits) + " (значення не виводяться)")

    # PP-gitignore, PP-scope
    src = str(Path(a.sources).resolve())
    ign = git(a.repo, "check-ignore", "-q", src).returncode == 0
    tracked = bool(git(a.repo, "ls-files", src).stdout.strip())
    add("PP-gitignore", ign and not tracked, "sources.md не ігнорується або відстежується - СТОП-ІНЦИДЕНТ")
    if a.scope_files:
        allowed = {x for x in a.scope_files.split(",") if x}
        changed = set(git(a.repo, "diff", "--name-only", "HEAD").stdout.split())
        extra = sorted(changed - allowed)
        add("PP-scope", not extra, "зайве: " + ", ".join(extra[:5]))

    print(json.dumps(out, ensure_ascii=False, indent=1))
    sys.exit(1 if any(o["status"] == "FAIL" for o in out) else 0)

if __name__ == "__main__":
    main()
