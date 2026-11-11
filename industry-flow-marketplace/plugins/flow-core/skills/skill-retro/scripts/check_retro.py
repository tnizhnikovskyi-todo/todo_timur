#!/usr/bin/env python3
"""check_retro.py -- звірка C-08R: сигнали за добу <-> уроки LSN, повнота чернеток, повтори, ПДн, строки.

CLI (з кореня репо флоу):
  python3 -I check_retro.py --signals flow/lessons/signals-<дата>.json --lessons flow/lessons/ [--today YYYY-MM-DD] [--root .]
signals.json: [{"id":"SIG-001","source":"...","ref":"...","lesson":"LSN-001"|null,"not_error":"причина"|null}]
Урок flow/lessons/LSN-xxx.md: рядки `- ключ: значення` (дата, крок, скіл, версія_скіла, серйозність, клас, статус,
  repeat_of, сигнали, fix_ref, eval_ref, причина_не_помилка, примітка_повтору, ескальовано, евал_зелений, закрито).
fix_ref -- шлях до чернетки `flow/lessons/drafts/LSN-xxx.md` (відносно --root) або `pr#N`; шлях має існувати.
Додаткові поля: eval_статус (запропоновано|зелений), правка_внесена. INDEX.md пише skill-retro (вихідний артефакт C-08R): відсутність/неповнота -> FAIL.
Перевірки: RET-coverage, RET-draft, RET-repeat, RET-pii, RET-stale (лише статус «відкрито»; ескальовано -> WARN), RET-close, RET-index (FAIL), RET-signals (WARN: `сигнали` уроку <-> signals.json).
ПДн (RET-pii) скануються в LSN-*.md, drafts/*.md, PACKAGE-*.md й файлі сигналів. ID сигналу -- SIG-YYYYMMDD-NNN. Вихід JSON [{"id","status","msg"}], код 1 при FAIL. Лише stdlib.
"""
import argparse, datetime, glob, json, os, re, sys

LSN = re.compile(r'^LSN-\d{3}$')
SIGID = re.compile(r'^SIG-\d{8}-\d{3}$')
SEV = ["низька", "середня", "висока", "критична"]
PII = [re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+'), re.compile(r'(?<![\w:])(\+?380\d{9}|0\d{9})(?!\w)'),
       re.compile(r'\b[А-ЯІЇЄҐ][а-яіїєґ\'’-]+\s+[А-ЯІЇЄҐ][а-яіїєґ\'’-]+\s+[А-ЯІЇЄҐ][а-яіїєґ\'’-]+\b'),
       re.compile(r'ЄДРПОУ\D{0,5}\d{8}', re.I), re.compile(r'\bUA\d{2}[\s\d]{20,}')]
ALLOWED_NOLINK = {'', '-', '—', 'null', 'none', 'н/д'}


def parse(path):
    d = {}
    for line in open(path, encoding='utf-8'):
        m = re.match(r'^\s*[-*]\s*([\w_а-яіїєґА-ЯІЇЄҐ]+)\s*:\s*(.*?)\s*$', line)
        if m:
            d[m.group(1)] = m.group(2)
    return d


def workdays(a, b):
    n, d = 0, a
    while d < b:
        d += datetime.timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--signals', required=True)
    ap.add_argument('--lessons', required=True)
    ap.add_argument('--today', default=None)
    ap.add_argument('--root', default='.')
    a = ap.parse_args(argv)
    res = []
    today = datetime.date.fromisoformat(a.today) if a.today else datetime.date.today()
    lessons = {}
    for f in sorted(glob.glob(os.path.join(a.lessons, 'LSN-*.md'))):
        lid = os.path.basename(f)[:-3]
        lessons[lid] = parse(f)
        lessons[lid]['_text'] = open(f, encoding='utf-8').read()
    try:
        sigs = json.load(open(a.signals, encoding='utf-8'))
    except Exception as e:
        print(json.dumps([{"id": "RET-coverage", "status": "FAIL", "msg": "signals.json: %s" % e}], ensure_ascii=False)); return 1
    if not isinstance(sigs, list) or not all(isinstance(s, dict) for s in sigs):
        print(json.dumps([{"id": "RET-coverage", "status": "FAIL", "msg": "signals.json має бути масивом об'єктів"}], ensure_ascii=False)); return 1
    bad = 0
    def add(i, s, m):
        nonlocal bad
        res.append({"id": i, "status": s, "msg": m}); bad += s == 'FAIL'
    for s in sigs:
        les, ne = s.get('lesson'), (s.get('not_error') or '').strip()
        if not s.get('id'):
            add('RET-coverage', 'FAIL', 'сигнал без поля id: %s' % json.dumps(s, ensure_ascii=False)[:80])
        elif isinstance(les, str) and LSN.match(les) and les in lessons:
            add('RET-coverage', 'PASS', '%s -> %s' % (s.get('id'), les))
        elif ne:
            add('RET-coverage', 'PASS', '%s: не помилка (%s)' % (s.get('id'), ne))
        else:
            add('RET-coverage', 'FAIL', '%s без уроку й без причини «не помилка»' % s.get('id'))
    if not sigs:
        add('RET-coverage', 'SKIP', 'сигналів за добу немає')
    for lid, l in lessons.items():
        st = l.get('статус', '')
        if st != 'не помилка':
            miss = [k for k in ('fix_ref', 'eval_ref') if l.get(k, '').strip().lower() in ALLOWED_NOLINK]
            if miss:
                add('RET-draft', 'FAIL', '%s: немає %s (кожен урок має чернетку правки й евал)' % (lid, ', '.join(miss)))
            else:
                fr = l.get('fix_ref', '').strip()
                if '/' in fr and not os.path.isfile(os.path.join(a.root, fr)):
                    add('RET-draft', 'FAIL', '%s: fix_ref %s -- файлу чернетки немає' % (lid, fr))
                else:
                    dtxt = open(os.path.join(a.root, fr), encoding='utf-8').read() if '/' in fr else ''
                    if '/' in fr and 'Пропозиція евал-кейса' not in dtxt:
                        add('RET-draft', 'WARN', '%s: у чернетці немає блоку «Пропозиція евал-кейса»' % lid)
                    else:
                        add('RET-draft', 'PASS', lid)
        rep = l.get('repeat_of', '').strip()
        if rep and rep.lower() not in ALLOWED_NOLINK:
            base = lessons.get(rep)
            if not base:
                add('RET-repeat', 'FAIL', '%s: repeat_of %s не знайдено' % (lid, rep))
            else:
                try:
                    up = SEV.index(l.get('серйозність', '')) > SEV.index(base.get('серйозність', ''))
                except ValueError:
                    up = False
                if up and 'правка не спрацювала' in l.get('примітка_повтору', ''):
                    add('RET-repeat', 'PASS', '%s повтор %s: серйозність вгору' % (lid, rep))
                else:
                    add('RET-repeat', 'FAIL', '%s: повтор %s без підвищення серйозності і примітки «правка не спрацювала»' % (lid, rep))
        txt = l['_text']
        if any(p.search(txt) for p in PII):
            add('RET-pii', 'FAIL', '%s: ПДн-подібний текст (e-mail/телефон/ПІБ/ЄДРПОУ); лише коди K-xx, П-xx' % lid)
        try:
            if st == 'відкрито' and l.get('дата'):
                wd = workdays(datetime.date.fromisoformat(l['дата']), today)
                if wd > 3 and l.get('ескальовано', '').strip().lower() not in ALLOWED_NOLINK:
                    add('RET-stale', 'WARN', '%s відкрито %d роб. днів (>3), ескальовано %s' % (lid, wd, l['ескальовано']))
                elif wd > 3:
                    add('RET-stale', 'FAIL', '%s відкрито %d роб. днів (>3): ескалація AI-інженеру (поле «ескальовано: <дата>»)' % (lid, wd))
            elif st == 'правка внесена' and l.get('правка_внесена', '').strip().lower() not in ALLOWED_NOLINK:
                wd = workdays(datetime.date.fromisoformat(l['правка_внесена']), today)
                if wd > 5:
                    add('RET-stale', 'WARN', '%s: правку внесено %d роб. днів тому, евал ще не зелений (без ескалації)' % (lid, wd))
        except ValueError:
            add('RET-stale', 'WARN', '%s: дата не ISO' % lid)
    for lid, l in lessons.items():
        if l.get('статус') not in ('закрито', 'евал зелений'):
            continue
        if l.get('eval_статус', '').strip() != 'зелений':
            add('RET-close', 'FAIL', '%s: статус «%s» без `eval_статус: зелений`' % (lid, l.get('статус'))); continue
        if l.get('статус') == 'евал зелений':
            add('RET-close', 'PASS', '%s: евал зелений' % lid); continue
        try:
            green = datetime.date.fromisoformat(l.get('евал_зелений', ''))
            closed = datetime.date.fromisoformat(l.get('закрито', ''))
        except ValueError:
            add('RET-close', 'FAIL', '%s: «закрито» без дат `евал_зелений` і `закрито`' % lid); continue
        reps = []
        for k, v in lessons.items():
            if v.get('repeat_of', '').strip() != lid:
                continue
            try:
                if green < datetime.date.fromisoformat(v.get('дата', '9999-12-31')) <= closed:
                    reps.append(k)
            except ValueError:
                add('RET-close', 'FAIL', '%s: повтор %s має дату не ISO (%s) -- не можна перевірити «2 тижні без повтору»' % (lid, k, v.get('дата', '')))
        if (closed - green).days < 14:
            add('RET-close', 'FAIL', '%s: закрито раніше ніж через 14 днів після «евал зелений»' % lid)
        elif reps:
            add('RET-close', 'FAIL', '%s: був повтор %s до закриття' % (lid, ', '.join(reps)))
        else:
            add('RET-close', 'PASS', lid)
    if lessons:
        idx = os.path.join(a.lessons, 'INDEX.md')
        itxt = open(idx, encoding='utf-8').read() if os.path.isfile(idx) else None
        miss = lessons.keys() if itxt is None else [k for k in lessons if k not in itxt]
        if miss:
            add('RET-index', 'FAIL', 'INDEX.md %s: немає рядків %s (INDEX.md пише skill-retro на кожному прогоні)' % ('відсутній' if itxt is None else 'неповний', ', '.join(sorted(miss))))
        else:
            add('RET-index', 'PASS', 'INDEX.md повний')
    sig_by_lesson = {}
    for s_ in sigs:
        if isinstance(s_.get('lesson'), str) and s_.get('id'):
            sig_by_lesson.setdefault(s_['lesson'], []).append(s_['id'])
    for lid, l in lessons.items():
        listed = [x.strip() for x in re.split(r'[,\s]+', l.get('сигнали', '')) if x.strip().startswith('SIG-')]
        badfmt = [x for x in listed if not SIGID.match(x)]
        miss = [x for x in sig_by_lesson.get(lid, []) if x not in listed]
        if badfmt:
            add('RET-signals', 'WARN', '%s: ID сигналу не SIG-YYYYMMDD-NNN: %s' % (lid, ', '.join(badfmt)))
        if miss:
            add('RET-signals', 'WARN', '%s: у signals.json сигнали %s посилаються на урок, але в уроці `сигнали:` їх немає' % (lid, ', '.join(miss)))
    extra = glob.glob(os.path.join(a.lessons, 'drafts', '*.md')) + glob.glob(os.path.join(a.lessons, 'PACKAGE-*.md')) + [a.signals]
    for f in sorted(extra):
        try:
            t = open(f, encoding='utf-8').read()
        except OSError:
            continue
        if any(p.search(t) for p in PII):
            add('RET-pii', 'FAIL', '%s: ПДн-подібний текст (e-mail/телефон/ПІБ/ЄДРПОУ)' % os.path.basename(f))
    if not any(r['id'] == 'RET-pii' for r in res):
        add('RET-pii', 'PASS', 'ПДн не знайдено')
    if not any(r['id'] == 'RET-stale' for r in res):
        add('RET-stale', 'PASS', 'прострочених уроків немає')
    print(json.dumps(res, ensure_ascii=False))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
