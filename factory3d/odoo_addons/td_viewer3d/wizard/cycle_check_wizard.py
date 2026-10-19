from markupsafe import Markup, escape

from odoo import fields, models

from ..tools.cycle_check import check
from ..tools.payload import PayloadBuilder


class F3dViewerCycleCheck(models.TransientModel):
    _name = "td.viewer.cycle.check"
    _description = "3D: перевірка циклу"

    result_html = fields.Html(readonly=True, sanitize=False)
    issue_count = fields.Integer(readonly=True)
    state = fields.Selection(
        [("draft", "—"), ("ok", "Цикл замкнений"), ("issues", "Є проблеми")], default="draft", readonly=True
    )
    payload_user_id = fields.Many2one("res.users", string="Дані від імені", default=lambda s: s.env.user)
    ran_at = fields.Datetime(readonly=True)
    first_ref = fields.Char(readonly=True)

    def _form(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
        }

    def action_run(self):
        self.ensure_one()
        user = self.env.user
        if self.payload_user_id and self.env.user.has_group("td_factory3d.group_td_admin"):
            user = self.payload_user_id
        payload = PayloadBuilder(self.env(user=user.id), full=True).build()
        issues = check(payload)
        names = {
            x["name"]
            for key in ("pickings", "productions", "quality_checks")
            for x in payload.get(key) or []
            if isinstance(x, dict) and x.get("name")
        }
        items, first = [], False
        for text in issues:
            head = text.split(":", 1)[0].strip()
            attr = "data-f3d-open" if head in names else "data-f3d-code"
            first = first or (attr, head)
            items.append(
                Markup('<li><a href="#" {}="{}">{}</a>{}</li>').format(
                    Markup(attr), head, head, escape(text[len(head) :])
                )
            )
        self.write(
            {
                "result_html": Markup("<ul>{}</ul>").format(Markup("").join(items)) if items else False,
                "issue_count": len(issues),
                "state": "issues" if issues else "ok",
                "ran_at": fields.Datetime.now(),
                "first_ref": f"{first[0]}:{first[1]}" if first else False,
            }
        )
        return self._form()

    def action_show_first(self):
        """Відкрити переглядач на першому проблемному об'єкті."""
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("td_viewer3d.action_td_viewer")
        if self.first_ref:
            attr, value = self.first_ref.split(":", 1)
            action["params"] = {"open" if attr == "data-f3d-open" else "code": value}
        return action
