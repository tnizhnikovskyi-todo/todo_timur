"""Фіксація версії data-модуля 19.0.1.0.0 → 19.0.2.0.0 (SPEC §5.3 крок 0)."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if version and version.endswith('1.0.0'):
        _logger.info("factory3d_iot_sim: upgrade from data module %s", version)
    cr.execute("SELECT 1 FROM ir_model WHERE model = 'x_f3d_signal'")
    if not cr.fetchone():
        _logger.warning("factory3d_iot_sim: модель x_f3d_signal відсутня (свіжа база без рівня 0)")
