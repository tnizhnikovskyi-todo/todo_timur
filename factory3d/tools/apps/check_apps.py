#!/usr/bin/env python3
"""Offline Odoo Apps (apps.odoo.com) readiness checker for the td_* addons. stdlib only, no network.

Rules come from https://apps.odoo.com/apps/vendor-guidelines and https://apps.odoo.com/apps/faq (Odoo 19 era):
  * manifest: name <= 25 chars, version 19.0.x.y.z, license from the Apps list, depends, summary/description in
    English, author, website, support (email), images, price >= 9 EUR/USD (only for paid apps);
  * static/description/icon.png - real PNG (Odoo gives no size; the project standard is square 140x140);
    cover image(s) from `images` - png/gif/jpeg; banner.png is checked as 1120x560 (project standard, 2:1);
  * static/description/index.html - English, tag/attribute whitelist (Odoo html sanitizer set), no JavaScript,
    no <style>, no external URLs except youtube/teams links, mailto:/skype:, local images only;
  * dependencies: a module declared Community (apps_catalog.json) must not depend, directly or through other
    td_* modules, on an Enterprise module (Enterprise = not in the Community sources, or in KNOWN_ENTERPRISE);
  * license compatibility of module vs. dependencies (table from the Apps FAQ);
  * i18n: a .pot file is expected (warning).

Usage: check_apps.py [ADDONS_DIR] [-m MODULE ...] [--ce-addons DIR ...] [--catalog FILE]
                     [--include-tests] [--ignore CODE,...] [--strict] [--quiet] [--json]
Exit code: 0 - no errors, 1 - errors (or warnings with --strict), 2 - usage problem.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import struct
import sys
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_ADDONS = HERE.parents[1] / "odoo_addons"
DEFAULT_CATALOG = HERE / "apps_catalog.json"
DEFAULT_CE_DIRS = ["/home/user/odoo19/addons", "/home/user/odoo19/odoo/addons"]

REQUIRED_KEYS = (
    "name",
    "version",
    "summary",
    "description",
    "author",
    "website",
    "support",
    "license",
    "category",
    "depends",
    "images",
)
NAME_MAX = 25
VERSION_RE = re.compile(r"^19\.0\.\d+\.\d+\.\d+$")
CYRILLIC_RE = re.compile("[Ѐ-ӿ]")
APPS_LICENSES = {"GPL-3", "AGPL-3", "LGPL-3", "OPL-1", "Other OSI approved licence", "Other proprietary"}
PROPRIETARY = {"OPL-1", "Other proprietary"}
LICENSE_COMPAT = {  # module license -> licenses of dependencies it may use (Apps FAQ table)
    "AGPL-3": {"AGPL-3", "GPL-3", "LGPL-3"},
    "GPL-3": {"GPL-3", "LGPL-3"},
    "LGPL-3": {"LGPL-3", "OPL-1", "OEEL-1", "Other OSI approved licence", "Other proprietary"},
    "OPL-1": {"LGPL-3", "OPL-1", "OEEL-1", "Other OSI approved licence", "Other proprietary"},
    "Other OSI approved licence": {"LGPL-3", "OEEL-1", "OPL-1", "Other OSI approved licence", "Other proprietary"},
    "Other proprietary": {"LGPL-3", "OEEL-1", "OPL-1", "Other OSI approved licence", "Other proprietary"},
}
ICON_SIZE = (140, 140)
BANNER_SIZE = (1120, 560)
MAX_INDEX_BYTES = 200 * 1024
MAX_IMAGE_BYTES = 1024 * 1024

# Enterprise modules of Odoo 19 that are certainly not in Community (used when Community sources are unavailable;
# when they are available, "not in Community" is the primary criterion).
KNOWN_ENTERPRISE = frozenset(
    [
        "account_accountant",
        "account_asset",
        "account_budget",
        "account_reports",
        "account_online_synchronization",
        "approvals",
        "appointment",
        "documents",
        "documents_sign",
        "hr_appraisal",
        "hr_payroll",
        "hr_referral",
        "helpdesk",
        "industry_fsm",
        "industry_fsm_sale",
        "iot",
        "knowledge",
        "marketing_automation",
        "mrp_maintenance",
        "mrp_mps",
        "mrp_plm",
        "mrp_workorder",
        "mrp_workorder_hr",
        "planning",
        "project_enterprise",
        "quality",
        "quality_control",
        "quality_mrp",
        "quality_mrp_workorder",
        "sale_renting",
        "sale_subscription",
        "sign",
        "social",
        "spreadsheet_dashboard_edition",
        "stock_barcode",
        "timesheet_grid",
        "voip",
        "web_cohort",
        "web_dashboard",
        "web_gantt",
        "web_map",
        "web_studio",
        "whatsapp",
        "worksheet",
    ]
)

# Odoo html sanitizer tag/attribute set (odoo.tools.mail), minus everything that can run code or load resources.
ALLOWED_TAGS = frozenset(
    [
        "a",
        "abbr",
        "acronym",
        "address",
        "article",
        "aside",
        "b",
        "big",
        "blockquote",
        "br",
        "caption",
        "center",
        "cite",
        "code",
        "col",
        "colgroup",
        "dd",
        "del",
        "dfn",
        "div",
        "dl",
        "dt",
        "em",
        "figcaption",
        "figure",
        "font",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "i",
        "img",
        "ins",
        "kbd",
        "li",
        "main",
        "mark",
        "nav",
        "ol",
        "p",
        "pre",
        "q",
        "s",
        "samp",
        "section",
        "small",
        "span",
        "strike",
        "strong",
        "sub",
        "sup",
        "table",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "tr",
        "tt",
        "u",
        "ul",
        "var",
    ]
)
ALLOWED_ATTRS = frozenset(
    [
        "class",
        "style",
        "id",
        "href",
        "src",
        "alt",
        "title",
        "width",
        "height",
        "colspan",
        "rowspan",
        "align",
        "valign",
        "border",
        "cellpadding",
        "cellspacing",
        "target",
        "rel",
        "name",
        "lang",
        "dir",
        "color",
        "face",
        "size",
        "bgcolor",
    ]
)
ALLOWED_STYLE_PROPS = (
    "color",
    "background",
    "font",
    "margin",
    "padding",
    "border",
    "text-align",
    "line-height",
    "text-decoration",
    "vertical-align",
    "width",
    "height",
    "max-width",
    "display",
)
YOUTUBE_RE = re.compile(
    r"^https://(www\.)?youtube(-nocookie)?\.com/(watch\?v=|embed/)[\w-]+$|^https://youtu\.be/[\w-]+$"
)
TEAMS_RE = re.compile(r"^https://teams\.microsoft\.com/")
IMG_EXT = {".png", ".gif", ".jpg", ".jpeg"}


class Result:
    def __init__(self):
        self.errors: list[tuple[str, str]] = []
        self.warnings: list[tuple[str, str]] = []

    def err(self, code, msg):
        self.errors.append((code, msg))

    def warn(self, code, msg):
        self.warnings.append((code, msg))


# ------------------------------------------------------------------------------------------------ helpers
def read_manifest(path: Path) -> dict:
    tree = ast.parse(path.read_text(encoding="utf8"))
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Dict):
            return ast.literal_eval(node.value)
    raise ValueError("no dict literal in manifest")


def image_info(path: Path):
    """Return (format, width, height) from the file header, or None if it is not PNG/GIF/JPEG."""
    with open(path, "rb") as f:
        head = f.read(32)
        if head[:8] == b"\x89PNG\r\n\x1a\n" and head[12:16] == b"IHDR":
            w, h = struct.unpack(">II", head[16:24])
            return "png", w, h
        if head[:6] in (b"GIF87a", b"GIF89a"):
            w, h = struct.unpack("<HH", head[6:10])
            return "gif", w, h
        if head[:2] == b"\xff\xd8":
            f.seek(2)
            while True:
                b = f.read(1)
                if not b:
                    return None
                if b != b"\xff":
                    continue
                m = f.read(1)
                while m == b"\xff":
                    m = f.read(1)
                if not m or m in (b"\x00", b"\x01") or b"\xd0" <= m <= b"\xd9":
                    continue
                seg = f.read(2)
                if len(seg) < 2:
                    return None
                ln = struct.unpack(">H", seg)[0]
                if m in (b"\xc0", b"\xc1", b"\xc2", b"\xc3", b"\xc5", b"\xc6", b"\xc7", b"\xc9", b"\xca", b"\xcb"):
                    data = f.read(5)
                    h, w = struct.unpack(">HH", data[1:5])
                    return "jpeg", w, h
                f.seek(ln - 2, 1)
    return None


def find_ce_modules(dirs) -> set[str] | None:
    names: set[str] = set()
    found = False
    for d in dirs:
        p = Path(d)
        if p.is_dir():
            found = True
            names.update(c.name for c in p.iterdir() if (c / "__manifest__.py").exists())
    return names if found and names else None


def classify(dep: str, ce_modules) -> str:
    """'ce' | 'ee' | 'unknown' for a non-td dependency."""
    if ce_modules is not None and dep in ce_modules:
        return "ce"
    if dep in KNOWN_ENTERPRISE:
        return "ee"
    return "unknown" if ce_modules is not None else "ce"


# ------------------------------------------------------------------------------------------------ index.html
class _Html(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, list[tuple[str, str | None]]]] = []
        self.text: list[str] = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, attrs))

    def handle_startendtag(self, tag, attrs):
        self.tags.append((tag, attrs))

    def handle_data(self, data):
        self.text.append(data)


def check_index(res: Result, mdir: Path):
    path = mdir / "static" / "description" / "index.html"
    if not path.is_file():
        res.err("html.missing", "static/description/index.html is missing")
        return
    raw = path.read_bytes()
    try:
        content = raw.decode("utf8")
    except UnicodeDecodeError:
        res.err("html.encoding", "index.html is not valid UTF-8")
        return
    if len(raw) > MAX_INDEX_BYTES:
        res.warn("html.size", f"index.html is {len(raw) // 1024} KB (> {MAX_INDEX_BYTES // 1024} KB)")
    if CYRILLIC_RE.search(content):
        res.err("html.language", "index.html contains Cyrillic text; the description must be in English")
    parser = _Html()
    parser.feed(content)
    base = path.parent
    seen: set[str] = set()

    def once(code, msg, error=True):
        if (code, msg) not in seen:
            seen.add((code, msg))
            (res.err if error else res.warn)(code, msg)

    sections = 0
    for tag, attrs in parser.tags:
        if tag == "script":
            once("html.script", "index.html contains <script> (JavaScript is forbidden)")
            continue
        if tag == "section":
            sections += 1
        if tag not in ALLOWED_TAGS:
            once("html.tag", f"tag <{tag}> is not allowed")
        for name, value in attrs:
            value = value or ""
            if name.startswith("on"):
                once("html.script", f"event handler attribute {name}= is forbidden")
            elif name not in ALLOWED_ATTRS:
                once("html.attr", f"attribute {name}= is not in the whitelist (will be stripped)", error=False)
            if name == "style":
                low = value.lower()
                if "url(" in low or "expression(" in low or "javascript:" in low or "@import" in low:
                    once("html.style", "style attribute with url()/expression()/@import is forbidden")
                for decl in filter(None, (d.strip() for d in value.split(";"))):
                    prop = decl.split(":", 1)[0].strip().lower()
                    if not prop.startswith(ALLOWED_STYLE_PROPS):
                        once(
                            "html.style", f"style property '{prop}' is not allowed (use Bootstrap classes)", error=False
                        )
            if name in ("src", "href"):
                v = value.strip()
                low = v.lower()
                if not v or v.startswith("#") or low.startswith(("mailto:", "skype:")):
                    continue
                if low.startswith(("javascript:", "data:")):
                    once("html.url", f"{name}={v[:40]!r}: javascript:/data: URLs are forbidden")
                elif re.match(r"^([a-z][a-z0-9+.-]*:)?//", low) or re.match(r"^[a-z][a-z0-9+.-]*:", low):
                    if name == "href" and tag == "a" and (YOUTUBE_RE.match(v) or TEAMS_RE.match(v)):
                        continue
                    once("html.url", f"external URL {v[:60]!r} (only local files, youtube and teams links are allowed)")
                else:
                    target = (base / v.split("#")[0].split("?")[0]).resolve()
                    if not target.is_file():
                        once("html.local", f"{name}={v!r}: local file does not exist")
                    elif tag == "img" or name == "src":
                        info = image_info(target)
                        if target.suffix.lower() not in IMG_EXT or info is None:
                            once("html.image", f"{v!r}: only real png/gif/jpeg images are allowed")
                        elif target.stat().st_size > MAX_IMAGE_BYTES:
                            once("html.image", f"{v!r} is larger than {MAX_IMAGE_BYTES // 1024} KB", error=False)
        if tag == "img" and not any(n == "alt" and v for n, v in attrs):
            once("html.alt", "an <img> without alt text", error=False)
    if re.search(r"https?://", " ".join(parser.text)):
        res.warn("html.text_url", "index.html text mentions an http(s) URL (only links to local files are valid)")
    if sections < 3:
        res.warn("html.blocks", f"index.html has {sections} <section> blocks; 3-6 are recommended")


# ------------------------------------------------------------------------------------------------ manifest files
GLOB_CHARS = set("*?[")


def check_files(res: Result, mdir: Path, manifest: dict, all_manifests: dict):
    """Every file named in data/demo and every td_* asset path must exist (also proves an export is complete)."""
    for key in ("data", "demo"):
        for rel in manifest.get(key) or []:
            if isinstance(rel, str) and not (mdir / rel).is_file():
                res.err("files.missing", f"{key} file {rel} does not exist")
    addons = mdir.parent
    for bundle, entries in (manifest.get("assets") or {}).items():
        for entry in entries:
            parts = list(entry[1:]) if isinstance(entry, (tuple, list)) else [entry]
            if isinstance(entry, (tuple, list)) and entry and entry[0] == "include":
                continue
            for path in parts:
                if not isinstance(path, str) or "/" not in path:
                    continue
                mod = path.split("/", 1)[0]
                if mod not in all_manifests:
                    continue
                if GLOB_CHARS & set(path):
                    if not list(addons.glob(path)):
                        res.warn("files.glob_empty", f"assets {bundle}: pattern {path} matches no file")
                elif not (addons / path).exists():
                    res.err("files.missing", f"assets {bundle}: {path} does not exist")


# ------------------------------------------------------------------------------------------------ per module
def check_module(
    mdir: Path, manifest: dict, all_manifests: dict, catalog: dict, ce_modules, closure_ee, chain
) -> Result:
    res = Result()
    name = mdir.name
    for key in REQUIRED_KEYS:
        if key not in manifest or manifest[key] in (None, "", [], ()):
            res.err("manifest.key", f"manifest key '{key}' is missing or empty")
    mname = manifest.get("name")
    if isinstance(mname, str):
        if len(mname) > NAME_MAX:
            res.err("manifest.name", f"name is {len(mname)} chars (max {NAME_MAX})")
        if CYRILLIC_RE.search(mname):
            res.err("manifest.language", "name must be in English")
    version = manifest.get("version")
    if version is not None and not VERSION_RE.match(str(version)):
        res.err("manifest.version", f"version {version!r} does not match 19.0.x.y.z")
    for key in ("summary", "description"):
        val = manifest.get(key)
        if isinstance(val, str) and CYRILLIC_RE.search(val):
            res.err("manifest.language", f"{key} must be in English (Cyrillic found)")
    summary = manifest.get("summary")
    if isinstance(summary, str) and len(summary) > 200:
        res.warn("manifest.summary", f"summary is {len(summary)} chars; keep it short")
    lic = manifest.get("license")
    if lic is not None and lic not in APPS_LICENSES:
        res.err("manifest.license", f"license {lic!r} is not accepted by Apps ({', '.join(sorted(APPS_LICENSES))})")
    site = manifest.get("website")
    if isinstance(site, str) and site and not site.startswith("https://"):
        res.warn("manifest.website", "website should be an https:// URL")
    sup = manifest.get("support")
    if isinstance(sup, str) and sup and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", sup):
        res.err("manifest.support", f"support {sup!r} must be an email address")
    if manifest.get("installable") is False:
        res.warn("manifest.installable", "installable is False")
    if "price" in manifest:
        price = manifest["price"]
        if not isinstance(price, (int, float)) or isinstance(price, bool):
            res.err("manifest.price", "price must be a number")
        elif price < 0:
            res.warn("manifest.price", "negative price: the app is treated as free")
        elif 0 < price < 9:
            res.err("manifest.price", f"price {price} is below the Apps minimum of 9")
        if manifest.get("currency", "EUR") not in ("EUR", "USD"):
            res.err("manifest.currency", "currency must be EUR or USD")
    elif "currency" in manifest:
        res.warn("manifest.currency", "currency without price")

    # images
    images = manifest.get("images")
    if isinstance(images, list):
        for rel in images:
            p = mdir / rel
            if not p.is_file():
                res.err("images.missing", f"image {rel} does not exist")
                continue
            info = image_info(p)
            if info is None or p.suffix.lower() not in IMG_EXT:
                res.err("images.format", f"image {rel} is not a real png/gif/jpeg file")
                continue
            _, w, h = info
            if p.name.startswith("banner"):
                if (w, h) != BANNER_SIZE:
                    res.err("images.size", f"banner {rel} is {w}x{h}, expected {BANNER_SIZE[0]}x{BANNER_SIZE[1]}")
            elif not (400 <= w <= 2400):
                res.warn("images.size", f"image {rel} is {w}x{h}; width 400-2400 expected")
            if p.stat().st_size > 2 * MAX_IMAGE_BYTES:
                res.warn("images.weight", f"image {rel} is {p.stat().st_size // 1024} KB")
    elif "images" in manifest:
        res.err("manifest.images", "images must be a list of paths")

    # icon
    icon = mdir / "static" / "description" / "icon.png"
    if not icon.is_file():
        res.err("icon.missing", "static/description/icon.png is missing (Apps shows a white cube)")
    else:
        info = image_info(icon)
        if info is None or info[0] != "png":
            res.err("icon.format", "icon.png is not a real PNG file")
        else:
            _, w, h = info
            if w != h or w < 64:
                res.err("icon.size", f"icon.png is {w}x{h}; it must be square (>= 64 px)")
            elif (w, h) != ICON_SIZE:
                res.warn("icon.size", f"icon.png is {w}x{h}; the project standard is {ICON_SIZE[0]}x{ICON_SIZE[1]}")

    check_index(res, mdir)
    check_files(res, mdir, manifest, all_manifests)

    # i18n and license file
    if not (mdir / "i18n").is_dir() or not list((mdir / "i18n").glob("*.pot")):
        res.warn("i18n.pot", "no i18n/*.pot translation template")
    if lic in PROPRIETARY and not (mdir / "LICENSE").is_file() and not (mdir.parent / "LICENSE").is_file():
        res.warn("license.file", f"{lic} module without a LICENSE file (module or repository root)")

    # dependencies
    depends = manifest.get("depends") or []
    for dep in depends:
        if dep.startswith(("td_", "test_td_")):
            if dep not in all_manifests:
                res.err("dep.missing", f"depends on {dep}, which is not in this addons directory")
                continue
            dlic = all_manifests[dep].get("license")
        else:
            kind = classify(dep, ce_modules)
            dlic = "OEEL-1" if kind == "ee" else "LGPL-3"
            if ce_modules is None and dep not in KNOWN_ENTERPRISE:
                continue
            if kind == "unknown":
                continue
        if lic in LICENSE_COMPAT and dlic and dlic not in LICENSE_COMPAT[lic]:
            res.err("license.compat", f"{lic} module cannot depend on {dep} ({dlic})")
        if lic == "LGPL-3" and dlic in PROPRIETARY:
            res.warn("license.proprietary_dep", f"LGPL-3 module depends on the proprietary module {dep} ({dlic})")

    declared = catalog.get(name, {}).get("edition")
    if declared is None:
        res.warn("edition.undeclared", "module is not in apps_catalog.json; Community assumed")
        declared = "ce"
    if closure_ee:
        if declared == "ce":
            res.err(
                "dep.enterprise", "declared Community, but depends on Enterprise/non-Community: " + "; ".join(chain)
            )
    elif declared == "ee":
        res.warn("edition.stale", "declared Enterprise, but no Enterprise dependency was found")
    if ce_modules is None:
        res.warn(
            "dep.unverified",
            "Community sources not found; dependencies checked against the built-in Enterprise list only",
        )
    return res


def enterprise_chains(all_manifests: dict, ce_modules) -> dict[str, list[str]]:
    """module -> list of 'td_a -> td_b -> mrp_workorder' chains to Enterprise (or not-in-Community) modules."""
    out: dict[str, list[str]] = {}
    for start in all_manifests:
        chains, stack, seen = [], [(start, [start])], {start}
        while stack:
            cur, path = stack.pop()
            for dep in all_manifests[cur].get("depends") or []:
                if dep in all_manifests:
                    if dep not in seen:
                        seen.add(dep)
                        stack.append((dep, path + [dep]))
                elif classify(dep, ce_modules) in ("ee", "unknown"):
                    chains.append(
                        " -> ".join(path + [dep]) + ("" if classify(dep, ce_modules) == "ee" else " (not in Community)")
                    )
        out[start] = sorted(set(chains))
    return out


def check_addons(addons_dir, modules=None, ce_dirs=None, catalog_path=None, include_tests=False):
    addons = Path(addons_dir)
    ce_modules = find_ce_modules(DEFAULT_CE_DIRS if ce_dirs is None else ce_dirs)
    catalog = {}
    cp = Path(catalog_path) if catalog_path else DEFAULT_CATALOG
    if cp.is_file():
        catalog = json.loads(cp.read_text(encoding="utf8")).get("modules", {})
    all_manifests, results = {}, {}
    for d in sorted(addons.iterdir()):
        if (d / "__manifest__.py").is_file():
            try:
                all_manifests[d.name] = read_manifest(d / "__manifest__.py")
            except Exception as exc:  # noqa: BLE001
                r = Result()
                r.err("manifest.parse", f"cannot parse __manifest__.py: {exc}")
                results[d.name] = r
    chains = enterprise_chains(all_manifests, ce_modules)
    names: dict[str, str] = {}
    for mod, man in all_manifests.items():
        if mod.startswith("test_") and not include_tests:
            continue
        if modules and mod not in modules:
            continue
        res = check_module(addons / mod, man, all_manifests, catalog, ce_modules, bool(chains[mod]), chains[mod])
        n = man.get("name")
        if n in names:
            res.err("manifest.name", f"duplicate name {n!r} (also {names[n]})")
        names.setdefault(n, mod)
        results[mod] = res
    return results, catalog


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Offline Odoo Apps readiness check for td_* addons.")
    ap.add_argument("addons_dir", nargs="?", default=str(DEFAULT_ADDONS))
    ap.add_argument("-m", "--module", action="append", default=[])
    ap.add_argument(
        "--ce-addons",
        action="append",
        default=None,
        help="Odoo Community addons dir(s); default: $ODOO_CE_ADDONS or /home/user/odoo19/addons",
    )
    ap.add_argument("--catalog", default=None)
    ap.add_argument("--include-tests", action="store_true", help="also check test_* modules")
    ap.add_argument("--ignore", default="", help="comma-separated issue codes to ignore, e.g. i18n.pot")
    ap.add_argument("--strict", action="store_true", help="warnings fail the run")
    ap.add_argument("-q", "--quiet", action="store_true", help="table only, no issue details")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if not Path(a.addons_dir).is_dir():
        print(f"not a directory: {a.addons_dir}", file=sys.stderr)
        return 2
    ce_dirs = a.ce_addons
    if ce_dirs is None and os.environ.get("ODOO_CE_ADDONS"):
        ce_dirs = os.environ["ODOO_CE_ADDONS"].split(os.pathsep)
    results, catalog = check_addons(a.addons_dir, a.module or None, ce_dirs, a.catalog, a.include_tests)
    ignore = set(filter(None, a.ignore.split(",")))
    for r in results.values():
        r.errors = [e for e in r.errors if e[0] not in ignore]
        r.warnings = [w for w in r.warnings if w[0] not in ignore]
    if a.json:
        print(
            json.dumps(
                {m: {"errors": r.errors, "warnings": r.warnings} for m, r in results.items()},
                ensure_ascii=False,
                indent=1,
            )
        )
    else:
        width = max([len(m) for m in results] + [6])
        print(f"{'module':<{width}}  ed  errors  warnings  status")
        for m, r in sorted(results.items()):
            ed = catalog.get(m, {}).get("edition", "?").upper()
            status = "ERROR" if r.errors else ("warn" if r.warnings else "ok")
            print(f"{m:<{width}}  {ed:<2}  {len(r.errors):>6}  {len(r.warnings):>8}  {status}")
        n_err = sum(1 for r in results.values() if r.errors)
        n_warn = sum(1 for r in results.values() if r.warnings and not r.errors)
        n_ok = len(results) - n_err - n_warn
        print(f"\nmodules: {len(results)}  ok: {n_ok}  warnings only: {n_warn}  with errors: {n_err}")
        if not a.quiet:
            for m, r in sorted(results.items()):
                for code, msg in r.errors:
                    print(f"  E {m}: [{code}] {msg}")
                for code, msg in r.warnings:
                    print(f"  W {m}: [{code}] {msg}")
    failed = any(r.errors for r in results.values()) or (a.strict and any(r.warnings for r in results.values()))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
