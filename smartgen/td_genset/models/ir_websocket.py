# Part of td_genset (ToDo). Власник файлу: W3 «UI». Каркас (робоча версія): W0.
"""Підписка web-клієнта на канал генератора — ТР 2.11, А.9.

Рядковий канал ``td_genset_<id>`` перетворюється на запис ``td.genset`` (канал ``_bus_send``), якщо
поточний користувач має право читання; інакше канал відкидається (за зразком ``mail`` для
``discuss.channel_<id>``).
"""
import re

from odoo import models

CHANNEL_RE = re.compile(r'^td_genset_(\d+)$')


class IrWebsocket(models.AbstractModel):
    _inherit = 'ir.websocket'

    def _build_bus_channel_list(self, channels):
        channels, gensets = self._td_genset_bus_channels(channels)
        return super()._build_bus_channel_list(channels + list(gensets))

    def _td_genset_bus_channels(self, channels):
        """Відокремити канали ``td_genset_<id>``: повертає ``(інші канали, генератори з правом читання)``."""
        other, genset_ids = [], []
        for channel in channels:
            match = CHANNEL_RE.match(channel) if isinstance(channel, str) else None
            if match:
                genset_ids.append(int(match.group(1)))
            else:
                other.append(channel)
        gensets = self.env['td.genset']
        if genset_ids and self.env.uid and not self.env.user._is_public():
            gensets = gensets.browse(genset_ids).exists()
            gensets = gensets.filtered(lambda genset: genset.has_access('read'))
        return other, gensets
