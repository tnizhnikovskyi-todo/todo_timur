import json
import logging
from datetime import timedelta

from odoo import api, fields, models

from ..tools.states import parse_ts

_logger = logging.getLogger(__name__)

BACKLOG_TTL = timedelta(hours=1)  # відкладені показання старші за це відкидаємо: стан верстата вже не залежить від них


class F3dMachineBacklog(models.Model):
    """Показання верстата, які push не зміг застосувати (рядок верстата зайнятий або змінений паралельною транзакцією).

    `td.signal` показання вже прийняв і колектор їх підтвердив (`rejected` колектор лише логує й відкидає), тож без
    черги зміна стану, імпульс тривоги чи мікрозупинка зникли б. Чергу застосовує наступний push цього верстата або такт
    (`td.machine._td_drain`), у порядку часу, під блокуванням рядка верстата. Лише службове читання/запис (sudo).
    """

    _name = "td.machine.backlog"
    _description = "Верстати: відкладені показання"
    _order = "id"

    # Ціле, а не Many2one: зовнішній ключ у INSERT чекав би блокування рядка верстата — а ми саме його й не дочекались
    machine_id = fields.Integer(string="Верстат (id)", required=True, index=True)
    items = fields.Text(string="Показання (JSON)", required=True)
    queued_at = fields.Datetime(string="Відкладено", required=True, default=fields.Datetime.now, index=True)

    @api.model
    def _td_put(self, machine_id, items):
        """Поставити в чергу показання верстата (`role`, `ts` naive UTC, `text`, `value`, `q`)."""
        data = [dict(it, ts=it["ts"].isoformat()) for it in items]
        return self.sudo().create({"machine_id": machine_id, "items": json.dumps(data)})

    def _td_items(self):
        """Показання черги в порядку постановки; `ts` — знову `datetime`."""
        res = []
        for rec in self:
            res.extend(dict(it, ts=parse_ts(it["ts"])) for it in json.loads(rec.items))
        return res

    @api.model
    def _td_purge(self, now):
        old = self.sudo().search([("queued_at", "<", now - BACKLOG_TTL)])
        if old:
            _logger.warning("td.machine.backlog: відкинуто %s застарілих пачок показань", len(old))
            old.unlink()
        return len(old)
