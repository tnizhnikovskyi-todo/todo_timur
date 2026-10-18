import shutil
import subprocess
from pathlib import Path

from odoo.tests import TransactionCase, tagged

FACTORY3D = Path(__file__).resolve().parents[3]
SCRIPT = FACTORY3D / 'tools' / 'test_core.mjs'


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_core")
class TestCoreNode(TransactionCase):
    """CD-29: ядро `factory3d/core/constructor` без Odoo перевіряє `node tools/test_core.mjs` (з `factory3d/`)."""

    def test_core_suite_in_node(self):
        node = shutil.which('node')
        if not node:
            self.skipTest("у PATH немає `node`: тести ядра конструктора (tools/test_core.mjs) пропущено")
        if not SCRIPT.is_file():
            self.skipTest("немає factory3d/tools/test_core.mjs: модуль встановлено поза репозиторієм factory3d")
        proc = subprocess.run(
            [node, str(SCRIPT)], cwd=FACTORY3D, capture_output=True, text=True, timeout=300, check=False
        )
        output = (proc.stdout + proc.stderr).strip().splitlines()
        self.assertEqual(proc.returncode, 0, "node tools/test_core.mjs:\n" + "\n".join(output[-25:]))
