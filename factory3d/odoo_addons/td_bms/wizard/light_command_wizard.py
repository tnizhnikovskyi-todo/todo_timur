from odoo import api, fields, models
from odoo.exceptions import ValidationError

from . import command_common as common


class F3dBmsLightCommandWizard(models.TransientModel):
    """M-09a: сцена або рівень для груп освітлення (FR-18, R-25)."""

    _name = "f3d.bms.light.command.wizard"
    _description = "Будівля: команда освітленню"

    group_ids = fields.Many2many("f3d.bms.light.group", string="Групи", required=True)
    action = fields.Selection(
        [("scene", "Викликати сцену"), ("level", "Встановити рівень")], string="Дія", required=True, default="scene"
    )
    scene_id = fields.Many2one("f3d.bms.light.scene", string="Сцена")
    level_pct = fields.Integer(string="Рівень, %")
    fade_s = fields.Float(string="Час переходу, с", digits=(6, 1), default=2.0)
    expires_min = fields.Integer(string="Дійсна, хв", default=10)
    note = fields.Char(string="Примітка", size=256)

    @api.model
    def _f3d_bms_check_operator(self):
        common.check_operator(self.env)

    def _validate(self):
        self.ensure_one()
        if self.action == "scene" and not self.scene_id:
            raise ValidationError("Оберіть сцену.")
        if self.action == "level" and not 0 <= self.level_pct <= 100:
            raise ValidationError("Рівень має бути в межах 0…100 %.")
        if not 0 <= self.fade_s <= 90:
            raise ValidationError("Час переходу має бути в межах 0…90 с.")
        if not 1 <= self.expires_min <= 60:
            raise ValidationError("Строк дії команди — 1…60 хв.")

    def action_apply(self):
        self.ensure_one()
        self._f3d_bms_check_operator()
        common.check_switches(self.env)
        field = "scene_signal_id" if self.action == "scene" else "level_signal_id"
        groups = self.group_ids.sudo()
        common.check_signals([(g.code, g[field]) for g in groups])
        self._validate()
        fade = "fade=%.1f" % self.fade_s
        value = float(self.scene_id.number if self.action == "scene" else self.level_pct)
        label = ("сцена %s" % self.scene_id.number) if self.action == "scene" else ("рівень %d %%" % self.level_pct)
        return common.send(self.env, [(g, g[field], value, fade) for g in groups], self.expires_min, self.note, label)
