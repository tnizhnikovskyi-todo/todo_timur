#!/usr/bin/env python3
"""Автоперевірка research/edition-claims.md (A-03b). stdlib. Вивід: JSON [{id,status,msg}]. Код виходу 1, якщо є FAIL.
Використання: check_edition_claims.py <research/edition-claims.md> [--scan <файл> ...]
Колонки рядка (шаблон edition-claims.tpl.md): ID | Редакція | Функція | Твердження | Вердикт | Доказ | Чого бракує | Дата.
Рядки читаються після strip (відступ не ховає рядок); `\\|` у клітинці не розбиває колонки; ID нормалізується (`**EC-001**`, `` `EC-001` `` = EC-001).
Перевірки:
  EC-verdict  — будь-який рядок таблиці з 8 колонками після заголовка: ID за EC-\\d{3} без дубля (інакше FAIL, не пропуск); редакція рівно CE або EE (порожньо, кирилична «СЕ», both = FAIL);
                вердикт із {повністю, частково, ні, не перевірено}; 0 рядків = FAIL.
  EC-evidence — вердикт, відмінний від «не перевірено», без доказу = FAIL. CE: `шлях.(py|xml|js|csv|po):N` або GitHub `…#LN` (посилання з `://`
                без #L, localhost, `:порт`, README.md:1, «версія 19.0:5» — не доказ); для «ні» — лише команда grep і «0 збігів».
                EE: https-URL + цитата («…»/"…"); URL не з odoo.com/documentation/19.0 = WARN «не документація 19.0»;
                або «база EE» з назвою/версією й датою РРРР-ММ-ДД (інакше FAIL). «не перевірено» в EE = WARN.
  EC-ce-unverified — CE «не перевірено»: код CE відкритий , тож без причини в колонці «Доказ» (слово «клон»: «клон недоступний: …») = FAIL;
                з причиною = WARN з лічильником «n з m CE-рядків».
  EC-partial  — «частково» без змістовної колонки «Чого бракує» (≥10 символів, не лише тире) = FAIL.
  Колонки     — рядок таблиці після заголовка з числом клітинок ≠ 8, або з першою клітинкою EC-… = FAIL у EC-verdict («рядок N: колонок 7, треба 8»), не пропуск.
  «ні» (CE)   — вимагає команду (`grep -…` або `rg <арг>`) і «0 збігів». Порожня дата перевірки = WARN в EC-evidence.
  EC-scan     — лише з --scan (файли або теки; тека береться рекурсивно за *.md, сам edition-claims.md пропускається): неіснуючий шлях = FAIL;
                рядок, де Enterprise/EE/Community/CE стоїть поруч із дає|надає|має|немає|відсутн|лише|тільки, без EC-NNN = WARN
                (евристика, не доказ повноти: решту ловить ручна перевірка рецензента).
"""
import json, re, sys
from pathlib import Path

VERDICTS = {"повністю", "частково", "ні", "не перевірено"}
res = []

def add(i, status, msg=""):
    res.append({"id": i, "status": status, "msg": msg})

def cells(line):
    line = line.strip().strip("|")
    return [c.replace("\\|", "|").strip() for c in re.split(r"(?<!\\)\|", line)]

CE_REF = re.compile(r"(?<![\w:/])[\w./-]+\.(?:py|xml|js|csv|po):\d+\b")
GH_REF = re.compile(r"https://github\.com/\S+#L\d+")
_ED = r"(?:Enterprise|\bEE\b|Community|\bCE\b)"
_VB = r"(?:дає|надає|має|немає|не має|відсутн\w*|лише|тільки|платн\w*|є застосунок|є модуль)"
SCAN = re.compile(rf"{_ED}[^|\n]{{0,40}}{_VB}|{_VB}[^|\n]{{0,40}}{_ED}", re.I)

def ce_ok(ev, verdict):
    if verdict == "ні":
        return bool(re.search(r"(?:\bgrep\s+-|\brg\s+\S)", ev.lower())) and "0 збігів" in ev.lower()
    if GH_REF.search(ev):
        return True
    ev2 = re.sub(r"https?://\S+", "", ev)
    if CE_REF.search(ev2):
        return True
    return False

def ee_ok(ev):
    """True / "warn" (URL не з документації 19.0) / False."""
    if re.search(r"https://\S+", ev) and re.search(r"[«\"“].{3,}[»\"”]", ev):
        return True if "odoo.com/documentation/19.0" in ev else "warn"
    m = re.search(r"база ee(.*)", ev, re.I)
    return bool(m and re.search(r"\d", m.group(1)) and re.search(r"\d{4}-\d{2}-\d{2}", m.group(1)))

def main():
    args = sys.argv[1:]
    scan = []
    if "--scan" in args:
        k = args.index("--scan")
        scan, args = args[k + 1:], args[:k]
    if len(args) != 1:
        print(__doc__); sys.exit(2)
    p = Path(args[0])
    if not p.exists():
        add("EC-verdict", "FAIL", f"немає файла {p}")
        print(json.dumps(res, ensure_ascii=False, indent=1)); sys.exit(1)
    rows, bad_cols, after_header = [], [], False
    for n, l in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        l = l.strip()
        if not l.startswith("|") or re.match(r"^\|[\s:|-]+\|$", l):
            continue
        c = cells(l)
        if c:
            c[0] = c[0].strip("` *")
        if re.match(r"(?i)^id$", c[0]):
            after_header = True
            continue
        if not any(x.strip() for x in c):
            continue
        if len(c) == 8:
            rows.append(c)
        elif after_header or re.match(r"(?i)^ec-", c[0]):
            bad_cols.append(f"рядок {n}: колонок {len(c)}, треба 8")  # не пропуск: загублена клітинка ховає «Доказ»/«Чого бракує»
    if not rows:
        add("EC-verdict", "FAIL", "немає жодного рядка EC-NNN")
        add("EC-evidence", "SKIP"); add("EC-partial", "SKIP")
        print(json.dumps(res, ensure_ascii=False, indent=1)); sys.exit(1)
    bad_v, bad_e, warn_e, warn_url, bad_p, seen = [], [], [], [], [], set()
    ce_total, ce_unv, ce_noreason = 0, [], []
    bad_v += bad_cols
    no_date = []
    for c in rows:
        i, ed, verdict, ev, gap = c[0], c[1].strip(), c[4].lower().strip(), c[5], c[6]
        if not re.fullmatch(r"EC-\d{3}", i) or i in seen:
            bad_v.append(f"{i}: ID не EC-NNN або дубль")
        seen.add(i)
        if ed not in ("CE", "EE"):
            bad_v.append(f"{i}: редакція «{ed}» не CE/EE (латиниця)")
            continue
        if verdict not in VERDICTS:
            bad_v.append(f"{i}: вердикт «{c[4]}» не з {sorted(VERDICTS)}")
            continue
        if ed == "CE":
            ce_total += 1
        if verdict == "не перевірено":
            if ed == "CE":
                ce_unv.append(i)
                if not re.search(r"клон", ev, re.I) or len(ev) < 15:
                    ce_noreason.append(i)
            else:
                warn_e.append(i)
        else:
            ok = ce_ok(ev, verdict) if ed == "CE" else ee_ok(ev)
            if ok == "warn":
                warn_url.append(i)
            elif not ok:
                bad_e.append(f"{i} ({ed}): доказ відсутній або не за формою (CE файл.py/xml/js/csv/po:рядок, «ні» — grep і «0 збігів»; EE URL документації 19.0 + цитата, або база EE з датою)")
        if verdict == "частково" and (len(gap.strip()) < 10 or not re.search(r"\w", gap)):
            bad_p.append(f"{i}: «частково» без змістовного «Чого бракує» (≥10 символів, не лише тире)")
        if not re.search(r"\d{4}-\d{2}-\d{2}", c[7]):
            no_date.append(i)
    add("EC-verdict", "FAIL" if bad_v else "PASS", "; ".join(bad_v))
    wmsg = []
    if warn_e:
        wmsg.append("не перевірено (немає доступу/доказу): " + ", ".join(warn_e))
    if no_date:
        wmsg.append("порожня або не РРРР-ММ-ДД дата перевірки: " + ", ".join(no_date))
    if warn_url:
        wmsg.append("URL не документація 19.0: " + ", ".join(warn_url))
    add("EC-evidence", "FAIL" if bad_e else ("WARN" if wmsg else "PASS"),
        "; ".join(bad_e) if bad_e else "; ".join(wmsg))
    add("EC-ce-unverified", "FAIL" if ce_noreason else ("WARN" if ce_unv else "PASS"),
        ("CE «не перевірено» без причини («клон недоступний: …»): " + ", ".join(ce_noreason)) if ce_noreason
        else (f"{len(ce_unv)} з {ce_total} CE-рядків не перевірено з причиною: " + ", ".join(ce_unv) if ce_unv else ""))
    add("EC-partial", "FAIL" if bad_p else "PASS", "; ".join(bad_p))
    if scan:
        hits, missing, files = [], [], []
        for f in scan:
            fp = Path(f)
            if not fp.exists():
                missing.append(f)  # у т.ч. нерозгорнутий glob: runner запускає без оболонки
            elif fp.is_dir():
                files += sorted(x for x in fp.rglob("*.md"))
            else:
                files.append(fp)
        for fp in files:
            if fp.resolve() == p.resolve():
                continue
            for n, l in enumerate(fp.read_text(encoding="utf-8").splitlines(), 1):
                if SCAN.search(l) and not re.search(r"EC-\d{3}", l):
                    hits.append(f"{fp}:{n}")
        if missing:
            add("EC-scan", "FAIL", "немає шляху для --scan (передай теку research/, не glob): " + ", ".join(missing))
        else:
            add("EC-scan", "WARN" if hits else "PASS", ("евристика: твердження про редакції без EC-NNN: " + ", ".join(hits[:20])) if hits else "")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(1 if any(r["status"] == "FAIL" for r in res) else 0)

main()
