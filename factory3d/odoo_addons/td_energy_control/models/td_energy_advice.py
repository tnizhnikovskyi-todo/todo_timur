"""M-36: правила рекомендацій `_td_advice_rule_*` (R-55) і банер «Виконано» (`get_open`, `_td_on_action_done`)."""

import logging
from datetime import timedelta

from odoo import api, models
from odoo.exceptions import AccessError

from odoo.addons.td_energy.tools import dates
from odoo.addons.td_energy.tools.tariff import to_local

from .. import tools
from ..tools import kinds

_logger = logging.getLogger(__name__)


class TdEnergyAdvice(models.Model):
    _inherit = "td.energy.advice"

    # --- допоміжне -----------------------------------------------------------------------------------------------
    @api.model
    def _td_signal(self, code):
        return self.env["td.signal"].sudo().search([("code", "=", code)], limit=1)

    @api.model
    def _td_fresh_value(self, code, now, max_age_s=120):
        """Свіже `last_value` (status ≠ stale, вік ≤ max_age_s) або None."""
        sig = self._td_signal(code)
        if not sig or sig.status == "stale" or not sig.last_ts:
            return None
        if (now - sig.last_ts).total_seconds() > max(3 * (sig.period_s or 0), max_age_s):
            return None
        return sig.last_value

    @api.model
    def _td_readings(self, code, since):
        sig = self._td_signal(code)
        if not sig:
            return []
        rows = self.env["td.reading"].sudo().search_read([("signal_id", "=", sig.id), ("ts", ">=", since)], ["value"])
        return [r["value"] for r in rows]

    @api.model
    def _td_scenario(self, code):
        sc = self.env["td.energy.scenario"].sudo().search([("code", "=", code)], limit=1)
        return (bool(sc.enabled), sc._td_params()) if sc else (False, dict(kinds.PARAM_DEFAULTS[code]))

    # --- EXPORT-T2 ------------------------------------------------------------------------------------------------
    @api.model
    def _td_advice_rule_export_t2(self, now):
        env = self.env
        _enabled, selfp = self._td_scenario("self")
        minutes = tools.cparam_int(env, "export_advice_min", 5)
        series = self._td_readings("infra/totals/export_kw", now - timedelta(minutes=minutes))
        export = self._td_fresh_value("infra/totals/export_kw", now)
        if not series and export is not None:
            series = [export]
        if not series or min(series) <= selfp["export_max_kw"]:
            return []
        qs = self._td_signal(kinds.SIGNALS["qs_state"])
        if not qs or (qs.last_text or "") != "open":
            return []
        pv = self._td_fresh_value("infra/totals/pv_now", now)
        if pv is None or pv < 1:
            return []
        latest = export if export is not None else series[-1]
        local = to_local(now)
        minutes_now = local.hour * 60 + local.minute
        until = next((h for h in (16, 23) if h * 60 > minutes_now + 30), None)
        soc = self._td_fresh_value("infra/totals/bess_soc", now)
        actions = [
            {
                "code": "open_event",
                "label": "Відкрити подію",
                "kind": "link",
                "class": None,
                "params": {"xmlid": "td_energy.action_td_energy_event", "res_id": None},
            }
        ]
        kwh_text = ""
        if until is not None and not (soc is not None and soc >= 95):
            hours = (until * 60 - minutes_now) / 60.0
            kwh = int(round(50 * hours / 10.0)) * 10
            kwh_text = "Заряд BESS 50 кВт збереже до %02d:00 приблизно %d кВт·год на старт другої зміни." % (until, kwh)
            actions.append(
                {
                    "code": "charge_bess",
                    "label": "Зарядити BESS 50 кВт",
                    "kind": "control",
                    "class": "A",
                    "params": {
                        "command_kind": "bess_charge",
                        "power_kw": 50,
                        "until": "%02d:00" % until,
                        "soc_limit_pct": 95,
                    },
                }
            )
        actions.append(
            {
                "code": "qs_on",
                "label": "Увімкнути QS…",
                "kind": "control",
                "class": "B",
                "params": {"command_kind": "qs_close"},
            }
        )
        text = "Секційний вимикач QS вимкнено, і генерація СЕС більша за навантаження секції 2."
        return [
            {
                "code": "EXPORT-T2",
                "dedup_key": "EXPORT-T2",
                "level": "info",
                "node_code": "T2",
                "expires_in_min": 60,
                "title": "СЕС віддає %d кВт у мережу через T2." % round(latest),
                "text": (text + " " + kwh_text).strip(),
                "actions": actions,
            }
        ]

    # --- PEAK-RISK --------------------------------------------------------------------------------------------------
    @api.model
    def _td_advice_rule_peak_risk(self, now):
        enabled, p = self._td_scenario("peak")
        if enabled:
            return []
        threshold = p["limit_kw"] - p["activate_margin_kw"]
        series = self._td_readings("infra/totals/grid_kw", now - timedelta(minutes=2))
        if len(series) < 2 or min(series) < threshold:
            return []
        grid = self._td_fresh_value("infra/totals/grid_kw", now)
        return [
            {
                "code": "PEAK-RISK",
                "dedup_key": "PEAK-RISK",
                "level": "warn",
                "node_code": None,
                "expires_in_min": 30,
                "title": "Імпорт наближається до уставки",
                "text": "Імпорт %s кВт наближається до уставки %s кВт. Увімкніть «Зрізання піку» або розрядіть BESS."
                % (kinds.fmt(round(grid if grid is not None else series[-1])), kinds.fmt(p["limit_kw"])),
                "actions": [
                    {
                        "code": "enable_peak",
                        "label": "Увімкнути «Зрізання піку»",
                        "kind": "control",
                        "class": "B",
                        "params": {"command_kind": "scenario_toggle", "scenario": "peak", "enabled": True},
                    },
                    {
                        "code": "discharge_bess",
                        "label": "Розрядити BESS 100 кВт",
                        "kind": "control",
                        "class": "B",
                        "params": {"command_kind": "bess_discharge", "power_kw": 100, "duration_min": 60},
                    },
                ],
            }
        ]

    # --- CHP-PRICE --------------------------------------------------------------------------------------------------
    @api.model
    def _td_advice_rule_chp_price(self, now):
        env = self.env
        enabled, p = self._td_scenario("chp")
        if enabled:
            return []
        _zone, price = env["td.energy.tariff"].sudo()._td_price_at(now)
        cost = p["gas_price_uah_m3"] * p["gas_m3_per_kwh"]
        if not price or price - cost < 2 * p["price_margin_uah_kwh"]:
            return []
        state = self._td_fresh_value("infra/chp/state", now)
        permit = self._td_fresh_value(kinds.SIGNALS["chp_permit"], now)
        gas = self._td_fresh_value(kinds.SIGNALS["chp_gas"], now)
        lock = env["td.energy.interlock"].sudo().search([("code", "=", "chp_gas_pressure")], limit=1)
        min_bar = (lock.params or {}).get("min_bar", 1.5) if lock else 1.5
        if state is None or int(state) != 0 or permit != 1 or gas is None or gas < min_bar:
            return []
        return [
            {
                "code": "CHP-PRICE",
                "dedup_key": "CHP-PRICE",
                "level": "info",
                "node_code": "CHP",
                "expires_in_min": 60,
                "title": "КГУ вигідно запустити",
                "text": "Газ дешевший за мережу: КГУ вигідно запустити (%s ₴ проти %s ₴ за кВт·год)."
                % (kinds.fmt(price, 2), kinds.fmt(cost, 2)),
                "actions": [
                    {
                        "code": "enable_chp",
                        "label": "Увімкнути сценарій КГУ",
                        "kind": "control",
                        "class": "B",
                        "params": {"command_kind": "scenario_toggle", "scenario": "chp", "enabled": True},
                    },
                    {
                        "code": "chp_start",
                        "label": "Пуск КГУ…",
                        "kind": "control",
                        "class": "B",
                        "params": {"command_kind": "chp_start"},
                    },
                ],
            }
        ]

    # --- банер «Виконано» (R-55 п.4) ---------------------------------------------------------------------------------
    @api.model
    def get_open(self):
        res = super().get_open()
        if res:
            return res
        return self._td_done_banner() or False

    @api.model
    def _td_done_banner(self):
        env = self.env
        now = dates.now_utc(env)
        window = tools.cparam_int(env, "undo_window_min", 15)
        acts = (
            env["td.energy.action"]
            .sudo()
            .search(
                [
                    ("origin", "=", "advice"),
                    ("state", "=", "done"),
                    ("finished_at", ">=", now - timedelta(minutes=window)),
                    ("undone_by_id", "=", False),
                ],
                order="finished_at desc, id desc",
            )
        )
        act = next((a for a in acts if a.undo_available), None)
        if not act:
            return None
        title, text = self._td_banner_text(act)
        undo_kind = act.kind_id.undo_kind_id
        return {
            "id": act.advice_id.id or act.id,
            "code": act.advice_id.code or act.kind_code,
            "title": title,
            "text": text,
            "level": "info",
            "state": "done",
            "node_code": act.advice_id.node_id.code or None,
            "actions": [
                {
                    "code": "undo",
                    "label": "Скасувати",
                    "kind": "control",
                    "class": undo_kind.cls,
                    "params": {"command_kind": "undo", "action_id": act.id},
                    "enabled": True,
                }
            ],
        }

    @api.model
    def _td_banner_text(self, act):
        p = act.params or {}
        if act.kind_code == "bess_charge":
            local = to_local(act.finished_at)
            until = p.get("until") or "16:00"
            hh, mm = (int(x) for x in until.split(":"))
            hours = max(0.0, (hh * 60 + mm - (local.hour * 60 + local.minute)) / 60.0)
            kwh = int(round(p.get("power_kw", 50) * hours / 10.0)) * 10
            return (
                "BESS заряджається %s кВт." % kinds.fmt(p.get("power_kw", 50)),
                "Експорт через T2 усунено, до %s накопичиться ≈ %d кВт·год." % (until, kwh),
            )
        if act.kind_code == "qs_close":
            return "QS увімкнено.", "Секції працюють разом, генерація СЕС іде на навантаження заводу."
        return "Виконано: %s" % (act.summary or act.kind_code), act.result_text or ""

    def _td_on_action_done(self, action):
        """R-55 п.4: виконана дія рекомендації → `action_done(note=result_text)` від імені того, хто підтвердив."""
        for rec in self:
            user = action.confirmed_by or action.prepared_by
            note = action.result_text or "виконано"
            try:
                rec.with_user(user).action_done(note=note)
            except AccessError:
                rec.sudo().write({"state": "done", "result_note": note[:256], "resolved_at": dates.now_utc(self.env)})
