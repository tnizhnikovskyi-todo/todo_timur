import json
import logging

from datetime import timedelta

from markupsafe import Markup

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.modules.registry import Registry
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)

RESPONSE_LIMIT = 2000
DEDUP_SECONDS = 60
DEFAULT_MAX_HOPS = 6
HOPS_PARAM = "td.claude.max_hops_per_day"


class TdClaudeRequest(models.Model):
    _name = "td.claude.request"
    _description = "Запит до Claude (журнал і черга)"
    _order = "id desc"

    agent_id = fields.Many2one("td.claude.agent", string="Агент", required=True, ondelete="cascade", index=True)
    owner_id = fields.Many2one(related="agent_id.owner_id", store=True, index=True)
    agent_user_id = fields.Many2one(related="agent_id.agent_user_id", store=True, index=True)
    kind = fields.Selection(
        [
            ("mention", "Згадка"),
            ("assign", "Призначення"),
            ("stage", "Зміна стадії"),
            ("ping", "Перевірка"),
            ("manual", "Вручну"),
        ],
        string="Тип",
        required=True,
        default="manual",
    )
    res_model = fields.Char(string="Модель")
    res_id = fields.Integer(string="ID запису")
    record_name = fields.Char(string="Запис")
    message_id = fields.Many2one("mail.message", string="Повідомлення", ondelete="set null")
    payload = fields.Text(string="Payload")
    state = fields.Selection(
        [("pending", "Очікує"), ("sent", "Надіслано"), ("failed", "Помилка")],
        string="Стан",
        default="pending",
        required=True,
        index=True,
    )
    http_status = fields.Integer(string="HTTP-статус")
    response = fields.Text(string="Відповідь")
    session_url = fields.Char(string="Посилання на сесію")

    @api.depends("kind", "record_name")
    def _compute_display_name(self):
        labels = dict(self._fields["kind"].selection)
        for rec in self:
            rec.display_name = f"{labels.get(rec.kind, '')} · {rec.record_name or ''}".strip(" ·") or str(rec.id)

    # ------------------------------------------------------------------
    # Запуски: правила й запобіжники
    # ------------------------------------------------------------------
    @api.model
    def _td_max_hops(self):
        value = self.env["ir.config_parameter"].sudo().get_param(HOPS_PARAM)
        try:
            return int(value) if value else DEFAULT_MAX_HOPS
        except ValueError:
            return DEFAULT_MAX_HOPS

    @api.model
    def _td_hops_today(self, record):
        """Кількість запусків (крім ping) для запису за останню добу."""
        if not record:
            return 0
        return self.sudo().search_count(
            [
                ("res_model", "=", record._name),
                ("res_id", "=", record.id),
                ("kind", "!=", "ping"),
                ("create_date", ">=", fields.Datetime.now() - timedelta(days=1)),
            ]
        )

    @api.model
    def _td_recent_duplicate(self, agent, record):
        return self.sudo().search_count(
            [
                ("agent_id", "=", agent.id),
                ("res_model", "=", record._name),
                ("res_id", "=", record.id),
                ("kind", "!=", "ping"),
                ("state", "in", ("pending", "sent")),
                ("create_date", ">=", fields.Datetime.now() - timedelta(seconds=DEDUP_SECONDS)),
            ]
        )

    @api.model
    def _td_launch(self, agent, kind, record=None, message=None):
        """Створює запит із запобіжниками. Повертає запит або порожній набір.

        Запускати може власник агента або інший агент того ж власника; агент не запускає сам себе.
        Згадка власника відправляється завжди; решта запусків задач — з паузою, лімітом на добу і склеюванням.
        """
        agent = agent.sudo()
        user = self.env.user
        empty = self.browse()
        if agent.agent_user_id == user:
            return empty
        if self.env["td.claude.agent"]._td_owner_of(user) != agent.owner_id:
            return empty
        owner_mention = kind == "mention" and user == agent.owner_id
        if not owner_mention and record is not None and record._name == "project.task":
            if record.td_claude_paused:
                return empty
            if self._td_hops_today(record) >= self._td_max_hops():
                record.sudo().message_post(
                    body=Markup("<p>%s</p>")
                    % _(
                        "Claude: ліміт запусків на задачу за добу (%(n)s) вичерпано, "
                        "запит до «%(agent)s» не надіслано.",
                        n=self._td_max_hops(),
                        agent=agent.name,
                    ),
                    message_type="notification",
                    subtype_xmlid="mail.mt_note",
                )
                return empty
        if kind in ("assign", "stage") and record is not None and self._td_recent_duplicate(agent, record):
            return empty
        return self._td_create(agent, kind, record=record, message=message)

    # ------------------------------------------------------------------
    # Створення і payload
    # ------------------------------------------------------------------
    @api.model
    def _td_create(self, agent, kind, record=None, message=None, schedule=True):
        agent = agent.sudo()
        vals = {"agent_id": agent.id, "kind": kind}
        if record:
            vals.update(res_model=record._name, res_id=record.id, record_name=record.display_name)
        if message:
            vals["message_id"] = message.id
        request = self.sudo().create(vals)
        payload = request._td_build_payload(record, message)
        request.payload = json.dumps(payload, ensure_ascii=False)
        if schedule:
            request._td_schedule_send()
        return request

    def _td_build_payload(self, record, message):
        self.ensure_one()
        env = self.env
        agent = self.agent_id.sudo()
        agent_user = agent.agent_user_id
        icp = env["ir.config_parameter"].sudo()
        base_url = (icp.get_param("web.base.url") or "").rstrip("/")
        model, res_id = self.res_model or None, self.res_id or None
        record_url = None
        if model and res_id:
            path = model if "." in model else f"m-{model}"
            record_url = f"{base_url}/odoo/{path}/{res_id}"
        project = None
        if record and record._name == "project.task" and record.project_id:
            info = record.project_id._td_claude_project_info()
            project = {k: info[k] for k in ("id", "name", "repo", "branch", "claude_url")}
        session = None
        if model and res_id:
            sess = (
                env["td.claude.session"]
                .sudo()
                .search([("agent_id", "=", agent.id), ("res_model", "=", model), ("res_id", "=", res_id)], limit=1)
            )
            if sess:
                session = {"session_id": sess.session_id or None, "session_url": sess.session_url or None}
        msg = None
        if message:
            msg = {
                "id": message.id,
                "text": html2plaintext(message.body or "").strip(),
                "date": fields.Datetime.to_string(message.date) if message.date else None,
            }
        role = agent.role_id
        hops = self._td_hops_today(record) if record else 0
        return {
            "v": 1,
            "kind": self.kind,
            "request_id": self.id,
            "db": env.cr.dbname,
            "base_url": base_url,
            "model": model,
            "res_id": res_id,
            "record_name": self.record_name or None,
            "record_url": record_url,
            "project": project,
            "author": {"user_id": env.user.id, "name": env.user.name},
            "agent": {"user_id": agent_user.id, "login": agent_user.login, "partner_id": agent_user.partner_id.id},
            "role": {"code": role.code, "name": role.name} if role else None,
            "hops_today": hops,
            "message": msg,
            "session": session,
        }

    # ------------------------------------------------------------------
    # Відправка (після COMMIT) і повтор
    # ------------------------------------------------------------------
    def _td_schedule_send(self):
        """Відправка після COMMIT, у новому курсорі: транзакція автора не чекає мережі."""
        dbname = self.env.cr.dbname
        ids = self.ids

        def _send_after_commit():
            try:
                with Registry(dbname).cursor() as cr:
                    env = api.Environment(cr, SUPERUSER_ID, {})
                    env["td.claude.request"].browse(ids).exists()._send_now()
            except Exception:
                _logger.exception("td_claude_agent: відправку запитів %s не виконано", ids)

        self.env.cr.postcommit.add(_send_after_commit)

    def _send_now(self):
        """Синхронно відправляє запити в стані pending/failed і записує результат."""
        for request in self.sudo():
            if request.state == "sent":
                continue
            agent = request.agent_id
            try:
                payload = json.loads(request.payload or "{}")
                status, text = agent._fire(payload)
            except Exception as exc:  # noqa: BLE001 - збій одного запиту не має зупиняти решту
                status, text = 0, type(exc).__name__
            ok = 200 <= status < 300
            session_url = False
            if ok:
                try:
                    data = json.loads(text)
                except ValueError:
                    data = None
                if isinstance(data, dict):
                    session_url = data.get("claude_code_session_url") or data.get("session_url") or False
            request.write(
                {
                    "state": "sent" if ok else "failed",
                    "http_status": status,
                    "response": (text or "")[:RESPONSE_LIMIT],
                    "session_url": session_url,
                }
            )
            agent.write(
                {
                    "last_fire_at": fields.Datetime.now(),
                    "last_fire_status": f"{status} {'OK' if ok else 'ERR'} · {request.kind}",
                }
            )

    def action_retry(self):
        todo = self.filtered(lambda r: r.state != "sent")
        todo.sudo().write({"state": "pending"})
        todo._send_now()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Повторна відправка"),
                "message": _("Опрацьовано запитів: %s", len(todo)),
                "type": "info",
            },
        }
