#!/usr/bin/env python3
"""Автоперевірка реєстру «не робимо й чому» (REJ-*). stdlib. Вивід: JSON [{id,status,msg}]; код виходу 1, якщо є FAIL.
Використання: check_rejected.py <реєстр або артефакт> [--intake ...] [--k1 ...]   (останні два — застарілі, ігноруються з WARN)
Формат — flow-core/references/rejected-register.md (0.3.0): мінімум `ID (REJ-NNN) · що не робимо · чому`; необов'язково `коли повернутись`.
Колонки шукаються за назвами (ID; назва|що; причина|чому), додаткові колонки ігноруються — старі 8-колонкові таблиці проходять.
REJ-exists — файл є й непорожній; є таблиця реєстру, розділ «## Не робимо» / «## Відкинуто» або рядок «нічого не відкинуто / не робимо».
REJ-fields — ID `REJ-\\d{3}` унікальні; «що не робимо» і «чому» непорожні; таблиця з ID без колонки «чому» — FAIL.
REJ-count  — якщо є рядок підсумку «Разом/Всього: N», N збігається з кількістю рядків; реєстр непорожній або явно «нічого не відкинуто».
REJ-args   — WARN «застарілий аргумент 0.2.0», якщо передано --intake / --k1 (REJ-dnr, REJ-returned, REJ-class-rule вилучено в 0.3.0)."""
import argparse, json, re, sys

res = []


def add(i, status, msg=""):
    res.append({"id": i, "status": status, "msg": msg})


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[*_`«»\"']", "", s)).strip().lower()


def base(c):
    return norm(re.sub(r"\(.*", "", c))


def tables(text):
    """[{head, hdr, rows[(line, cells)]}] для md-таблиць."""
    out, cur, head = [], None, ""
    for n, l in enumerate(text.splitlines(), 1):
        if l.startswith("#"):
            head = l.lstrip("# ").strip()
        if l.startswith("|"):
            cells = [c.strip() for c in l.strip().strip("|").split("|")]
            if cur is None:
                cur = {"head": head, "hdr": cells, "rows": [], "sep": False}
                out.append(cur)
            elif not cur["sep"] and all(re.fullmatch(r":?-{2,}:?|\s*", c) for c in cells):
                cur["sep"] = True
            else:
                cur["rows"].append((n, cells))
        else:
            cur = None
    return out


def colidx(hdr, pred):
    for i, h in enumerate(hdr):
        if pred(base(h)):
            return i
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file"); ap.add_argument("--intake"); ap.add_argument("--k1")
    a = ap.parse_args()
    for flag in ("intake", "k1"):
        if getattr(a, flag):
            add("REJ-args", "WARN", f"--{flag} — застарілий аргумент 0.2.0, ігнорується (REJ-dnr/REJ-returned вилучено в 0.3.0)")
    try:
        text = open(a.file, encoding="utf-8").read()
    except OSError:
        text = ""
    if not text.strip():
        add("REJ-exists", "FAIL", f"Немає або порожній {a.file}: створи реєстр «не робимо й чому» за flow-core/references/rejected-register.md (рядок «нічого не відкинуто» — якщо так)")
        for i in ("REJ-fields", "REJ-count"):
            add(i, "SKIP", "немає реєстру")
        print(json.dumps(res, ensure_ascii=False, indent=1)); sys.exit(1)
    reg_tabs = [t for t in tables(text) if t["hdr"] and base(t["hdr"][0]) == "id"
                and (colidx(t["hdr"], lambda b: b.startswith("назва") or b.startswith("що не роб")) is not None
                     or any(re.match(r"\s*`?REJ-", c[0]) for _, c in t["rows"] if c))]
    reg_tabs = [t for t in reg_tabs if not any(
        re.match(r"\s*`?[A-Z]+-\d", c[0]) and not re.match(r"\s*`?REJ", c[0]) for _, c in t["rows"] if c)
        or any(re.match(r"\s*`?REJ-", c[0]) for _, c in t["rows"] if c)]  # таблиці AI-/REUSE-/REQ- — не реєстр
    has_section = bool(re.search(r"(?im)^#{1,4}\s*(не\s+робимо|відкинуто)", text))
    none_rejected = bool(re.search(r"(?i)нічого\s+не\s+(відкинуто|робимо)", text))
    if not reg_tabs and not (has_section or none_rejected):
        add("REJ-exists", "FAIL", "Немає таблиці реєстру (колонки ID, що не робимо, чому) і розділу «## Не робимо»: додай реєстр або рядок «нічого не відкинуто»")
    elif not reg_tabs and has_section and not none_rejected:
        add("REJ-exists", "FAIL", "Розділ «Не робимо / Відкинуто» без таблиці реєстру: додай таблицю ID · що не робимо · чому або «нічого не відкинуто»")
    else:
        add("REJ-exists", "PASS")
    bad, ids, nrows = [], {}, 0
    for t in reg_tabs:
        ni = colidx(t["hdr"], lambda b: b.startswith("назва") or b.startswith("що"))
        ri = colidx(t["hdr"], lambda b: b.startswith("причина") or b.startswith("чому"))
        if ni is None:
            bad.append(f"таблиця «{t['head'][:30]}»: немає колонки «що не робимо» (назва)")
        if ri is None:
            bad.append(f"таблиця «{t['head'][:30]}»: немає колонки «чому» (причина)")
        for n, r in t["rows"]:
            if not any(x for x in r):
                continue
            rid = r[0].strip("` *")
            if not re.fullmatch(r"REJ-\d{3}", rid):
                if rid and not re.fullmatch(r"\{\{.*\}\}", rid):
                    bad.append(f"рядок {n}: ID «{rid}» не за шаблоном REJ-NNN")
                continue
            nrows += 1
            if rid in ids:
                bad.append(f"рядок {n}: дубль ID {rid} (перший — {ids[rid]})")
            ids[rid] = n
            for k, label in ((ni, "що не робимо"), (ri, "чому")):
                if k is not None and (k >= len(r) or not r[k].strip(" -—")):
                    bad.append(f"{rid}: порожня колонка «{label}»")
    if reg_tabs:
        add("REJ-fields", "FAIL" if bad else "PASS", ("Виправ реєстр: " + "; ".join(bad[:10])) if bad else "")
    else:
        add("REJ-fields", "SKIP", "таблиць реєстру немає (порожній реєстр)")
    probs = []
    m = re.search(r"(?im)^\W*(?:разом|всього)\W*[:\-—]?\s*(\d+)\b", text)
    if m and ids and int(m.group(1)) != nrows:
        probs.append(f"у підсумку {m.group(1)}, у таблицях {nrows}")
    if probs:
        add("REJ-count", "FAIL", "Узгодь підсумок і рядки: " + "; ".join(probs))
    elif ids or none_rejected:
        add("REJ-count", "PASS")
    else:
        add("REJ-count", "SKIP", "немає рядків")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(1 if any(r["status"] == "FAIL" for r in res) else 0)


if __name__ == "__main__":
    main()
