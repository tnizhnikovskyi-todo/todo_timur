#!/usr/bin/env python3
"""Автоперевірка реєстру відкинутого (REJ-*). stdlib. Вивід: JSON [{id,status,msg}]; код виходу 1, якщо є FAIL.
Використання: check_rejected.py <реєстр або артефакт> [--intake OWNER-INTAKE.md] [--k1 research/K1.md]
Формат — flow-core/references/rejected-register.md (колонки читаються звідти; запасний перелік зашито нижче).
REJ-exists — файл є; є таблиця реєстру (колонка «ID») або розділ «## Відкинуто» / рядок «нічого не відкинуто».
REJ-fields — перші 8 колонок канонічні; ID `REJ-\\d{3}` унікальні; група ∈ G1|G2|G3|G4|G4а (кирилична «а»); причина, умова
             повернення непорожні; доказ непорожній (немає — «гіпотеза»).
REJ-dnr   — (з --k1 — лише непорожня відповідь у колонці «Відповідь власника» (колонка шукається за заголовком); відповідь «повернути» цієї позиції не підтверджує відкидання; питання без відповіді не рахується) позиція з do_not_reject анкети в реєстрі без посилання на рішення K1 (K1-Qn у колонці «рішення» або в --k1 відповідь) і не G4а — FAIL.
Відповідь власника: повернення = `повернут|не відкидати|лишити|залишити|ні` (без ID REJ — усі рядки реєстру з цим K1-Qn); підтвердження відкидання = лише явне `відкинути|так|згоден|підтверджую`; інша непорожня відповідь — MANUAL «відповідь неоднозначна» (не PASS). --k1 передано, а файла немає — FAIL.
REJ-returned — з --k1: кожна позиція, яку власник у колонці «Відповідь власника» повернув («повернути: REJ-NNN», «повернути все»), мусить бути в G4а — інакше FAIL (також без do_not_reject).
REJ-class-rule — MANUAL, якщо в анкеті задано class_rule (у реєстрі давати точну назву позиції з анкети).
REJ-count — підсумкова таблиця «група | позицій» (якщо є) збігається з кількістю рядків; з --k1: кількість кандидатів не менша за REJ у реєстрі."""
import argparse, importlib.util, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
_s = importlib.util.spec_from_file_location("_miniyaml", os.path.join(HERE, "_miniyaml.py"))
Y = importlib.util.module_from_spec(_s); _s.loader.exec_module(Y)
REGISTER_MD = os.path.normpath(os.path.join(HERE, "..", "..", "..", "references", "rejected-register.md"))
FALLBACK_COLS = ["ID", "назва", "група", "причина", "доказ", "умова повернення", "де живе зараз", "рішення (K1/гейт, дата)"]
GROUPS = {"G1", "G2", "G3", "G4", "G4а"}  # G4а — кирилична «а»
res = []


def add(i, status, msg=""):
    res.append({"id": i, "status": status, "msg": msg})


def canon_cols():
    try:
        t = open(REGISTER_MD, encoding="utf-8").read()
        m = re.search(r"## Колонки[^\n]*\n(.+)", t)
        cols = [c.strip().strip("`") for c in m.group(1).split("·")]
        if len(cols) >= 8:
            return cols[:8]
    except Exception:  # noqa
        pass
    return FALLBACK_COLS


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[*_`«»\"']", "", s)).strip().lower()


def base(c):
    return norm(re.sub(r"\(.*", "", c))


def tables(text):
    """[(heading, header, rows[(line, cells)])] для md-таблиць."""
    out, cur, head, lines = [], None, "", text.splitlines()
    for n, l in enumerate(lines, 1):
        if l.startswith("#"):
            head = l.lstrip("# ").strip()
        if l.startswith("|"):
            cells = [c.strip() for c in l.strip().strip("|").split("|")]
            if cur is None:
                cur = {"head": head, "hdr": cells, "rows": [], "line": n, "sep": False}
                out.append(cur)
            elif not cur["sep"] and all(re.fullmatch(r":?-{2,}:?|\s*", c) for c in cells):
                cur["sep"] = True
            else:
                cur["rows"].append((n, cells))
        else:
            cur = None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file"); ap.add_argument("--intake"); ap.add_argument("--k1")
    a = ap.parse_args()
    try:
        text = open(a.file, encoding="utf-8").read()
    except OSError:
        text = ""
    if not text.strip():
        add("REJ-exists", "FAIL", f"Немає або порожній {a.file}: створи реєстр відкинутого за flow-core/references/rejected-register.md (рядок «нічого не відкинуто» — якщо так)")
        for i in ("REJ-fields", "REJ-dnr", "REJ-count"):
            add(i, "SKIP", "немає реєстру")
        print(json.dumps(res, ensure_ascii=False, indent=1)); sys.exit(1)
    cols = canon_cols()
    reg_tabs = [t for t in tables(text) if t["hdr"] and norm(t["hdr"][0]) == "id" and len(t["hdr"]) >= 3 and "група" in [base(h) for h in t["hdr"]]]
    has_section = bool(re.search(r"(?im)^#{1,4}\s*відкинуто", text))
    none_rejected = bool(re.search(r"(?i)нічого\s+не\s+відкинуто", text))
    if not reg_tabs and not (has_section or none_rejected):
        add("REJ-exists", "FAIL", "Немає таблиці реєстру (колонки ID, назва, група…) і розділу «## Відкинуто»: додай реєстр або рядок «нічого не відкинуто»")
    elif not reg_tabs and has_section and not none_rejected:
        add("REJ-exists", "FAIL", "Розділ «Відкинуто» без таблиці реєстру: додай таблицю з 8 колонками або «нічого не відкинуто»")
    else:
        add("REJ-exists", "PASS")
    # REJ-fields
    bad, ids, rows_all = [], {}, []
    for t in reg_tabs:
        for k, c in enumerate(cols):
            h = t["hdr"][k] if k < len(t["hdr"]) else ""
            if base(h) != base(c) and not base(h).startswith(base(c)):
                bad.append(f"таблиця «{t['head'][:30]}» колонка {k + 1}: «{h}» ≠ «{c}»")
        gi = [base(h) for h in t["hdr"]].index("група") if "група" in [base(h) for h in t["hdr"]] else 2
        for n, r in t["rows"]:
            if not any(x for x in r):
                continue
            rows_all.append((n, r, t))
            rid = r[0].strip("` *")
            if not re.fullmatch(r"REJ-\d{3}", rid):
                if rid and not re.fullmatch(r"\{\{.*\}\}|", rid):
                    bad.append(f"рядок {n}: ID «{rid}» не за шаблоном REJ-NNN")
                continue
            if rid in ids:
                bad.append(f"рядок {n}: дубль ID {rid} (перший — {ids[rid]})")
            ids[rid] = n
            g = r[gi].strip("` *") if gi < len(r) else ""
            if g not in GROUPS:
                lat = g.replace("a", "а") in GROUPS
                bad.append(f"{rid}: група «{g}» не з G1|G2|G3|G4|G4а" + (" (латинська «a» замість кириличної «а»)" if lat else ""))
            for k in (3, 4, 5):
                if k < len(r) and not r[k].strip(" -—"):
                    bad.append(f"{rid}: порожня колонка «{cols[k]}»" + (" (немає доказу — напиши «гіпотеза»)" if k == 4 else ""))
    if reg_tabs:
        add("REJ-fields", "FAIL" if bad else "PASS", ("Виправ реєстр: " + "; ".join(bad[:10])) if bad else "")
    else:
        add("REJ-fields", "SKIP", "таблиць реєстру немає (порожній реєстр)")
    # K1: відповіді власника й повернуте
    k1 = ""
    if a.k1 and os.path.exists(a.k1):
        k1 = open(a.k1, encoding="utf-8").read()
    viol, viol_ret, ambig = [], [], []
    k1_missing = bool(a.k1) and not os.path.exists(a.k1)
    RET = re.compile(r"(?i)повернут|не\s+відкидати|лишити|залишити|(?<!\w)ні(?!\w)")
    CONF = re.compile(r"(?i)відкинути|(?<!\w)так(?!\w)|згоден|підтверджую")
    answers, returned, ret_all = {}, set(), set()  # K1-Qn -> непорожня відповідь у колонці «Відповідь власника» (за заголовком, не за позицією)
    for t in tables(k1):
        ai = next((i for i, h in enumerate(t["hdr"]) if "відповідь власника" in norm(h)), None)
        if ai is None:
            continue  # таблиці без цієї колонки (напр. прогалини K1-Q3…) відповідей не дають
        for _, cells in t["rows"]:
            q = re.match(r"K1-Q\d+$", cells[0].strip("` *")) if cells else None
            ans = cells[ai].strip() if ai < len(cells) else ""
            if q and ans and not re.fullmatch(r"[\s\-—]*|\{\{.*\}\}", ans):
                if RET.search(ans):
                    ret_all_ids = set(re.findall(r"REJ-\d{3}", ans))
                    if ret_all_ids:
                        returned |= ret_all_ids
                    else:
                        ret_all.add(q.group(0))  # без ID: повернено все, що посилається на це K1-Qn
                elif CONF.search(ans):
                    answers[q.group(0)] = ans
                else:
                    ambig.append(f"{q.group(0)}: «{ans[:40]}»")
    for n, r, t in rows_all:  # повернене власником має бути в G4а — незалежно від do_not_reject
        grp = r[2].strip("` *") if len(r) > 2 else ""
        qs = set(re.findall(r"K1-Q\d+", r[7] if len(r) > 7 else ""))
        if grp.replace("a", "а") != "G4а" and (r[0].strip("` *") in returned or any(q in ret_all for q in qs)):
            viol_ret.append(f"{r[0]} (рядок {n})")
    viol_ret.extend(f"{i}: немає в реєстрі" for i in sorted(returned) if i not in ids)
    if k1_missing:
        add("REJ-returned", "FAIL", f"--k1 передано, але файла немає: {a.k1}")
    elif a.k1 and viol_ret:
        add("REJ-returned", "FAIL", "Власник повернув у K1 («повернути: …»), але позиції не в групі G4а: " + "; ".join(viol_ret[:8]) + " — переведи в G4а (кирилична «а»)")
    elif a.k1 and ambig:
        add("REJ-returned", "MANUAL", "відповідь неоднозначна (не повернення і не підтвердження відкидання): " + "; ".join(ambig[:6]))
    elif a.k1:
        add("REJ-returned", "PASS")
    # REJ-dnr
    if a.intake:
        try:
            intake = open(a.intake, encoding="utf-8").read()
            m = re.search(r"```ya?ml\s*\n(.*?)```", intake, re.S)
            dnr = (Y.loads(m.group(1)) or {}).get("do_not_reject", {}) if m else {}
            items, cls = dnr.get("items"), dnr.get("class_rule")
        except Exception:  # noqa
            items, cls = None, None
        items = [str(x) for x in (items or [])]
        viol = []
        for it in items:
            ni = norm(it)
            for n, r, t in rows_all:
                if ni and (ni in norm(r[1]) or norm(r[1]) in ni) and norm(r[1]):
                    grp = r[2].strip("` *") if len(r) > 2 else ""
                    dec = r[7] if len(r) > 7 else ""
                    qs = re.findall(r"K1-Q\d+", dec)
                    backed = grp == "G4а"
                    if r[0].strip("` *") in returned or any(q in ret_all for q in qs):
                        backed = backed  # власник повернув цю позицію: підтвердженням відкидання вона не є
                    elif k1_missing:
                        backed = False
                    elif qs and not a.k1:
                        backed = True  # --k1 не передано: лише посилання на K1-Qn у колонці «рішення»
                    elif qs:
                        backed = backed or any(answers.get(q) for q in qs)  # потрібна непорожня відповідь власника
                    if not backed:
                        viol.append(f"{r[0]} «{it[:30]}» (рядок {n})" + (" — K1-Qn без відповіді власника" if qs else ""))
        if not items:
            add("REJ-dnr", "SKIP", "у анкеті немає do_not_reject.items")
        else:
            add("REJ-dnr", "FAIL" if (viol or k1_missing) else ("MANUAL" if ambig else "PASS"),
                (f"--k1 передано, але K1.md немає ({a.k1}) — підтвердження відкидання не перевірити. " if k1_missing else "") + ("Зніми з відкинутого або додай у колонку «рішення» посилання на K1-Qn, на яке власник відповів (відповідь у K1; внесено AI від імені власника, К-08): " + "; ".join(viol)) if viol else ("відповідь власника неоднозначна: " + "; ".join(ambig[:6]) if (ambig and not k1_missing) else ""))
            if cls:
                add("REJ-class-rule", "MANUAL", f"class_rule анкети: «{str(cls)[:80]}» — перевір очима позиції цього класу у відкинутому (скрипт звіряє лише items за назвою)")
    else:
        add("REJ-dnr", "SKIP", "--intake не передано")
    # REJ-count
    probs = []
    for t in tables(text):
        if len(t["hdr"]) >= 2 and "група" in norm(t["hdr"][0]) and "позиц" in norm(t["hdr"][1]):
            for n, r in t["rows"]:
                m = re.match(r"^\W*(\d+)[а-я]?\.", r[0].strip("* ")) or re.match(r"^\W*(\d+)\b", r[0].strip("* "))
                if not m or not r[1].strip().isdigit() or "разом" in norm(r[0]):
                    continue
                gname = f"G{m.group(1)}" + ("а" if re.match(r"^\W*4а", r[0].strip("* ")) else "")
                actual = sum(1 for _, rr, _ in rows_all if len(rr) > 2 and rr[2].strip("` *") == gname)
                if actual != int(r[1]):
                    probs.append(f"{gname}: у підсумку {r[1]}, у таблицях {actual}")
    if a.k1 and os.path.exists(a.k1) and ids:
        k1t = open(a.k1, encoding="utf-8").read()
        cand = set(re.findall(r"REJ-\d{3}", k1t))
        probs += [f"{i} є в реєстрі, але не показувався в K1" for i in sorted(ids) if cand and i not in cand][:5]
    if probs:
        add("REJ-count", "FAIL", "Узгодь підсумок і рядки: " + "; ".join(probs[:8]))
    else:
        add("REJ-count", "PASS" if (ids or none_rejected) else "SKIP", "" if (ids or none_rejected) else "немає рядків")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(1 if any(r["status"] == "FAIL" for r in res) else 0)


if __name__ == "__main__":
    main()
