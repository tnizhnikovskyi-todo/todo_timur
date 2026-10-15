# Порядок імпорту важливий (BUILD_PLAN 1.6, ТР А.11): genset.py оголошує всі поля td.genset,
# inherit-файли потоків (monitoring/scheduler/ui/fuel) імпортуються після нього й перекривають заглушки.
from . import relay_client
from . import genset
from . import genset_monitoring
from . import genset_scheduler
from . import genset_ui
from . import genset_fuel
from . import genset_reading
from . import genset_event
from . import genset_alarm
from . import genset_command
from . import genset_schedule
from . import genset_config
from . import genset_controller_model
from . import maintenance_ext
from . import res_config_settings
from . import ir_websocket
