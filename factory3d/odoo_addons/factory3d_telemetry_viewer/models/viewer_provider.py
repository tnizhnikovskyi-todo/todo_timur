from datetime import timezone
from zoneinfo import ZoneInfo

from odoo import models

KYIV = ZoneInfo("Europe/Kyiv")
SOURCE_LABEL = "телеметрія (factory3d_telemetry)"


class F3dViewerProviderTelemetry(models.AbstractModel):
    # Контракт провайдера — duck typing (ARCHITECTURE §6.7): без `_inherit` моделей viewer.
    _name = "f3d.viewer.provider.telemetry"
    _description = "3D: значення сигналів телеметрії"
    _f3d_sequence = 95
    _f3d_sections = ()
    _f3d_group = "factory3d_base.group_f3d_user"

    # --- R-12 ----------------------------------------------------------------------------------------
    def _f3d_visible_signals(self):
        return self.env["f3d.signal"].sudo().search([
            ("active", "=", True), ("viewer_visible", "=", True), ("status", "!=", "unknown")])

    @staticmethod
    def _f3d_value(sig):
        if sig.kind == "state":
            return sig.last_text
        v = sig.last_value
        if sig.unit == "%":
            return round(v / 100, 3)
        return round(v, 2) if abs(v) < 20 else round(v, 1)

    @staticmethod
    def _f3d_node(payload, code):
        """Вузол payload для `code` (без створення відсутніх) і останній ключ; або (None, None)."""
        *path, leaf = code.split("/")
        node = payload
        for step in path:
            node = node.get(step) if isinstance(node, dict) else None
            if not isinstance(node, dict):
                return None, None
        return node, leaf

    def _f3d_meta_iot(self, signals):
        stamps = [s.last_ts for s in signals if s.last_ts]
        updated = ""
        if stamps:
            updated = max(stamps).replace(tzinfo=timezone.utc).astimezone(KYIV).strftime("%Y-%m-%d %H:%M")
        return {
            "source": SOURCE_LABEL,
            "signals": len(signals),
            "alarms": len(signals.filtered(lambda s: s.status == "alarm")),
            "stale": len(signals.filtered(lambda s: s.status == "stale")),
            "updated": updated,
        }

    def _f3d_viewer_collect(self, payload, ctx):
        signals = self._f3d_visible_signals()
        for sig in signals:
            node, leaf = self._f3d_node(payload, sig.code)
            if node is None:
                continue
            if sig.kind != "state" and sig.last_value is None:
                continue
            node[leaf] = self._f3d_value(sig)
        totals = ((payload.get("infra") or {}).get("totals")) if isinstance(payload.get("infra"), dict) else None
        energy = (payload.get("energy") or {}).get("totals") if isinstance(payload.get("energy"), dict) else None
        if isinstance(totals, dict) and isinstance(energy, dict):
            for src, dst in (("pv_now", "pv_kw"), ("chp_kw", "chp_kw")):
                if src in totals:
                    energy[dst] = totals[src]
        payload.setdefault("meta", {})["iot"] = self._f3d_meta_iot(signals)

    def _f3d_viewer_delta(self, patch, ctx):
        codes = (ctx.get("changes") or {}).get("f3d.signal", set())
        if not codes:
            return
        signals = self._f3d_visible_signals()
        patch["signals"] = [
            {"path": sig.code, "value": self._f3d_value(sig)}
            for sig in signals.filtered(lambda s: s.code in codes and (s.kind == "state" or s.last_value is not None))
        ]
        patch.setdefault("meta", {})["iot"] = self._f3d_meta_iot(signals)

    def _f3d_viewer_bus_models(self):
        return ["f3d.signal"]
