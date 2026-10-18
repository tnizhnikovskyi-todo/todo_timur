import logging

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..tools import params as P
from ..tools.biostar_client import BioStarError, BioStarWriteDisabled

_logger = logging.getLogger(__name__)

SECURITY = 'td_access.group_td_access_security'
ADMIN = 'td_access.group_td_access_admin'
CARD_TYPE_ID = {'csn': 0, 'wiegand': 1, 'secure': 2, 'mobile': 4}
SYNC_STATES = [('local', 'Лише в Odoo'), ('pending', 'Очікує запису'), ('synced', 'Синхронізовано'),
               ('error', 'Помилка')]
OPS = [('issue', 'Видати'), ('block', 'Заблокувати'), ('unblock', 'Розблокувати'), ('return', 'Повернути')]


class F3dAccessCard(models.Model):
    _name = 'td.access.card'
    _description = 'СКУД: картка доступу'
    _inherit = ['mail.thread']
    _order = 'state, number'
    _rec_name = 'number'

    def _default_server_id(self):
        Server = self.env['td.access.server'].sudo()
        return (Server.search([('active', '=', True), ('company_id', '=', self.env.company.id)], limit=1)
                or Server.search([('active', '=', True)], limit=1)).id

    number = fields.Char(string='Номер картки (CSN)', size=32, required=True, index=True, tracking=True)
    card_type = fields.Selection(
        [('csn', 'CSN'), ('wiegand', 'Wiegand'), ('secure', 'Secure Credential'), ('mobile', 'Mobile CSN')],
        required=True, default='csn')
    server_id = fields.Many2one('td.access.server', required=True, ondelete='restrict',
                                default=lambda self: self._default_server_id())
    company_id = fields.Many2one('res.company', related='server_id.company_id', store=True, index=True)
    holder_type = fields.Selection(
        [('employee', 'Працівник'), ('visitor', 'Відвідувач'), ('pool', 'Пул відвідувачів')],
        required=True, default='employee', tracking=True)
    employee_id = fields.Many2one('hr.employee', index=True, ondelete='set null', tracking=True)
    visitor_id = fields.Many2one('td.access.visitor', index=True, ondelete='set null', tracking=True)
    state = fields.Selection(
        [('draft', 'Чернетка'), ('active', 'Видана'), ('blocked', 'Заблокована'), ('returned', 'Повернута'),
         ('lost', 'Втрачена')], required=True, default='draft', tracking=True)
    block_reason = fields.Char(string='Причина блокування', size=128, tracking=True)
    issued_at = fields.Datetime(readonly=True)
    blocked_at = fields.Datetime(readonly=True)
    returned_at = fields.Datetime(readonly=True)
    biostar_card_id = fields.Char(string='ID картки в BioStar', size=64, readonly=True)
    sync_state = fields.Selection(SYNC_STATES, required=True, default='local', tracking=True, readonly=True)
    pending_op = fields.Selection(OPS, readonly=True)
    sync_error = fields.Char(size=255, readonly=True)
    sync_ts = fields.Datetime(readonly=True)
    sync_attempts = fields.Integer(readonly=True, default=0)
    holder_name = fields.Char(compute='_compute_holder_name')
    active = fields.Boolean(default=True)

    _f3d_access_card_uniq = models.Constraint('UNIQUE(server_id, number)', 'Картка з таким номером уже є.')

    @api.depends('holder_type', 'employee_id', 'visitor_id')
    def _compute_holder_name(self):
        for card in self:
            if card.holder_type == 'employee':
                card.holder_name = card.employee_id.sudo().name or False
            elif card.holder_type == 'visitor':
                card.holder_name = card.visitor_id.sudo().name or False
            else:
                card.holder_name = 'Пул'

    @api.constrains('number', 'holder_type', 'employee_id', 'visitor_id', 'state', 'block_reason')
    def _check_card(self):
        for card in self:
            if not P.CARD_RE.match(card.number or ''):
                raise ValidationError("Номер картки: лише цифри, до 32 знаків (CSN з BioStar).")
            holder = card.holder_type
            if holder == 'employee' and (not card.employee_id or card.visitor_id):
                raise ValidationError("Картка працівника: вкажіть працівника.")
            if holder == 'visitor' and not card.visitor_id:
                raise ValidationError("Картка відвідувача: вкажіть відвідувача.")
            # повернута картка відвідувача лишає visitor_id як історію до R-20 крок 5
            if holder == 'pool' and (card.employee_id or card.visitor_id) and card.state != 'returned':
                raise ValidationError("Картка пулу не прив'язується до людини.")
            if card.state == 'blocked' and not card.block_reason:
                raise ValidationError("Вкажіть причину блокування.")
            if card.visitor_id and card.state == 'active' and self.sudo().search_count(
                    [('visitor_id', '=', card.visitor_id.id), ('state', '=', 'active'), ('id', '!=', card.id)]):
                raise ValidationError("У відвідувача вже є видана картка.")

    # ------------------------------------------------------------------ права
    def _check_admin(self):
        if not self.env.su and not self.env.user.has_group(ADMIN):
            raise AccessError("Цю дію з карткою може виконати лише адміністратор СКУД.")

    def _check_security(self):
        if self.env.su or self.env.user.has_group(ADMIN):
            return
        if not self.env.user.has_group(SECURITY):
            raise AccessError("Видавати й повертати картки може лише охорона або адміністратор СКУД.")
        if self.filtered(lambda c: c.holder_type == 'employee'):
            raise AccessError("Картки працівників змінює лише адміністратор СКУД.")

    # ------------------------------------------------------------------ переходи (§10.3)
    def action_issue(self):
        self._check_security()
        for card in self:
            if card.state not in ('draft', 'returned'):
                raise UserError("Видати можна лише чернетку або повернуту картку.")
            if card.holder_type == 'pool':
                raise UserError("Спершу оберіть, кому видається картка.")
        self.write({'state': 'active', 'issued_at': fields.Datetime.now(), 'returned_at': False})
        self._f3d_queue('issue')
        return True

    def action_block(self):
        self._check_admin()
        for card in self:
            if card.state != 'active':
                raise UserError("Заблокувати можна лише видану картку.")
            if not card.block_reason:
                raise UserError("Вкажіть причину блокування.")
        self.write({'state': 'blocked', 'blocked_at': fields.Datetime.now()})
        self._f3d_queue('block')
        return True

    def action_unblock(self):
        self._check_admin()
        for card in self:
            if card.state != 'blocked':
                raise UserError("Розблокувати можна лише заблоковану картку.")
        self.write({'state': 'active', 'block_reason': False})
        self._f3d_queue('unblock')
        return True

    def action_return(self):
        self._check_security()
        for card in self:
            if card.state not in ('active', 'blocked'):
                raise UserError("Повернути можна лише видану або заблоковану картку.")
        for card in self:
            vals = {'state': 'returned', 'returned_at': fields.Datetime.now()}
            if card.holder_type == 'visitor':
                vals['holder_type'] = 'pool'
            card.write(vals)
        self._f3d_queue('return')
        return True

    def action_mark_lost(self):
        self._check_admin()
        for card in self:
            if card.state not in ('active', 'blocked'):
                raise UserError("Втраченою можна позначити лише видану або заблоковану картку.")
        self.write({'state': 'lost', 'block_reason': 'Втрачена'})
        self._f3d_queue('block')
        return True

    # ------------------------------------------------------------------ запис у BioStar (R-13)
    def _f3d_queue(self, op):
        label = dict(OPS)[op]
        write_enabled = P.get_flag(self.env, 'write_enabled')
        for card in self:
            if write_enabled:
                card.write({'pending_op': op, 'sync_state': 'pending', 'sync_attempts': 0, 'sync_error': False})
                card._f3d_push()
            else:
                card.write({'pending_op': op, 'sync_state': 'local'})
                card.message_post(body="Запис у BioStar вимкнено стоп-краном. Виконайте операцію «%s» у BioStar "
                                       "вручну і натисніть «Позначити синхронізованим»." % label)

    def _f3d_owner(self):
        """(user_id BioStar, власник) картки: працівник через зв'язок, відвідувач через своє поле."""
        self.ensure_one()
        if self.employee_id:
            link = self.env['td.access.user.link'].sudo().search(
                [('server_id', '=', self.server_id.id), ('employee_id', '=', self.employee_id.id)], limit=1)
            return link.biostar_user_id or False, ('employee_id', self.employee_id)
        if self.visitor_id:
            return self.visitor_id.biostar_user_id or False, ('visitor_id', self.visitor_id)
        return False, None

    def _f3d_cards_payload(self, op):
        """Повний список карток власника з BioStar-id (API-08); `return` — без цієї картки."""
        self.ensure_one()
        _user, owner = self._f3d_owner()
        cards = self.browse()
        if owner:
            cards = self.sudo().search([
                ('server_id', '=', self.server_id.id), (owner[0], '=', owner[1].id), ('biostar_card_id', '!=', False),
                ('state', 'in', ('active', 'blocked')), ('id', '!=', self.id)])
        if op != 'return':
            cards |= self
        return [{'id': c.biostar_card_id, 'is_blocked': 'false' if c.state == 'active' else 'true'}
                for c in cards.sorted('id') if c.biostar_card_id]

    def _f3d_push(self):
        """R-13 кроки 2–5 (sudo): записати чергову операцію в BioStar."""
        for card in self.sudo().filtered(lambda c: c.sync_state in ('pending', 'error') and c.pending_op):
            card._f3d_push_one()
        return True

    def _f3d_push_one(self):
        self.ensure_one()
        op = self.pending_op
        user_id, _owner = self._f3d_owner()
        if not user_id:
            return self._f3d_fail("У власника картки немає користувача BioStar.")
        server = self.server_id
        client = server._get_client()
        try:
            if op == 'issue' and not self.biostar_card_id:
                # API-07 не ідемпотентний: отриманий id записуємо одразу й більше не перезаписуємо
                self.biostar_card_id = client.create_card(self.number, CARD_TYPE_ID[self.card_type])
            elif op != 'issue' and not self.biostar_card_id:
                return self._f3d_fail("Картку не записано в BioStar: видайте її під стоп-краном або позначте "
                                      "синхронізованою вручну.")
            client.update_user_cards(user_id, self._f3d_cards_payload(op))
        except BioStarWriteDisabled:
            self.write({'sync_state': 'local'})
            return False
        except BioStarError as exc:
            return self._f3d_fail(str(exc))
        finally:
            server._save_session(client)
        label = dict(OPS)[op]
        self.write({'sync_state': 'synced', 'sync_ts': fields.Datetime.now(), 'pending_op': False,
                    'sync_error': False})
        self.message_post(body="Записано в BioStar: %s" % label)
        return True

    def _f3d_fail(self, text):
        self.ensure_one()
        self.write({'sync_state': 'error', 'sync_error': text[:255], 'sync_attempts': self.sync_attempts + 1})
        self.message_post(body="Помилка запису в BioStar: %s" % text)
        return False

    def action_retry_sync(self):
        self._check_admin()
        if not P.get_flag(self.env, 'write_enabled'):
            raise UserError("Запис у BioStar вимкнено стоп-краном td.access.write_enabled.")
        todo = self.filtered(lambda c: c.sync_state in ('error', 'local'))
        todo.write({'sync_state': 'pending'})
        todo._f3d_push()
        return True

    def action_mark_synced(self):
        self._check_admin()
        todo = self.filtered(lambda c: c.sync_state in ('local', 'error'))
        todo.write({'sync_state': 'synced', 'sync_ts': fields.Datetime.now(), 'pending_op': False,
                    'sync_error': False})
        for card in todo:
            card.message_post(body="Позначено синхронізованим вручну")
        return True

    @api.model
    def _cron_card_sync(self):
        if not P.get_flag(self.env, 'write_enabled'):
            return
        attempts = P.get_int(self.env, 'card_sync_max_attempts', 10, 1, 1000)
        self.sudo().search([('sync_state', 'in', ('pending', 'error')), ('sync_attempts', '<', attempts)],
                           limit=100)._f3d_push()


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    td_access_card_ids = fields.One2many('td.access.card', 'employee_id', string='Картки доступу',
                                          groups=SECURITY)
