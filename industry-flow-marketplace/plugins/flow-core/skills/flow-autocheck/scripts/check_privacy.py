#!/usr/bin/env python3
"""Автоперевірка приватності артефактів галузі (PRV-*). stdlib. Вивід: JSON [{id,status,msg}]; код виходу 1, якщо є FAIL.
Використання: check_privacy.py <research> [--pages research/owner-page] [--materials prototype-real]
Патерни зашито в скрипт (secret — лише значення ≥12 символів без пробілів із цифрами й літерами або відомий префікс; `--token:` у CSS і «token: primary» не збігаються; email без службових доменів example/.test/.invalid і без імен ресурсів `logo@2x.png`, телефон, секрет, ЄДРПОУ/IBAN — FAIL; 10 цифр з нуля без контексту «тел./моб.» — WARN; ПІБ-подібне — MANUAL).
--allow <файл>: контакти бренду ToDo (BRAND.md або список) — email/телефони з файлу не є ПДн.
DOM-дампи (shoot/, dom/, screens*/, rec/) у --materials пропускаються: перевіряються SHOW*, captions, тексти відео.
Коди клієнтів K-xx/П-xx у --pages і --materials (публічні артефакти) — FAIL PRV-client-code; у research/*.md дозволені.
Сирі цитати без маркера internal-raw скрипт не бачить — рецензент перевіряє очима.
Додатково: суми угод поруч із кодом клієнта (K-xx/П-xx) — FAIL (клас internal-raw). Самі по собі (без суми) коди K-xx/П-xx у research/*.md дозволені.
PRV-pii        — ПДн у research/** (крім research/sources/), сторінках і матеріалах. Значення збігу у вивід не потрапляє: лише файл:рядок.
PRV-raw-place  — `internal-raw` лише в research/sources/: у сторінках і матеріалах згадка internal-raw або посилання на research/sources/ — FAIL;
                 у research/**.md (крім sources/ і sources-log.md) маркер `<!-- internal-raw` / `[internal-raw]` — FAIL, проста згадка слова — WARN."""
import argparse, json, os, re, sys

TEXT = {".md", ".txt", ".csv", ".html", ".htm", ".yaml", ".yml", ".json", ".srt", ".vtt", ".xml"}
PATTERNS = [
    ("email", re.compile(r"[\w.+-]+@(?:[\w-]+\.)+[\w-]+", re.I)),
    ("phone", re.compile(r"(?<![\w:])(\+?380[\s()-]?\d{2}[\s()-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}|0\d{9})(?!\w|[/-]|[.,]\d)")),
    ("secret", re.compile(r"(?<![-\w])(password|passwd|pwd|api[_-]?key|token|secret)\s*[:=]\s*(?:[\"']?)(?=\S*\d)(?=\S*[A-Za-z])\S{12,}|\b(?:sk-|ghp_|xox[bp]-|AKIA)[\w-]{10,}", re.I)),
    ("iban", re.compile(r"\bUA\d{2}[\s\d]{20,}")),
    ("edrpou", re.compile(r"ЄДРПОУ\D{0,5}\d{8}\b", re.I)),
]
PHONE_CTX = re.compile(r"(?i)(тел|моб|tel\b|phone|call|дзвон|звоні|whatsapp|viber|telegram|\+380)")
RES_DOMAIN = re.compile(r"^\d+(\.\d+)?x\.(png|jpe?g|svg|webp|gif|avif)$|\.(png|jpe?g|svg|webp|gif|avif|css|js)$", re.I)


def fake_email(g):
    """Службові/демо-адреси (example, .test, .invalid, localhost) і імена ресурсів (logo@2x.png) — не ПДн."""
    dom = g.rsplit("@", 1)[1].lower().rstrip(".")
    labels = dom.split(".")
    return "example" in labels or labels[-1] in ("example", "test", "invalid", "localhost") or bool(RES_DOMAIN.search(dom))


PIB = re.compile(r"\b[А-ЯІЇЄҐ][а-яіїєґ'’-]+\s+[А-ЯІЇЄҐ][а-яіїєґ'’-]+\s+[А-ЯІЇЄҐ][а-яіїєґ'’-]+\b")
CLIENT = re.compile(r"(?<![\w])[KКП]-\d{2,3}\b")
SUM = re.compile(r"(\d[\d\s.,]*\s?(грн|₴|\$|€|USD|UAH|EUR|тис\.?|млн|млрд))|([$€₴]\s?\d)")
DEAL = re.compile(r"(?i)(угод|договір|контракт|замовлен|рахунок|оплат|invoice|deal)")
res = []


def add(i, status, msg=""):
    res.append({"id": i, "status": status, "msg": msg})


SKIPDIRS = {"shoot", "dom", "screens", "screens-mobile", "rec"}


def walk(root, skip_sources=False, skip_dumps=False):
    for r, ds, fs in os.walk(root):
        if skip_dumps:
            ds[:] = [d for d in ds if d not in SKIPDIRS]
        if skip_sources:
            ds[:] = [d for d in ds if not (d == "sources" and os.path.basename(r) == "research") and d != "owner-page"]
        for f in sorted(fs):
            if os.path.splitext(f)[1].lower() in TEXT:
                yield os.path.join(r, f)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("research"); ap.add_argument("--pages"); ap.add_argument("--materials"); ap.add_argument("--allow")
    a = ap.parse_args()
    if not os.path.isdir(a.research):
        add("PRV-pii", "FAIL", f"Немає теки {a.research}"); add("PRV-raw-place", "SKIP", "немає research")
        print(json.dumps(res, ensure_ascii=False, indent=1)); sys.exit(1)
    scope = [("research", f) for f in walk(a.research, skip_sources=True)]
    scope += [("pages", f) for f in (walk(a.pages) if a.pages and os.path.isdir(a.pages) else [])]
    scope += [("materials", f) for f in (walk(a.materials, skip_dumps=True) if a.materials and os.path.isdir(a.materials) else [])]
    allow = set()
    if a.allow and os.path.isfile(a.allow):
        at = open(a.allow, encoding="utf-8", errors="replace").read()
        allow |= {m.lower() for m in re.findall(r"[\w.+-]+@[\w.-]+\w", at)}
        allow |= {re.sub(r"\D", "", m) for m in re.findall(r"\+?\d[\d\s()-]{8,}\d", at)}
    hits, pib, rawbad, rawwarn, codes, bare = [], [], [], [], [], []
    for kind, f in scope:
        try:
            lines = open(f, encoding="utf-8", errors="replace").read().splitlines()
        except OSError:
            continue
        name = os.path.relpath(f, os.path.dirname(os.path.abspath(a.research)) or ".")
        for n, l in enumerate(lines, 1):
            ev = f"{name}:{n}"
            for tname, rx in PATTERNS:
                for m in rx.finditer(l):
                    g = m.group(0)
                    if tname == "email" and (g.lower() in allow or fake_email(g)):
                        continue
                    if tname == "phone" and g.lstrip("+").startswith("0") and not PHONE_CTX.search(l):
                        bare.append(ev)  # 10 цифр з нуля без контексту — може бути номер рахунку: WARN
                        continue
                    if tname == "phone" and re.sub(r"\D", "", g) in allow:
                        continue
                    hits.append(f"{tname} {ev}")
                    break
            if CLIENT.search(l) and SUM.search(l) and DEAL.search(l):
                hits.append(f"deal-sum {ev}")
            if kind in ("pages", "materials") and CLIENT.search(l):
                codes.append(ev)
            if PIB.search(l):
                pib.append(ev)
            low = l.lower()
            if kind in ("pages", "materials"):
                if "internal-raw" in low or re.search(r"research/sources/", low):
                    rawbad.append(ev)
            elif os.path.basename(f) != "sources-log.md":
                if re.search(r"<!--\s*internal-raw|\[internal-raw\]", low):
                    rawbad.append(ev)
                elif "internal-raw" in low:
                    rawwarn.append(ev)
    if hits:
        add("PRV-pii", "FAIL", "Прибери/знеособ (значення не наводимо): " + "; ".join(hits[:10]))
    elif pib:
        add("PRV-pii", "MANUAL", "ПІБ-подібні рядки (три слова з великої) — перевір очима: " + "; ".join(pib[:8]))
    else:
        add("PRV-pii", "PASS")
    if bare:
        add("PRV-phone-bare", "WARN", "10 цифр з нуля без слів тел./моб. — перевір, що це не телефон: " + "; ".join(bare[:8]))
    if codes:
        add("PRV-client-code", "FAIL", "Код клієнта K-xx/П-xx у сторінці власника чи матеріалах (FTR №9: без кодів клієнтів) — прибери: " + "; ".join(codes[:8]))
    if rawbad:
        add("PRV-raw-place", "FAIL", "internal-raw лише в research/sources/: прибери зі сторінок/матеріалів/research-документів (залиш знеособлений висновок): " + "; ".join(rawbad[:10]))
    elif rawwarn:
        add("PRV-raw-place", "WARN", "Згадка internal-raw поза sources/ — перевір, що це не сирі дані: " + "; ".join(rawwarn[:8]))
    else:
        add("PRV-raw-place", "PASS", "сирі цитати без маркера internal-raw скрипт не бачить — рецензент перевіряє очима")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(1 if any(r["status"] == "FAIL" for r in res) else 0)


if __name__ == "__main__":
    main()
