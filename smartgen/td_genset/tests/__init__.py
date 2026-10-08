# Part of td_genset (ToDo). Власник: W0. Усі файли тестів імпортуються заздалегідь (BUILD_PLAN 1.6):
# потоки наповнюють свої файли, цей __init__ не змінюють.
from . import test_w0_smoke
from . import test_w1_relay_client
from . import test_w1_pull_readings
from . import test_w1_semantics
from . import test_w1_journal_slots
from . import test_w1_link_health
from . import test_w1_events
from . import test_w1_alarms_escalation
from . import test_w1_cleanup
from . import test_w2_commands
from . import test_w2_scheduler
from . import test_w2_timer_test
from . import test_w3_ui_http
from . import test_w3_security
from . import test_w4_fuel
from . import test_w4_maintenance
from . import test_w6_prod_readiness
# Стендові тести W5 (tests/stand/test_w5_stand_*.py, тег td_genset_stand) — підхоплюються автоматично.
from .stand import *  # noqa: F401,F403
