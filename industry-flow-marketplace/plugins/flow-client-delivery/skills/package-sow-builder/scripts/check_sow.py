#!/usr/bin/env python3
"""Автоперевірки clients/<к>/sow.md (B-03). Вихід: JSON [{id, status, msg}]. Лише stdlib.
Без потрібного аргумента перевірка -> SKIP (не PASS). Значень ПДн у msg немає.
Використання: check_sow.py <sow.md> --mode main|addendum --tag <тег> [--fit-gap f] [--answers f] [--data-policy f]
  [--business-case f] [--reference-clients f] [--base <sha>] [--source tr|scope|answers|changelog] [--tr f]
  [--first-run|--rerun] [--repo dir]"""
import argparse, json, re, subprocess
from pathlib import Path

REQUIRED = ["Обсяг", "Позиції", "Доробки (для шлюзу)", "Версія пакета", "Редакція Odoo і хостинг", "Ціна", "Терміни",
            "Залежності від клієнта", "Договір супроводу", "Умови оновлення пакета", "Критерії приймання",
            "Зобов'язання клієнта", "Пункт про AI і дані", "Допущення", "Відповіді анкети", "Додатки", "Підписи"]
MARKS = {"з пакета", "доналаштування", "доробка"}
TAGRE = re.compile(r"^package/v\d+\.\d+(\.\d+)?$")
PII = {"email": r"[\w.+-]+@[\w-]+\.[\w.-]+", "phone": r"(?<![\w:])(\+?380\d{9}|0\d{9})(?!\w)",
       "iban": r"\bUA\d{2}[\s\d]{20,}|ЄДРПОУ\D{0,5}\d{8}\b", "secret": r"(?i)(password|passwd|pwd|api[_-]?key|token|secret)\s*[:=]\s*\S+"}
FIO = re.compile(r"\b[А-ЯІЇЄҐ][а-яіїєґ'’-]+\s+[А-ЯІЇЄҐ][а-яіїєґ'’-]+\s+[А-ЯІЇЄҐ][а-яіїєґ'’-]+\b")
OUT = []


def add(i, st, msg=""):
    OUT.append({"id": i, "status": st, "msg": msg})


def read(p):
    return Path(p).read_text(encoding="utf-8") if p and Path(p).is_file() else None


def norm(t):
    return re.sub(r"\s+", " ", t or "").strip()


def sections(text, level=2):
    out, cur = {}, None
    for l in text.splitlines():
        m = re.match(r"^(#{2,3})\s+(.*?)\s*$", l)
        if m and len(m.group(1)) <= level + 1:
            cur = m.group(2); out[cur] = []
        elif cur is not None:
            out[cur].append(l)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def top_sections(text):
    out, cur = {}, None
    for l in text.splitlines():
        m = re.match(r"^##\s+(?!#)(.*?)\s*$", l)
        if m:
            cur = re.sub(r"\s*\([^)]*\)\s*$", "", m.group(1)); out[cur] = []
        elif cur is not None:
            out[cur].append(l)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def table(body):
    hdr, rows = None, []
    for l in body.splitlines():
        if not l.startswith("|") or re.match(r"^\|[\s:|-]+\|?\s*$", l):
            continue
        c = [x.strip() for x in re.split(r"(?<!\\)\|", l.strip().strip("|"))]
        if hdr is None:
            hdr = [x.lower() for x in c]
        else:
            rows.append(dict(zip(hdr, c)))
    return rows


def col(r, *names):
    for k, v in r.items():
        if any(k.startswith(n) for n in names):
            return v
    return ""


def num(s):
    s = re.sub(r"[^\d,.\-–—]", "", (s or "").replace(" ", ""))
    parts = re.split(r"[–—-]", s.strip("-–—")) if s else []
    vals = []
    for p in parts:
        p = p.replace(",", ".")
        try:
            vals.append(float(p))
        except ValueError:
            pass
    return max(vals) if vals else None


def fg_parse(text):
    S = top_sections(text)
    req = [r for r in table(S.get("Вимоги", "")) if re.match(r"FG-\d+", col(r, "id"))]
    live = [r for r in req if "знято" not in (col(r, "рішення", "вимога") + col(r, "примітка")).lower()]
    contra = [l for l in S.get("Суперечності й відкриті питання", "").splitlines()
              if re.match(r"^\s*([-*]|\d+[.)])\s+\S", l) or (l.startswith("|") and not re.match(r"^\|[\s:|-]+\|?\s*$", l))]
    contra = [l for l in contra if not re.match(r"^\|\s*(id|#)\b", l, re.I)]
    notes = [r for r in live if col(r, "примітка").strip(" -—")]
    return live, len(contra), len(notes)


def parse_answers(text):
    d = {}
    for l in text.splitlines():
        m = re.match(r"^\s*(VP-\d+)\s*:\s*(.*?)\s*(#.*)?$", l)
        if m:
            d[m.group(1)] = m.group(2).strip("'\"")
    return d


def git(repo, *a):
    return subprocess.run(["git", "-C", repo or ".", *a], capture_output=True, text=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sow"); ap.add_argument("--mode", required=True, choices=["main", "addendum"])
    ap.add_argument("--tag"); ap.add_argument("--fit-gap"); ap.add_argument("--answers"); ap.add_argument("--data-policy")
    ap.add_argument("--business-case"); ap.add_argument("--reference-clients"); ap.add_argument("--base")
    ap.add_argument("--source"); ap.add_argument("--tr"); ap.add_argument("--repo")
    ap.add_argument("--first-run", action="store_true"); ap.add_argument("--rerun", action="store_true")
    a = ap.parse_args()
    sow = read(a.sow)
    if sow is None:
        print(json.dumps([{"id": "SOW-file", "status": "FAIL", "msg": "sow.md не знайдено"}], ensure_ascii=False)); return
    S = top_sections(sow)
    sub = sections(sow)
    main = a.mode == "main"
    fg_text, ans_text = read(a.fit_gap), read(a.answers)
    live = []
    if fg_text:
        live, ncontra, nnotes = fg_parse(fg_text)

    # SOW-sections
    if main:
        miss = [h for h in REQUIRED if h not in S and h not in sub]
        msg = "немає заголовків: " + ", ".join(miss) if miss else ""
        if not miss and fg_text:
            rows = table(S.get("Допущення", ""))
            n = sum(1 for r in rows if "fit-gap" in col(r, "джерело").lower())
            if n != ncontra + nnotes:
                miss, msg = ["count"], f"допущень з джерелом fit-gap {n}, у fit-gap {ncontra + nnotes}"
        add("SOW-sections", "FAIL" if miss else "PASS", msg)
    else:
        add("SOW-sections", "SKIP", "режим addendum")

    # SOW-coverage
    if main and fg_text:
        pos = {col(r, "id"): col(r, "відмітка").lower() for r in table(S.get("Позиції", "")) if re.match(r"FG-\d+", col(r, "id"))}
        fg = {col(r, "id"): col(r, "рішення").lower() for r in live}
        bad = sorted(set(pos) ^ set(fg)) + [k for k in fg if k in pos and pos[k] != fg[k]]
        badm = [k for k, v in pos.items() if v not in MARKS]
        add("SOW-coverage", "FAIL" if bad or badm else "PASS", ("ID/відмітки не збігаються: " + ", ".join(bad + badm)) if bad or badm else "")
    else:
        add("SOW-coverage", "SKIP", "немає fit-gap чи режим addendum")

    # SOW-price
    if main:
        rows = [r for r in table(S.get("Позиції", "")) if re.match(r"FG-\d+", col(r, "id"))]
        pr = table(S.get("Ціна", ""))
        errs = []
        for r in rows:
            if not col(r, "ціна") or not col(r, "термін"):
                errs.append(f"{col(r, 'id')}: немає ціни/терміну")
        amt = {col(r, "стаття").lower(): num(col(r, "сума")) for r in pr}
        total = next((v for k, v in amt.items() if k.startswith("разом")), None)
        parts = [v for k, v in amt.items() if not k.startswith("разом") and v is not None]
        if total is not None and abs(sum(parts) - total) > 0.5:
            errs.append(f"Разом {total} != сума статей {sum(parts)}")
        pos_sum = sum(num(col(r, "ціна")) or 0 for r in rows)
        dn = next((v for k, v in amt.items() if k.startswith("доналаштування")), None)
        db = next((v for k, v in amt.items() if k.startswith("доробки")), None)
        if dn is not None or db is not None:
            if abs(pos_sum - ((dn or 0) + (db or 0))) > 0.5:
                errs.append(f"сума цін позицій {pos_sum} != доналаштування+доробки {(dn or 0) + (db or 0)}")
        if "enterprise" in S.get("Редакція Odoo і хостинг", "").lower() and not any(k.startswith("ліцензія") for k in amt):
            errs.append("Enterprise без рядка ліцензії")
        add("SOW-price", "FAIL" if errs else "PASS", "; ".join(errs))
    else:
        add("SOW-price", "SKIP", "режим addendum")

    # SOW-tag
    m = re.search(r"Git-тег:\s*`?([^\s`(]+)`?", sow)
    if not a.tag:
        add("SOW-tag", "SKIP", "немає --tag")
    else:
        errs = []
        if not TAGRE.match(a.tag):
            errs.append("форма тегу з наряду не package/vX.Y[.Z]")
        if main and (not m or m.group(1) != a.tag):
            errs.append("Git-тег у SOW != тег наряду")
        if not main and a.tag not in sow:
            errs.append("тег наряду не згадано в додатку")
        if git(a.repo, "rev-parse", "-q", "--verify", f"refs/tags/{a.tag}").returncode != 0:
            errs.append("git не знаходить тег")
        add("SOW-tag", "FAIL" if errs else "PASS", "; ".join(errs))

    # SOW-ac
    if main:
        errs = []
        for r in table(S.get("Позиції", "")):
            i, mk, ac = col(r, "id"), col(r, "відмітка").lower(), col(r, "приймання")
            if not re.match(r"FG-\d+", i):
                continue
            if mk == "з пакета" and not re.search(r"\bS-\d+", ac):
                errs.append(f"{i}: немає сценарію A-16")
            elif mk == "доналаштування" and not re.search(r"\b(S|CS)-\d+", ac):
                errs.append(f"{i}: немає S-xx чи CS-xx")
            elif mk == "доробка" and (re.search(r"\b(S|CS)-\d+", ac) or "ТР-доробок.md" not in ac):
                errs.append(f"{i}: доробка має лише посилання на ТР-доробок.md")
        for r in table(S.get("Критерії приймання", "")):
            if "ID позиції" in r or any(k.startswith("id позиції") for k in r):
                if not all(col(r, k) for k in ("очікувана", "роль", "підтвердження")):
                    errs.append(f"{col(r, 'id')}: порожнє поле клієнтського рядка")
        add("SOW-ac", "FAIL" if errs else "PASS", "; ".join(errs))
    else:
        add("SOW-ac", "SKIP", "режим addendum")

    # SOW-clarify
    if main:
        bad = [k for k, v in S.items() if k not in ("Допущення", "Відповіді анкети", "Додатки") and "уточнити" in v.lower()
               and not (k == "Критерії приймання" and "залежить від" in v.lower())]
        bad = [k for k in bad if k != "Критерії приймання" or re.search(r"уточнити(?! з BA)", S[k], re.I)]
        add("SOW-clarify", "FAIL" if bad else "PASS", ("«уточнити» у розділах: " + ", ".join(bad)) if bad else "")
    else:
        add("SOW-clarify", "SKIP", "режим addendum")

    # SOW-answers
    if not ans_text:
        add("SOW-answers", "SKIP", "немає answers.yaml")
    elif not main and a.first_run:
        add("SOW-answers", "MANUAL", "очікує людини (BA внесе ключі VP-xx з додатка в answers.yaml)")
    elif main:
        ay = parse_answers(ans_text)
        sv = {col(r, "vp-xx", "vp"): col(r, "значення") for r in table(S.get("Відповіді анкети", ""))}
        sv = {k: v for k, v in sv.items() if re.match(r"VP-\d+", k)}
        bad = [k for k in sorted(set(sv) | set(ay)) if sv.get(k) != ay.get(k)]
        add("SOW-answers", "FAIL" if bad else "PASS", ("розбіжність: " + ", ".join(bad)) if bad else "")
    else:
        ay = parse_answers(ans_text)
        keys = sorted(set(re.findall(r"VP-\d+", S.get("Додатки", ""))))
        miss = [k for k in keys if k not in ay]
        add("SOW-answers", "FAIL" if miss else "PASS", ("немає в answers.yaml: " + ", ".join(miss)) if miss else "")

    # SOW-nosla
    if main:
        rest = "\n".join(v for k, v in S.items() if k != "Договір супроводу")
        hit = re.findall(r"(?i)\bSLA\b|час реакції|год реакції|канал звернень", rest)
        add("SOW-nosla", "FAIL" if hit else "PASS", f"збігів поза «Договір супроводу»: {len(hit)}" if hit else "")
    else:
        add("SOW-nosla", "SKIP", "режим addendum")

    # SOW-ai / update / pilot
    dp = read(a.data_policy)
    if main and dp:
        ref = norm(top_sections(dp).get("Пункт про AI у договорі", ""))
        body = norm(S.get("Пункт про AI і дані", ""))
        if not ref or "відкрите питання" in ref.lower():
            add("SOW-ai", "FAIL", "розділ DATA_POLICY порожній чи відкрите питання (джерело C-05)")
        elif ref not in body:
            add("SOW-ai", "FAIL", "пункт про AI не дорівнює тексту DATA_POLICY")
        elif not re.search(r"верс", body, re.I):
            add("SOW-ai", "FAIL", "немає версії DATA_POLICY")
        else:
            add("SOW-ai", "PASS")
    else:
        add("SOW-ai", "SKIP", "немає DATA_POLICY чи режим addendum")
    if main:
        upd = S.get("Умови оновлення пакета", "")
        add("SOW-update", "FAIL" if (not upd or "відкрите питання" in upd.lower()) else "PASS",
            "умови оновлення відсутні — відкрите питання (Керівник напряму/Юрист)" if (not upd or "відкрите питання" in upd.lower()) else "")
    else:
        add("SOW-update", "SKIP", "режим addendum")
    bc, rc = read(a.business_case), read(a.reference_clients)
    if main and bc is not None and rc is not None:
        cid = (re.match(r"#\s*SOW:\s*(\S+)", sow) or [None, ""])[1]
        pilot = bool(cid) and re.search(re.escape(cid) + r"(?![\w-])", rc) is not None
        sec = norm(top_sections(bc).get("Умови участі еталонних клієнтів у пілоті", ""))
        have = norm(S.get("Умови пілота", "")) if "Умови пілота" in S else None
        if pilot:
            add("SOW-pilot", "PASS" if have and sec and have == sec else "FAIL", "" if have and sec and have == sec else "умови пілота не дорівнюють business-case")
        else:
            add("SOW-pilot", "FAIL" if have else "PASS", "розділ «Умови пілота» не має бути" if have else "")
    else:
        add("SOW-pilot", "SKIP", "немає business-case/reference-clients чи режим addendum")

    # SOW-sign
    sign = [l for k in ("Підписи",) for l in S.get(k, "").splitlines() if re.search(r"(Керівник напряму|Клієнт):", l)]
    sign += re.findall(r"(?m)^.*(?:Підпис Клієнта|Підписи:).*$", sow)
    bad = [l for l in sign if "[плейсхолдер" not in l]
    add("SOW-sign", "MANUAL" if not bad else "FAIL", "очікує людини: підписи й погодження строків" if not bad else "підпис без плейсхолдера")

    # SOW-pii
    hits = []
    for n, l in enumerate(sow.splitlines(), 1):
        for t, rx in PII.items():
            if re.search(rx, l) and not re.search(r"@example\.", l):
                hits.append(f"{t}:{n}")
        if FIO.search(l):
            hits.append(f"піб?:{n}")
    fails = [h for h in hits if not h.startswith("піб")]
    add("SOW-pii", "FAIL" if fails else ("MANUAL" if hits else "PASS"), ", ".join(hits))

    # addendum
    if not main:
        if not a.base:
            add("SOW-addendum-only", "SKIP", "немає --base")
        else:
            r = git(a.repo, "show", f"{a.base}:{a.sow}")
            if r.returncode:
                add("SOW-addendum-only", "FAIL", "не вдалося git show base")
            else:
                def split(t):
                    lines = t.splitlines(); i = next((n for n, l in enumerate(lines) if re.match(r"^##\s+Додатки\s*$", l)), None)
                    if i is None: return None
                    j = next((n for n in range(i + 1, len(lines)) if re.match(r"^##\s+(?!#)", lines[n])), len(lines))
                    return "\n".join(lines[:i]), "\n".join(lines[i + 1:j]), "\n".join(lines[j:])
                o, n_ = split(r.stdout), split(sow)
                errs = []
                if not o or not n_:
                    errs.append("немає розділу «Додатки»")
                else:
                    if o[0] != n_[0] or o[2] != n_[2]:
                        errs.append("змінено текст поза розділом «Додатки»")
                    old = re.sub(r"(?m)^\s*<порожньо.*>\s*$", "", o[1]).strip()
                    if not n_[1].strip().startswith(old):
                        errs.append("змінено попередні додатки")
                    nums = [int(x) for x in re.findall(r"(?m)^###\s+Додаток №(\d+)", n_[1])]
                    onums = [int(x) for x in re.findall(r"(?m)^###\s+Додаток №(\d+)", o[1])]
                    if nums != list(range(1, len(nums) + 1)) or len(nums) != len(onums) + 1:
                        errs.append(f"нумерація додатків {nums}, очікується {len(onums) + 1} нових = 1")
                add("SOW-addendum-only", "FAIL" if errs else "PASS", "; ".join(errs))
        if a.source == "tr" and a.tr and read(a.tr):
            trt = read(a.tr)
            acs = re.findall(r"(?m)^\|\s*(AC-[\w-]+)\s*\|\s*([^|]+?)\s*\|", trt) or re.findall(r"(?m)^\s*[-*]?\s*(AC-[\w-]+)[:.)\s]+(.+)$", trt)
            body = S.get("Додатки", "")
            miss = [i for i, t in acs if i not in body or norm(t) not in norm(body)]
            add("SOW-addendum-ac", "FAIL" if miss or not acs else "PASS", ("AC не збігаються: " + ", ".join(miss)) if miss else ("AC не знайдено в ТР-доробок.md" if not acs else ""))
        else:
            add("SOW-addendum-ac", "SKIP", "не режим tr чи немає --tr")
    print(json.dumps(OUT, ensure_ascii=False, indent=1))


main()
