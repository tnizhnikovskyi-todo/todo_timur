# Порядок імпорту — SPEC §0.1 (f3d_fire_norm першим). Розкоментовувати по мірі появи файлів W1…W4.
from . import f3d_fire_norm
from . import f3d_fire_panel
from . import f3d_fire_loop
from . import f3d_fire_zone
from . import f3d_fire_device
from . import f3d_fire_event
from . import f3d_fire_system
from . import f3d_fire_smoke_zone  # W3 (device.smoke_zone_id, system.smoke_zone_ids)
from . import f3d_fire_exit  # W3
from . import f3d_fire_route  # W3 (f3d.zone.f3d_evac_route_id)
from . import f3d_fire_drill  # W4 (event.drill_id)
# from . import passage_source
from . import f3d_zone
from . import maintenance_request
from . import f3d_source
from . import f3d_signal
from . import f3d_command
from . import res_config_settings
from . import push_handler
# from . import iot_sim_bridge
