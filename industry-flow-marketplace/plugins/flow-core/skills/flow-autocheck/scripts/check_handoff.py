#!/usr/bin/env python3
"""Автоперевірки режиму manager (0.4.2). stdlib. Вивід: JSON [{id,status,msg}]; код виходу 1, якщо є FAIL.
Використання: check_handoff.py [--report <tests/reports/…md>] [--naryad <tests/naryad/…yaml>]
report-handoff      — у звіті є YAML-блок `handoff:` з усіма полями (branch, head_sha, pr, base, stand, done, open, ai_decisions,
                      defects, next_hint, review_needed); порожнє значення — `[]`/`null`/`""`, а не відсутній ключ; `done` і `next_hint`
                      непорожні; `next_hint` — факти (імперативні «зроби/виконай/запусти …» = WARN); review_needed — повний збіг так|ні|yes|no (шаблон «так|ні» = FAIL); YAML-список «- …» на рівні ключа — продовження `done`/`next_hint`.
naryad-from-manager — наряд має `created_by: manager`, ключ `executor_session` і ключ `review` (об'єкт або null); у `mode: queue` — SKIP.
Формат — flow-core/references/report-format.md, naryad-format.md («Режим manager»), manager-mode.md."""
import argparse, json, re, sys

FIELDS = ["branch", "head_sha", "pr", "base", "stand", "done", "open", "ai_decisions", "defects", "next_hint", "review_needed"]
IMPERATIVE = re.compile(r"(?i)(^|[.;]\s*)(зроби|виконай|запусти|створи|додай|перевір|не\s+(?:роби|виконуй|запускай|створюй|додавай|мерж\w*|чіпай|змінюй|пиши)|do\s+not|don\'t)\b")


def handoff_block(text):
    """Повертає (dict ключ->значення рядком, помилка|None) для блока `handoff:` у тексті звіту."""
    lines = text.splitlines()
    for i, l in enumerate(lines):
        if re.match(r"^handoff:\s*(#.*)?$", l):
            ind, vals, cur = None, {}, None
            for l2 in lines[i + 1:]:
                if not l2.strip():
                    continue
                if l2.startswith("```") or (not l2.startswith(" ") and not l2.startswith("\t")):
                    break
                m = re.match(r"^(\s+)([A-Za-z_][\w-]*):\s*(.*)$", l2)
                lst = re.match(r"^(\s*)-\s+\S", l2)
                if lst and cur is not None and ind is not None and len(lst.group(1)) >= ind:
                    # YAML-список: «- …» на рівні ключа (або глибше) — продовження значення ключа
                    vals[cur] = (vals[cur] + " " + l2.strip()).strip()
                elif m and (ind is None or len(m.group(1)) == ind):
                    ind = len(m.group(1))
                    cur = m.group(2)
                    vals[cur] = re.sub(r"\s+#.*$", "", m.group(3)).strip()
                elif cur is not None and ind is not None and len(l2) - len(l2.lstrip()) > ind and l2.strip():
                    vals[cur] = (vals[cur] + " " + l2.strip()).strip()
            return vals, None
    return None, "у звіті немає блока `handoff:`"


def check_report(text):
    res = []
    vals, err = handoff_block(text)
    if err:
        return [{"id": "report-handoff", "status": "FAIL", "msg": err}]
    miss = [f for f in FIELDS if f not in vals]
    if miss:
        res.append({"id": "report-handoff", "status": "FAIL", "msg": "немає полів handoff: " + ", ".join(miss)})
    for f in ("done", "next_hint", "branch", "head_sha"):
        if f in vals and vals[f] in ("", '""', "''", "null", "~"):
            res.append({"id": "report-handoff", "status": "FAIL", "msg": f"порожнє обов'язкове handoff.{f}"})
    rn = vals.get("review_needed", "")
    if "review_needed" in vals and not re.fullmatch(r"(так|ні|yes|no)", rn.strip("\"' "), re.I):
        res.append({"id": "report-handoff", "status": "FAIL", "msg": "review_needed має бути так|ні"})
    nh = vals.get("next_hint", "")
    if IMPERATIVE.search(nh.strip("\"' ")):
        res.append({"id": "report-handoff-facts", "status": "WARN", "msg": "next_hint схожий на наказ; лише факти (наряд наступного кроку пише менеджер)"})
    if not any(r["status"] == "FAIL" for r in res):
        res.insert(0, {"id": "report-handoff", "status": "PASS", "msg": ""})
    return res


def top_keys(text):
    keys = {}
    for l in text.splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", l)
        if m:
            keys[m.group(1)] = re.sub(r"\s+#.*$", "", m.group(2)).strip().strip("\"'")
    return keys


def check_naryad(text):
    k = top_keys(text)
    if k.get("mode") == "queue":
        return [{"id": "naryad-from-manager", "status": "SKIP", "msg": "mode: queue (Odoo)"}]
    if "mode" not in k and "created_by" not in k:
        return [{"id": "naryad-from-manager", "status": "WARN", "msg": "наряд без mode/created_by (формат до 0.4.2)"}]
    bad = []
    if k.get("created_by") != "manager":
        bad.append("немає `created_by: manager` (наряд пише менеджер)")
    if "executor_session" not in k:
        bad.append("немає ключа `executor_session`")
    if "review" not in k:
        bad.append("немає ключа `review:` (об'єкт або null)")
    if bad:
        return [{"id": "naryad-from-manager", "status": "FAIL", "msg": "; ".join(bad)}]
    return [{"id": "naryad-from-manager", "status": "PASS", "msg": ""}]


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--report")
    ap.add_argument("--naryad")
    a = ap.parse_args(argv)
    res = []
    if a.report:
        res += check_report(open(a.report, encoding="utf-8").read())
    if a.naryad:
        res += check_naryad(open(a.naryad, encoding="utf-8").read())
    if not (a.report or a.naryad):
        res.append({"id": "args", "status": "ERROR", "msg": "потрібен --report і/або --naryad"})
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 1 if any(r["status"] == "FAIL" for r in res) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
