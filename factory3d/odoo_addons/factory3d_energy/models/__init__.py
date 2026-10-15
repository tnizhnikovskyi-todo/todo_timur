# Порядок (SPEC §0). Кожен воркер розкоментовує свої рядки разом із файлом моделі.
from . import f3d_source, f3d_signal, f3d_energy_tariff, f3d_energy_node, f3d_energy_pool, f3d_energy_meter  # noqa: F401
from . import f3d_energy_event, f3d_energy_interval, f3d_energy_balance, f3d_energy_node_live  # noqa: F401  (W2)

# W3: from . import f3d_energy_outage, f3d_energy_alloc
from . import f3d_energy_outage  # noqa: F401  (W4)
# W3: from . import mrp_workorder, mrp_production, mrp_workcenter, maintenance_equipment, maintenance_request
# W5: from . import res_config_settings, viewer_provider
