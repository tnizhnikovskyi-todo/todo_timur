"""Тестове джерело проходів (SPEC §0.3, A-19): БЕЗ _inherit, без _f3d_on_site і _f3d_key."""
from odoo import models


class F3dFirePassageSourceZzTest(models.AbstractModel):
    _name = "f3d.fire.passage.source.zz_test"
    _description = "Пожежна безпека: тестове джерело проходів zz_test"

    _f3d_priority = 5

    def _f3d_available(self):
        return bool(self.env.context.get("f3d_test_passage_source"))

    def _f3d_passages(self, start, end):
        return list(self.env.context.get("f3d_test_passages", []))
