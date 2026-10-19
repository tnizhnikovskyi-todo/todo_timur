"""Тестове джерело проходів (SPEC §0.3, A-19): БЕЗ _inherit, без _td_on_site і _td_key."""
from odoo import models


class F3dFirePassageSourceZzTest(models.AbstractModel):
    _name = "td.fire.passage.source.zz_test"
    _description = "Пожежна безпека: тестове джерело проходів zz_test"

    _td_priority = 5

    def _td_available(self):
        return bool(self.env.context.get("f3d_test_passage_source"))

    def _td_passages(self, start, end):
        return list(self.env.context.get("f3d_test_passages", []))
