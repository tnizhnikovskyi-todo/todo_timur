import logging
import re

from odoo import api, models

from ..tools import dates, live
from ..tools.dates import param_bool

_logger = logging.getLogger(__name__)
PV_P_RE = re.compile(r"^infra/pv/PV-INV-\d+/p_kw$")
PV_TODAY_RE = re.compile(r"^infra/pv/PV-INV-\d+/kwh_today$")
BAD_STATUS = ("stale", "unknown")


class F3dEnergyNodeLive(models.Model):
    """R-06, R-12 п. 3: крон живих показників `cron_f3d_energy_live` (розширення `f3d.energy.node`)."""

    _inherit = "f3d.energy.node"

    @api.model
    def _f3d_fresh_values(self):
        """{код: (значення, текст)} свіжих сигналів енергетики й `infra/` (R-06: не stale/unknown, не bad)."""
        rows = (
            self.env["f3d.signal"]
            .sudo()
            .search_read(
                ["|", ("code", "=like", "energy/%"), ("code", "=like", "infra/%")],
                ["code", "last_value", "last_text", "last_ts", "last_quality", "status"],
            )
        )
        return {
            r["code"]: (r["last_value"], r["last_text"])
            for r in rows
            if r["last_ts"] and r["status"] not in BAD_STATUS and r["last_quality"] != "bad"
        }

    @api.model
    def _f3d_live_snapshot(self, fresh=None):
        """R-06 п. 1–7: розрахунок живих показників з свіжих сигналів (без запису)."""
        fresh = fresh if fresh is not None else self._f3d_fresh_values()
        Node = self.sudo()

        def val(code):
            item = fresh.get(code)
            return item[0] if item else None

        lines, stale_lines = {}, 0
        for line in Node.search([("kind", "=", "line")]):
            p = val("energy/lines/%s/p_now" % line.code)
            if p is None:
                stale_lines += 1
                continue
            cos = live.pf_to_cos(val("energy/lines/%s/cos_phi" % line.code))
            lines[line.code] = {
                "section": line.section or line.parent_id.section,
                "p": p,
                "cos": cos,
                "i": val("energy/lines/%s/i_now" % line.code),
                "rating_a": line.rating_a,
                "cos_nominal": line.cos_phi_nominal,
            }
        pfc = {n.section: n for n in Node.search([("kind", "=", "cell"), ("cell_type", "=", "pfc")])}
        q_kvar = {s: val("energy/cells/Q%d/q_kvar" % s) for s in (1, 2)}
        totals = live.site_totals(lines, q_kvar, {s: n.rating_kvar for s, n in pfc.items()})
        p_q = [val("energy/cells/Q%d/p_now" % s) for s in (1, 2)]
        position = val("infra/ats/position")
        island = position is not None and position == 3
        grid_kw, export_kw = live.grid_split(p_q[0] or 0.0, p_q[1] or 0.0, island=island)
        bess_kw = val("infra/totals/bess_kw")
        critical = []
        for node in Node.search([("is_critical", "=", True), ("kind", "in", ("consumer", "line"))]):
            kind = "consumers" if node.kind == "consumer" else "lines"
            critical.append(val("energy/%s/%s/p_now" % (kind, node.code)))
        return {
            "totals": totals,
            "pfc": pfc,
            "stale_feeders": stale_lines,
            "stale_incomers": sum(1 for p in p_q if p is None),
            "island": island,
            "grid_kw": grid_kw,
            "export_kw": export_kw,
            "pv_now": sum(max(0.0, v[0]) for c, v in fresh.items() if PV_P_RE.match(c) and v[0] is not None),
            "pv_today": sum(v[0] for c, v in fresh.items() if PV_TODAY_RE.match(c) and v[0] is not None),
            "chp_kw": val("infra/totals/chp_kw"),
            "bess_kw": bess_kw,
            "bess_soc": val("infra/totals/bess_soc"),
            "bess_mode": live.bess_mode(bess_kw),
            "critical_kw": live.critical_kw(critical),
        }

    @api.model
    def _f3d_live_write(self, snap, now):
        """R-06 п. 8: тотали й `pfc_q_now`; при > 2 несвіжих фідерах або двох несвіжих вводах — не пишуться."""
        if snap["stale_feeders"] > 2 or snap["stale_incomers"] >= 2 or not snap["totals"]["lines"]:
            return False
        ts = dates.floor_minute(now)
        totals = snap["totals"]
        readings = [
            {"code": "energy/totals/p_now", "ts": ts, "value": round(totals["p_now"], 2), "q": "good"},
            {"code": "energy/totals/cos_phi", "ts": ts, "value": round(totals["cos_after"], 3), "q": "good"},
            {"code": "infra/totals/pv_now", "ts": ts, "value": round(snap["pv_now"], 2), "q": "good"},
            {"code": "infra/totals/grid_kw", "ts": ts, "value": round(snap["grid_kw"], 2), "q": "good"},
            {"code": "infra/totals/export_kw", "ts": ts, "value": round(snap["export_kw"], 2), "q": "good"},
        ]
        self.env["f3d.signal"].sudo()._f3d_energy_put(readings)
        for section, node in snap["pfc"].items():
            sec = totals["sections"].get(section)
            if sec is not None and node.pfc_q_now != sec["pfc_q_now"]:
                old = node.pfc_q_now
                node.write({"pfc_q_now": sec["pfc_q_now"]})
                self.env["f3d.energy.event"]._f3d_pfc_event(node, old, sec["pfc_q_now"], sec["cos_after"], ts=now)
        return True

    @api.model
    def _f3d_asymmetry(self, now, fresh=None):
        """R-12 п. 3: асиметрія фазних струмів шаф з фазними струмами → `…/i_unbal_pct`."""
        fresh = fresh if fresh is not None else self._f3d_fresh_values()
        ts = dates.floor_minute(now)
        readings = []
        cells = self.sudo().search([("kind", "=", "cell"), ("cell_type", "in", ("incomer", "feeder", "cable"))])
        for cell in cells:
            if cell.cell_type == "incomer":
                prefix = "energy/cells/%s" % cell.code
            else:
                line = cell.child_ids.filtered(lambda n: n.kind == "line")[:1]
                if not line:
                    continue
                prefix = "energy/lines/%s" % line.code
            phases = [fresh.get("%s/i_%s" % (prefix, ph), (None,))[0] for ph in "abc"]
            pct = live.unbalance_pct(*phases, cell.rating_a)
            if pct is not None:
                readings.append({"code": prefix + "/i_unbal_pct", "ts": ts, "value": round(pct, 2), "q": "good"})
        self.env["f3d.signal"].sudo()._f3d_energy_put(readings)
        return readings

    @api.model
    def _cron_live(self):
        if not param_bool(self.env, "read_enabled"):
            return False
        now = dates.now_utc(self.env)
        source = self.env.ref("factory3d_energy.source_en_derived", raise_if_not_found=False)
        try:
            with self.env.cr.savepoint():
                fresh = self._f3d_fresh_values()
                self._f3d_live_write(self._f3d_live_snapshot(fresh), now)
                if now.minute % 5 == 0:
                    self._f3d_asymmetry(now, fresh)
                self.env["f3d.energy.meter"].sudo().search([("active", "=", True)])._f3d_update_state()
            if source and source.state != "online":
                source.sudo().write({"state": "online", "last_error": False})
        except Exception as exc:
            _logger.exception("f3d_energy: крон живих показників")
            if source:
                source.sudo().write({"state": "error", "last_error": str(exc)[:512]})
        return True
