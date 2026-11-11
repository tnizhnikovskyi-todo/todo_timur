#!/usr/bin/env python3
"""Перелік застарілих артефактів галузі за DEPENDS.yaml (STALE-list, N-07). stdlib. Вивід: JSON [{id,status,msg}]; код виходу 1 при FAIL.
Використання: check_stale.py <research/DEPENDS.yaml> --base <sha>   (--base у result-перевірці кроку = ГОЛОВА результату кроку, `HEAD`/`<git.head>`, а не git.base кроку:
`git diff sha base` симетричний, і власні зміни кроку були б прочитані як «змінено після sha». Якщо `sha` артефакта — не предок --base, порівнюється `sha..HEAD` і додається WARN STALE-order.)
Вимога до злиття: PR кроків зливати МЕРЖ-КОМІТОМ (не squash), інакше коміт `sha` зникає з main; після squash/свіжого клону перезаписати sha на коміт main або зробити `git fetch`. Відсутній коміт sha — окремий ID STALE-sha-missing (FAIL), не змішується зі списком застарілих.
Схема DEPENDS.yaml: `artifacts: {<файл>: {depends_on: [<файл|тека|інший артефакт>…], sha: <коміт|null>}}`; шляхи — від кореня галузі
(теки `docs/industries/<галузь>/`; якщо DEPENDS лежить у `research/`, корінь — його батько). `sha` — КОМІТ РЕЗУЛЬТАТУ кроку (git.head до коміту, що вписує сам sha), у якому артефакт і всі його входи вже в узгодженому вигляді; НЕ git.base кроку:
інакше залежність, створена чи змінена тим самим кроком, дала б хибний STALE. Правило: крок не підтягує main після старту без перерахунку артефактів.
Після перерахунку виконавець ставить `sha` = `git rev-parse HEAD` після коміту артефактів. (Те саме семантика — в templates/DEPENDS.yaml, WP-04.)
Залежність із префіксом `/` — шлях від кореня git-репо (наприклад `/flow/decisions.md` — рішення власника), без префікса — від кореня галузі.
Артефакт застарілий, якщо будь-яка залежність змінилась між його `sha` і --base, або залежить від застарілого артефакта (транзитивно).
STALE-list: PASS — застарілих немає; FAIL — є (msg: список у порядку перерахунку — спершу ті, що не залежать від інших застарілих);
WARN — для артефактів без `sha` (не зафіксовано, не вважаються застарілими). Git лише читається (diff --name-only); репо не змінюється."""
import argparse, importlib.util, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
_s = importlib.util.spec_from_file_location("_miniyaml", os.path.join(HERE, "_miniyaml.py"))
Y = importlib.util.module_from_spec(_s); _s.loader.exec_module(Y)
res = []


def add(i, status, msg=""):
    res.append({"id": i, "status": status, "msg": msg})


def git(root, *a):
    r = subprocess.run(["git", "-C", root, *a], capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr.strip()[:150]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("depends"); ap.add_argument("--base", required=True)
    a = ap.parse_args()
    try:
        data = Y.loads(open(a.depends, encoding="utf-8").read()) or {}
    except Exception as e:  # noqa
        add("STALE-list", "FAIL", f"Не вдалося прочитати {a.depends}: {str(e)[:80]}")
        print(json.dumps(res, ensure_ascii=False, indent=1)); sys.exit(1)
    arts = data.get("artifacts") or {}
    d = os.path.dirname(os.path.abspath(a.depends))
    root = os.path.dirname(d) if os.path.basename(d) == "research" else d
    if git(root, "rev-parse", "--git-dir")[0] != 0:
        add("STALE-list", "SKIP", "тека не в git-репо"); print(json.dumps(res, ensure_ascii=False, indent=1)); sys.exit(0)
    top = git(root, "rev-parse", "--show-toplevel")[1].strip() or root
    rc, out, err = git(root, "rev-parse", "--verify", "--quiet", a.base + "^{commit}")
    if rc != 0:
        add("STALE-list", "FAIL", f"Базовий коміт {a.base[:12]} не знайдено в репо: git fetch origin <повний SHA>")
        print(json.dumps(res, ensure_ascii=False, indent=1)); sys.exit(1)
    direct, nosha, bad, newer = {}, [], [], []
    for art, spec in arts.items():
        sha = (spec or {}).get("sha")
        if not sha:
            nosha.append(art); continue
        if git(root, "rev-parse", "--verify", "--quiet", str(sha) + "^{commit}")[0] != 0:
            bad.append(f"{art}: коміт {str(sha)[:12]} відсутній"); continue
        ch = []
        upper = a.base
        if git(root, "merge-base", "--is-ancestor", str(sha), a.base)[0] != 0:  # sha новіший за base / не предок
            upper = "HEAD"; newer.append(art)
        for dep in (spec.get("depends_on") or []):
            if dep in arts:  # залежність від іншого артефакта — через транзитивність
                pass
            spec_path = dep.rstrip("/")[1:] if dep.startswith("/") else "./" + dep.rstrip("/")
            rc, out, _ = git(root if not dep.startswith("/") else top, "diff", "--name-only", str(sha), upper, "--", spec_path)
            if rc == 0 and out.strip():
                ch.append(dep)
        if ch:
            direct[art] = ch
    stale = set(direct)
    changed = True
    while changed:
        changed = False
        for art, spec in arts.items():
            if art in stale or art in nosha:
                continue
            if any(dep in stale for dep in ((spec or {}).get("depends_on") or [])):
                stale.add(art); changed = True
    # порядок перерахунку: топологічний серед застарілих
    order, left = [], set(stale)
    while left:
        ready = sorted(x for x in left if not any(dep in left for dep in ((arts[x] or {}).get("depends_on") or []) if dep != x))
        if not ready:
            ready = sorted(left)
        order += ready; left -= set(ready)
    if bad:
        add("STALE-sha-missing", "FAIL", "Коміт sha відсутній у репо (squash/свіжий клон?): git fetch origin <повний SHA> або перезапиши sha на коміт main: " + "; ".join(bad))
    if newer:
        add("STALE-order", "WARN", f"sha новіший за --base або не його предок ({len(newer)}): " + ", ".join(newer[:8]) + "; порівняно sha..HEAD. Передавай --base = голова результату кроку")
    if bad:
        pass
    elif stale:
        parts = [f"{x} (змінено: {', '.join(direct[x])})" if x in direct else f"{x} (залежить від застарілого)" for x in order]
        add("STALE-list", "FAIL", "Застарілі артефакти, порядок перерахунку (наряд params.mode: recalc): " + "; ".join(parts))
    else:
        add("STALE-list", "PASS")
    if nosha:
        add("STALE-sha", "WARN", f"Без sha в DEPENDS.yaml ({len(nosha)}): " + ", ".join(nosha[:8]) + (" …" if len(nosha) > 8 else ""))
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(1 if any(r["status"] == "FAIL" for r in res) else 0)


if __name__ == "__main__":
    main()
