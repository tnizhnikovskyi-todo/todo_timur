#!/usr/bin/env python3
"""Автоперевірки A-20c (OP-*) для набору сторінок власника. stdlib. Вивід: JSON [{id,status,msg}]; код виходу 1, якщо є FAIL.
Використання: check_owner_page.py <research/owner-page> [--research research] [--sample]
OP-pages    — рівно index.html, competitors.html, rejected.html (з --sample лише index.html обов'язковий).
OP-nav      — на кожній сторінці навігація з 3 відносними посиланнями (index/competitors/rejected.html) і рівно одним aria-current="page" на себе.
OP-anchors  — теза веде на рядок дослідження (секція ai-decisions — обов’язково з якорем AI-DECISIONS.md§Рішення): <a class="src" data-src="<файл дослідження>§<розділ>|SRC-NNN">; у ключових розділах index (summary, pain,
              screens, ai-decisions, risks) обов'язково; з --research: файл існує, розділ/SRC-NNN знайдено (без --research лише формат).
OP-contract — PAGE-CONTRACT.md: назва 2-4 слова; без {{плейсхолдерів}}; зовнішнє лише Google Fonts; логотип/картинки data:; токени :root + темна тема;
              без iframe/fetch/alert/print/download; ПДн (email, телефон) відсутні; зовнішні url()/@import у CSS — лише Google Fonts (хост);
              ◎ у блоці тексту (p/li/td/th/h*, без навігації) з «факт/підтверджено/вже є/працює» без «гіпотеза/план» — MANUAL; у колонці/рядку «наш пакет» матриці ● або ◐ — FAIL.
              Повний обсяг: немає var DEC — FAIL, 0 рядків «open» або запуск без --research — WARN; buildText має починати рядок з d.id і містити «не згоден»; кожен відкритий рядок DEC
              має id/ai/risk; ≤15 рядків; #copyBtn; є #not-doing; rejected.html має #not-doing; #current лише якщо є ../prototype-real/PLAN.md.
              Якір на research/sources/** — FAIL (OP-anchors).
OP-rejected — з --research: набір REJ-NNN у rejected.html = набір у research/REJECTED.md (FAIL).
OP-money    — FAIL: секція id=money; маркери «окупн», «TCO», «вартість володіння», «business-case/бізнес-кейс», «вердикт про гроші», ROI, «беззбитков», «ставка розробки» у тексті сторінок (ціни конкурентів як факт не чіпаємо). Нечисловий фрагмент якоря шукається лише в заголовках .md / ключах .yaml.
Числа з маркерами fact і решту сусідніх перевірок A-20c (check_facts, check_brand, check_privacy, check_intake --page, check_rejected, check_stale) цей скрипт не виконує.
OP-target   — форма під ціль публікації: index без <!doctype>/<html>/<head>/<body>; competitors/rejected з <!doctype>, charset, viewport; розмір ≤ 60 KB (WARN)."""
import argparse, json, re, sys
from urllib.parse import urlparse
from html.parser import HTMLParser
from pathlib import Path

PAGES = ["index.html", "competitors.html", "rejected.html"]
CORE = ["summary", "pain", "screens", "ai-decisions", "risks"]
FONT_HOSTS = {"fonts.googleapis.com", "fonts.gstatic.com"}
REJ_IDS = ["not-doing"]
MONEY = re.compile(r"окупн|\bTCO\b|вартість\s+володіння|business[- ]case|бізнес-кейс|вердикт\s+про\s+гроші|\bROI\b|беззбитков|ставк\w*\s+розробки|годин.{0,20}(×|x|\*).{0,10}ставк", re.I)
MONEY_SKIP = re.compile(r"REJ-\d{3}|https?://")  # як в autocheck.py: рядок реєстру відкинутого і цитата з URL не рахуються
SRC_RE = re.compile(r"^(?:SRC-\d{3,}|[\w./-]+\.(?:md|yaml|yml)§\S.*)$")
PII = {"email": r"[\w.+-]+@[\w-]+\.[\w.-]+", "phone": r"(?<![\w:])(\+?380\d{9}|0\d{9})(?!\w)"}
res = []

def add(i, status, msg=""):
    res.append({"id": i, "status": status, "msg": msg})

VOID = {"meta", "link", "img", "br", "hr", "input", "source", "col", "area", "base", "wbr"}
BLOCK = {"p", "li", "td", "th", "tr", "div", "section", "header", "footer", "main", "article", "aside", "table", "thead", "tbody",
         "ul", "ol", "dl", "dt", "dd", "blockquote", "figure", "figcaption", "details", "summary", "h1", "h2", "h3", "h4", "h5", "h6", "pre"}

class P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []        # (tag, attrs dict)
        self.sections = {}    # id -> [src anchors]
        self.cur = None
        self.text = []
        self.blocks = []      # текстові блоки (p/li/td/th/tr/h*/div...), без nav/script/style
        self.buf = []
        self.tables = []      # [[(tag, text)...] рядки]
        self._row = None
        self._cell = None
        self.style = []
        self.script = []
        self._in = None
        self.stack = []       # (tag, skip)
    def _flush(self):
        t = " ".join("".join(self.buf).split())
        if t: self.blocks.append(t)
        self.buf = []
    def _skip(self):
        return any(s for _, s in self.stack)
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.tags.append((tag, a))
        if tag in BLOCK: self._flush()
        if tag not in VOID:
            cls = (a.get("class") or "").split()
            self.stack.append((tag, tag == "nav" or bool(set(cls) & {"nav", "nav-inner", "sitelinks"})))
        if tag == "table": self.tables.append([])
        if tag == "tr" and self.tables: self._row = []; self.tables[-1].append(self._row)
        if tag in ("td", "th") and self._row is not None: self._cell = [tag, []]; self._row.append(self._cell)
        if tag == "section" and a.get("id"):
            self.cur = a["id"]; self.sections.setdefault(self.cur, [])
        if tag == "a" and "src" in (a.get("class") or "").split() and a.get("data-src") is not None:
            self.sections.setdefault(self.cur or "_", []).append(a["data-src"])
        if tag in ("style", "script"):
            self._in = tag
    def handle_endtag(self, tag):
        if tag in BLOCK: self._flush()
        if tag in ("td", "th"): self._cell = None
        if tag == "tr": self._row = None
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]; break
        if tag == "section":
            self.cur = None
        if tag in ("style", "script"):
            self._in = None
    def handle_data(self, d):
        if self._in == "style": self.style.append(d)
        elif self._in == "script": self.script.append(d)
        else:
            self.text.append(d)
            if not self._skip():
                self.buf.append(d)
                if self._cell is not None: self._cell[1].append(d)

def load(d, name):
    f = d / name
    raw = f.read_text(encoding="utf-8")
    p = P(); p.feed(raw)
    return raw, p

def headings(path):
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None

def resolve(ref, research):
    """-> (ok, msg). ref = SRC-NNN | файл§розділ. Нечисловий фрагмент — лише в заголовках (.md) або як ключ на початку рядка (.yaml)."""
    if ref.startswith("SRC-"):
        log = headings(research / "sources-log.md")
        if log is None:
            return False, f"{ref}: немає research/sources-log.md"
        ok = any(l.lstrip().startswith("|") and re.search(rf"\b{re.escape(ref)}\b", l) for l in log.splitlines())
        return ok, f"{ref}: рядка таблиці немає в sources-log.md"
    fn, sec = ref.split("§", 1)
    f = research / fn
    txt = headings(f)
    if txt is None:
        return False, f"{ref}: файла {fn} немає"
    sec = sec.strip().strip("§ ")
    if fn.endswith((".yaml", ".yml")):
        key = re.split(r"[.\[]", sec)[-1].rstrip("]")
        ok = bool(re.search(rf"^\s*-?\s*{re.escape(key)}\s*:", txt, re.M))
        return ok, f"{ref}: ключа {key}: немає у {fn}"
    hs = []
    for l in txt.splitlines():
        if l.startswith("#"):
            h = l.lstrip("#").strip()
            hs.append(re.sub(r"^(?:§\s*|розділ\s+|section\s+)", "", h, flags=re.I))
    num = re.match(r"^(\d+[а-яіїєґ]?)\.?$", sec, re.I)
    for h in hs:
        if num and re.match(rf"^{re.escape(num.group(1))}(?:[.\s)]|$)", h, re.I): return True, ""
        if not num and sec.lower() in h.lower(): return True, ""
    return False, f"{ref}: розділ не знайдено у заголовках {fn}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir"); ap.add_argument("--research"); ap.add_argument("--sample", action="store_true")
    a = ap.parse_args()
    d = Path(a.dir)
    research = Path(a.research) if a.research else None
    need = ["index.html"] if a.sample else PAGES
    htmls = sorted(x.name for x in d.glob("*.html")) if d.is_dir() else []
    miss = [n for n in need if n not in htmls]
    extra = [n for n in htmls if n not in PAGES]
    if miss or extra:
        add("OP-pages", "FAIL", f"немає: {miss}; зайві: {extra}; потрібно рівно {PAGES}")
    else:
        add("OP-pages", "PASS")
    pages = {}
    for n in htmls:
        if n in PAGES:
            pages[n] = load(d, n)
    if not pages:
        add("OP-nav", "SKIP"); add("OP-anchors", "SKIP"); add("OP-contract", "SKIP"); add("OP-money", "SKIP"); add("OP-target", "SKIP")
        print(json.dumps(res, ensure_ascii=False, indent=1)); sys.exit(1)

    # OP-nav
    bad = []
    for n, (raw, p) in pages.items():
        navs = [x for t, x in p.tags if t == "nav"]
        links = [x for t, x in p.tags if t == "a" and x.get("href") in PAGES]
        hrefs = {x["href"] for x in links}
        cur = [x for x in links if x.get("aria-current") == "page"]
        need_h = {n} if a.sample else set(PAGES)
        if not navs or not need_h <= hrefs:
            bad.append(f"{n}: немає навігації з {sorted(need_h - hrefs)}")
        if len(cur) != 1 or cur[0]["href"] != n:
            bad.append(f"{n}: aria-current=\"page\" має бути рівно один і на себе")
    add("OP-nav", "FAIL" if bad else "PASS", "; ".join(bad))

    # OP-anchors
    bad, warn = [], []
    for n, (raw, p) in pages.items():
        for sec, refs in p.sections.items():
            if sec == "ai-decisions" and refs and not any(r.strip().startswith("AI-DECISIONS.md§") for r in refs):
                bad.append(f"{n}#ai-decisions: немає якоря AI-DECISIONS.md§Рішення")
            for r in refs:
                if not SRC_RE.match(r.strip()):
                    bad.append(f"{n}#{sec}: data-src «{r}» не у форматі файл§розділ або SRC-NNN")
                elif not r.strip().startswith("SRC-") and re.match(r"^(?:\./)?(?:sources/|.*/sources/)", r.strip().split("§", 1)[0] + "/"):
                    bad.append(f"{n}#{sec}: якір «{r}» на сирі дані research/sources/** (internal-raw)")
                elif research:
                    ok, m = resolve(r.strip(), research)
                    if not ok: bad.append(f"{n}#{sec}: {m}")
    if "index.html" in pages:
        p = pages["index.html"][1]
        for s in CORE:
            if s not in p.sections:
                warn.append(f"index: немає розділу #{s}")
            elif not p.sections[s]:
                bad.append(f"index#{s}: теза без якоря на дослідження (a.src[data-src])")
        for s, refs in p.sections.items():
            if s not in CORE and s not in ("_", "sources", "chain") and not refs:
                warn.append(f"index#{s}: без якоря")
    if bad: add("OP-anchors", "FAIL", "; ".join(bad[:8]))
    elif warn: add("OP-anchors", "WARN", "; ".join(warn[:8]))
    elif not research: add("OP-anchors", "WARN", "існування якорів не перевірено (без --research)")
    else: add("OP-anchors", "PASS")

    # OP-contract
    bad, warn, manual = [], [], []
    for n, (raw, p) in pages.items():
        m = re.search(r"<title>(.*?)</title>", raw, re.S)
        title = " ".join(m.group(1).split()) if m else ""
        if n == "index.html":
            if not 2 <= len(title.split()) <= 4: bad.append(f"index.html: <title> має бути 2-4 слова («{title}»)")
        elif not title:
            bad.append(f"{n}: порожній або відсутній <title>")
        if "{{" in raw: bad.append(f"{n}: лишились плейсхолдери {{{{…}}}}")
        css = "".join(p.style); js = "".join(p.script)
        for tg, at in p.tags:
            if tg == "iframe": bad.append(f"{n}: iframe")
            for k in ("href", "src"):
                v = at.get(k, "")
                if v.startswith(("http://", "https://", "//")):
                    host = urlparse("https:" + v if v.startswith("//") else v).hostname or ""
                    if host not in FONT_HOSTS and not (tg == "script" and host == "cdnjs.cloudflare.com" and re.search(r"/\d+\.\d+", v)):
                        bad.append(f"{n}: зовнішній ресурс {v[:60]}")
            if tg == "img" and not at.get("src", "").startswith("data:"): bad.append(f"{n}: <img> не з data:-URI")
            if tg == "a" and "download" in at: bad.append(f"{n}: <a download>")
        for u in re.findall(r"url\(\s*['\"]?\s*((?:https?:)?//[^'\")\s]+)", css) + re.findall(r"@import\s+(?:url\(\s*)?['\"]?((?:https?:)?//[^'\")\s;]+)", css):
            if (urlparse("https:" + u if u.startswith("//") else u).hostname or "") not in FONT_HOSTS:
                bad.append(f"{n}: зовнішній ресурс у CSS {u[:60]}")
        if re.search(r"\b(fetch\s*\(|XMLHttpRequest|alert\s*\(|confirm\s*\(|prompt\s*\(|window\.print)", js): bad.append(f"{n}: заборонений виклик у скрипті")
        if "localStorage" in js and "try" not in js: bad.append(f"{n}: localStorage без try/catch")
        if not re.search(r":root\s*\{[^}]*--", css): bad.append(f"{n}: немає токенів на :root")
        if not (re.search(r"prefers-color-scheme:\s*dark", css) and 'data-theme="dark"' in css): bad.append(f"{n}: немає темної теми (@media + [data-theme=dark])")
        if not re.search(r"body\s*\{[^}]*background\s*:\s*var\(--", css): bad.append(f"{n}: body без background з токена")
        if "overflow-x" not in css: warn.append(f"{n}: немає overflow-x для таблиць")
        if "safe-area-inset" not in css: warn.append(f"{n}: немає safe-area-inset")
        body = " ".join("".join(p.text).split())
        for k, rx in PII.items():
            if re.search(rx, body): bad.append(f"{n}: ПДн ({k})")
        for blk in p.blocks:
            if "◎" not in blk: continue
            for line in re.split(r"(?<=[.!?;])\s+", blk):
                if "◎" in line and re.search(r"факт|підтверджен|вже є|вже закриває|працює|закриває", line, re.I) and not re.search(r"гіпотез|прогноз|не перевірено|план|не факт|ціль", line, re.I):
                    manual.append(f"{n}: ◎ подано як підтверджене: …{line.strip()[:70]}")
        # матриця: у колонці/рядку «наш пакет» не має бути ● або ◐ (це факт/частково; наш пакет лише ◎)
        for tb in p.tables:
            hdr = next((r for r in tb if r and all(c[0] == "th" for c in r)), None)
            cols = [i for i, c in enumerate(hdr or []) if "наш пакет" in " ".join("".join(c[1]).split()).lower()]
            for r in tb:
                if r is hdr: continue
                cells = [" ".join("".join(c[1]).split()) for c in r]
                if any(i < len(cells) and re.search("[●◐]", cells[i]) for i in cols):
                    bad.append(f"{n}: у колонці «наш пакет» стоїть ●/◐ замість ◎: …{cells[cols[0]][:50]}")
                if cells and "наш пакет" in cells[0].lower() and any(re.search("[●◐]", c) for c in cells[1:]):
                    bad.append(f"{n}: у рядку «наш пакет» стоїть ●/◐ замість ◎: …{' '.join(cells)[:60]}")

    # OP-contract: структура сторінки (зауваження 13) — не для зразка; один підсумковий запис разом із попередніми
    if "index.html" in pages and not a.sample:
        raw, p = pages["index.html"]
        navcur = 'href="#current"' in raw
        if research is None:
            warn.append("наявність #current і prototype-real/PLAN.md не перевірено (запуск без --research)")
        if ("current" in p.sections or navcur) and research is not None and not (research.parent / "prototype-real" / "PLAN.md").is_file():
            bad.append("index: є #current, а prototype-real/PLAN.md немає: прибери розділ і пункт навігації")
        js = "".join(p.script)
        jsn = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
        m = re.search(r"var\s+DEC\s*=\s*\[(.*)\]\s*;", jsn, re.S)
        opens = re.findall(r"\{[^{}]*\"st\"\s*:\s*\"open\"[^{}]*\}", m.group(1) if m else "")
        if not m: bad.append("index: у повному обсязі немає масиву var DEC=[…] (блок «Що вирішив AI»)")
        elif not opens: warn.append("index: у DEC 0 відкритих рядків — підтвердь у memo, що рішень AI справді немає")
        # контракт «Скопіювати мої заперечення»: рядок = «<AI-NN>: не згоден — що замість» (приймач veto-batch)
        bt = re.search(r"function\s+buildText\b(.*?)\breturn\s+out\b", jsn, re.S)
        if not bt: bad.append("index: немає функції buildText (текст для «Скопіювати мої заперечення»)")
        else:
            pm = re.search(r"\.push\(\s*\[?\s*(.*)", bt.group(1), re.S)
            if not pm or not re.match(r"(?:oneLine\(\s*)?d\.id\b", pm.group(1)):
                bad.append("index: buildText має видавати рядок, що починається з d.id (формат «AI-NN: не згоден — що замість»)")
            if "не згоден" not in bt.group(1):
                bad.append("index: buildText: немає тексту «не згоден» (формат «AI-NN: не згоден — що замість»)")
        if len(opens) > 15: bad.append(f"index: рядків рішень AI {len(opens)} > 15")
        for o in opens:
            nn = re.search(r'"n"\s*:\s*(\d+)', o)
            lab = "№" + (nn.group(1) if nn else "?")
            for fld in ("id", "ai", "risk"):
                if not re.search(rf'"{fld}"\s*:\s*"[^"]+"', o): bad.append(f"index: рядок {lab} без поля {fld}")
        if "copyBtn" not in raw: bad.append("index: немає кнопки #copyBtn")
        if "not-doing" not in p.sections: bad.append("index: немає розділу #not-doing")
    if "rejected.html" in pages and not a.sample:
        ids = {x.get("id") for t, x in pages["rejected.html"][1].tags if t == "section"}
        miss = [i for i in REJ_IDS if i not in ids]
        if miss: bad.append(f"rejected.html: немає розділів {miss}")
    if bad: add("OP-contract", "FAIL", "; ".join(bad[:12] + manual[:3]))
    elif manual: add("OP-contract", "MANUAL", "; ".join(manual[:3] + warn[:3]))
    elif warn: add("OP-contract", "WARN", "; ".join(warn[:6]))
    else: add("OP-contract", "PASS")

    # OP-rejected: ID рядків REJ-NNN у rejected.html збігаються з research/REJECTED.md
    if research is not None and "rejected.html" in pages and not a.sample:
        rj = research / "REJECTED.md"
        if rj.is_file():
            md = set(re.findall(r"REJ-\d{3}", rj.read_text(encoding="utf-8")))
            ht = set(re.findall(r"REJ-\d{3}", pages["rejected.html"][0]))
            if md != ht:
                add("OP-rejected", "FAIL", f"rejected.html ≠ REJECTED.md: немає на сторінці {sorted(md-ht)}, зайві {sorted(ht-md)}")
            else: add("OP-rejected", "PASS")
        else: add("OP-rejected", "WARN", "немає research/REJECTED.md — відповідність rejected.html не перевірено")

    # OP-money (LESSONS §24): грошей на сторінках немає
    bad = []
    for n, (raw, p) in pages.items():
        if "money" in p.sections: bad.append(f"{n}: секція id=money")
        hit = sorted({m.group(0).lower() for ln in "".join(p.text).splitlines() if not MONEY_SKIP.search(ln)
                      for m in MONEY.finditer(" ".join(ln.split()))})
        if hit: bad.append(f"{n}: грошові маркери {hit}")
    add("OP-money", "FAIL" if bad else "PASS", "; ".join(bad[:6]))

    # OP-target
    bad, warn = [], []
    for n, (raw, p) in pages.items():
        head = raw.lstrip()[:400].lower()
        tags = {t for t, _ in p.tags}
        if n == "index.html":
            if head.startswith("<!doctype") or tags & {"html", "head", "body"}: bad.append("index.html: має бути без <!doctype>/<html>/<head>/<body>")
            if not any(t == "meta" and x.get("name") == "claude:viewport-fit-sides" for t, x in p.tags): bad.append("index.html: немає meta claude:viewport-fit-sides")
        else:
            if not head.startswith("<!doctype html"): bad.append(f"{n}: немає <!doctype html>")
            if "charset" not in raw.lower()[:600]: bad.append(f"{n}: немає meta charset")
            if not any(t == "meta" and x.get("name") == "viewport" for t, x in p.tags): bad.append(f"{n}: немає meta viewport")
        if len(raw.encode()) > 60 * 1024: warn.append(f"{n}: {len(raw.encode())//1024} KB (> 60 KB)")
    if bad: add("OP-target", "FAIL", "; ".join(bad))
    elif warn: add("OP-target", "WARN", "; ".join(warn))
    else: add("OP-target", "PASS")

    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(1 if any(r["status"] == "FAIL" for r in res) else 0)

if __name__ == "__main__":
    main()
