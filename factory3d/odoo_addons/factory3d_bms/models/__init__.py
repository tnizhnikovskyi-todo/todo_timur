# Модулі моделей додають W1…W5 (порядок — SPEC §0.1)
from . import f3d_bms_light_norm
from . import f3d_bms_light_panel
from . import f3d_bms_light_group
from . import f3d_bms_light_scene
from . import f3d_bms_hvac_unit, f3d_bms_heat_balance  # noqa: F401
from . import f3d_source, f3d_signal  # noqa: F401
from . import f3d_bms_deviation, f3d_bms_check  # noqa: F401
from . import maintenance_request, maintenance_equipment, f3d_zone  # noqa: F401
from . import res_config_settings  # noqa: F401
