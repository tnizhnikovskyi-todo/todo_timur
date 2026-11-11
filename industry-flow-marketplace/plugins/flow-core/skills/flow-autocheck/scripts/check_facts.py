#!/usr/bin/env python3
"""Автоперевірка чисел проти єдиного джерела (FACT-*). stdlib. Вивід: JSON [{id,status,msg}]; код виходу 1, якщо є FAIL.
Використання: check_facts.py <facts.yaml|facts.json> <файли або теки…>
Число в тексті, що походить із фактів, позначають одним із способів (інакше воно не перевіряється):
  md/txt/csv:  12 000 грн <!--fact:pricing.ce_entry-->        (число — останнє перед маркером у рядку; «тис.», «млн», «%» враховуються)
  html:        <span data-fact="pricing.ce_entry">12 000 грн</span>
  yaml/json:   рядок із ключом і коментарем  # fact:pricing.ce_entry
Угода про маркери (обов'язкова для файлів, що несуть числа з facts: OWNER-BRIEF, BOX, SALES, owner-page, SHOW, captions): див. references/checks.md, «Маркери фактів».
--require-markers: рядки з грошовими сумами (грн, $, €) без маркера — WARN FACT-unmarked із файл:рядок (понад 5 — FAIL); кожен перевірений файл із числами з одиницями (грн, %, год, $, €, млн, тис., шт) мусить мати ≥1 маркер, інакше FACT-markers FAIL.
Без прапорця: FAIL, коли у всіх файлах разом 0 маркерів, а числа з одиницями є (числа не звірено); 0 маркерів і чисел немає — WARN.
Шлях — точковий ключ у facts (market.bands.0.companies; для facts.json — так само).
FACT-mismatch — значення в тексті ≠ значення факта (порівняння після прибирання пробілів/nbsp, коми як десяткового знака, множників).
FACT-orphan   — маркер посилається на ключ, якого немає у facts (FAIL); непорожні факти, на які ніхто не посилається — WARN (не блокує)."""
import importlib.util, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
_s = importlib.util.spec_from_file_location("_miniyaml", os.path.join(HERE, "_miniyaml.py"))
Y = importlib.util.module_from_spec(_s); _s.loader.exec_module(Y)
EXT = {".md", ".txt", ".csv", ".html", ".htm", ".yaml", ".yml", ".json"}
NUM = r"-?(?:\d{1,3}(?:[\s\u00a0\u202f]\d{3})+|\d+)(?:[.,]\d+)?"  # групи через пробіл — лише по 3 цифри (інакше «2026 12 000» склеюється)
MULT = {"тис": 1e3, "тис.": 1e3, "млн": 1e6, "млрд": 1e9, "k": 1e3, "m": 1e6}
res = []


def add(i, status, msg=""):
    res.append({"id": i, "status": status, "msg": msg})


def to_num(raw, tail=""):
    s = re.sub(r"[\s  ]", "", raw).replace(",", ".")
    try:
        v = float(s)
    except ValueError:
        return None
    t = tail.strip().lower()
    m = re.match(r"(тис\.?|млн|млрд|k|m)\b", t)
    return v * MULT[m.group(1)] if m else v


def load_facts(path):
    t = open(path, encoding="utf-8").read()
    obj = json.loads(t) if path.endswith(".json") else Y.loads(t)
    return Y.flatten(obj)


def files(paths):
    for p in paths:
        if os.path.isdir(p):
            for r, _, fs in os.walk(p):
                for f in sorted(fs):
                    if os.path.splitext(f)[1].lower() in EXT:
                        yield os.path.join(r, f)
        elif os.path.exists(p):
            yield p


def same(a, b):
    return abs(a - b) <= max(1e-9, abs(b) * 1e-9)


def main():
    argv = [x for x in sys.argv[1:] if x != "--require-markers"]
    req = len(argv) != len(sys.argv) - 1
    if len(argv) < 2:
        print("usage: check_facts.py <facts.yaml|facts.json> <файли/теки…> [--require-markers]", file=sys.stderr); sys.exit(2)
    try:
        facts = load_facts(argv[0])
    except Exception as e:  # noqa
        add("FACT-mismatch", "FAIL", f"Не вдалося прочитати {argv[0]}: {str(e)[:80]}"); add("FACT-orphan", "SKIP", "немає facts")
        print(json.dumps(res, ensure_ascii=False, indent=1)); sys.exit(1)
    used, mism, orph, nmark = set(), [], [], 0
    unit_files, nomark_files, nunits, money_nomark = [], [], 0, []
    MONEY = re.compile(r"\d[\d\s  .,]*\s?(грн|\$|€|₴|UAH|USD|EUR)|[$€₴]\s?\d", re.I)
    UNITS = re.compile(r"\d[\d\s  .,]*\s?(грн|%|год|\$|€|₴|млн|млрд|тис\.?|шт)", re.I)
    for f in files(argv[1:]):
        if os.path.abspath(f) == os.path.abspath(argv[0]):
            continue
        try:
            lines = open(f, encoding="utf-8").read().splitlines()
        except Exception:  # noqa
            continue
        f_marks0, f_units = nmark, sum(1 for l in lines if UNITS.search(re.sub(r"<[^>]+>|<!--.*?-->", " ", l)))
        nunits += f_units
        for n, l in enumerate(lines, 1):
            if req and MONEY.search(re.sub(r"<[^>]+>|<!--.*?-->", " ", l)) and not re.search(r"fact:|data-fact=", l):
                money_nomark.append(f"{os.path.basename(f)}:{n}")
            marks = [(m.start(), m.group(1), None) for m in re.finditer(r"<!--\s*fact:([\w.\-]+)\s*-->", l)]
            marks += [(m.start(), m.group(1), m.group(2)) for m in re.finditer(r"data-fact=\"([\w.\-]+)\"[^>]*>([^<]*)<", l)]
            if re.search(r"#\s*fact:([\w.\-]+)\s*$", l) and f.lower().endswith((".yaml", ".yml")):
                m = re.search(r"#\s*fact:([\w.\-]+)\s*$", l)
                marks.append((m.start(), m.group(1), l[:m.start()].split(":", 1)[-1]))
            for pos, key, inner in marks:
                nmark += 1
                if key not in facts:
                    orph.append(f"{os.path.basename(f)}:{n} {key}"); continue
                used.add(key)
                want = facts[key]
                if want is None or isinstance(want, (str, bool)) and not str(want).replace(".", "").isdigit():
                    if isinstance(want, str) and inner is not None and want.strip().lower() == inner.strip().lower():
                        continue
                    if isinstance(want, str) and inner is None and want.lower() in l.lower():
                        continue
                    if want is None:
                        mism.append(f"{os.path.basename(f)}:{n} {key}: у facts значення не задано (null)"); continue
                    mism.append(f"{os.path.basename(f)}:{n} {key}: текст ≠ «{want}»"); continue
                seg = inner if inner is not None else l[:pos]
                cands = list(re.finditer(f"({NUM})\\s*([A-Za-zА-Яа-яІіЇїЄє.]*)", seg))
                if not cands:
                    mism.append(f"{os.path.basename(f)}:{n} {key}: у рядку немає числа"); continue
                c = cands[0] if inner is not None else cands[-1]
                got = to_num(c.group(1), c.group(2))
                if got is None or not same(got, float(want)):
                    mism.append(f"{os.path.basename(f)}:{n} {key}: у тексті {c.group(1).strip()}{(' ' + c.group(2)) if c.group(2) else ''}, у facts {want}")
            pass
        if f_units and nmark == f_marks0:
            nomark_files.append(os.path.basename(f))
    if nmark == 0 and nunits:
        add("FACT-mismatch", "FAIL", "Числа з одиницями є, а маркерів fact: немає ні в одному файлі — числа не звірено з facts: познач їх <!--fact:ключ--> або data-fact (угода — checks.md): " + ", ".join(nomark_files[:8]))
    elif nmark == 0:
        add("FACT-mismatch", "WARN", "У перевірених файлах немає жодного маркера fact: — числа не звірено; познач їх <!--fact:ключ-->")
    else:
        add("FACT-mismatch", "FAIL" if mism else "PASS", ("Виправ число в тексті за facts (джерело — facts, не навпаки): " + "; ".join(mism[:10])) if mism else "")
    if req and nomark_files and nmark:
        add("FACT-markers", "FAIL", "Файли з числами (грн/%/год…) без жодного маркера fact: " + ", ".join(nomark_files[:8]) + " — познач числа з facts або винеси їх у facts")
    if req and money_nomark:
        add("FACT-unmarked", "FAIL" if len(money_nomark) > 5 else "WARN",
            f"Рядки з грошовими сумами без маркера fact: ({len(money_nomark)}; понад 5 — FAIL): " + "; ".join(money_nomark[:10]) + " — познач суму з facts або винеси в facts")
    unused = sorted(k for k, v in facts.items() if v is not None and k not in used and not k.startswith("meta.")
                    and not isinstance(v, str))[:8]
    if orph:
        add("FACT-orphan", "FAIL", "Маркер веде на ключ, якого немає у facts: " + "; ".join(orph[:10]) + " — додай ключ у facts або виправ шлях")
    elif unused and nmark:
        add("FACT-orphan", "WARN", "Факти без жодного посилання в артефактах: " + ", ".join(unused))
    else:
        add("FACT-orphan", "PASS")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(1 if any(r["status"] == "FAIL" for r in res) else 0)


if __name__ == "__main__":
    main()
