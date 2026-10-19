"""pytest for check_apps.py: run `pytest factory3d/tools/apps -q` (stdlib + pytest, no Odoo, no network)."""

import json
import struct
import sys
import zlib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_apps as ca

GOOD_HTML = """<section class="oe_container"><div class="oe_row"><h2 class="oe_slogan">Demo</h2></div></section>
<section class="oe_container"><h3>Features</h3><ul><li>One</li></ul></section>
<section class="oe_container"><img class="img img-fluid" src="shot.png" alt="Shot"/>
<p style="color:#333; margin-top:8px">Contact <a href="mailto:a@b.co">a@b.co</a>
<a href="https://www.youtube.com/watch?v=abc123">video</a> <a href="#top">top</a></p></section>
"""


def make_png(path, w, h):
    path.parent.mkdir(parents=True, exist_ok=True)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + b"\x20\x40\x80" * w for _ in range(h))
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def manifest_text(**over):
    m = {
        "name": "Demo App",
        "version": "19.0.1.0.0",
        "summary": "A demo summary",
        "description": "Demo.",
        "author": "ToDo",
        "website": "https://todo.ltd",
        "support": "support@todo.ltd",
        "license": "LGPL-3",
        "category": "Manufacturing",
        "depends": ["base"],
        "images": ["static/description/banner.png"],
    }
    m.update(over)
    for k in [k for k, v in m.items() if v is ...]:
        del m[k]
    return "# header comment\n" + repr(m) + "\n"


def make_module(root, mod="td_demo", html=GOOD_HTML, icon=(140, 140), banner=(1120, 560), pot=True, **over):
    over.setdefault("name", "Demo " + mod)
    d = root / mod
    (d / "static" / "description").mkdir(parents=True)
    (d / "__manifest__.py").write_text(manifest_text(**over), encoding="utf8")
    if html is not None:
        (d / "static/description/index.html").write_text(html, encoding="utf8")
    if icon:
        make_png(d / "static/description/icon.png", *icon)
    if banner:
        make_png(d / "static/description/banner.png", *banner)
    make_png(d / "static/description/shot.png", 600, 300)
    if pot:
        (d / "i18n").mkdir()
        (d / "i18n" / f"{mod}.pot").write_text("# pot\n")
    return d


@pytest.fixture
def env(tmp_path):
    ce = tmp_path / "ce"
    for m in ("base", "stock", "mrp", "web"):
        (ce / m).mkdir(parents=True)
        (ce / m / "__manifest__.py").write_text("{}")
    addons = tmp_path / "addons"
    addons.mkdir()
    cat = tmp_path / "catalog.json"
    cat.write_text(json.dumps({"modules": {}}))
    return tmp_path, addons, ce, cat


def run(env, **kw):
    _, addons, ce, cat = env
    results, _ = ca.check_addons(addons, ce_dirs=[str(ce)], catalog_path=str(cat), **kw)
    return results


def codes(res, kind="errors"):
    return {c for c, _ in getattr(res, kind)}


def set_edition(env, **editions):
    _tmp, _, _, cat = env
    cat.write_text(json.dumps({"modules": {m: {"edition": e} for m, e in editions.items()}}))


def test_valid_module_has_no_errors_and_no_warnings(env):
    make_module(env[1])
    set_edition(env, td_demo="ce")
    r = run(env)["td_demo"]
    assert r.errors == [] and r.warnings == []


@pytest.mark.parametrize("key", ["summary", "description", "author", "website", "support", "images", "category"])
def test_missing_manifest_key(env, key):
    make_module(env[1], **{key: ...})
    assert "manifest.key" in codes(run(env)["td_demo"])


def test_version_must_be_19(env):
    make_module(env[1], version="18.0.1.0.0")
    assert "manifest.version" in codes(run(env)["td_demo"])
    make_module(env[1], mod="td_demo2", version="19.0.1.0", name="Other")
    assert "manifest.version" in codes(run(env)["td_demo2"])


def test_name_length_and_language(env):
    make_module(env[1], name="X" * 26)
    assert "manifest.name" in codes(run(env)["td_demo"])
    make_module(env[1], mod="td_ua", name="Генератори")
    assert "manifest.language" in codes(run(env)["td_ua"])


def test_summary_description_must_be_english(env):
    make_module(env[1], summary="Короткий опис")
    assert "manifest.language" in codes(run(env)["td_demo"])


def test_license_and_support(env):
    make_module(env[1], license="MIT", support="not-an-email")
    c = codes(run(env)["td_demo"])
    assert {"manifest.license", "manifest.support"} <= c


def test_price_rules(env):
    make_module(env[1], price=5)
    assert "manifest.price" in codes(run(env)["td_demo"])
    make_module(env[1], mod="td_p2", price=49, currency="GBP", name="P2")
    assert "manifest.currency" in codes(run(env)["td_p2"])
    make_module(env[1], mod="td_p3", price=49, currency="EUR", name="P3")
    r = run(env)["td_p3"]
    assert "manifest.price" not in codes(r) and "manifest.currency" not in codes(r)


def test_images_missing_format_and_banner_size(env):
    make_module(env[1], images=["static/description/nope.png"])
    assert "images.missing" in codes(run(env)["td_demo"])
    make_module(env[1], mod="td_b", banner=(560, 280), name="B")
    assert "images.size" in codes(run(env)["td_b"])
    d = make_module(env[1], mod="td_fake", name="Fake")
    (d / "static/description/banner.png").write_bytes(b"not a png at all")
    assert "images.format" in codes(run(env)["td_fake"])


def test_icon_checks(env):
    make_module(env[1], icon=None)
    assert "icon.missing" in codes(run(env)["td_demo"])
    make_module(env[1], mod="td_i2", icon=(140, 100), name="I2")
    assert "icon.size" in codes(run(env)["td_i2"])
    make_module(env[1], mod="td_i3", icon=(128, 128), name="I3")
    r = run(env)["td_i3"]
    assert "icon.size" in codes(r, "warnings") and "icon.size" not in codes(r)


def test_index_html_missing(env):
    make_module(env[1], html=None)
    assert "html.missing" in codes(run(env)["td_demo"])


@pytest.mark.parametrize(
    "snippet,code",
    [
        ("<script>alert(1)</script>", "html.script"),
        ('<p onclick="x()">t</p>', "html.script"),
        ("<style>p{}</style>", "html.tag"),
        ("<iframe src='x.png'></iframe>", "html.tag"),
        ('<img src="https://example.com/a.png" alt="x"/>', "html.url"),
        ('<a href="https://example.com">x</a>', "html.url"),
        ('<a href="javascript:alert(1)">x</a>', "html.url"),
        ('<img src="missing.png" alt="x"/>', "html.local"),
        ('<p style="background:url(a.png)">x</p>', "html.style"),
        ("<p>Опис українською</p>", "html.language"),
    ],
)
def test_index_html_forbidden_content(env, snippet, code):
    make_module(env[1], html=GOOD_HTML + snippet)
    assert code in codes(run(env)["td_demo"])


def test_index_html_not_a_real_image(env):
    d = make_module(env[1], html=GOOD_HTML + '<img src="fake.png" alt="x"/>')
    (d / "static/description/fake.png").write_text("text")
    assert "html.image" in codes(run(env)["td_demo"])


def test_index_html_warnings(env):
    make_module(env[1], html='<section><p style="float:left">x</p><img src="shot.png"/></section>')
    w = codes(run(env)["td_demo"], "warnings")
    assert {"html.style", "html.alt", "html.blocks"} <= w


def test_i18n_pot_is_a_warning(env):
    make_module(env[1], pot=False)
    r = run(env)["td_demo"]
    assert "i18n.pot" in codes(r, "warnings") and "i18n.pot" not in codes(r)


def test_enterprise_direct_dependency_for_community_module(env):
    make_module(env[1], depends=["base", "mrp_workorder"])
    set_edition(env, td_demo="ce")
    r = run(env)["td_demo"]
    assert "dep.enterprise" in codes(r) and "mrp_workorder" in r.errors[0][1] + "".join(m for _, m in r.errors)


def test_enterprise_transitive_dependency(env):
    make_module(env[1], mod="td_a", depends=["base", "td_b"], name="A")
    make_module(env[1], mod="td_b", depends=["base", "web_gantt"], name="B")
    set_edition(env, td_a="ce", td_b="ee")
    res = run(env)
    assert "dep.enterprise" in codes(res["td_a"])
    assert any("td_a -> td_b -> web_gantt" in m for _, m in res["td_a"].errors)
    assert "dep.enterprise" not in codes(res["td_b"])


def test_enterprise_declaration_stale_and_unknown_dependency(env):
    make_module(env[1])
    set_edition(env, td_demo="ee")
    assert "edition.stale" in codes(run(env)["td_demo"], "warnings")
    make_module(env[1], mod="td_u", depends=["base", "some_third_party"], name="U")
    set_edition(env, td_u="ce")
    assert "dep.enterprise" in codes(run(env)["td_u"])  # not in Community and not known -> not Community


def test_missing_td_dependency_and_undeclared_edition(env):
    make_module(env[1], depends=["base", "td_ghost"])
    r = run(env)["td_demo"]
    assert "dep.missing" in codes(r) and "edition.undeclared" in codes(r, "warnings")


def test_license_compatibility(env):
    make_module(env[1], mod="td_opl", license="OPL-1", name="Opl")
    make_module(env[1], mod="td_agpl", license="AGPL-3", depends=["td_opl"], name="Agpl")
    make_module(env[1], mod="td_lgpl", license="LGPL-3", depends=["td_opl"], name="Lgpl")
    res = run(env)
    assert "license.compat" in codes(res["td_agpl"])
    assert "license.compat" not in codes(res["td_lgpl"])
    assert "license.proprietary_dep" in codes(res["td_lgpl"], "warnings")
    assert "license.file" in codes(res["td_opl"], "warnings")


def test_duplicate_names_and_tests_are_skipped(env):
    make_module(env[1], mod="td_one", name="Same")
    make_module(env[1], mod="td_two", name="Same")
    make_module(env[1], mod="test_td_one", name="Other")
    res = run(env)
    assert "manifest.name" in codes(res["td_two"])
    assert "test_td_one" not in res
    assert "test_td_one" in run(env, include_tests=True)


def test_manifest_files_must_exist(env):
    d = make_module(
        env[1],
        data=["views/a.xml"],
        demo=["demo/d.xml"],
        assets={
            "web.assets_backend": [
                "td_demo/static/src/*.js",
                ("remove", "td_demo/static/src/x.js"),
                ("include", "web._assets_helpers"),
                "web/static/lib/y.js",
            ]
        },
    )
    r = run(env)["td_demo"]
    msgs = " | ".join(m for _, m in r.errors)
    assert "views/a.xml" in msgs and "demo/d.xml" in msgs and "td_demo/static/src/x.js" in msgs
    assert "files.glob_empty" in codes(r, "warnings")
    (d / "views").mkdir()
    (d / "views/a.xml").write_text("<odoo/>")
    (d / "demo").mkdir()
    (d / "demo/d.xml").write_text("<odoo/>")
    (d / "static/src").mkdir()
    (d / "static/src/x.js").write_text("//")
    r = run(env)["td_demo"]
    assert "files.missing" not in codes(r) and "files.glob_empty" not in codes(r, "warnings")


def test_unparsable_manifest(env):
    d = env[1] / "td_bad"
    d.mkdir()
    (d / "__manifest__.py").write_text("{'name': ")
    assert "manifest.parse" in codes(run(env)["td_bad"])


def test_image_info_gif_jpeg(tmp_path):
    gif = tmp_path / "a.gif"
    gif.write_bytes(b"GIF89a" + struct.pack("<HH", 30, 20) + b"\x00" * 10)
    assert ca.image_info(gif) == ("gif", 30, 20)
    jpg = tmp_path / "a.jpg"
    jpg.write_bytes(
        b"\xff\xd8\xff\xe0"
        + struct.pack(">H", 4)
        + b"\x00\x00"
        + b"\xff\xc0"
        + struct.pack(">H", 11)
        + b"\x08"
        + struct.pack(">HH", 50, 70)
        + b"\x03\x00\x00"
    )
    assert ca.image_info(jpg) == ("jpeg", 70, 50)
    assert ca.image_info(tmp_path / "a.gif") is not None
    (tmp_path / "x.png").write_bytes(b"junk")
    assert ca.image_info(tmp_path / "x.png") is None


def test_main_exit_codes(env, capsys):
    tmp, addons, ce, cat = env
    make_module(addons)
    set_edition(env, td_demo="ce")
    args = [str(addons), "--ce-addons", str(ce), "--catalog", str(cat)]
    assert ca.main(args) == 0
    out = capsys.readouterr().out
    assert "td_demo" in out and "ok: 1" in out
    assert ca.main(args + ["--strict", "--include-tests"]) == 0
    make_module(addons, mod="td_bad", icon=None, name="Bad")
    assert ca.main(args) == 1
    assert "icon.missing" in capsys.readouterr().out
    assert ca.main(args + ["-m", "td_demo"]) == 0
    assert ca.main([str(tmp / "nope")]) == 2


def test_main_strict_fails_on_warnings(env):
    _tmp, addons, ce, cat = env
    make_module(addons, pot=False)
    set_edition(env, td_demo="ce")
    args = [str(addons), "--ce-addons", str(ce), "--catalog", str(cat)]
    assert ca.main(args) == 0
    assert ca.main(args + ["--strict"]) == 1
    assert ca.main(args + ["--strict", "--ignore", "i18n.pot"]) == 0


def test_repo_addons_have_no_errors():
    """Regression guard: the real td_* addons of this repository must stay Apps-ready."""
    if not ca.DEFAULT_ADDONS.is_dir():
        pytest.skip("odoo_addons not found")
    results, _ = ca.check_addons(ca.DEFAULT_ADDONS)
    bad = {m: r.errors for m, r in results.items() if r.errors}
    assert not bad, bad


def test_export_script_flat_layout(tmp_path):
    """export_apps.sh: module in the root, dependency closure, no tests/pyc/internal docs, check passes."""
    import shutil
    import subprocess

    script = Path(__file__).resolve().parent / "export_apps.sh"
    if not ca.DEFAULT_ADDONS.is_dir() or not shutil.which("tar") or not shutil.which("bash"):
        pytest.skip("odoo_addons/tar/bash not available")
    out = tmp_path / "out"
    cp = subprocess.run(
        ["bash", str(script), str(out), "--modules", "td_viewer3d_sale"], capture_output=True, text=True, check=False
    )
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert sorted(p.name for p in out.iterdir() if p.is_dir()) == ["td_factory3d", "td_viewer3d", "td_viewer3d_sale"]
    assert (out / "README.md").is_file() and (out / "td_viewer3d_sale" / "__manifest__.py").is_file()
    assert not list(out.glob("*/tests")) and not list(out.rglob("*.pyc")) and not list(out.glob("*/ruff.toml"))
    assert not list(out.glob("*/*.md")) and (out / "td_viewer3d" / "static" / "description" / "banner.png").is_file()
    again = subprocess.run(["bash", str(script), str(out)], capture_output=True, text=True, check=False)
    assert again.returncode == 2 and "--force" in again.stderr  # refuses a non-empty directory
    skip = subprocess.run(
        ["bash", str(script), str(tmp_path / "noee"), "--skip-ee", "--no-check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert skip.returncode == 0, skip.stderr
    names = {p.name for p in (tmp_path / "noee").iterdir() if p.is_dir()}
    assert "td_yard_gantt" not in names and "td_yard" in names and "test_td_viewer3d" not in names
