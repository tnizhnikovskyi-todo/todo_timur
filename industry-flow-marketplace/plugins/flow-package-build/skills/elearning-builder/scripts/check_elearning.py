#!/usr/bin/env python3
"""Автоперевірки A-17b без бази: EL-courses, EL-quiz, EL-source, EL-content, EL-blocked, EL-lang, EL-pass, EL-mode, EL-score, EL-access, EL-deps, EL-tests.
Агент перевіряє сам (скрипт не робить): EL-install (установка на чистій CE і запуск тестів модуля через run_tests.sh),
EL-cert (website_slides_survey підтверджено у вихідниках 19.0 файл:рядок, інакше «не перевірено» в AI-DECISIONS), доказ для EL-score/EL-access
(файл:рядок 19.0 справді підтверджує сказане в README), lint.
Запуск: python3 -I check_elearning.py --module package/addons/td_<галузь>_elearning --guide package/docs/user-guide
        [--answers package/templates/answers.yaml] [--pass-score 80] [--min-questions 5] [--allow Word,Word] [--schema schema.json]
Ролі беруться з таблиці «## Ролі» у INDEX.md A-16b (файли — звірка); заблоковані сценарії («Статус: заблоковано») пропускаються з WARN.
--answers: elearning.mode має бути "on" (у лапках; off = модуль не збирається) і elearning.pass_score задає поріг (інакше --pass-score/80).
Схема моделей/полів (SCHEMA нижче) — ЧЕРНЕТКА: імена моделей і полів website_slides треба підтвердити у вихідниках 19.0
(файл:рядок) і за потреби підмінити через --schema (JSON з тими самими ключами); до підтвердження EL-* зі схеми мають статус
«не перевірено на 19.0» у memo.
Маркери в XML-коментарях усередині <record>: «role: <роль>» (курс), «source: <файл>.md#SC-NN» (урок; для admin.md — також #<заголовок розділу>), «multi: true» (питання з кількома правильними).
Вихід: JSON [{id,status,msg}]. Код повернення 1, якщо є FAIL."""
import argparse, ast, json, os, re, sys
import xml.etree.ElementTree as ET

SCHEMA = {  # ЧЕРНЕТКА: звірити з вихідниками 19.0 (website_slides), файл:рядок — у SKILL.md «Крок 1»
    "course": "slide.channel", "lesson": "slide.slide", "question": "slide.question", "answer": "slide.answer",
    "lesson_course_field": "channel_id", "question_lesson_field": "slide_id", "answer_question_field": "question_id",
    "answer_correct_field": "is_correct", "lesson_text_field": "html_content", "lesson_image_field": "image_1920",
    "text_fields": ["name", "description", "question", "text_value", "comment", "html_content"],
}
DEFAULT_ALLOW = {"Odoo", "ToDo", "PDF", "CSV", "Excel", "QR", "CRM", "SMS", "URL", "BAS", "Email", "SC", "AC", "VP", "ID"}
LATIN = re.compile(r"\b[A-Za-z][A-Za-z']{2,}\b")
SOURCE_ADMIN = re.compile(r"source:\s*(admin\.md)#([^\n(]+)")
ID_PATTERN = r"SC-\d{2,}"  # ID сценарію; змінюється --id-pattern
SOURCE = re.compile(r"source:\s*([\w./-]+\.md)#(" + ID_PATTERN + ")")
ROLE = re.compile(r"role:\s*([\w-]+)")
IMG = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")
EVID = re.compile(r"\S+\.(?:py|xml|js|csv):\d+")


def index_roles(guide):
    """Ролі з таблиці «## Ролі» INDEX.md: файл розділу `<роль>.md` у будь-якій комірці (без cards/)."""
    p = os.path.join(guide, "INDEX.md")
    if not os.path.isfile(p):
        return None
    out, inside = [], False
    for line in open(p, encoding="utf-8").read().splitlines():
        if re.match(r"^##\s", line):
            inside = bool(re.match(r"^##\s*Ролі", line))
            continue
        if inside and line.strip().startswith("|"):
            for cell in line.strip().strip("|").split("|"):
                m = re.fullmatch(r"\s*([\w-]+)\.md\s*", cell)
                if m and not cell.strip().startswith("cards/"):
                    out.append(m.group(1))
                    break
    return out


def guide_sections(guide, role):
    """{SC-NN: (blocked, images)} для файлу ролі."""
    p = os.path.join(guide, role + ".md")
    res = {}
    if not os.path.isfile(p):
        return res
    parts = re.split(r"(?m)^(?=##\s)", open(p, encoding="utf-8").read())
    for part in parts:
        m = re.match(r"##\s.*?\b(" + ID_PATTERN + r")\b", part)
        if m:
            st = re.search(r"Статус:\s*(.+)", part)
            res[m.group(1)] = ("заблоковано" in (st.group(1).lower() if st else ""), IMG.findall(part))
    return res


def answers_elearning(path):
    """(mode_raw, pass_score) з блоку `elearning:` без бібліотеки YAML; None, якщо файлу/блоку немає."""
    if not path or not os.path.isfile(path):
        return None
    mode = score = None
    inside = False
    for line in open(path, encoding="utf-8").read().splitlines():
        if re.match(r"^elearning:\s*(#.*)?$", line):
            inside = True
            continue
        if inside and re.match(r"^\S", line):
            inside = False
        if inside:
            m = re.match(r"^\s+mode:\s*(\S+?)\s*(#.*)?$", line)
            if m:
                mode = m.group(1)
            m = re.match(r"^\s+pass_score:\s*(\d+)", line)
            if m:
                score = int(m.group(1))
    return mode, score


def local(ref):
    return ref.split(".", 1)[1] if "." in ref else ref


def parse_records(module):
    recs = []
    data_dir = os.path.join(module, "data")
    if not os.path.isdir(data_dir):
        return recs
    for n in sorted(os.listdir(data_dir)):
        if not n.endswith(".xml"):
            continue
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
        try:
            root = ET.parse(os.path.join(data_dir, n), parser=parser).getroot()
        except ET.ParseError as e:
            recs.append({"model": "__broken__", "id": n, "fields": {}, "refs": {}, "comments": [str(e)], "file": n})
            continue
        for r in root.iter("record"):
            fields, refs, evals, comments = {}, {}, {}, []
            for ch in r:
                if ch.tag is ET.Comment:
                    comments.append(ch.text or "")
                elif ch.tag == "field":
                    nm = ch.get("name")
                    if ch.get("ref"):
                        refs[nm] = local(ch.get("ref"))
                    if ch.get("eval"):
                        evals[nm] = ch.get("eval")
                    fields[nm] = "".join(ch.itertext()).strip()
            recs.append({"model": r.get("model"), "id": local(r.get("id", "")), "fields": fields, "refs": refs,
                         "evals": evals, "comments": comments, "file": n})
    return recs


def main():
    global ID_PATTERN, SOURCE
    ap = argparse.ArgumentParser()
    ap.add_argument("--module", required=True)
    ap.add_argument("--guide", required=True)
    ap.add_argument("--answers")
    ap.add_argument("--pass-score", type=int, default=None)
    ap.add_argument("--min-questions", type=int, default=5)
    ap.add_argument("--allow", default="")
    ap.add_argument("--id-pattern", default=ID_PATTERN, help="regex ID сценарію (як у check_guides.py; за замовчуванням SC-\\d{2,})")
    ap.add_argument("--schema")
    a = ap.parse_args()
    ID_PATTERN = a.id_pattern
    SOURCE = re.compile(r"source:\s*([\w./-]+\.md)#(" + ID_PATTERN + ")")
    S = dict(SCHEMA)
    if a.schema:
        S.update(json.load(open(a.schema, encoding="utf-8")))
    ael = answers_elearning(a.answers)
    pass_score = a.pass_score if a.pass_score is not None else (ael[1] if ael and ael[1] else 80)
    allow = {w.lower() for w in DEFAULT_ALLOW | {x.strip() for x in a.allow.split(",") if x.strip()}}
    try:  # «Дозволені латинські назви: A, B» з INDEX.md (як у check_guides.py)
        for ln in open(os.path.join(a.guide, "INDEX.md"), encoding="utf-8"):
            m_ = re.match(r"\s*Дозволені латинські назви:\s*(.+)", ln)
            if m_:
                allow |= {w.strip().lower() for w in re.split(r"[,;]", m_.group(1)) if w.strip()}
    except OSError:
        pass
    lesson_src = {}
    res = []

    def add(i, status, msg=""):
        res.append({"id": i, "status": status, "msg": msg})

    recs = parse_records(a.module)
    broken = [r["id"] for r in recs if r["model"] == "__broken__"]
    courses = [r for r in recs if r["model"] == S["course"]]
    lessons = [r for r in recs if r["model"] == S["lesson"]]
    questions = [r for r in recs if r["model"] == S["question"]]
    answers = [r for r in recs if r["model"] == S["answer"]]
    params = [r for r in recs if r["model"] == "ir.config_parameter"]

    # EL-courses
    idx_roles = index_roles(a.guide)
    roles = sorted(set(idx_roles or []))
    sec = {r: guide_sections(a.guide, r) for r in roles}
    blocked = {(r, sc) for r, d in sec.items() for sc, (b, _) in d.items() if b}
    nofile = [r for r in roles if not os.path.isfile(os.path.join(a.guide, r + ".md"))]
    course_roles = {}
    for c in courses:
        for cm in c["comments"]:
            m = ROLE.search(cm)
            if m:
                course_roles[c["id"]] = m.group(1)
    msg = []
    if broken:
        msg.append("XML не розбирається: " + ", ".join(broken))
    if idx_roles is None:
        msg.append("у --guide немає INDEX.md (A-16b не готовий)")
    elif not roles:
        msg.append("у INDEX.md немає таблиці «Ролі» з файлами <роль>.md")
    if nofile:
        msg.append("INDEX називає ролі без файлу: " + ", ".join(nofile))
    miss = [r for r in roles if r not in course_roles.values()]
    extra = [v for v in course_roles.values() if v not in roles]
    norole = [c["id"] for c in courses if c["id"] not in course_roles]
    if miss: msg.append("немає курсу ролі: " + ", ".join(miss))
    if extra: msg.append("курс без ролі в INDEX: " + ", ".join(extra))
    if norole: msg.append("курс без маркера «role:»: " + ", ".join(norole))
    if len(courses) != len(roles) and roles: msg.append(f"курсів {len(courses)} != ролей {len(roles)}")
    add("EL-courses", "FAIL" if msg else "PASS", "; ".join(msg))

    # EL-quiz
    by_lesson = {}
    for q in questions:
        by_lesson.setdefault(q["refs"].get(S["question_lesson_field"]), []).append(q)
    lesson_course = {l["id"]: l["refs"].get(S["lesson_course_field"]) for l in lessons}
    ans_by_q = {}
    for an in answers:
        ans_by_q.setdefault(an["refs"].get(S["answer_question_field"]), []).append(an)
    msg = []
    for c in courses:
        qs = [q for ls, lst in by_lesson.items() if lesson_course.get(ls) == c["id"] for q in lst]
        if not qs:
            msg.append(f"{c['id']}: немає тесту")
        elif len(qs) < a.min_questions:
            msg.append(f"{c['id']}: питань {len(qs)} < {a.min_questions}")
        for q in qs:
            ans = ans_by_q.get(q["id"], [])
            correct = [x for x in ans if re.search(r"\bTrue\b|^1$|^true$", x["evals"].get(S["answer_correct_field"], x["fields"].get(S["answer_correct_field"], "")), re.I)]
            multi = any(re.search(r"multi:\s*true", cm, re.I) for cm in q["comments"])
            if len(ans) < 2:
                msg.append(f"{q['id']}: відповідей {len(ans)} < 2")
            elif not correct or (len(correct) != 1 and not multi):
                msg.append(f"{q['id']}: правильних {len(correct)} (потрібна рівно 1)")
    two = [q["id"] for q in questions if len(ans_by_q.get(q["id"], [])) == 2]
    if msg:
        add("EL-quiz", "FAIL", "; ".join(msg[:10]))
    elif two:
        add("EL-quiz", "WARN", "питання лише з 2 варіантами (рекомендовано >=3, 2 - лише так/ні з поясненням у memo): " + ", ".join(two[:10]))
    else:
        add("EL-quiz", "PASS", "")

    # EL-source, EL-content, EL-blocked
    msg, cmsg, wmsg = [], [], []
    test_lessons = set(by_lesson)
    for l in lessons:
        if l["id"] in test_lessons:
            continue
        src = None
        for cm in l["comments"]:
            m = SOURCE.search(cm)
            if m:
                src = m.groups()
            else:  # admin.md: якір на будь-який заголовок («source: admin.md#Параметри»)
                ma = SOURCE_ADMIN.search(cm)
                if ma:
                    src = (ma.group(1), ma.group(2).strip())
        if src:
            lesson_src[l["id"]] = src[0]
        if not src:
            msg.append(f"{l['id']}: немає «source: <файл>.md#SC-NN» (для admin.md — #<заголовок розділу>)")
            continue
        fp = os.path.join(a.guide, src[0])
        if not os.path.isfile(fp):
            msg.append(f"{l['id']}: файлу {src[0]} немає в user-guide")
            continue
        if src[0] == "admin.md" and not re.fullmatch(ID_PATTERN, src[1]):
            if not any(src[1].lower() in h.lower() for h in re.findall(r"^#{2,4}\s+(.+)$", open(fp, encoding="utf-8").read(), re.M)):
                msg.append(f"{l['id']}: у {src[0]} немає заголовка «{src[1]}»")
                continue
        elif not re.search(r"^#{2,4}\s.*\b" + re.escape(src[1]) + r"\b", open(fp, encoding="utf-8").read(), re.M):
            msg.append(f"{l['id']}: у {src[0]} немає розділу {src[1]}")
            continue
        role = src[0][:-3]
        is_blocked, imgs = guide_sections(a.guide, role).get(src[1], (False, []))
        if is_blocked:
            wmsg.append(f"{l['id']}: урок для заблокованого {src[0]}#{src[1]} (A-14) — прибрати")
            continue
        text = re.sub(r"<[^>]+>", " ", l["fields"].get(S["lesson_text_field"], "")).strip()
        if not text:
            cmsg.append(f"{l['id']}: порожній урок (немає тексту в полі {S['lesson_text_field']})")
        if imgs:
            html = l["fields"].get(S["lesson_text_field"], "")
            has_img = bool(l["fields"].get(S["lesson_image_field"], "").strip()) or "<img" in html or "static/img" in html
            if not has_img:
                cmsg.append(f"{l['id']}: розділ {src[1]} має знімки, а в уроці зображень немає")
    if not lessons:
        msg.append("немає жодного уроку")
    add("EL-source", "FAIL" if msg else "PASS", "; ".join(msg[:10]))
    add("EL-content", "FAIL" if cmsg else "PASS", "; ".join(cmsg[:10]))
    blk = sorted(f"{r}.md#{sc}" for r, sc in blocked)
    if blk or wmsg:
        add("EL-blocked", "WARN", "; ".join((["заблоковані сценарії без уроку: " + ", ".join(blk)] if blk else []) + wmsg))
    else:
        add("EL-blocked", "PASS", "")

    # EL-lang
    hits = []
    for r in courses + lessons + questions + answers:
        for fn in S["text_fields"]:
            v = r["fields"].get(fn)
            if not v or fn in r["refs"]:
                continue
            if r["id"] in lesson_src and lesson_src[r["id"]] == "admin.md":
                continue  # admin.md — з іменами параметрів і модулів, як UG-lang
            txt = re.sub(r"<code\b[^>]*>.*?</code>", " ", v, flags=re.S)
            txt = re.sub(r"`[^`]*`", " ", txt)
            txt = re.sub(r"<[^>]+>", " ", txt)
            words = [w for w in LATIN.findall(txt) if w.lower() not in allow]
            if words:
                hits.append(f"{r['id']}.{fn}: {', '.join(sorted(set(words))[:3])}")
    add("EL-lang", "FAIL" if hits else "PASS", "; ".join(hits[:8]))

    # EL-pass
    pp = [p for p in params if re.search(r"pass_score$", p["fields"].get("key", ""))]
    msg = ""
    if not pp:
        msg = "немає ir.config_parameter *.pass_score"
    else:
        v = pp[0]["fields"].get("value", "")
        if not v.isdigit() or not (1 <= int(v) <= 100):
            msg = f"pass_score={v!r} не 1..100"
        elif int(v) != pass_score:
            msg = f"pass_score={v} != {pass_score} (answers.yaml elearning.pass_score / 80 за замовчуванням)"
    add("EL-pass", "FAIL" if msg else "PASS", msg)

    # EL-mode: ключ у answers.yaml; при off модуль не збирається
    if not ael:
        add("EL-mode", "SKIPPED", "немає --answers: звірити elearning.mode вручну (має бути \"on\" у лапках)")
    else:
        raw = (ael[0] or "").strip()
        val = raw.strip("\"'")
        if not raw:
            add("EL-mode", "FAIL", "в answers.yaml немає elearning.mode (додає A-17b у package/templates/answers.yaml)")
        elif val == "off":
            add("EL-mode", "FAIL", 'elearning.mode: "off" — A-17b не запускається, модуль не збирати')
        elif val != "on" or raw == val:
            add("EL-mode", "FAIL", f"elearning.mode={raw}: потрібно рядок у лапках \"on\"|\"off\" (YAML 1.1 читає on/off як булеве)")
        else:
            add("EL-mode", "PASS", "")

    # EL-score: механізм порога реально застосовується (доказ файл:рядок 19.0 — вручну, EL-cert)
    rd = os.path.join(a.module, "README.md")
    readme = open(rd, encoding="utf-8").read() if os.path.isfile(rd) else ""
    td_ = os.path.join(a.module, "tests")
    tbody = "".join(open(os.path.join(td_, n), encoding="utf-8").read() for n in os.listdir(td_) if n.endswith(".py")) if os.path.isdir(td_) else ""
    m = re.search(r"Механізм порога:\s*(штатний|survey|код)\b(.*)", readme)
    if not m:
        add("EL-score", "FAIL", "README.md без рядка «Механізм порога: штатний|survey|код <файл:рядок 19.0>»; «параметр без механізму» = не готово (AI-DECISIONS + memo власнику)")
    elif m.group(1) in ("штатний", "survey") and not EVID.search(m.group(2)):
        add("EL-score", "FAIL", f"механізм «{m.group(1)}» без доказу файл:рядок 19.0 у тому самому рядку")
    elif m.group(1) == "код" and "pass_score" not in tbody:
        add("EL-score", "FAIL", "механізм «код»: тест модуля не перевіряє застосування pass_score")
    else:
        add("EL-score", "PASS", "доказ файл:рядок звірити вручну")

    # EL-access: курси не публічні
    m = re.search(r"Доступ:\s*(.*)", readme)
    if not m or not EVID.search(m.group(1)):
        add("EL-access", "FAIL", "README.md без рядка «Доступ: <хто бачить курси> <файл:рядок 19.0>»")
    elif not re.search(r"def test_\w*access", tbody):
        add("EL-access", "FAIL", "немає тесту test_*access* (курси не видимі анонімам/публічному користувачу)")
    else:
        add("EL-access", "PASS", "доказ файл:рядок звірити вручну")

    # EL-deps
    mf = os.path.join(a.module, "__manifest__.py")
    msg = ""
    try:
        dep = ast.literal_eval(open(mf, encoding="utf-8").read()).get("depends", [])
        if "website_slides" not in dep:
            msg = "depends без website_slides"
        elif any("survey" in (r["model"] or "") for r in recs) and "website_slides_survey" not in dep:
            msg = "є survey-записи, але depends без website_slides_survey"
    except Exception as e:
        msg = f"__manifest__.py не читається: {e}"
    add("EL-deps", "FAIL" if msg else "PASS", msg)

    # EL-tests
    td = os.path.join(a.module, "tests")
    tests = [n for n in os.listdir(td) if re.match(r"test_.*\.py$", n)] if os.path.isdir(td) else []
    body = "".join(open(os.path.join(td, n), encoding="utf-8").read() for n in tests)
    msg = []
    if not os.path.isfile(os.path.join(td, "__init__.py")) or not tests:
        msg.append("немає tests/__init__.py або test_*.py")
    else:
        for need in (S["course"], S["question"]):
            if need not in body:
                msg.append(f"тести не звертаються до {need}")
    add("EL-tests", "FAIL" if msg else "PASS", "; ".join(msg))

    for i, why in (("EL-install", "установка на чистій CE і run_tests.sh модуля — агент/runner (немає бази = SKIPPED = не готово)"),
                   ("EL-cert", "сертифікація: website_slides_survey підтверджено у вихідниках 19.0 файл:рядок або «не перевірено» в AI-DECISIONS"),
                   ("EL-schema", "імена моделей/полів звірено з вихідниками 19.0 (файл:рядок) — агент")):
        add(i, "MANUAL", why)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(1 if any(r["status"] == "FAIL" for r in res) else 0)


if __name__ == "__main__":
    main()
