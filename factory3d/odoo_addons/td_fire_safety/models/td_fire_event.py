import uuid
from datetime import timedelta, timezone

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from psycopg2 import IntegrityError

from ..tools.dates import local
from ..tools.etypes import ETYPE_TABLE, ETYPES, KINDS
from ..tools.sanitize import clean_text

LINKS = ("panel", "loop", "zone", "device", "system", "drill", "signal", "request")
EXTRA = ("message_text", "raw_from", "raw_to", "note", "in_drill", "user_id", "scene_code")
GROUP_SCENE = {"mcp": "FA-MCP", "sounder": "FA-SND", "flame": "FA-FLAME", "spark_detector": "SPARK-1",
               "spark_nozzle": "SPARK-1", "smoke_vent": "SMOKE-VENTS"}
LEVEL_TO_PAYLOAD = {"info": "info", "warn": "warn", "alarm": "bad"}
WRITABLE = {"ack", "ack_user_id", "ack_ts", "note"}


class F3dFireEvent(models.Model):
    _name = "td.fire.event"
    _description = "Пожежна безпека: подія журналу"
    _order = "ts desc, id desc"
    _rec_name = "text"
    _log_access = False

    ts = fields.Datetime(string="Час", required=True, index=True, default=fields.Datetime.now)
    etype = fields.Selection(ETYPES, string="Тип", required=True, index=True)
    kind = fields.Selection(KINDS, compute="_compute_kind", store=True, index=True)
    level = fields.Selection(
        [("info", "Інформація"), ("warn", "Попередження"), ("alarm", "Тривога")], required=True, index=True)
    object_code = fields.Char(string="Об'єкт", size=32, required=True, index=True, default="FACP-1")
    scene_code = fields.Char(string="Код у 3D", size=32)
    panel_id = fields.Many2one("td.fire.panel", ondelete="set null", index=True)
    loop_id = fields.Many2one("td.fire.loop", ondelete="set null")
    zone_id = fields.Many2one("td.fire.zone", ondelete="set null", index=True)
    device_id = fields.Many2one("td.fire.device", ondelete="set null", index=True)
    system_id = fields.Many2one("td.fire.system", ondelete="set null")
    drill_id = fields.Many2one("td.fire.drill", ondelete="set null", index=True)
    signal_id = fields.Many2one("td.signal", ondelete="set null")
    request_id = fields.Many2one("maintenance.request", string="Заявка ТО", ondelete="set null")
    raw_from = fields.Char(string="Було", size=32)
    raw_to = fields.Char(string="Стало", size=32)
    text = fields.Char(string="Подія", size=500, required=True)
    message_text = fields.Char(string="Текст приладу", size=500)
    source = fields.Selection(
        [("signal", "Сигнал"), ("bacnet", "Повідомлення BACnet"), ("cron", "Звірка"), ("drill", "Навчання"),
         ("manual", "Вручну"), ("demo", "Демо"), ("system", "Модуль")], required=True, default="signal")
    dedup_key = fields.Char(size=96, required=True, index=True, copy=False)
    in_drill = fields.Boolean(string="Під час навчання")
    ack_required = fields.Boolean(compute="_compute_ack_required")
    ack = fields.Boolean(string="Підтверджено", default=False, index=True)
    ack_user_id = fields.Many2one("res.users", string="Підтвердив", readonly=True)
    ack_ts = fields.Datetime(string="Підтверджено о", readonly=True)
    note = fields.Text(string="Коментар")
    user_id = fields.Many2one("res.users", string="Автор", default=lambda self: self.env.user)

    _f3d_fire_event_dedup_uniq = models.Constraint("UNIQUE(dedup_key)", "Подія з таким ключем уже записана.")
    _f3d_fire_event_ts_kind_idx = models.Index("(ts, kind)")
    _f3d_fire_event_object_ts_idx = models.Index("(object_code, ts)")

    # --- compute ------------------------------------------------------------------------------------------
    @api.depends("etype")
    def _compute_kind(self):
        for rec in self:
            rec.kind = ETYPE_TABLE[rec.etype][1] if rec.etype in ETYPE_TABLE else "info"

    def _compute_ack_required(self):
        required = self.env["td.fire.panel"]._get_param("event_ack_required", True)
        for rec in self:
            rec.ack_required = rec.level == "alarm" and required

    # --- службовий запис ----------------------------------------------------------------------------------
    @api.model
    def _default_key(self, etype, object_code, ts):
        return "%s:%s:%d" % (etype, object_code, int(ts.replace(tzinfo=timezone.utc).timestamp()) // 2)

    @api.model
    def _scene_code(self, vals):
        env = self.env
        device, zone, system = (env["td.fire.device"].browse(vals.get("device_id")),
                                env["td.fire.zone"].browse(vals.get("zone_id")),
                                env["td.fire.system"].browse(vals.get("system_id")))
        if device:
            if device.type in GROUP_SCENE:
                return GROUP_SCENE[device.type]
            return device.zone_id.code or device.address
        if zone:
            return zone.code
        if system:
            return system.code
        if vals.get("drill_id"):
            drill = env["td.fire.drill"].browse(vals["drill_id"])
            zone = getattr(drill, "zone_id", False)
            return zone.code if zone and "code" in zone._fields else False
        if vals.get("loop_id") or vals.get("panel_id"):
            panel = env["td.fire.panel"].browse(vals.get("panel_id")) or env["td.fire.loop"].browse(
                vals["loop_id"]).panel_id
            return panel.code
        return False

    @api.model
    def _log(self, etype, object_code, ts, text, level=None, source="signal", key=None, **links):
        """Записати подію з дедуплікацією (2-секундний кошик, A-04); службовий метод (sudo)."""
        self = self.sudo()
        level = level or ETYPE_TABLE[etype][2]
        ts = fields.Datetime.to_datetime(ts)
        key = key or self._default_key(etype, object_code, ts)
        vals = {}
        for name in LINKS:
            value = links.pop(name + "_id", None)
            if value is None:
                value = links.pop(name, None)
            vals[name + "_id"] = value.id if isinstance(value, models.BaseModel) else (value or False)
        for name in EXTRA:
            if name in links:
                value = links.pop(name)
                vals[name] = value.id if isinstance(value, models.BaseModel) else value
        if links:
            raise TypeError("_log: невідомі аргументи %s" % sorted(links))
        existing = self.search([("dedup_key", "=", key)], limit=1)
        if existing:
            fill = {name: vals[name] for name in ("message_text", "request_id")
                    if vals.get(name) and not existing[name]}
            if fill:
                existing.write(fill)
            return existing
        vals["in_drill"] = vals.get("in_drill") or (
            "td.fire.drill" in self.env and bool(self.env["td.fire.drill"].search_count(
                [("state", "=", "running")])))
        vals["scene_code"] = vals.get("scene_code") or self._scene_code(vals)
        if vals.get("message_text"):
            vals["message_text"] = clean_text(vals["message_text"], 500)
        vals.setdefault("user_id", self.env.ref("base.user_root").id)
        vals.update({"etype": etype, "level": level, "object_code": object_code, "ts": ts,
                     "text": clean_text(text, 500) or etype, "source": source, "dedup_key": key})
        try:
            with self.env.cr.savepoint():
                return self.create(vals)
        except IntegrityError:
            return self.search([("dedup_key", "=", key)], limit=1)

    # --- права --------------------------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            if not self.env.user.has_group("td_fire_safety.group_td_fire_drill"):
                raise AccessError("Користувач може додати лише коментар до журналу (тип «Коментар»).")
            limit = fields.Datetime.now() + timedelta(seconds=60)
            for vals in vals_list:
                if vals.get("etype") == "manual":
                    vals.setdefault("level", "info")
                    vals.setdefault("source", "manual")
                ts = fields.Datetime.to_datetime(vals.get("ts")) or fields.Datetime.now()
                if (vals.get("etype") != "manual" or vals.get("level") != "info"
                        or vals.get("source") != "manual" or ts > limit):
                    raise AccessError("Користувач може додати лише коментар до журналу (тип «Коментар»).")
        for vals in vals_list:
            if vals.get("etype") == "manual" and not vals.get("dedup_key"):
                vals["dedup_key"] = "manual:%s:%s" % (uuid.uuid4().hex, self.env.uid)
            for name, size in (("text", 500), ("message_text", 500)):
                if vals.get(name):
                    vals[name] = clean_text(vals[name], size)
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su and set(vals) - WRITABLE:
            raise AccessError("Журнал подій змінювати не можна; дозволено лише підтвердження й коментар.")
        if vals.get("ack") is False and any(self.mapped("ack")):
            raise UserError("Підтвердження не знімається.")
        return super().write(vals)

    def unlink(self):
        if not (self.env.context.get("f3d_fire_allow_unlink") and self.env.su):
            raise UserError("Журнал подій не видаляється (A-12).")
        return super().unlink()

    # --- дії ----------------------------------------------------------------------------------------------
    def action_ack(self):
        todo = self.filtered(lambda e: not e.ack)
        if todo:
            todo.write({"ack": True, "ack_user_id": self.env.uid, "ack_ts": fields.Datetime.now()})
        return True

    def action_open_object(self):
        self.ensure_one()
        for name in ("device_id", "zone_id", "system_id", "drill_id", "loop_id", "panel_id"):
            target = self[name]
            if target:
                return {"type": "ir.actions.act_window", "res_model": target._name, "res_id": target.id,
                        "view_mode": "form", "target": "current"}
        raise UserError("Подія не прив'язана до жодного об'єкта.")

    def action_f3d_show(self):
        self.ensure_one()
        for name in ("zone_id", "device_id", "system_id", "panel_id"):
            target = self[name]
            if target:
                return target.action_f3d_show()
        raise UserError("Подія не прив'язана до об'єкта сцени.")

    def _payload_item(self):
        self.ensure_one()
        return {"time": local(self.ts), "level": LEVEL_TO_PAYLOAD[self.level],
                "code": self.scene_code or self.object_code, "text": self.text}
