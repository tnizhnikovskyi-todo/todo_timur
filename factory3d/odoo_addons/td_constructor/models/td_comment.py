from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

COMMENT_TARGET_SELECTION = [
    ('site', "Площадка"),
    ('layer', "Шар"),
    ('slot', "Місце"),
    ('cell', "Комірка"),
    ('placement', "Розміщення"),
    ('item', "Об'єкт будівлі"),
]
DESIGN_XMLIDS = (
    'td_constructor.group_td_constructor_technologist',
    'td_constructor.group_td_constructor_storekeeper',
    'td_constructor.group_td_constructor_engineer',
    'td_constructor.group_td_constructor_manager',
)
TEXT_MAX = 4000


class TdComment(models.Model):
    """Коментар або задача на об'єкті чернетки (F13); об'єкт — за `target_uid`, бо записів Odoo в чернетки немає.

    Зв'язок з Odoo: коментар — документ із обговоренням (`mail.thread`), задача з виконавцем створює завдання
    (`mail.activity`) у виконавця; вирішення закриває завдання. Читають і додають усі з доступом до конструктора;
    вирішує автор або «Проєктування»; чужі видаляє «Проєктування» (F13-04)."""

    _name = 'td.comment'
    _description = "Коментар конструктора"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'site_id, state, id desc'

    site_id = fields.Many2one('td.site', string="Площадка", required=True, ondelete='cascade', index=True)
    target_kind = fields.Selection(COMMENT_TARGET_SELECTION, string="Об'єкт", required=True, default='slot')
    target_uid = fields.Char(
        string="UID об'єкта", size=64, index=True, help="UID шару/місця/розміщення або код комірки"
    )
    target_label = fields.Char(string="Підпис об'єкта")
    kind = fields.Selection(
        [('note', "Коментар"), ('task', "Задача")], string="Вид", required=True, default='note', tracking=True
    )
    state = fields.Selection(
        [('open', "Відкрито"), ('resolved', "Вирішено")],
        string="Стан",
        required=True,
        default='open',
        index=True,
        tracking=True,
    )
    text = fields.Text(string="Текст", required=True)
    author_id = fields.Many2one(
        'res.users', string="Автор", required=True, default=lambda self: self.env.user, ondelete='restrict'
    )
    assignee_id = fields.Many2one('res.users', string="Виконавець", ondelete='set null', tracking=True)
    resolved_by_id = fields.Many2one('res.users', string="Вирішив", readonly=True, copy=False, ondelete='set null')
    resolved_at = fields.Datetime(string="Вирішено", readonly=True, copy=False)
    company_id = fields.Many2one('res.company', related='site_id.company_id', store=True, index=True)
    active = fields.Boolean(default=True)

    @api.depends('kind', 'text', 'target_label')
    def _compute_display_name(self):
        for comment in self:
            head = (comment.text or '').strip().splitlines()[0][:60] if (comment.text or '').strip() else ''
            comment.display_name = "%s: %s" % (comment.target_label or comment.target_uid or '', head)

    # --- права (F13-04) ------------------------------------------------------------------------------------
    @api.model
    def _td_is_designer(self, user=None):
        user = user or self.env.user
        return self.env.su or any(user.has_group(xmlid) for xmlid in DESIGN_XMLIDS)

    def _td_can_resolve(self):
        self.ensure_one()
        return self._td_is_designer() or self.author_id == self.env.user

    def _td_can_delete(self):
        self.ensure_one()
        return self._td_is_designer() or self.author_id == self.env.user

    # --- API-22 -----------------------------------------------------------------------------------------------
    @api.model
    def f3d_add(self, site, vals):
        """Новий коментар/задача від імені користувача (запис від імені сервера: читач без права запису теж додає)."""
        if not (self.env.su or self.env.user.has_group('td_factory3d.group_td_user')):
            raise AccessError("Немає доступу до конструктора.")
        text = (vals.get('text') or '').strip()
        if not text:
            raise UserError("Введіть текст коментаря.")
        if len(text) > TEXT_MAX:
            raise UserError("Текст довший за %d символів." % TEXT_MAX)
        kind = vals.get('kind') or 'note'
        if kind not in ('note', 'task'):
            raise UserError("Вид: коментар або задача.")
        target_kind = vals.get('target_kind') or 'site'
        if target_kind not in dict(COMMENT_TARGET_SELECTION):
            raise UserError("Невідомий вид об'єкта.")
        assignee = self.env['res.users'].browse(int(vals['assignee_id'])).exists() if vals.get('assignee_id') else False
        if assignee and kind != 'task':
            raise UserError("Виконавця можна призначити лише задачі.")
        if assignee and not assignee.has_group('td_factory3d.group_td_user'):
            raise UserError("Виконавець не має доступу до конструктора.")
        comment = (
            self.sudo()
            .with_context(mail_create_nolog=True, mail_create_nosubscribe=True, mail_notrack=True)
            .create(
                {
                    'site_id': site.id,
                    'target_kind': target_kind,
                    'target_uid': (vals.get('target_uid') or '')[:64] or False,
                    'target_label': (vals.get('target_label') or '')[:200] or False,
                    'kind': kind,
                    'text': text,
                    'author_id': self.env.user.id,
                    'assignee_id': assignee.id if assignee else False,
                }
            )
        )
        comment._td_sync_activity()
        return comment

    def _td_sync_activity(self):
        """Задача з виконавцем — завдання `mail.activity`; вирішена або не задача — завдань немає."""
        for comment in self.sudo():
            wanted = comment.kind == 'task' and comment.state == 'open' and comment.assignee_id
            if not wanted:
                comment.activity_ids.unlink()
                continue
            mine = comment.activity_ids.filtered(lambda a, c=comment: a.user_id == c.assignee_id)
            (comment.activity_ids - mine).unlink()
            if not mine:
                comment.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=(comment.text or '')[:100],
                    note=comment.target_label or comment.target_uid or '',
                    user_id=comment.assignee_id.id,
                )

    def f3d_set_text(self, text):
        self.ensure_one()
        if not (self.author_id == self.env.user or self._td_is_designer()):
            raise AccessError("Змінити коментар може автор або «Проєктування».")
        text = (text or '').strip()
        if not text:
            raise UserError("Введіть текст коментаря.")
        self.sudo().write({'text': text[:TEXT_MAX]})
        self._td_sync_activity()

    def f3d_resolve(self, resolved=True):
        """Вирішити (або відкрити знову); завдання виконавця закривається."""
        self.ensure_one()
        if not self._td_can_resolve():
            raise AccessError("Вирішує автор або «Проєктування».")
        record = self.sudo()
        if resolved:
            if record.state == 'resolved':
                return self
            for activity in record.activity_ids:
                activity.action_feedback(feedback="Вирішено в конструкторі")
            record.write(
                {'state': 'resolved', 'resolved_by_id': self.env.user.id, 'resolved_at': fields.Datetime.now()}
            )
        else:
            record.write({'state': 'open', 'resolved_by_id': False, 'resolved_at': False})
            record._td_sync_activity()
        return self

    def f3d_remove(self):
        self.ensure_one()
        if not self._td_can_delete():
            raise AccessError("Видаляє автор або «Проєктування».")
        self.sudo().unlink()

    def f3d_dict(self):
        self.ensure_one()
        return {
            'id': self.id,
            'target_kind': self.target_kind,
            'target_uid': self.target_uid or '',
            'target_label': self.target_label or '',
            'kind': self.kind,
            'state': self.state,
            'text': self.text,
            'author': self.author_id.name or '',
            'author_id': self.author_id.id,
            'mine': self.author_id == self.env.user,
            'assignee': self.assignee_id.name or '',
            'assignee_id': self.assignee_id.id or None,
            'at': fields.Datetime.to_string(self.create_date) if self.create_date else '',
            'resolved_by': self.resolved_by_id.name or '',
            'resolved_at': fields.Datetime.to_string(self.resolved_at) if self.resolved_at else '',
            'can_resolve': self._td_can_resolve(),
            'can_delete': self._td_can_delete(),
        }
