"""R-26 (расширение ядра, VX-01…VX-05; AC-278…AC-281): сторожові перевірки джерел клієнта.

Поведінку розширень перевіряє HOOT (`static/tests/hoot/extension_energy.test.js`, запускається `test_hoot.py`);
тут — те, що hoot не бачить: мінімізатор асетів (`rjsmin`) і межі втручання в ядро.
"""

import re
from pathlib import Path

from odoo.tests import BaseCase, tagged

STATIC = Path(__file__).resolve().parent.parent / "static"
CORE = STATIC / "src" / "viewer" / "core.js"
BEGIN = "// ---------------------------------------------------------------- розширення ядра (R-26"
END = '$(".o_f3d_opt-labels").onchange'
NESTED_TEMPLATE = re.compile(r"\$\{[^}`]*`")  # шаблонний літерал усередині `${...}`: rjsmin стирає в ньому пробіли


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestR26Extension(BaseCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.core = CORE.read_text(encoding="utf-8")
        start = cls.core.index(BEGIN)
        cls.block = cls.core[start : cls.core.index(END, start)]

    def test_extension_points_in_core(self):  # AC-278…AC-280
        for token in (
            "export function registerViewerExtension",
            "ext.colorModes",
            "xm.ext.modeColor(colorMode, root, D)",
            "ext.applyData(extApi, D, info)",
            "ext.cardBlocks(code, D, extApi)",
            "ext.onAction(extApi, act",
            "data-ext",  # в обробнику кліку панелі: `[data-ext]`
        ):
            self.assertIn(token, self.core, token)
        for reason in ("load", "patch", "snapshot", "now"):
            self.assertIn('extData("%s"' % reason, self.core, reason)
        self.assertIn("openAction(act) { if (!opts.onOpenAction) {return false;}", self.core)

    def test_block_is_small_and_without_nested_templates(self):  # SPEC 8.4.1: вставки ≤ 90 рядків; rjsmin
        self.assertLessEqual(len(self.block.splitlines()), 70)
        self.assertFalse(NESTED_TEMPLATE.search(self.block), "вкладений шаблонний літерал у блоці R-26")
        for line in self.core.splitlines():
            if "extData(" in line or "extModeOf(" in line or "extCards(" in line:
                self.assertFalse(NESTED_TEMPLATE.search(line), line)

    def test_rjsmin_keeps_block_literals(self):  # мінімізація не ламає рядки з пробілами/лапками
        try:
            import rjsmin
        except ImportError:
            self.skipTest("rjsmin не встановлено")
        minified = rjsmin.jsmin(self.core)
        for literal in (
            '"o_f3d_layer"',
            "'input[name=\"cmode\"]'",
            '"<div class=\\"o_f3d_sub\\">"',
            'el.dataset.ext.split(":")',
        ):
            self.assertIn(literal, minified, literal)
        self.assertIn("registerViewerExtension", minified)

    def test_open_action_only_in_backend_action(self):  # VX-05: у киоску onOpenAction не задано → openAction() = false
        action = (STATIC / "src" / "action" / "viewer_action.js").read_text(encoding="utf-8")
        self.assertIn("onOpenAction: (act) => this.action.doAction(act)", action)
        self.assertNotIn("onOpenAction", (STATIC / "src" / "kiosk" / "kiosk.js").read_text(encoding="utf-8"))

    def test_hoot_covers_all_points(self):  # AC-278…AC-280: по тесту на кожен VX
        hoot = (STATIC / "tests" / "hoot" / "extension_energy.test.js").read_text(encoding="utf-8")
        for vx in ("VX01", "VX02", "VX03", "VX04", "VX05"):
            self.assertRegex(hoot, r'test\("%s' % vx)
