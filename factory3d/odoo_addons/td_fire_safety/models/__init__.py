# Порядок імпорту — SPEC §0.1 (td_fire_norm першим). Розкоментовувати по мірі появи файлів W1…W4.
from . import td_fire_norm
from . import td_fire_panel
from . import td_fire_loop
from . import td_fire_zone
from . import td_fire_device
from . import td_fire_event
from . import td_fire_system
from . import td_fire_smoke_zone  # W3 (device.smoke_zone_id, system.smoke_zone_ids)
from . import td_fire_exit  # W3
from . import td_fire_route  # W3 (td.zone.td_evac_route_id)
from . import td_fire_drill  # W4 (event.drill_id)
from . import td_fire_drill_zone  # M-11g: SQL-представлення над td.fire.drill.person
from . import passage_source
from . import td_zone
from . import maintenance_request
from . import td_source
from . import td_signal
from . import td_command
from . import res_config_settings
from . import push_handler
from . import iot_sim_bridge  # W4 (після td_fire_drill)
