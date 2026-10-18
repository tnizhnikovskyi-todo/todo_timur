# Порядок (SPEC §0). Кожен воркер розкоментовує свої рядки разом із файлом моделі.
from . import td_source, td_signal, td_energy_tariff, td_energy_node, td_energy_pool, td_energy_meter  # noqa: F401
from . import td_energy_day_mixin  # noqa: F401  (Y-2)
from . import td_energy_event, td_energy_interval, td_energy_balance, td_energy_node_live  # noqa: F401  (W2)
from . import td_energy_alloc  # noqa: F401  (W3)
from . import td_energy_outage  # noqa: F401  (W4)
from . import mrp_workorder, mrp_production, mrp_workcenter, maintenance_equipment, maintenance_request  # noqa: F401  (W3)
from . import res_config_settings, viewer_provider  # noqa: F401  (W5)
