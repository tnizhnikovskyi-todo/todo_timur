import hashlib
import json
import os
import re
import shutil
import tempfile

from odoo.tests import BaseCase, tagged

from odoo.addons.td_viewer3d.tools import dates, static_data


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestStatic(BaseCase):

    def test_static_keys(self):
        data = static_data.load()
        for key in ("passports", "energy", "layout", "path_templates", "lighting", "ventilation", "fire", "infra",
                    "evacuation", "zones", "locations", "workcenters", "equipment"):
            self.assertIn(key, data)

    def test_static_etag_stable(self):
        with open(static_data.STATIC_PATH, "rb") as fh:
            sha1 = hashlib.sha1(fh.read()).hexdigest()
        self.assertEqual(static_data.etag(), sha1)
        self.assertEqual(static_data.etag(), static_data.etag())
        body, body_gz, tag = static_data.static_body()
        self.assertEqual(tag, sha1)
        doc = json.loads(body)
        self.assertEqual(doc["meta"]["static_etag"], sha1[:16])
        self.assertEqual(set(doc["meta"]), {"schema", "built_at", "static_etag"})

    def test_schema_version(self):
        self.assertEqual(static_data.load()["meta"]["schema"], "1.1")

    def test_reload_on_mtime(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        path = os.path.join(tmp, "s.json")
        with open(path, "w") as fh:
            json.dump({"meta": {"schema": "1.1"}, "a": 1}, fh)
        self.patch(static_data, "STATIC_PATH", path)
        first = static_data.etag()
        self.assertEqual(static_data.load()["a"], 1)
        with open(path, "w") as fh:
            json.dump({"meta": {"schema": "1.1"}, "a": 2}, fh)
        os.utime(path, (1, 1))
        self.assertEqual(static_data.load()["a"], 2)
        self.assertNotEqual(static_data.etag(), first)

    def test_parts_manifest(self):
        body, sha1 = static_data.parts_manifest()
        manifest = json.loads(body)
        self.assertTrue(manifest["parts"])
        for part in manifest["parts"]:
            self.assertRegex(part["file"], r"^/td_viewer3d/static/model/parts/\w+\.glb\?v=[0-9a-f]{12}$")
        self.assertEqual(hashlib.sha1(body).hexdigest(), sha1)


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestDates(BaseCase):

    def test_roundtrip_kyiv(self):
        # 12.10.2026 — літній час (UTC+3)
        self.assertEqual(dates.local(dates.utc("2026-10-12 10:30")), "2026-10-12 10:30")
        self.assertEqual(dates.utc("2026-10-12 10:30").hour, 7)
        # січень — UTC+2
        self.assertEqual(dates.utc("2026-01-12 10:30").hour, 8)

    def test_iso(self):
        dt = dates.parse_iso_utc("2026-10-12T07:30:12Z")
        self.assertEqual(dates.iso_utc(dt), "2026-10-12T07:30:12Z")
        self.assertEqual(dates.parse_iso_utc("2026-10-12T07:30:12"), dt)
        with self.assertRaises(ValueError):
            dates.parse_iso_utc("вчора")
        self.assertTrue(re.match(r"^\d{4}-\d\d-\d\d \d\d:\d\d$", dates.local(dates.real_now())))
