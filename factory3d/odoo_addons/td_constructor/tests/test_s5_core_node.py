import shutil
import subprocess
from pathlib import Path

from odoo.tests import TransactionCase, tagged

FACTORY3D = Path(__file__).resolve().parents[3]
SCRIPT = FACTORY3D / 'tools' / 'test_core_s5.mjs'


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_s5", "f3d_core")
class TestS5CoreNode(TransactionCase):
    """S5: ядро (будівля, перевірки, специфікація, майстер) перевіряє `node tools/test_core_s5.mjs`."""

    def test_s5_core_in_node(self):
        node = shutil.which('node')
        if not node:
            self.skipTest("у PATH немає `node`: тести ядра S5 (tools/test_core_s5.mjs) пропущено")
        if not SCRIPT.is_file():
            self.skipTest("немає factory3d/tools/test_core_s5.mjs: модуль встановлено поза репозиторієм factory3d")
        proc = subprocess.run(
            [node, str(SCRIPT)], cwd=FACTORY3D, capture_output=True, text=True, timeout=300, check=False
        )
        output = (proc.stdout + proc.stderr).strip().splitlines()
        self.assertEqual(proc.returncode, 0, "node tools/test_core_s5.mjs:\n" + "\n".join(output[-25:]))
