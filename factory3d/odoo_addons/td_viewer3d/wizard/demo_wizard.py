import json
import logging
import time
from collections import OrderedDict

from odoo import api, fields, models
from odoo.modules import module
from odoo.exceptions import UserError

from . import demo_steps

_logger = logging.getLogger(__name__)

PREFIX = "td.viewer."
LOG_LINES = 500
STALE_S = 2100  # крон ≤ 30 хв
LABELS = OrderedDict(
    [
        ("modules", "Модулі"),
        ("settings", "Налаштування складу/виробництва"),
        ("base", "Компанія, валюта, товари, партнери, одиниці"),
        ("views", "Поля ворота/фура на формі переміщення"),
        ("calendar", "Графік «Зміна 1 (07:00–15:30)»"),
        ("locations", "689 місць зі штрихкодом = код сцени"),
        ("workcenters", "35 робочих центрів"),
        ("people", "35 співробітників"),
        ("purchase", "13 закупівель і приймання"),
        ("sale", "8 замовлень клієнтів і відвантаження"),
        ("internal", "Внутрішні переміщення (INT, PC, SFP)"),
        ("production", "32 МО"),
        ("boms", "27 специфікацій, 171 операція"),
        ("layout", "Групи локацій, маршрути складу"),
        ("lots", "131 партія"),
        ("stock", "Залишки (інвентаризація за квантами)"),
        ("routes", "Маршрути 2/3 кроки"),
        ("orderpoints", "167 правил поповнення"),
        ("children", "Дочірні МО фасадів"),
        ("fronts", "Етажерки фасадів"),
        ("mo_locations", "Місця компонентів МО"),
        ("consumption", "Спожиті компоненти виконаних операцій"),
        ("po_links", "Рядки закупівель ↔ правила"),
        ("docks", "14 воріт і батчі з доком і фурою"),
        ("wc_tags", "Дільниці робочих центрів"),
        ("losses", "73 простої за зміну"),
        ("quality", "Точки й перевірки контролю"),
        ("maintenance", "Команда, 6 заявок"),
        ("equipment", "210 одиниць обладнання з паспортами"),
        ("preventive", "Планове ТО"),
        ("iot_module", "Імпорт data-модуля імітації IoT"),
        ("signals", "196 сигналів імітації"),
        ("attendance", "Відмітки 35 людей"),
        ("carriers", "Перевізники"),
        ("finish", "Резерви, зупинка CNC-2, зсув нумерації"),
    ]
)
DISABLED_MSG = (
    "Заливка демо вимкнена на цій базі (td.viewer.demo_enabled). Увімкніть у Завод 3D → "
    "Налаштування → Налаштування переглядача лише на тестовому сервері."
)


class F3dDemoWizardStep(models.TransientModel):
    _name = "td.demo.wizard.step"
    _description = "3D: крок заливки демо"
    _order = "sequence, id"

    wizard_id = fields.Many2one("td.demo.wizard", ondelete="cascade", required=True)
    name = fields.Char("Ключ", readonly=True)
    label = fields.Char("Крок")
    sequence = fields.Integer(default=10)
    selected = fields.Boolean("Виконати", default=True)
    state = fields.Selection(
        [
            ("todo", "Очікує"),
            ("running", "Виконується"),
            ("done", "Виконано"),
            ("skipped", "Пропущено"),
            ("error", "Помилка"),
        ],
        default="todo",
    )
    duration_s = fields.Float("Секунд", digits=(8, 1))
    message = fields.Char("Повідомлення")

    @api.model_create_multi
    def create(self, vals_list):
        """Вебклієнт не шле readonly-поле name: ключ кроку відновлюється з назви (або за порядком)."""
        by_label = {v: k for k, v in LABELS.items()}
        keys = list(LABELS)
        for i, vals in enumerate(vals_list):
            if not vals.get("name"):
                seq = vals.get("sequence") or 0
                vals["name"] = by_label.get(vals.get("label")) or (
                    keys[seq // 10 - 1] if seq and 0 < seq // 10 <= len(keys) else keys[i % len(keys)]
                )
        return super().create(vals_list)


class F3dDemoWizard(models.TransientModel):
    _name = "td.demo.wizard"
    _description = "3D: заливка демо-даних"

    step_ids = fields.One2many("td.demo.wizard.step", "wizard_id", string="Кроки")
    state = fields.Selection(
        [
            ("draft", "Готово до запуску"),
            ("queued", "У черзі"),
            ("running", "Виконується"),
            ("done", "Виконано"),
            ("error", "Помилка"),
        ],
        default="draft",
        readonly=True,
    )
    enabled = fields.Boolean(compute="_compute_enabled")
    progress = fields.Integer(readonly=True)
    current_step = fields.Char(readonly=True)
    log = fields.Text(readonly=True)
    demo_clock = fields.Char(
        default=lambda s: s._param("demo_clock") or "2026-10-12 10:30",
        help="Демо-годинник: дата й час, до яких прив'язані документи",
    )
    cron_id = fields.Many2one("ir.cron", readonly=True, default=lambda s: s._cron())
    new_records = fields.Integer(readonly=True)

    # --- службове --------------------------------------------------------
    def _param(self, name):
        return self.env["ir.config_parameter"].sudo().get_param(PREFIX + name)

    def _set_param(self, name, value):
        self.env["ir.config_parameter"].sudo().set_param(PREFIX + name, value)

    def _cron(self):
        return self.env.ref("td_viewer3d.cron_td_demo", raise_if_not_found=False)

    def _load_state(self):
        try:
            return json.loads(self._param("demo_state") or "{}")
        except ValueError:
            return {}

    def _compute_enabled(self):
        enabled = self._param("demo_enabled") == "True"
        for rec in self:
            rec.enabled = enabled

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "step_ids" in fields_list:
            res["step_ids"] = [
                (0, 0, {"name": k, "label": v, "sequence": i * 10}) for i, (k, v) in enumerate(LABELS.items(), 1)
            ]
        return res

    def _form(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
        }

    # --- кнопки ----------------------------------------------------------
    def action_select_all(self):
        self.step_ids.write({"selected": True})
        return self._form()

    def action_select_none(self):
        self.step_ids.write({"selected": False})
        return self._form()

    def action_run(self):
        self.ensure_one()
        if not self.enabled:
            raise UserError(DISABLED_MSG)
        cron = self._cron()
        if not cron:
            raise UserError("Крон «3D: заливка демо» не знайдено.")
        st = self._load_state()
        fresh = time.time() - st.get("ts", 0) < STALE_S  # «завислий» running після збою не блокує вічно
        if cron.sudo().active and st.get("state") == "running" and fresh:
            raise UserError("Заливка вже виконується")
        steps = [s.name for s in self.step_ids.sorted("sequence") if s.selected and s.name in LABELS]
        if not steps:
            raise UserError("Оберіть хоча б один крок.")
        self._set_param("demo_clock", self.demo_clock or "2026-10-12 10:30")
        self._set_param("demo_queue", json.dumps({"wizard_id": self.id, "steps": steps}))
        self._set_param(
            "demo_state",
            json.dumps(
                {
                    "wizard_id": self.id,
                    "state": "queued",
                    "progress": 0,
                    "log": [],
                    "steps": {},
                    "new_records": 0,
                    "current_step": "",
                }
            ),
        )
        self.step_ids.write({"state": "todo", "duration_s": 0, "message": False})
        self.write(
            {
                "state": "queued",
                "progress": 0,
                "current_step": False,
                "log": False,
                "new_records": 0,
                "cron_id": cron.id,
            }
        )
        cron.sudo().write({"active": True, "nextcall": fields.Datetime.now()})
        cron.sudo()._trigger()
        return self._form()

    def action_refresh(self):
        self.ensure_one()
        st = self._load_state()
        if st.get("wizard_id") == self.id:
            self._apply(st)
        cron = self._cron()
        if cron and cron.sudo().active and st.get("state") in ("done", "error"):
            cron.sudo().active = False  # поза кроном: після завершення вимкнути
        return self._form()

    def _apply(self, st):
        """Перенести стан із параметра в запис майстра й рядки кроків."""
        vals = {
            "state": st.get("state", "draft"),
            "progress": st.get("progress", 0),
            "current_step": st.get("current_step") or False,
            "new_records": st.get("new_records", 0),
            "log": "\n".join(st.get("log", [])[-LOG_LINES:]) or False,
        }
        self.write(vals)
        for step in self.step_ids:
            s = (st.get("steps") or {}).get(step.name)
            if s:
                step.write(s)

    # --- крон ------------------------------------------------------------
    def _cron_run(self):
        params = self.env["ir.config_parameter"].sudo()
        try:
            queue = json.loads(params.get_param(PREFIX + "demo_queue") or "{}")
        except ValueError:
            queue = {}
        names = queue.get("steps") or []
        if not names:  # крон активний, а роботи немає (повторний виклик за розкладом) — просто вийти
            return
        st = {
            "wizard_id": queue.get("wizard_id"),
            "state": "running",
            "progress": 0,
            "log": [],
            "steps": {},
            "new_records": 0,
            "current_step": "",
        }
        wiz = self.browse(queue.get("wizard_id") or 0).exists()

        def save():
            st["ts"] = time.time()
            params.set_param(PREFIX + "demo_state", json.dumps(st, ensure_ascii=False))
            if wiz:
                wiz._apply(st)
            if not module.current_test:  # у тестах commit заборонений
                self.env.cr.commit()

        def say(msg):
            st["log"] = (st["log"] + [str(msg)])[-LOG_LINES:]

        runner = demo_steps.Runner(self.env, log=say)
        save()
        for k, name in enumerate(names, 1):
            st["current_step"] = LABELS.get(name, name)
            st["steps"][name] = {"state": "running", "message": False}
            say(f"[{k}/{len(names)}] {name}")
            save()
            t0 = time.monotonic()
            try:
                with self.env.cr.savepoint():
                    state, msg = runner.run(name)
            except Exception as e:  # noqa: BLE001 — будь-яка помилка кроку зупиняє заливку
                _logger.exception("demo step %s", name)
                self.env.invalidate_all()
                st["steps"][name] = {
                    "state": "error",
                    "duration_s": round(time.monotonic() - t0, 1),
                    "message": f"{type(e).__name__}: {e}"[:250],
                }
                say(f"ПОМИЛКА {name}: {type(e).__name__}: {e}")
                st["new_records"] = runner.n_new
                return self._finish(st, save, say, "error")
            st["steps"][name] = {"state": state, "duration_s": round(time.monotonic() - t0, 1), "message": msg}
            st["progress"] = round(k / len(names) * 100)
            st["new_records"] = runner.n_new
            save()
        return self._finish(st, save, say, "done")

    def _finish(self, st, save, say, state):
        st["state"] = state
        if state == "done":
            st["progress"] = 100
            st["current_step"] = ""
            say(self._cycle_check_line())
        self._set_param("demo_queue", "")  # крон лишається активним до «Оновити»: сам себе він вимкнути не може
        save()

    def _cycle_check_line(self):
        from ..tools.cycle_check import check
        from ..tools.payload import PayloadBuilder

        try:
            user = self.env.ref("td_viewer3d.user_kiosk")
            issues = check(PayloadBuilder(self.env(user=user.id), full=True).build())
        except Exception as e:  # noqa: BLE001
            _logger.exception("cycle_check після заливки")
            return f"cycle_check: помилка {type(e).__name__}: {e}"
        return "cycle_check: OK" if not issues else "cycle_check: " + "; ".join(issues)
