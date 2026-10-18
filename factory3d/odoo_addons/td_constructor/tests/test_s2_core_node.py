import shutil
import subprocess
from pathlib import Path

from odoo.tests import TransactionCase, tagged

FACTORY3D = Path(__file__).resolve().parents[3]
SCRIPT = FACTORY3D / 'tools' / 'test_core_s2.mjs'


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_s2", "f3d_core")
class TestS2CoreNode(TransactionCase):
    """S2: ядро (план, журнал, відкат, ємність, правила, «Odoo» прототипа, адаптер) — `node tools/test_core_s2.mjs`."""

    def test_s2_core_in_node(self):
        node = shutil.which('node')
        if not node:
            self.skipTest("у PATH немає `node`: тести ядра S2 (tools/test_core_s2.mjs) пропущено")
        if not SCRIPT.is_file():
            self.skipTest("немає factory3d/tools/test_core_s2.mjs: модуль встановлено поза репозиторієм factory3d")
        proc = subprocess.run(
            [node, str(SCRIPT)], cwd=FACTORY3D, capture_output=True, text=True, timeout=300, check=False
        )
        output = (proc.stdout + proc.stderr).strip().splitlines()
        self.assertEqual(proc.returncode, 0, "node tools/test_core_s2.mjs:\n" + "\n".join(output[-25:]))
