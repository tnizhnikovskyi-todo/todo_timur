"""W1-A: M-26 `td.energy.advice` — слот рекомендацій (R-32, API-11, FR-32). Правил у W1 немає: реєстр і контракт."""

import logging
from datetime import timedelta

from odoo import _, api, fields, models, tools
from odoo.exceptions import AccessError

from ..tools import bus, dates
from ..tools.dates import param_float

_logger = logging.getLogger(__name__)

RULE_PREFIX = "_td_advice_rule_"
OPEN_STATES = ("open", "snoozed")
ACTION_KINDS = ("link", "ticket", "control")


class TdEnergyAdvice(models.Model):
    _name = "td.energy.advice"
    _description = "Енергетика: рекомендація"
    _order = "level desc, create_date desc"

    code = fields.Char(string="Код", size=32, required=True, index=True)
    dedup_key = fields.Char(string="Ключ дедуплікації", size=64, index=True)
    kind = fields.Selection([("rule", "Правило"), ("manual", "Вручну")], string="Джерело", default="manual")
    title = fields.Char(string="Заголовок", size=128, required=True)
    text = fields.Text(string="Текст", required=True)
    level = fields.Selection([("info", "Інформація"), ("warn", "Увага")], string="Рівень", default="warn")
    node_id = fields.Many2one("td.energy.node", string="Вузол", ondelete="set null")
    state = fields.Selection(
        [
            ("open", "Відкрита"),
            ("snoozed", "Відкладена"),
            ("done", "Виконана"),
            ("dismissed", "Відхилена"),
            ("expired", "Прострочена"),
        ],
        string="Стан",
        default="open",
        index=True,
    )
    snooze_until = fields.Datetime(string="Відкладена до")
    expires_at = fields.Datetime(string="Діє до")
    actions = fields.Json(string="Дії", default=list)
    result_note = fields.Char(string="Результат", size=256)
    resolved_at = fields.Datetime(string="Закрито", readonly=True)
    resolved_by = fields.Many2one("res.users", string="Закрив", readonly=True)

    def init(self):
        self.env.cr.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS td_energy_advice_dedup_open_uniq ON td_energy_advice (dedup_key) "
            "WHERE state IN ('open', 'snoozed') AND dedup_key IS NOT NULL"
        )
        tools.sql.create_index(self.env.cr, "td_energy_advice_state_idx", self._table, ["state"])

    # --- права ----------------------------------------------------------------------------------------
    def _td_check_energetic(self):
        if not self.env.user.has_group("td_energy.group_td_energy_manager"):
            raise AccessError(_("Керувати рекомендаціями може лише енергетик."))

    @api.model
    @tools.ormcache()
    def _td_control_available(self):
        """C-32: `true`, коли встановлено `td_energy_control` (W2) — кнопки `kind='control'` дозволені."""
        return bool(
            self.env["ir.module.module"]
            .sudo()
            .search_count([("name", "=", "td_energy_control"), ("state", "=", "installed")])
        )

    # --- API-11 ---------------------------------------------------------------------------------------
    @api.model
    def get_open(self):
        """Найсерйозніша відкрита (або відкладена, чий час минув) рекомендація (формат `advice` API-05) чи False."""
        now = dates.now_utc(self.env)
        Advice = self.sudo()
        woken = Advice.search([("state", "=", "snoozed"), ("snooze_until", "<=", now)])
        if woken:
            woken.write({"state": "open", "snooze_until": False})
        rec = Advice.search([("state", "=", "open")], limit=1)
        if not rec:
            return False
        control = self._td_control_available()
        actions = [
            {
                "code": a.get("code"),
                "label": a.get("label"),
                "kind": a.get("kind"),
                "class": a.get("class"),
                "params": a.get("params") or {},
                "enabled": a.get("kind") != "control" or control,
            }
            for a in (rec.actions or [])
        ]
        return {
            "id": rec.id,
            "code": rec.code,
            "title": rec.title,
            "text": rec.text,
            "level": rec.level,
            "node_code": rec.node_id.code or None,
            "actions": actions,
        }

    def action_snooze(self, minutes=None):
        self._td_check_energetic()
        minutes = int(minutes or param_float(self.env, "advice_snooze_min", 30))
        until = dates.now_utc(self.env) + timedelta(minutes=minutes)
        self.sudo().write({"state": "snoozed", "snooze_until": until})
        bus.tick(self.env, "advice")
        return True

    def action_dismiss(self):
        self._td_check_energetic()
        self.sudo().write({"state": "dismissed", "resolved_at": dates.now_utc(self.env), "resolved_by": self.env.uid})
        bus.tick(self.env, "advice")
        return True

    def action_done(self, note=None):
        self._td_check_energetic()
        self.sudo().write(
            {
                "state": "done",
                "result_note": (note or "")[:256],
                "resolved_at": dates.now_utc(self.env),
                "resolved_by": self.env.uid,
            }
        )
        bus.tick(self.env, "advice")
        return True

    # --- R-32: реєстр правил ---------------------------------------------------------------------------
    @api.model
    def _td_rule_methods(self):
        return sorted(name for name in dir(self) if name.startswith(RULE_PREFIX) and callable(getattr(self, name)))

    @api.model
    def _cron_advice(self):
        """Збирає `_td_advice_rule_*(now)`; створює відсутні, закриває ті, що правила більше не повертають."""
        if not dates.param_bool(self.env, "read_enabled"):
            return False
        try:
            with self.env.cr.savepoint():
                self._td_run_rules(dates.now_utc(self.env))
        except Exception:
            _logger.exception("td_energy: крон рекомендацій")
        return True

    @api.model
    def _td_run_rules(self, now):
        Advice = self.sudo()
        returned, created = set(), 0
        for name in self._td_rule_methods():
            try:
                items = getattr(Advice, name)(now) or []
            except Exception:
                _logger.exception("td_energy: правило рекомендацій %s", name)
                continue
            for item in items:
                key = item.get("dedup_key")
                if key:
                    returned.add(key)
                if key and Advice.search_count([("dedup_key", "=", key), ("state", "in", OPEN_STATES)]):
                    continue
                node = (
                    self.env["td.energy.node"].search([("code", "=", item.get("node_code"))], limit=1)
                    if item.get("node_code")
                    else self.env["td.energy.node"]
                )
                minutes = item.get("expires_in_min")
                Advice.create(
                    {
                        "code": item["code"],
                        "dedup_key": key or False,
                        "kind": "rule",
                        "title": item["title"],
                        "text": item["text"],
                        "level": item.get("level") or "warn",
                        "node_id": node.id,
                        "actions": item.get("actions") or [],
                        "expires_at": now + timedelta(minutes=minutes) if minutes else False,
                    }
                )
                created += 1
        stale = Advice.search(
            [("kind", "=", "rule"), ("state", "in", OPEN_STATES), ("dedup_key", "not in", list(returned))]
        )
        timed = Advice.search([("state", "in", OPEN_STATES), ("expires_at", "!=", False), ("expires_at", "<", now)])
        (stale | timed).write({"state": "expired", "resolved_at": now})
        if created or stale or timed:
            bus.tick(self.env, "advice")
        return created

    @api.model
    def _td_demo_seed(self):
        """R-36 (`with_advice`): демо-рекомендація EXPORT-T2 за макетом (дії керування приховані без W2)."""
        Advice = self.sudo()
        if Advice.search_count([("dedup_key", "=", "EXPORT-T2"), ("state", "in", OPEN_STATES)]):
            return Advice.browse()
        export = self.env["td.signal"].sudo().search([("code", "=", "infra/totals/export_kw")], limit=1)
        kw = int(round(export.last_value)) if export and export.last_value else 26
        node = self.env["td.energy.node"].search([("code", "=", "T2")], limit=1)
        return Advice.create(
            {
                "code": "EXPORT-T2",
                "dedup_key": "EXPORT-T2",
                "kind": "manual",
                "title": "СЕС віддає %d кВт у мережу через T2." % kw,
                "text": "Надлишок генерації йде в мережу. Можна зарядити накопичувач або з'єднати секції, щоб "
                "споживати власну енергію.",
                "level": "warn",
                "node_id": node.id,
                "expires_at": dates.now_utc(self.env) + timedelta(hours=4),
                "actions": [
                    {
                        "code": "open_event",
                        "label": "Відкрити подію",
                        "kind": "link",
                        "class": None,
                        "params": {"xmlid": "td_energy.action_td_energy_event", "res_id": None},
                    },
                    {
                        "code": "charge_bess",
                        "label": "Зарядити BESS 50 кВт",
                        "kind": "control",
                        "class": "A",
                        "params": {"command_kind": "bess_charge"},
                    },
                    {
                        "code": "qs_on",
                        "label": "Увімкнути QS…",
                        "kind": "control",
                        "class": "B",
                        "params": {"command_kind": "qs_close"},
                    },
                ],
            }
        )
