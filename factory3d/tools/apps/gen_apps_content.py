#!/usr/bin/env python3
"""Generate Odoo Apps listing content for td_* modules from apps_catalog.json.

For every module in the catalog:
  * manifest keys: name, summary, description (replaced), author, website, support (added if missing),
    images (replaced) - edited textually (ast gives line ranges), business keys are never touched;
  * static/description/index.html (English, whitelist-friendly HTML, no scripts, local images only);
  * static/description/banner.png (1120x560), icon.png (140x140, only if missing or a flat placeholder;
    a designed icon of another size is resampled to 140x140);
  * static/description/<screenshot>.png if the catalog entry has a "shot".

Usage:
  gen_apps_content.py [--addons DIR] [--only td_a,td_b] [--skip manifest,html,images]
The script is idempotent. Pillow is required for images (--skip images to run without it).
"""
from __future__ import annotations

import argparse
import ast
import html
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
DEFAULT_ADDONS = REPO / "factory3d" / "odoo_addons"
CATALOG = HERE / "apps_catalog.json"

BANNER_SIZE = (1120, 560)
ICON_SIZE = (140, 140)
GENERATED_MARK = "td_apps_generated"
BANNER_REL = "static/description/banner.png"
FONT_DIRS = ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype/liberation", "/usr/share/fonts"]


# --------------------------------------------------------------------------------------------- manifest
def _q(value: str, style: str) -> str:
    if style == '"':
        return json.dumps(value, ensure_ascii=False)
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _rst_description(entry: dict) -> str:
    title = entry["name"]
    out = ["", title, "=" * len(title), ""]
    out += [p + "\n" for p in entry["intro"]]
    out += ["Key features", "------------", ""]
    out += ["* " + f for f in entry["features"]]
    if entry.get("notes"):
        out += ["", "Requirements and notes", "----------------------", ""]
        out += ["* " + n for n in entry["notes"]]
    out.append("")
    return "\n".join(out)


def load_manifest(text: str) -> dict:
    tree = ast.parse(text)
    node = next(n.value for n in tree.body if isinstance(n, ast.Expr) and isinstance(n.value, ast.Dict))
    return ast.literal_eval(node)


def patch_manifest(path: Path, entry: dict, defaults: dict) -> bool:
    text = path.read_text(encoding="utf8")
    lines = text.split("\n")
    tree = ast.parse(text)
    dct = next(n.value for n in tree.body if isinstance(n, ast.Expr) and isinstance(n.value, ast.Dict))
    keys = {}
    for k, v in zip(dct.keys, dct.values):
        if isinstance(k, ast.Constant) and isinstance(k.value, str):
            keys[k.value] = (k, v)
    first = keys["name"][0]
    style = lines[first.lineno - 1][first.col_offset]
    indent = " " * first.col_offset
    kq = lambda key: style + key + style  # noqa: E731

    def entry_range(key):
        k, v = keys[key]
        return k.lineno, v.end_lineno

    def one_line(key, value):
        return f"{indent}{kq(key)}: {_q(value, style)},"

    replace: dict[str, tuple[int, int, list[str]]] = {}
    insert: dict[int, list[str]] = {}

    def set_key(key, new_lines, anchors, replace_existing=True):
        if key in keys:
            if replace_existing:
                s, e = entry_range(key)
                tail = lines[e - 1].encode("utf8")[keys[key][1].end_col_offset:].decode("utf8")
                comment = tail[tail.index("#"):] if "#" in tail else ""
                nl = list(new_lines)
                if comment:
                    nl[-1] += "  " + comment
                replace[key] = (s, e, nl)
            return
        for a in anchors:
            if a in keys:
                insert.setdefault(entry_range(a)[1], []).extend(new_lines)
                return
        raise SystemExit(f"{path}: no anchor for {key}")

    set_key("name", [one_line("name", entry["name"])], [])
    set_key("summary", [one_line("summary", entry["summary"])], ["name"])
    desc = f'{indent}{kq("description")}: """' + _rst_description(entry) + '""",'
    set_key("description", desc.split("\n"), ["summary", "name"])
    set_key("author", [one_line("author", defaults["author"])], ["version", "name"], replace_existing=False)
    set_key("website", [one_line("website", defaults["website"])], ["author", "version"], replace_existing=False)
    set_key("support", [one_line("support", defaults["support"])], ["website", "author"], replace_existing=False)
    set_key("images", [f"{indent}{kq('images')}: [{_q(BANNER_REL, style)}],"], ["depends", "license"])

    ops = [(s, e, nl) for s, e, nl in replace.values()]
    for after, nl in insert.items():
        ops.append((after + 1, after, nl))  # empty range -> pure insertion after line `after`
    new = lines[:]
    for s, e, nl in sorted(ops, key=lambda o: (o[0], o[1]), reverse=True):
        new[s - 1:e] = nl
    out = "\n".join(new)
    parsed = load_manifest(out)
    assert parsed["name"] == entry["name"] and parsed["summary"] == entry["summary"], path
    assert parsed["images"] == [BANNER_REL] and parsed.get("support") and parsed.get("website"), path
    if out != text:
        path.write_text(out, encoding="utf8")
        return True
    return False


# --------------------------------------------------------------------------------------------- index.html
def _li(items, tag="li"):
    return "\n".join(f"            <{tag}>{x}</{tag}>" for x in items)


def render_index(mod: str, entry: dict, manifest: dict, catalog: dict, addons: Path) -> str:
    esc = html.escape
    names = {m: e["name"] for m, e in catalog["modules"].items()}
    deps = manifest.get("depends", [])
    suite = [f"{esc(names.get(d, d))} (<code>{d}</code>)" for d in deps if d.startswith("td_")]
    odoo = [f"<code>{d}</code>" for d in deps if not d.startswith("td_")]
    pydeps = manifest.get("external_dependencies", {}).get("python", [])
    ee = entry["edition"] == "ee"
    req = []
    if ee:
        req.append(f"<b>Requires Odoo 19 Enterprise</b>: {esc(entry.get('edition_reason', ''))}.")
    else:
        req.append("Works on <b>Odoo 19 Community</b> and Enterprise; no Enterprise module is required.")
    if suite:
        req.append("Factory 3D suite modules: " + ", ".join(suite) + ".")
    if odoo:
        req.append("Odoo modules: " + ", ".join(odoo) + ".")
    if pydeps:
        req.append("Python packages: " + ", ".join(f"<code>{p}</code>" for p in pydeps) + ".")
    for n in entry.get("notes", []):
        if ee and n.startswith("Requires Odoo Enterprise"):
            continue
        req.append(esc(n))
    has_ui = (addons / mod / "views").is_dir() or (addons / mod / "static" / "src").is_dir()
    if has_ui:
        has_en = any((addons / mod / "i18n").glob("en*.po")) if (addons / mod / "i18n").is_dir() else False
        req.append("Interface language: Ukrainian" + (" and English." if has_en else
                   "; an English translation is not included yet."))
    shot = ""
    if entry.get("shot"):
        s = entry["shot"]
        shot = f"""
<section class="oe_container">
    <div class="oe_row oe_spaced">
        <h3 class="oe_slogan">Screenshot</h3>
        <img class="img img-fluid oe_picture oe_screenshot" src="{esc(s['name'])}" alt="{esc(s['caption'])}"/>
        <p class="text-muted">{esc(s['caption'])}</p>
    </div>
</section>
"""
    support = manifest.get("support", "")
    intro = "\n".join(f"        <p>{esc(p)}</p>" for p in entry["intro"])
    return f"""<section class="oe_container">
    <div class="oe_row oe_spaced">
        <h2 class="oe_slogan">{esc(entry['name'])}</h2>
        <h3 class="oe_slogan">{esc(entry['summary'])}</h3>
    </div>
</section>

<section class="oe_container">
    <div class="oe_row">
        <h3>What it does</h3>
{intro}
    </div>
</section>

<section class="oe_container">
    <div class="oe_row">
        <h3>Key features</h3>
        <ul>
{_li(esc(f) for f in entry['features'])}
        </ul>
    </div>
</section>
{shot}
<section class="oe_container">
    <div class="oe_row">
        <h3>Requirements</h3>
        <ul>
{_li(req)}
        </ul>
    </div>
</section>

<section class="oe_container">
    <div class="oe_row">
        <h3>Support</h3>
        <p>Part of the Factory 3D suite for Odoo 19. Questions and support requests:
            <a href="mailto:{esc(support)}">{esc(support)}</a></p>
    </div>
</section>
"""


# --------------------------------------------------------------------------------------------- images
def _font(size: int, bold: bool = True):
    from PIL import ImageFont
    names = ["DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"] if bold else ["DejaVuSans.ttf", "LiberationSans-Regular.ttf"]
    for d in FONT_DIRS:
        for n in names:
            p = Path(d) / n
            if p.exists():
                return ImageFont.truetype(str(p), size)
    return ImageFont.load_default(size=size)


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= max_w:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def make_icon(path: Path, entry: dict):
    from PIL import Image, ImageDraw
    S = 4
    w, h = ICON_SIZE
    im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    col = _hex(entry["color"])
    d.rounded_rectangle([0, 0, w * S - 1, h * S - 1], radius=26 * S, fill=col + (255,))
    d.ellipse([10 * S, 10 * S, (w - 10) * S, (h - 10) * S], outline=(255, 255, 255, 80), width=2 * S)
    f = _font(46 * S)
    mono = entry["mono"]
    d.text((w * S / 2, h * S / 2), mono, font=f, fill=(255, 255, 255, 255), anchor="mm")
    if entry["edition"] == "ee":
        bf = _font(15 * S)
        bx, by = w * S - 50 * S, h * S - 30 * S
        d.rounded_rectangle([bx, by, w * S - 10 * S, h * S - 10 * S], radius=6 * S, fill=(255, 255, 255, 235))
        d.text(((bx + w * S - 10 * S) / 2, (by + h * S - 10 * S) / 2), "EE", font=bf, fill=col + (255,), anchor="mm")
    from PIL.PngImagePlugin import PngInfo
    meta = PngInfo()
    meta.add_text(GENERATED_MARK, "1")
    im.resize(ICON_SIZE, Image.LANCZOS).save(path, optimize=True, pnginfo=meta)


def make_banner(path: Path, entry: dict):
    from PIL import Image, ImageDraw
    w, h = BANNER_SIZE
    col = _hex(entry["color"])
    im = Image.new("RGB", (w, h), col)
    d = ImageDraw.Draw(im)
    # vertical gradient: darker towards the bottom
    for y in range(h):
        k = 1 - 0.38 * (y / h)
        d.line([(0, y), (w, y)], fill=tuple(int(c * k) for c in col))
    d.ellipse([w - 470, -150, w + 130, 450], fill=tuple(min(255, int(c * 1.18) + 12) for c in col))
    d.ellipse([w - 360, h - 250, w - 60, h + 50], outline=(255, 255, 255), width=3)
    d.text((w - 235, 175), entry["mono"], font=_font(150), fill=(255, 255, 255), anchor="mm")
    d.text((70, 62), "FACTORY 3D SUITE  /  ODOO 19", font=_font(24), fill=(255, 255, 255))
    title_font = _font(66)
    y = 120
    for ln in _wrap(d, entry["name"], title_font, 640):
        d.text((70, y), ln, font=title_font, fill=(255, 255, 255))
        y += 82
    sum_font = _font(30, bold=False)
    y += 14
    for ln in _wrap(d, entry["summary"], sum_font, 600)[:4]:
        d.text((70, y), ln, font=sum_font, fill=(235, 240, 245))
        y += 42
    badge = "Requires Odoo Enterprise" if entry["edition"] == "ee" else "Community & Enterprise"
    bf = _font(26)
    tw = d.textlength(badge, font=bf)
    d.rounded_rectangle([70, h - 90, 70 + tw + 44, h - 36], radius=27, fill=(255, 255, 255))
    d.text((92, h - 63), badge, font=bf, fill=col, anchor="lm")
    im.save(path, optimize=True)


def is_placeholder(path: Path) -> bool:
    """True for a missing/broken icon, a flat stub (<=3 colors) or an icon generated by this script."""
    from PIL import Image
    try:
        raw = Image.open(path)
        if GENERATED_MARK in raw.info:
            return True
        im = raw.convert("RGBA")
    except Exception:
        return True
    return len(im.getcolors(10000) or range(10001)) <= 3  # flat single-color / 2-3 color stubs


def ensure_icon(path: Path, entry: dict) -> str:
    from PIL import Image
    if not path.exists() or is_placeholder(path):
        make_icon(path, entry)
        return "generated"
    im = Image.open(path)
    if im.size != ICON_SIZE and im.size[0] == im.size[1]:
        im.convert("RGBA").resize(ICON_SIZE, Image.LANCZOS).save(path, optimize=True)
        return "resized"
    return "kept"


def make_shot(dst: Path, shot: dict):
    from PIL import Image
    im = Image.open(REPO / shot["src"]).convert("RGB")
    if shot.get("crop"):
        im = im.crop(tuple(shot["crop"]))
    w = shot["width"]
    im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
    im.save(dst, optimize=True)


# --------------------------------------------------------------------------------------------- main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--addons", default=str(DEFAULT_ADDONS))
    ap.add_argument("--only", default="")
    ap.add_argument("--skip", default="", help="comma list: manifest,html,images")
    a = ap.parse_args(argv)
    addons = Path(a.addons)
    catalog = json.loads(CATALOG.read_text(encoding="utf8"))
    skip = set(filter(None, a.skip.split(",")))
    only = set(filter(None, a.only.split(",")))
    for mod, entry in catalog["modules"].items():
        if only and mod not in only:
            continue
        mdir = addons / mod
        if not mdir.is_dir():
            print(f"{mod}: directory not found", file=sys.stderr)
            return 2
        desc = mdir / "static" / "description"
        desc.mkdir(parents=True, exist_ok=True)
        done = []
        if "manifest" not in skip:
            if patch_manifest(mdir / "__manifest__.py", entry, catalog["defaults"]):
                done.append("manifest")
        manifest = load_manifest((mdir / "__manifest__.py").read_text(encoding="utf8"))
        if "html" not in skip:
            (desc / "index.html").write_text(render_index(mod, entry, manifest, catalog, addons), encoding="utf8")
            done.append("index.html")
        if "images" not in skip:
            make_banner(desc / "banner.png", entry)
            done.append("banner")
            done.append("icon:" + ensure_icon(desc / "icon.png", entry))
            if entry.get("shot"):
                make_shot(desc / entry["shot"]["name"], entry["shot"])
                done.append("shot")
        print(f"{mod}: {', '.join(done) or 'nothing'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
