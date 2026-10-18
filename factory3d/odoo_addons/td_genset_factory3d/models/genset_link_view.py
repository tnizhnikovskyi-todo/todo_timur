from odoo import api, models

from ..adapters import telemetry


class F3dGensetLinkView(models.Model):
    """R-05 (з уже прочитаних значень) і R-13 (коди критичних споживачів) для провайдера переглядача."""

    _inherit = "td.genset3d.link"

    def _island_state_from_signals(self, vals=None, pos=None, s1=None):
        """R-05 без нового читання знімка. `vals` — {leaf: значення} щойно прочитаних сигналів генератора;
        `pos`/`s1` — явні значення АВР (інакше читаються за кодами з параметрів, TEL-04, зі свіжістю)."""
        self.ensure_one()
        vals = vals or {}
        if pos is None:
            now = telemetry.now()
            pos_code = (self._param("ats_position_code", "") or "").strip()
            s1_code = (self._param("ats_src1_code", "") or "").strip()
            codes = [c for c in (pos_code, s1_code) if c]
            if codes:
                values = telemetry.read_values(self.env, codes)
                periods = telemetry.signal_periods(self.env, codes)
                pos = self._fresh_value(values, periods, pos_code, now)
                s1 = self._fresh_value(values, periods, s1_code, now)
        if pos is not None:
            return self._island_from_ats(pos, s1)
        if vals.get("online"):
            mains_ok = vals.get("mains_ok")
            return {
                "island": vals.get("breaker") == 2 and vals.get("state") in (6, 7),
                "grid_ok": None if mains_ok is None else bool(mains_ok),
                "source": "hgm",
            }
        last = self.last_state_json or {}
        return {"island": last.get("island"), "grid_ok": None, "source": "stale"}

    @api.model
    def _critical_signal_codes(self):
        """Коди сигналів критичних споживачів R-04 (для умови дельти R-13 п. 1в)."""
        codes = []
        if "td.energy.node" in self.env:
            nodes = self.env["td.energy.node"].sudo().search_read([("is_critical", "=", True)], ["code", "kind"])
            for node in nodes:
                folder = {"consumer": "consumers", "line": "lines"}.get(node["kind"])
                if folder:
                    codes.append("energy/%s/%s/p_now" % (folder, node["code"]))
        if not codes:
            raw = self.env["ir.config_parameter"].sudo().get_param("td.genset.critical_codes", "") or ""
            codes = [c.strip() for c in raw.split(",") if c.strip()]
        return codes
