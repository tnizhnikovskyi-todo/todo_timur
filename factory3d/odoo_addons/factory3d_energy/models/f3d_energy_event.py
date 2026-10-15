import logging
from datetime import timedelta

from odoo import api, fields, models

from odoo.addons.factory3d_telemetry.tools import thresholds
from odoo.addons.factory3d_telemetry.tools.titles import fmt_num, render_title

from ..tools import dates

_logger = logging.getLogger(__name__)

STATUS_LEVEL = {"warn": "warn", "alarm": "bad"}


class F3dEnergyEvent(models.Model):
    """M-09. Журнал подій енергетики (R-13). Поле `outage_id` — W4 (R-14)."""

    _name = "f3d.energy.event"
    _description = "Енергетика: подія"
    _order = "ts desc, id desc"
    _log_access = False

    ts = fields.Datetime(string="Час", required=True, index=True, default=fields.Datetime.now)
    level = fields.Selection(
        [("info", "Інформація"), ("warn", "Увага"), ("bad", "Аварія")], string="Рівень", required=True, index=True
    )
    kind = fields.Selection(
        [
            ("threshold", "Поріг сигналу"),
            ("peak", "Пік потужності"),
            ("balance", "Баланс"),
            ("meter", "Лічильник"),
            ("ats", "АВР"),
            ("outage", "Відключення"),
            ("pfc", "Компенсація"),
            ("manual", "Вручну"),
        ],
        string="Вид",
        required=True,
    )
    code = fields.Char(string="Код", size=32)
    node_id = fields.Many2one("f3d.energy.node", string="Вузол", ondelete="set null")
    signal_id = fields.Many2one("f3d.signal", string="Сигнал", ondelete="set null")
    text = fields.Char(string="Текст", size=256, required=True)
    outage_id = fields.Many2one("f3d.energy.outage", string="Відключення", ondelete="set null", index=True)  # W4

    @api.model
    def _f3d_log(self, level, kind, code, text, ts=None, node=None, signal=None, outage=None, dedup_min=0):
        """M-09: подія; `dedup_min > 0` і є така сама (kind, code, text) за останні хвилини — не створювати."""
        ts = ts or dates.now_utc(self.env)
        text = (text or "")[:256]
        if dedup_min > 0 and self.sudo().search_count(
            [
                ("kind", "=", kind),
                ("code", "=", code or False),
                ("text", "=", text),
                ("ts", ">=", ts - timedelta(minutes=dedup_min)),
            ]
        ):
            return self.browse()
        vals = {"ts": ts, "level": level, "kind": kind, "code": code or False, "text": text}
        if node:
            vals["node_id"] = node.id
        if signal:
            vals["signal_id"] = signal.id
        if outage:
            vals["outage_id"] = outage.id
        rec = self.sudo().create(vals)
        if "f3d.viewer.event" in self.env:
            self.env["f3d.viewer.event"]._notify("f3d.energy", [code] if code else [], "signal")
        return rec

    # --- R-13 п. 1–2: події за зміною показань ---------------------------------------------------------
    @api.model
    def _f3d_on_ingest(self, before, readings):
        """`before` — {код: (status, last_text, last_value)} до прийому пакета; пакет уже в базі."""
        try:
            with self.env.cr.savepoint():
                self._f3d_on_ingest_inner(before)
        except Exception:
            _logger.exception("f3d_energy: помилка журналу подій після прийому показань")

    @api.model
    def _f3d_on_ingest_inner(self, before):
        Signal = self.env["f3d.signal"].sudo()
        self._f3d_ats_hook(before)  # W4: R-14
        signals = Signal.search([("code", "in", list(before))])
        for sig in signals.sorted("code"):
            old_status, old_text, _old_value = before[sig.code]
            if sig.code.startswith("workcenters/"):
                if sig.last_text == "fault" and old_text != "fault":
                    self._f3d_machine_fault(sig)
            elif sig.module == "energy" and sig.status != old_status:
                self._f3d_status_event(sig, old_status)

    @api.model
    def _f3d_ats_hook(self, before):
        """W4, R-14 п. 1: похідні `src{1,2}_ok`; п. 2–10: автомат відключення (крок після кожного пакета АВР/вводів)."""
        if self.env.context.get("f3d_ats_busy"):
            return
        from ..models.f3d_energy_outage import TRIGGER_CODES

        if not any(c in TRIGGER_CODES for c in before):
            return
        self = self.with_context(f3d_ats_busy=True)
        Signal = self.env["f3d.signal"].sudo()
        derived = []
        for n in (1, 2):
            sig = Signal.search([("code", "=", "infra/ats/src%d_state" % n)], limit=1)
            if sig and "infra/ats/src%d_state" % n in before and sig.last_ts:
                derived.append(
                    {
                        "code": "infra/ats/src%d_ok" % n,
                        "ts": sig.last_ts,
                        "value": 1 if sig.last_text == "available" else 0,
                        "q": "good",
                    }
                )
        if derived:
            Signal._f3d_energy_put(derived)
        self.env["f3d.energy.outage"]._f3d_ats_step()

    @api.model
    def _f3d_status_event(self, sig, old_status):
        new = sig.status
        if new in ("stale", "unknown"):
            return
        ts = sig.last_ts or dates.now_utc(self.env)
        unit = (" " + sig.unit) if sig.unit else ""
        if new in STATUS_LEVEL:
            threshold, rel = thresholds.breach_info(sig._f3d_cfg(), sig.last_value)
            text = render_title(sig, sig.last_value, rel, threshold, sig.last_text)
            level = STATUS_LEVEL[new]
        elif old_status in ("warn", "alarm"):
            if sig.kind == "state":
                value = sig.last_text or ""
            else:
                value = ("%s%s" % (fmt_num(sig.last_value, sig.decimals), unit)).strip()
            text = "%s: повернувся в норму (%s)" % (sig.name, value)
            level = "info"
        else:
            return
        self._f3d_log(level, "threshold", sig.equipment_code or False, text, ts=ts, signal=sig)

    @api.model
    def _f3d_machine_fault(self, sig):
        """R-13 п. 2: верстат став `fault` — аварійна зупинка зі споживанням вузла."""
        wc_code = sig.code.split("/")[1]
        Node = self.env["f3d.energy.node"].sudo()
        node = Node.search([("code", "=", wc_code)], limit=1) or Node.search(
            [("workcenter_id.name", "=", wc_code)], limit=1
        )
        p_now = node.p_now if node else 0.0
        text = "%s: аварійна зупинка, споживання впало до %s кВт." % (wc_code, fmt_num(p_now, 1))
        self._f3d_log("bad", "threshold", wc_code, text, ts=sig.last_ts, node=node or None, signal=sig)

    @api.model
    def _f3d_pfc_event(self, node, old_q, new_q, cos_after, ts=None):
        """R-13 п. 4: зміна кількості увімкнених ступенів компенсації секції."""
        diff = int(new_q) - int(old_q)
        if not diff:
            return self.browse()
        n = abs(diff) // 50
        if n == 1:
            action = "увімкнено ще один ступінь 50 квар" if diff > 0 else "вимкнено ступінь 50 квар"
        else:
            word = "ступені" if n in (2, 3, 4) else "ступенів"
            action = "%s %d %s (%d квар)" % ("увімкнено" if diff > 0 else "вимкнено", n, word, abs(diff))
        text = "Компенсація секції %d: %s, cos φ %s." % (node.section, action, fmt_num(cos_after, 2))
        return self._f3d_log("info", "pfc", node.code, text, ts=ts, node=node, dedup_min=10)
