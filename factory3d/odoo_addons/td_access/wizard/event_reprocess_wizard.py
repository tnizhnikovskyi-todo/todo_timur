from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


class F3dAccessEventReprocessWizard(models.TransientModel):
    _name = 'td.access.event.reprocess.wizard'
    _description = 'СКУД: повторна обробка подій'

    mode = fields.Selection(
        [('reprocess', 'Обробити події повторно'), ('repoll', 'Опитати BioStar за період')],
        required=True, default='reprocess')
    server_id = fields.Many2one(
        'td.access.server', required=True,
        default=lambda self: self.env['td.access.server'].search([('active', '=', True)], limit=1))
    date_from = fields.Datetime(required=True, default=lambda self: fields.Datetime.now() - timedelta(hours=24))
    date_to = fields.Datetime(required=True, default=fields.Datetime.now)
    only_errors = fields.Boolean(string='Лише нові й з помилками', default=True)
    result = fields.Text(readonly=True)

    @api.constrains('date_from', 'date_to')
    def _check_period(self):
        for wiz in self:
            if wiz.date_to <= wiz.date_from:
                raise ValidationError("Кінець періоду має бути пізніше за початок.")
            if wiz.date_to - wiz.date_from > timedelta(days=7):
                raise ValidationError("Період — не довше 7 діб.")

    def action_run(self):
        self.ensure_one()
        if not self.env.su and not self.env.user.has_group('td_access.group_td_access_admin'):
            raise AccessError("Виконувати повторну обробку може лише адміністратор СКУД.")
        server = self.server_id.sudo()
        if self.mode == 'reprocess':
            domain = [('server_id', '=', server.id), ('ts', '>=', self.date_from), ('ts', '<=', self.date_to)]
            if self.only_errors:
                domain.append(('process_state', 'in', ('new', 'error')))
            events = self.env['td.access.event'].sudo().search(domain)
            events.action_reprocess()
            after = events.exists()
            self.result = "Оброблено подій: %d; з помилками: %d" % (
                len(after), len(after.filtered(lambda e: e.process_state == 'error')))
        else:
            server._check_read_enabled()
            res = server._poll_window(self.date_from, self.date_to, max_pages=100)
            self.result = "Рядків: %(rows)d; нових: %(new)d; дублікатів: %(duplicates)d; " \
                          "невалідних: %(invalid)d; оброблено: %(processed)d" % res
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                'view_mode': 'form', 'target': 'new'}
