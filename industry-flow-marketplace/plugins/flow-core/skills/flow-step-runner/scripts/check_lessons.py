#!/usr/bin/env python3
"""check_lessons.py -- LSN-coverage: кожне зауваження людини в сесії кроку має observation ЦІЄЇ сесії.

CLI (з кореня репо):
  python3 -I check_lessons.py --remarks <файл зауважень> --observations observations/ [--task <id>] [--since YYYY-MM-DD]
Файл зауважень (його веде runner; джерела -- чат людини, коментарі «Повернути», коментарі PR, самозвіт): рядки `- [R-NN] <суть>`;
  `(не помилка: <причина>)` у рядку = явне «не помилка» (покриття без observation; причину runner виносить і в memo звіту).
Observation `observations/*.md` покриває зауваження, якщо має рядок `remark: R-NN`, непорожній текст і належить ЦІЙ сесії:
  --task <id> -- у тексті є `#<id>` (поле «репо/задача» `<owner/repo>#<id>`) або точний рядок <id>, якщо він не число;
  --since <дата> -- дата в імені файлу YYYY-MM-DD- не раніше. R-NN рахуються в межах сесії, тож без --task/--since
  старі observation можуть хибно покрити нове R-NN: тоді WARN «покриття не прив'язане до сесії».
Відсутній файл зауважень або зауважень немає -> SKIP (код 0). Нерозпізнаний рядок `R-…` -> WARN.
Вихід: JSON [{"id","status","msg"}], код 1 при FAIL. Лише stdlib.
"""
import argparse, glob, json, os, re, sys

REM = re.compile(r'^\s*[-*]\s*\[?(R-\d{2,3})\]?[:\s]\s*(.*\S)\s*$')
LOOSE = re.compile(r'^\s*[-*]\s*\[?R-')
OBS_REM = re.compile(r'^\s*remark\s*:\s*(R-\d{2,3})\b', re.M)
NOT_ERR = re.compile(r'\(\s*не\s+помилка\s*:\s*(\S.*?)\)', re.I)
DATED = re.compile(r'^(\d{4}-\d{2}-\d{2})-')


def in_session(txt, name, task, since):
    if since:
        m = DATED.match(name)
        if not m or m.group(1) < since:
            return False
    if task:
        t = task.split('#')[-1]
        pat = r'#%s\b' % re.escape(t) if t.isdigit() else re.escape(task)
        if not re.search(pat, txt):
            return False
    return True


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--remarks', required=True)
    ap.add_argument('--observations', required=True)
    ap.add_argument('--task', default=None)
    ap.add_argument('--since', default=None)
    a = ap.parse_args(argv)
    res = []
    if not os.path.isfile(a.remarks):
        res.append({"id": "LSN-coverage", "status": "SKIP", "msg": "зауважень у сесії немає (файл відсутній: %s)" % a.remarks})
        print(json.dumps(res, ensure_ascii=False)); return 0
    rems = []
    for line in open(a.remarks, encoding='utf-8'):
        m = REM.match(line)
        if m:
            rems.append((m.group(1), m.group(2)))
        elif LOOSE.match(line):
            res.append({"id": "LSN-remark-format", "status": "WARN",
                        "msg": "нерозпізнаний рядок (потрібно `- [R-NN] суть`, NN = 2-3 цифри): %s" % line.strip()[:60]})
    if not rems:
        res.append({"id": "LSN-coverage", "status": "SKIP", "msg": "зауважень у сесії немає"})
        print(json.dumps(res, ensure_ascii=False)); return 0
    if not a.task and not a.since:
        res.append({"id": "LSN-session-scope", "status": "WARN",
                    "msg": "не задано --task/--since: observation попередніх кроків можуть хибно покрити R-NN"})
    obs = {}
    for f in sorted(glob.glob(os.path.join(a.observations, '*.md'))):
        name = os.path.basename(f)
        txt = open(f, encoding='utf-8').read()
        if not DATED.match(name):
            res.append({"id": "LSN-observation-name", "status": "WARN", "msg": "ім'я без дати YYYY-MM-DD-: %s" % name})
        if len(txt.strip()) < 40 or not in_session(txt, name, a.task, a.since):
            continue
        for rid in set(OBS_REM.findall(txt)):
            obs.setdefault(rid, []).append(f)
    bad = 0
    for rid, text in rems:
        ne = NOT_ERR.search(text)
        if rid in obs:
            res.append({"id": "LSN-coverage", "status": "PASS", "msg": "%s -> %s" % (rid, os.path.basename(obs[rid][0]))})
        elif ne:
            res.append({"id": "LSN-coverage", "status": "PASS", "msg": "%s: не помилка (%s)" % (rid, ne.group(1))})
        else:
            bad += 1
            res.append({"id": "LSN-coverage", "status": "FAIL", "msg": "%s без observation цієї сесії: %s" % (rid, text[:80])})
    print(json.dumps(res, ensure_ascii=False))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
