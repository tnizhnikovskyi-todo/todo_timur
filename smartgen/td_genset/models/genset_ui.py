# Part of td_genset (ToDo). Власник файлу: W3 «UI». Каркас (заглушки): W0.
"""``td.genset`` (inherit): дані для форми і пульта — ТР 2.10, 2.11, А.9; SPEC 9, 10, 11.

``get_pult_state`` у W0 повертає повну структуру А.9 з нейтральними значеннями (пульт неактивний).
``is_tech``/``is_admin`` працюють з W0 (видимість у поданнях). KPI «Аналітики» — заглушка (див. звіт W0:
у BUILD_PLAN власника не названо, розміщено тут поруч з UI-обчисленнями).
"""
from odoo import _, api, fields, models

from .genset import GENSET_STATUS

PULT_BUTTONS = ('auto', 'manual', 'start', 'stop', 'test')
KPI_FIELDS = (
    'kpi_run_hours_7d', 'kpi_run_hours_30d', 'kpi_starts_7d', 'kpi_starts_30d',
    'kpi_energy_kwh_7d', 'kpi_energy_kwh_30d', 'kpi_outages_7d', 'kpi_outages_30d',
    'kpi_covered_pct_7d', 'kpi_covered_pct_30d', 'kpi_avg_load_pct_7d', 'kpi_avg_load_pct_30d',
    'kpi_first_try_pct_7d', 'kpi_first_try_pct_30d', 'kpi_crank_battery_min_7d', 'kpi_crank_battery_min_30d',
)


class TdGensetUi(models.Model):
    _inherit = 'td.genset'

    def get_pult_state(self):
        """Стан пульта для OWL-віджета ``td_genset_pult`` (А.9). Перевіряє ``check_access('read')``.

        Формат: ``{can_control, block_reason, buttons{auto,manual,start,stop,test: {enabled, active}},
        breakers{gen, mains}, gauges{…}, status{code,label,stage,delay}, feed, timer, test, server_now}``.

        TODO: W3 — AC-24, AC-62 (умови активності кнопок — зв'язок, ``remote_lock``, ``commands_allowed``,
        ``is_tech``; таймер/тест). Заглушка W0: структура з нейтральними значеннями, ``can_control = False``.
        """
        self.ensure_one()
        self.check_access('read')
        status_labels = dict(GENSET_STATUS)
        mode = self.controller_mode
        return {
            'can_control': False,
            'block_reason': _('Пульт: у розробці'),
            'buttons': {name: {'enabled': False, 'active': mode == name} for name in PULT_BUTTONS},
            'breakers': {
                'gen': {'closed': bool(self.gen_on_load), 'target_label': _('Розімкнути') if self.gen_on_load
                        else _('Замкнути'), 'enabled': False},
                'mains': {'closed': bool(self.mains_on_load), 'target_label': _('Розімкнути') if self.mains_on_load
                          else _('Замкнути'), 'enabled': False,
                          'available': bool(self.controller_model_id.has_mains_breaker)},
            },
            'gauges': {
                'speed': None, 'active_power': None, 'oil_pressure': None, 'water_temp': None,
                'fuel_liters': None, 'battery_v': None, 'load_pct': None,
            },
            'status': {
                'code': self.genset_status or None,
                'label': status_labels.get(self.genset_status) if self.genset_status else None,
                'stage': self.genset_stage or None,
                'delay': self.genset_status_delay or 0,
            },
            'feed': self.feed_source or 'none',
            'timer': None,
            'test': None,
            'server_now': fields.Datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
        }

    @api.depends('last_reading_id', 'last_values_json', 'last_reading_at', 'fuel_source', 'link_state')
    def _compute_current_data_html(self):
        """HTML вкладки «Поточні дані» з ``last_values_json`` і словника підписів (оми поруч із %/°C/kPa,
        літри з позначкою ``fuel_source``, блок «Ретранслятор»).

        TODO: W3 — AC-05, AC-06, AC-60. Заглушка W0: порожній стан.
        """
        for genset in self:
            if genset.last_reading_id:
                genset.current_data_html = False
            else:
                genset.current_data_html = '<p class="text-muted">%s</p>' % _('Очікуємо перший знімок.')

    @api.depends('timer_end', 'timer_started_at')
    def _compute_timer_progress(self):
        """Прогрес таймера 0–100 від ``timer_started_at`` до ``timer_end``.

        TODO: W3 — AC-31 (показ). Заглушка W0: ``0``.
        """
        for genset in self:
            genset.timer_progress = 0.0

    @api.depends_context('uid')
    def _compute_is_tech(self):
        """Поточний користувач — «Генератори: Тех. адміністратор» (видимість кнопок, AC-24, AC-55)."""
        is_tech = self.env.user.has_group('td_genset.group_tech')
        for genset in self:
            genset.is_tech = is_tech

    @api.depends_context('uid')
    def _compute_is_admin(self):
        """Поточний користувач — «Генератори: Адміністратор» (редагування розкладу, AC-29, AC-56)."""
        is_admin = self.env.user.has_group('td_genset.group_admin')
        for genset in self:
            genset.is_admin = is_admin

    def _compute_kpi(self):
        """KPI вкладки «Аналітика» за 7/30 днів (``_read_group`` по подіях ``run``/``outage`` і знімках, 2.10).

        TODO: W3 (за рішенням архітектора — може перейти до W1/W4). Заглушка W0: нулі.
        """
        for genset in self:
            for name in KPI_FIELDS:
                genset[name] = 0
