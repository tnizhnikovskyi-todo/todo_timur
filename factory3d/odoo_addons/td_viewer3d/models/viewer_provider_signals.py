from odoo import api, models

from ..tools import dates
from ..tools import payload as payload_tools

SIGNAL_MODEL = "x_f3d_signal"
SIGNAL_FIELDS = ["x_code", "x_value", "x_unit", "x_mode", "x_charging", "x_updated", "x_state"]
IOT_SOURCE = "імітація датчиків (модуль td_iot_sim)"


def signal_value(row):
    """Значення сигналу як у LiveDemo.sync_signals: % → частка, інакше округлення за порядком."""
    v = row["x_value"] or 0.0
    if row.get("x_unit") == "%":
        return round(v / 100, 3)
    return round(v, 2) if abs(v) < 20 else round(v, 1)


def apply_signals(payload, rows):
    """Записує значення в наявні вузли `payload[a][b][c]`; шлях без вузла пропускається."""
    for r in rows:
        *path, leaf = r["x_code"].split("/")
        node = payload
        for k in path:
            node = node.get(k) if isinstance(node, dict) else None
            if node is None:
                break
        if not isinstance(node, dict):
            continue
        node[leaf] = signal_value(r)
        if r.get("x_mode") == "drain" and "state" in node:
            node["state"] = "charging" if r.get("x_charging") else "busy"


def iot_meta(rows):
    stamps = [r["x_updated"] for r in rows if r.get("x_updated")]
    return {"source": IOT_SOURCE, "signals": len(rows),
            "alarms": sum(r.get("x_state") == "тривога" for r in rows),
            "updated": dates.local(max(stamps)) if stamps else None}


class F3dViewerProviderSignals(models.AbstractModel):
    """M-01h: значення сигналів імітації за шляхами (Додаток C)."""
    _name = "td.viewer.provider.signals"
    _inherit = "td.viewer.provider"
    _description = "3D: постачальник — сигнали імітації"

    _f3d_sequence = 90
    _f3d_sections = ()
    _f3d_group = payload_tools.DEFAULT_GROUP

    @api.model
    def _f3d_signal_rows(self, codes=None):
        domain = [("x_active", "=", True), ("x_code", "!=", False)]
        if codes is not None:
            domain.append(("x_code", "in", list(codes)))
        return payload_tools.read(self.env, SIGNAL_MODEL, domain, SIGNAL_FIELDS)

    @api.model
    def _f3d_viewer_collect(self, payload, ctx):
        sections = ctx.get("sections")
        if SIGNAL_MODEL not in self.env:
            if isinstance(sections, dict):
                sections["signals"] = "missing"
            return
        if not payload_tools.access_ok(self.env, SIGNAL_MODEL):
            if isinstance(sections, dict):
                sections["signals"] = "denied"
            return
        rows = self._f3d_signal_rows()
        apply_signals(payload, rows)
        totals = (payload.get("infra") or {}).get("totals") or {}
        energy_totals = (payload.get("energy") or {}).get("totals")
        if isinstance(energy_totals, dict):
            if "pv_now" in totals:
                energy_totals["pv_kw"] = totals["pv_now"]
            if "chp_kw" in totals:
                energy_totals["chp_kw"] = totals["chp_kw"]
        payload.setdefault("meta", {})["iot"] = iot_meta(rows)
        if isinstance(sections, dict):
            sections["signals"] = "live"

    @api.model
    def _f3d_viewer_delta(self, patch, ctx):
        """R-14 п. 5: `patch.signals = [{path, value}]` для шляхів із `codes` + `meta.iot`."""
        changes = ctx.get("changes") or {}
        if SIGNAL_MODEL not in self.env or SIGNAL_MODEL not in changes \
                or not payload_tools.access_ok(self.env, SIGNAL_MODEL):
            return
        codes = set(changes[SIGNAL_MODEL])
        rows = self._f3d_signal_rows(codes) if codes else []
        patch["signals"] = [{"path": r["x_code"], "value": signal_value(r)} for r in rows]
        patch.setdefault("meta", {})["iot"] = iot_meta(self._f3d_signal_rows())
