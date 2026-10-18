# W1: f3d_access_server, f3d_access_device, f3d_access_door, f3d_access_user_link
from . import f3d_access_server, f3d_access_device, f3d_access_door, f3d_access_user_link
# W2 (hr_employee — до f3d_access_presence; presence після visitor, якщо W3 переставить імпорт)
from . import f3d_access_event, hr_employee, hr_attendance, f3d_zone, fire_passage_source
from . import f3d_access_presence
# W3: visitor розширює presence, тому імпортується після нього; visitor.init() перебудовує SQL-представлення presence
from . import f3d_access_card, f3d_access_visitor
# W4: res_config_settings, viewer_data (агрегати sudo), viewer_provider, telemetry_bridge
from . import res_config_settings, viewer_data, viewer_provider, telemetry_bridge
