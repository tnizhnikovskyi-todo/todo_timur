# W1: td_access_server, td_access_device, td_access_door, td_access_user_link
from . import td_access_server, td_access_device, td_access_door, td_access_user_link

# W2 (hr_employee — до td_access_presence; presence після visitor, якщо W3 переставить імпорт)
from . import td_access_event, hr_employee, hr_attendance, td_zone, fire_passage_source
from . import td_access_presence

# W3: visitor розширює presence, тому імпортується після нього; visitor.init() перебудовує SQL-представлення presence
from . import td_access_card, td_access_visitor

# W4: res_config_settings, viewer_data (агрегати sudo), viewer_provider, telemetry_bridge
from . import res_config_settings, viewer_data, viewer_provider, telemetry_bridge
