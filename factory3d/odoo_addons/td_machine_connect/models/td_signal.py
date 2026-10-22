import logging

from odoo import api, fields, models

from .td_machine import CONTENTION_ERRORS, env_default, param_bool

_logger = logging.getLogger(__name__)


class F3dSignal(models.Model):
    """M-18: вхід показань (`_td_ingest`, `_mark_stale` з `super()` першим)."""

    _inherit = "td.signal"

    @api.model
    def _td_ingest(self, readings, src="module", collector=None):
        res = super()._td_ingest(readings, src=src, collector=collector)
        if self.env.context.get("f3d_mc_internal") or not param_bool(self.env, "read_enabled", env_default(self.env)):
            return res
        # unknown_state telemetry приймає (q='bad') і лише повідомляє — такі показання модуль обробляє сам (R-01)
        rejected = {r["i"] for r in res.get("rejected", ()) if r.get("reason") != "unknown_state"}
        code_map = self.env["td.machine"]._td_code_map()
        mine = [dict(r, i=i) for i, r in enumerate(readings) if i not in rejected and r.get("code") in code_map]
        if mine:
            self.env["td.machine"].sudo()._td_dispatch(mine, src)
        return res

    def _mark_stale(self, reason):
        """Сигнал → `stale` (super), а верстат його стану → `nodata`.

        DEC-20: сигнали стану підключених верстатів — по одному, у власному savepoint: верстат, зайнятий паралельною
        транзакцією (push, такт) або змінений нею після знімка, не валить крон. Його сигнал лишається у попередньому
        статусі й потрапить до наступного запуску `_cron_stale` (повтор через хвилину).
        """
        code_map = self.env["td.machine"]._td_code_map()
        of_machine = self.filtered(lambda s: code_map.get(s.code, (0, ""))[1] == "state")
        res = super(F3dSignal, self - of_machine)._mark_stale(reason)
        Machine = self.env["td.machine"].sudo()
        enabled = param_bool(self.env, "read_enabled", env_default(self.env))
        for sig in of_machine.sorted(lambda s: code_map[s.code][0]):
            machine = Machine.browse(code_map[sig.code][0]).exists().filtered(lambda m: m.active and m.read_enabled)
            machine = machine if enabled else Machine  # читання вимкнено — `_td_mark_nodata` нічого не робить
            try:
                with self.env.cr.savepoint() as savepoint:
                    if machine and not machine._td_lock_skip_locked():
                        savepoint.close(rollback=True)
                        _logger.info("td.signal %s: верстат зайнятий, stale повторить крон", sig.code)
                        continue
                    super(F3dSignal, sig)._mark_stale(reason)
                    if machine and not machine._td_mark_nodata(fields.Datetime.now(), reason):
                        savepoint.close(rollback=True)  # nodata не вдалось — сигнал лишається, повторить крон
            except CONTENTION_ERRORS as exc:
                _logger.info("td.signal %s: паралельне оновлення (%s), повтор кроном", sig.code, type(exc).__name__)
        return res
