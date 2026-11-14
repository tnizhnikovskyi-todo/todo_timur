#!/usr/bin/env python3
"""Автоперевірки A-17b без бази: EL-courses, EL-quiz, EL-source, EL-lang, EL-pass, EL-mode, EL-deps, EL-tests.
Агент перевіряє сам (скрипт не робить): EL-install (установка на чистій CE і запуск тестів модуля через run_tests.sh),
EL-cert (website_slides_survey підтверджено у вихідниках 19.0 файл:рядок, інакше «не перевірено» в AI-DECISIONS), lint.
Запуск: python3 -I check_elearning.py --module package/addons/td_<галузь>_elearning --guide package/docs/user-guide
        [--pass-score 80] [--min-questions 5] [--allow Word,Word] [--schema schema.json]
Схема моделей/полів (SCHEMA нижче) — ЧЕРНЕТКА: імена моделей і полів website_slides треба підтвердити у вихідниках 19.0
(файл:рядок) і за потреби підмінити через --schema (JSON з тими самими ключами); до підтвердження EL-* зі схеми мають статус
«не перевірено на 19.0» у memo.
Маркери в XML-коментарях усередині <record>: «role: <роль>» (курс), «source: <файл>.md#SC-NN» (урок), «multi: true» (питання з кількома правильними).
Вихід: JSON [{id,status,msg}]. Код повернення 1, якщо є FAIL."""
import argparse, ast, json, os, re, sys
import xml.etree.ElementTree as ET

SCHEMA = {  # ЧЕРНЕТКА: звірити з вихідниками 19.0 (website_slides), файл:рядок — у SKILL.md «Крок 1»
    "course": "slide.channel", "lesson": "slide.slide", "question": "slide.question", "answer": "slide.answer",
    "lesson_course_field": "channel_id", "question_lesson_field": "slide_id", "answer_question_field": "question_id",
    "answer_correct_field": "is_correct", "text_fields": ["name", "description", "question", "text_value", "comment", "html_content"],
}
DEFAULT_ALLOW = {"Odoo", "PDF", "CSV", "Excel", "QR", "SC", "AC", "VP", "ID"}
LATIN = re.compile(r"\b[A-Za-z][A-Za-z']{2,}\b")
SOURCE = re.compile(r"source:\s*([\w./-]+\.md)#(SC-\d{2,})")
ROLE = re.compile(r"role:\s*([\w-]+)")


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
    ap = argparse.ArgumentParser()
    ap.add_argument("--module", required=True)
    ap.add_argument("--guide", required=True)
    ap.add_argument("--pass-score", type=int, default=80)
    ap.add_argument("--min-questions", type=int, default=5)
    ap.add_argument("--allow", default="")
    ap.add_argument("--schema")
    a = ap.parse_args()
    S = dict(SCHEMA)
    if a.schema:
        S.update(json.load(open(a.schema, encoding="utf-8")))
    allow = {w.lower() for w in DEFAULT_ALLOW | {x.strip() for x in a.allow.split(",") if x.strip()}}
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
    roles = []
    if os.path.isdir(a.guide):
        roles = sorted(n[:-3] for n in os.listdir(a.guide) if n.endswith(".md") and n != "INDEX.md")
    course_roles = {}
    for c in courses:
        for cm in c["comments"]:
            m = ROLE.search(cm)
            if m:
                course_roles[c["id"]] = m.group(1)
    msg = []
    if broken:
        msg.append("XML не розбирається: " + ", ".join(broken))
    if not roles:
        msg.append("у --guide немає ролей (A-16b не готовий)")
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
    add("EL-quiz", "FAIL" if msg else "PASS", "; ".join(msg[:10]))

    # EL-source
    msg = []
    test_lessons = set(by_lesson)
    for l in lessons:
        if l["id"] in test_lessons:
            continue
        src = None
        for cm in l["comments"]:
            m = SOURCE.search(cm)
            if m:
                src = m.groups()
        if not src:
            msg.append(f"{l['id']}: немає «source: <файл>.md#SC-NN»")
            continue
        fp = os.path.join(a.guide, src[0])
        if not os.path.isfile(fp):
            msg.append(f"{l['id']}: файлу {src[0]} немає в user-guide")
        elif not re.search(r"^#{2,4}\s.*\b" + re.escape(src[1]) + r"\b", open(fp, encoding="utf-8").read(), re.M):
            msg.append(f"{l['id']}: у {src[0]} немає розділу {src[1]}")
    if not lessons:
        msg.append("немає жодного уроку")
    add("EL-source", "FAIL" if msg else "PASS", "; ".join(msg[:10]))

    # EL-lang
    hits = []
    for r in courses + lessons + questions + answers:
        for fn in S["text_fields"]:
            v = r["fields"].get(fn)
            if not v or fn in r["refs"]:
                continue
            txt = re.sub(r"<[^>]+>", " ", v)
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
        elif int(v) != a.pass_score:
            msg = f"pass_score={v} != {a.pass_score} (answers.yaml elearning.pass_score / 80 за замовчуванням)"
    add("EL-pass", "FAIL" if msg else "PASS", msg)

    # EL-mode
    mp = [p for p in params if re.search(r"elearning(\.mode)?$", p["fields"].get("key", ""))]
    ok = bool(mp) and mp[0]["fields"].get("value", "") in ("on", "off")
    add("EL-mode", "PASS" if ok else "FAIL", "" if ok else "немає ir.config_parameter *elearning(.mode) зі значенням on|off")

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
